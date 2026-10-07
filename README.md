# Research Agent

Fai una domanda: l'agente cerca sul web, legge i risultati e risponde citando le fonti. Usa solo servizi gratuiti.

## Architettura

```text
Browser (public/index.html)
  |  POST /api/ask
  v
FastAPI (api/index.py)
  |--> Ricerca web: Tavily (se c'è la chiave) oppure DuckDuckGo
  |--> LLM gratuito su OpenRouter
  v
Risposta + fonti
```

## Servizi gratuiti

- **LLM**: [OpenRouter](https://openrouter.ai/keys), modelli `:free` (circa 50 richieste al giorno senza credito).
- **Ricerca web**: [Tavily](https://app.tavily.com) (1000 ricerche al mese, opzionale). Senza chiave si usa DuckDuckGo.

## Deploy su Vercel

In **Settings → Environment Variables** aggiungi:

| Variabile | Obbligatoria | Note |
|---|---|---|
| `OPENROUTER_API_KEY` | sì | chiave OpenRouter |
| `OPENROUTER_MODELS` | no | modelli separati da virgola, provati in ordine (default `openrouter/free`) |
| `TAVILY_API_KEY` | no | ricerca più affidabile di DuckDuckGo |

Poi rifai il deploy.

## Sviluppo locale

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt uvicorn

cp .env.example .env   # inserisci le chiavi
export $(grep -v '^#' .env | xargs)
uvicorn api.index:app --reload
```

Apri http://localhost:8000/api/health per verificare. Per l'interfaccia completa usa `vercel dev`.
