# Research Agent

Assistente personale per il lavoro: cerca sul web, ricorda quello che gli insegni e risponde unendo memoria e ricerca, citando le fonti. Solo servizi gratuiti.

## Come funziona

```text
Browser (public/index.html, protetto da password)
  |  /api/chat, /api/memories/*
  v
FastAPI (api/index.py)
  |--> Memoria: Supabase (Postgres, ricerca full-text in italiano)
  |--> Web: Tavily (se c'è la chiave) oppure DuckDuckGo
  |--> LLM gratuito: OpenRouter
```

Come gli dai informazioni:

- **In chat**: scrivi `ricorda: il cliente Rossi paga a 60 giorni` (salva una nota senza usare richieste al modello).
- **Documenti**: dal pannello Memoria carichi PDF, TXT, MD, CSV (il testo è estratto nel tuo browser).
- **Google**: incolli il link di un Docs/Sheets/Slides condiviso con «Chiunque abbia il link».

Il pulsante 🌐 Web attiva o disattiva la ricerca web per le domande.

## Setup

1. **Supabase** (gratis): crea un progetto su supabase.com, apri *SQL Editor*, incolla ed esegui `supabase/schema.sql`.
2. **OpenRouter** (gratis): chiave su openrouter.ai/keys.
3. **Vercel** → Settings → Environment Variables:

| Variabile | Obbligatoria | Note |
|---|---|---|
| `APP_PASSWORD` | sì | password per entrare nell'app |
| `OPENROUTER_API_KEY` | sì | chiave OpenRouter |
| `SUPABASE_URL` | sì | Supabase → Project Settings → API → Project URL |
| `SUPABASE_SERVICE_KEY` | sì | Supabase → API → chiave `service_role` / secret (solo sul server, mai nel browser) |
| `OPENROUTER_MODELS` | no | modelli separati da virgola (default `openrouter/free`) |
| `TAVILY_API_KEY` | no | ricerca web più affidabile (1000/mese gratis) |

4. Redeploy.

## Limiti

- I modelli free di OpenRouter hanno un tetto giornaliero di richieste.
- La ricerca nella memoria è per parole chiave (non semantica): funziona bene se nelle note usi le stesse parole che userai nelle domande.
- Google: solo file condivisi via link; l'accesso diretto al tuo Drive richiederebbe OAuth.

## Sviluppo locale

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt uvicorn
cp .env.example .env   # compila i valori
export $(grep -v '^#' .env | xargs)
uvicorn api.index:app --reload
```
