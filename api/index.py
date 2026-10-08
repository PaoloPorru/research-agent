import hmac
import os
import re
from datetime import date
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from openai import OpenAI
from pydantic import BaseModel

app = FastAPI(title="Research Agent")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MAX_WEB = 5
MAX_MEM = 6
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150
MAX_DOC_CHARS = 2_000_000

SYSTEM_PROMPT = """Sei l'assistente personale di lavoro dell'utente. Lo aiuti a
ricercare, ragionare, scrivere e organizzare, usando due fonti di contesto:

- MEMORIA [M1], [M2]...: appunti e documenti dell'utente. Sono la fonte più
  affidabile per fatti su di lui, i suoi clienti, progetti e materiali.
- WEB [W1], [W2]...: risultati di ricerca aggiornati, per fatti esterni e recenti.

Regole:
- Cita le fonti usate con il loro codice, es. [M2] o [W1].
- Se memoria e web si contraddicono, segnalalo.
- Se l'informazione non è nel contesto, dillo chiaramente: non inventare fatti,
  fonti o URL. Puoi comunque usare le tue conoscenze generali, distinguendole.
- Per scrivere, riassumere o rivedere testi, lavora direttamente senza chiedere
  conferme inutili.
- Rispondi in italiano, in modo chiaro e conciso, senza tabelle."""


# ---------------------------------------------------------------- auth

def require_auth(x_app_password: Optional[str] = Header(None)):
    expected = os.getenv("APP_PASSWORD")
    if not expected:
        raise HTTPException(500, "APP_PASSWORD non configurata su Vercel.")
    if not x_app_password or not hmac.compare_digest(
        x_app_password.encode(), expected.encode()
    ):
        raise HTTPException(401, "Password errata.")


# ---------------------------------------------------------------- database

def memory_configured() -> bool:
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_KEY"))


def sb(method: str, path: str, **kwargs) -> httpx.Response:
    if not memory_configured():
        raise HTTPException(
            500, "Memoria non configurata: mancano SUPABASE_URL / SUPABASE_SERVICE_KEY."
        )
    key = os.environ["SUPABASE_SERVICE_KEY"]
    headers = {"apikey": key, "Content-Type": "application/json"}
    if key.startswith("eyJ"):  # chiave legacy JWT
        headers["Authorization"] = f"Bearer {key}"
    headers.update(kwargs.pop("headers", {}))
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/" + path
    try:
        r = httpx.request(method, url, headers=headers, timeout=25, **kwargs)
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Supabase non raggiungibile: {exc}")
    if r.status_code >= 400:
        raise HTTPException(502, f"Errore Supabase ({r.status_code}): {r.text[:300]}")
    return r


def db_insert(rows: list[dict]) -> None:
    for i in range(0, len(rows), 100):
        sb("POST", "memories", json=rows[i : i + 100], headers={"Prefer": "return=minimal"})


def db_search(tsquery: str) -> list[dict]:
    return sb("POST", "rpc/search_memories", json={"q": tsquery, "n": MAX_MEM}).json()


def db_list_notes() -> list[dict]:
    return sb(
        "GET",
        "memories",
        params={
            "kind": "eq.nota",
            "select": "id,content,created_at",
            "order": "created_at.desc",
            "limit": "200",
        },
    ).json()


def db_list_sources() -> list[dict]:
    return sb("POST", "rpc/list_sources", json={}).json()


def db_delete(id: Optional[int] = None, source: Optional[str] = None) -> None:
    if id is not None:
        params = {"id": f"eq.{id}"}
    elif source:
        params = {"source": f"eq.{source}", "kind": "neq.nota"}
    else:
        raise HTTPException(400, "Specifica id o source.")
    sb("DELETE", "memories", params=params, headers={"Prefer": "return=minimal"})


# ---------------------------------------------------------------- testo

def to_tsquery(text: str) -> str:
    """Parole chiave in OR, sicure per to_tsquery."""
    words: list[str] = []
    for w in re.findall(r"[^\W_]{3,}", text.lower()):
        if w not in words:
            words.append(w)
    return " | ".join(words[:14])


def chunk_text(text: str) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    chunks: list[str] = []
    i, n = 0, len(text)
    while i < n:
        end = min(i + CHUNK_SIZE, n)
        if end < n:
            cut = max(text.rfind("\n", i, end), text.rfind(". ", i, end))
            if cut > i + CHUNK_SIZE // 2:
                end = cut + 1
        piece = text[i:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        i = max(end - CHUNK_OVERLAP, i + 1)
    return chunks


# ---------------------------------------------------------------- ricerca web

def search_tavily(query: str, api_key: str) -> list[dict]:
    r = httpx.post(
        "https://api.tavily.com/search",
        json={"api_key": api_key, "query": query, "max_results": MAX_WEB},
        timeout=20,
    )
    r.raise_for_status()
    return [
        {"title": x.get("title") or x["url"], "url": x["url"], "snippet": x.get("content", "")}
        for x in r.json().get("results", [])
    ]


def search_duckduckgo(query: str) -> list[dict]:
    from ddgs import DDGS

    return [
        {"title": x.get("title") or x["href"], "url": x["href"], "snippet": x.get("body", "")}
        for x in DDGS().text(query, max_results=MAX_WEB)
    ]


def web_search(query: str) -> list[dict]:
    key = os.getenv("TAVILY_API_KEY")
    if key:
        try:
            results = search_tavily(query, key)
            if results:
                return results
        except Exception:
            pass
    try:
        return search_duckduckgo(query)
    except Exception:
        return []


# ---------------------------------------------------------------- Google Docs

GOOGLE_RE = re.compile(
    r"^https://(?:docs|drive)\.google\.com/(document|spreadsheets|presentation|file)/d/([\w-]+)"
)


def google_export_url(url: str) -> tuple[str, str]:
    m = GOOGLE_RE.match(url.strip())
    if not m:
        raise HTTPException(
            400, "Link non valido: incolla un link di Google Docs, Sheets, Slides o Drive."
        )
    kind, file_id = m.groups()
    if kind == "document":
        return f"https://docs.google.com/document/d/{file_id}/export?format=txt", file_id
    if kind == "spreadsheets":
        return f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv", file_id
    if kind == "presentation":
        return f"https://docs.google.com/presentation/d/{file_id}/export?format=txt", file_id
    return f"https://drive.google.com/uc?export=download&id={file_id}", file_id


def fetch_google_text(url: str) -> tuple[str, str]:
    export_url, file_id = google_export_url(url)
    try:
        r = httpx.get(export_url, follow_redirects=True, timeout=30)
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Download da Google non riuscito: {exc}")
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or "text/html" in ctype:
        raise HTTPException(
            400,
            "Impossibile leggere il file: condividilo con 'Chiunque abbia il link' "
            "(Visualizzatore) e riprova.",
        )
    if not (ctype.startswith("text/") or "csv" in ctype):
        raise HTTPException(
            400, "Tipo di file non supportato dal link: scaricalo e caricalo come file."
        )
    return r.text, file_id


# ---------------------------------------------------------------- modelli

class Turn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[Turn] = []
    web: bool = True


class NoteRequest(BaseModel):
    text: str


class DocumentRequest(BaseModel):
    name: str
    text: str
    replace: bool = True


class UrlRequest(BaseModel):
    url: str
    name: Optional[str] = None


REMEMBER_RE = re.compile(r"^\s*/?ricorda(?:ti)?\s*[:\-]?\s+(.+)$", re.I | re.S)


def models_to_try() -> list[str]:
    raw = os.getenv("OPENROUTER_MODELS") or os.getenv("OPENROUTER_MODEL") or "openrouter/free"
    return [m.strip() for m in raw.split(",") if m.strip()]


def save_note(text: str) -> None:
    text = text.strip()
    if not text:
        raise HTTPException(400, "La nota è vuota.")
    if len(text) > 8000:
        raise HTTPException(400, "Nota troppo lunga (max 8000 caratteri): caricala come documento.")
    db_insert([{"source": "nota", "kind": "nota", "content": text}])


# ---------------------------------------------------------------- endpoint

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/me", dependencies=[Depends(require_auth)])
def me():
    return {"ok": True, "memory": memory_configured()}


@app.get("/api/memories", dependencies=[Depends(require_auth)])
def list_memories():
    notes = [
        {"type": "nota", "id": n["id"], "label": n["content"][:200], "created_at": n["created_at"]}
        for n in db_list_notes()
    ]
    docs = [
        {
            "type": "documento",
            "source": d["source"],
            "label": d["source"],
            "chunks": d["chunks"],
            "created_at": d["created_at"],
        }
        for d in db_list_sources()
    ]
    return {"notes": notes, "documents": docs}


@app.post("/api/memories/note", dependencies=[Depends(require_auth)])
def add_note(req: NoteRequest):
    save_note(req.text)
    return {"ok": True}


@app.post("/api/memories/document", dependencies=[Depends(require_auth)])
def add_document(req: DocumentRequest):
    name = req.name.strip()[:120]
    if not name:
        raise HTTPException(400, "Nome documento mancante.")
    if len(req.text) > MAX_DOC_CHARS:
        raise HTTPException(400, "Parte di documento troppo grande.")
    chunks = chunk_text(req.text)
    if not chunks:
        raise HTTPException(400, "Nessun testo estratto (PDF scansionato o file vuoto?).")
    if req.replace:
        db_delete(source=name)
    db_insert([{"source": name, "kind": "documento", "content": c} for c in chunks])
    return {"name": name, "chunks": len(chunks)}


@app.post("/api/memories/url", dependencies=[Depends(require_auth)])
def add_from_url(req: UrlRequest):
    text, file_id = fetch_google_text(req.url)
    name = (req.name or f"Google {file_id[:10]}").strip()[:120]
    chunks = chunk_text(text)
    if not chunks:
        raise HTTPException(400, "Il documento è vuoto.")
    db_delete(source=name)
    db_insert([{"source": name, "kind": "documento", "content": c} for c in chunks])
    return {"name": name, "chunks": len(chunks)}


@app.delete("/api/memories", dependencies=[Depends(require_auth)])
def delete_memory(id: Optional[int] = Query(None), source: Optional[str] = Query(None)):
    db_delete(id=id, source=source)
    return {"ok": True}


@app.post("/api/chat", dependencies=[Depends(require_auth)])
def chat(req: ChatRequest):
    message = req.message.strip()
    if not message:
        raise HTTPException(400, "Il messaggio è vuoto.")
    if len(message) > 6000:
        raise HTTPException(400, "Messaggio troppo lungo (max 6000 caratteri).")

    # "ricorda: ..." salva una nota senza consumare una richiesta al modello
    m = REMEMBER_RE.match(message)
    if m:
        note = re.sub(r"^che\s+", "", m.group(1).strip(), flags=re.I)
        save_note(note)
        return {"answer": "Memorizzato ✅", "memory": [], "web": [], "warnings": [], "saved": True}

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(500, "OPENROUTER_API_KEY non configurata.")

    history = [
        {"role": t.role, "content": t.content[:4000]}
        for t in req.history[-10:]
        if t.role in {"user", "assistant"}
    ]
    prev_user = next((t["content"] for t in reversed(history) if t["role"] == "user"), "")

    warnings: list[str] = []
    memory: list[dict] = []
    tsq = to_tsquery(f"{message} {prev_user}")
    if tsq and memory_configured():
        try:
            memory = db_search(tsq)
        except HTTPException as exc:
            warnings.append(f"Memoria non consultata: {exc.detail}")
    elif not memory_configured():
        warnings.append("Memoria non configurata: rispondo senza.")

    web: list[dict] = []
    if req.web:
        web = web_search(message)
        if not web:
            warnings.append("Ricerca web non disponibile in questo momento.")

    parts = [f"Data di oggi: {date.today().isoformat()}"]
    if memory:
        parts.append(
            "MEMORIA:\n"
            + "\n\n".join(f"[M{i}] ({x['source']})\n{x['content']}" for i, x in enumerate(memory, 1))
        )
    else:
        parts.append("MEMORIA: (nessun elemento pertinente)")
    if req.web:
        parts.append(
            "WEB:\n"
            + (
                "\n\n".join(
                    f"[W{i}] {x['title']}\nURL: {x['url']}\n{x['snippet']}"
                    for i, x in enumerate(web, 1)
                )
                if web
                else "(nessun risultato)"
            )
        )
    system = SYSTEM_PROMPT + "\n\n" + "\n\n".join(parts)

    client = OpenAI(
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
        timeout=45,
        max_retries=0,
        default_headers={"X-Title": "Research Agent"},
    )
    messages = [{"role": "system", "content": system}, *history, {"role": "user", "content": message}]

    last_error = "nessun modello disponibile"
    for model in models_to_try():
        try:
            completion = client.chat.completions.create(model=model, messages=messages)
            text = (completion.choices[0].message.content or "").strip()
            if not text:
                last_error = f"{model}: risposta vuota"
                continue
            return {
                "answer": text,
                "memory": [{"ref": f"M{i}", "source": x["source"]} for i, x in enumerate(memory, 1)],
                "web": [
                    {"ref": f"W{i}", "title": x["title"], "url": x["url"]}
                    for i, x in enumerate(web, 1)
                ],
                "warnings": warnings,
            }
        except Exception as exc:
            last_error = f"{model}: {exc}"

    raise HTTPException(
        502, f"Il modello non ha risposto (limite giornaliero dei modelli free?). {last_error}"
    )
