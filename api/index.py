import os
from datetime import date

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel


app = FastAPI(title="Research Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MAX_RESULTS = 6

SYSTEM_PROMPT = """Sei un research agent. Rispondi alla domanda dell'utente
basandoti sui risultati di ricerca web forniti nel messaggio.

Regole:
- Usa solo le informazioni presenti nei risultati; se non bastano, dillo chiaramente.
- Non inventare fatti, fonti o URL.
- Distingui fatti verificati, interpretazioni e incertezze.
- Se le fonti si contraddicono, segnalalo.
- Cita le fonti con il loro numero tra parentesi quadre, es. [1].
- Rispondi in italiano, in modo chiaro e strutturato, senza usare tabelle."""


class AskRequest(BaseModel):
    question: str


def search_tavily(query: str, api_key: str) -> list[dict]:
    r = httpx.post(
        "https://api.tavily.com/search",
        json={"api_key": api_key, "query": query, "max_results": MAX_RESULTS},
        timeout=20,
    )
    r.raise_for_status()
    return [
        {"title": x.get("title") or x["url"], "url": x["url"], "snippet": x.get("content", "")}
        for x in r.json().get("results", [])
    ]


def search_duckduckgo(query: str) -> list[dict]:
    from ddgs import DDGS

    results = DDGS().text(query, max_results=MAX_RESULTS)
    return [
        {"title": x.get("title") or x["href"], "url": x["href"], "snippet": x.get("body", "")}
        for x in results
    ]


def web_search(query: str) -> list[dict]:
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        try:
            results = search_tavily(query, tavily_key)
            if results:
                return results
        except Exception:
            pass  # ripiego su DuckDuckGo
    try:
        return search_duckduckgo(query)
    except Exception:
        return []


def models_to_try() -> list[str]:
    raw = os.getenv("OPENROUTER_MODELS") or os.getenv("OPENROUTER_MODEL") or "openrouter/free"
    return [m.strip() for m in raw.split(",") if m.strip()]


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/ask")
def ask(request: AskRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="La domanda non può essere vuota.")
    if len(question) > 2000:
        raise HTTPException(status_code=400, detail="La domanda è troppo lunga (max 2000 caratteri).")

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY non configurata.")

    sources = web_search(question)

    if sources:
        context = "\n\n".join(
            f"[{i}] {s['title']}\nURL: {s['url']}\n{s['snippet']}"
            for i, s in enumerate(sources, 1)
        )
    else:
        context = "(Nessun risultato di ricerca disponibile: dichiaralo e rispondi con cautela.)"

    user_message = (
        f"Data di oggi: {date.today().isoformat()}\n\n"
        f"Risultati di ricerca:\n{context}\n\n"
        f"Domanda: {question}"
    )

    client = OpenAI(
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
        timeout=45,
        max_retries=0,
        default_headers={"X-Title": "Research Agent"},
    )

    last_error = "nessun modello disponibile"
    for model in models_to_try():
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
            )
            text = (completion.choices[0].message.content or "").strip()
            if not text:
                last_error = f"{model}: risposta vuota"
                continue

            if sources:
                text += "\n\nFonti:\n" + "\n".join(
                    f"[{i}] {s['title']} - {s['url']}" for i, s in enumerate(sources, 1)
                )
            return {"answer": text}
        except Exception as exc:
            last_error = f"{model}: {exc}"

    raise HTTPException(
        status_code=502,
        detail=f"Il modello non ha risposto (limite giornaliero dei modelli free?). {last_error}",
    )
