# Research Agent

Primo AI Agent personale: fai una domanda e l'agente può utilizzare la ricerca web per trovare informazioni aggiornate, analizzarle e restituire una risposta con le fonti.

## Architettura

```text
Utente
  |
  v
Streamlit UI
  |
  v
Research Agent
  |
  +--> LLM
  |
  +--> Web Search
  |
  v
Risposta + fonti
```

## Requisiti

- macOS
- Python 3.11+
- una API key OpenAI con credito disponibile

## Installazione

Apri Terminale nella cartella del progetto:

```bash
cd research-agent

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

Crea il file `.env`:

```bash
cp .env.example .env
```

Aprilo:

```bash
nano .env
```

Inserisci la tua API key:

```text
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-6-luna
```

Salva con:

- CTRL+O
- INVIO
- CTRL+X

## Avvio

```bash
source .venv/bin/activate
streamlit run app.py
```

Si aprirà l'interfaccia web di Streamlit.

Se non si apre automaticamente, vai su:

http://localhost:8501

## Esempi di domande

```text
Qual è l'ultima versione di Shopify CLI e quali sono le novità principali?
```

```text
Quali sono le principali novità dell'AI uscite questa settimana?
```

```text
Confronta Shopify Functions e Salesforce Commerce Cloud OCAPI.
Usa principalmente documentazione ufficiale.
```

```text
Qual è la situazione attuale dei tassi BCE?
```

## Cosa imparare nella V1

Il progetto volutamente non usa ancora LangChain, CrewAI o altri framework.

Il flusso fondamentale è:

1. input utente
2. modello
3. tool web search
4. analisi
5. risposta
6. fonti

Una volta capito questo, possiamo aggiungere:

- memoria
- ricerca multi-step
- ranking delle fonti
- RAG con documenti personali
- tool custom
- database
- agenti specializzati
- API backend
- autenticazione
- deployment

## Costi

La Web Search API è fatturata separatamente oltre ai token del modello. Controlla i prezzi aggiornati prima di usare il progetto intensivamente.
