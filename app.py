import os
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

st.set_page_config(
    page_title="Research Agent",
    page_icon="🔎",
    layout="centered",
)

SYSTEM_PROMPT = """
Sei Research Agent, un assistente AI di ricerca sul web.

Obiettivo:
- Rispondere alle domande dell'utente usando informazioni aggiornate.
- Usa la ricerca web quando la domanda può dipendere da informazioni attuali,
  quando l'utente chiede esplicitamente di cercare/verificare, oppure quando
  non sei sufficientemente sicuro della risposta.
- Dai priorità a fonti primarie e autorevoli: documentazione ufficiale,
  siti istituzionali, paper, comunicati ufficiali e fonti giornalistiche
  affidabili quando pertinenti.
- Confronta le fonti quando l'informazione è controversa o importante.
- Non inventare fatti, fonti o URL.
- Distingui chiaramente fatti verificati da interpretazioni.
- Rispondi in italiano salvo diversa richiesta.
- Sii conciso ma sufficientemente dettagliato.
- Cita le fonti utilizzate nella risposta quando sono disponibili.
"""

def extract_citations(response: Any) -> list[dict[str, str]]:
    """Estrae URL citati dalla struttura della Responses API in modo robusto."""
    found = []
    seen = set()

    def walk(obj):
        if obj is None:
            return

        if hasattr(obj, "model_dump"):
            try:
                obj = obj.model_dump()
            except Exception:
                pass

        if isinstance(obj, dict):
            annotation_type = obj.get("type", "")
            if annotation_type in {"url_citation", "url_citation_param"}:
                url = obj.get("url")
                title = obj.get("title") or url
                if url and url not in seen:
                    seen.add(url)
                    found.append({"title": title, "url": url})

            for value in obj.values():
                walk(value)

        elif isinstance(obj, (list, tuple)):
            for value in obj:
                walk(value)

    walk(response)
    return found


def ask_agent(question: str):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY non configurata. Copia .env.example in .env "
            "e inserisci la tua API key."
        )

    model = os.getenv("OPENAI_MODEL", "gpt-6-luna")
    client = OpenAI(api_key=api_key)

    response = client.responses.create(
        model=model,
        instructions=SYSTEM_PROMPT,
        tools=[
            {
                "type": "web_search",
                "search_context_size": "medium",
            }
        ],
        input=question,
        include=["web_search_call.action.sources"],
    )

    return response.output_text, extract_citations(response)


st.title("🔎 Research Agent")
st.caption("Fai una domanda. L'agente può cercare sul web, analizzare le fonti e rispondere.")

with st.sidebar:
    st.header("Configurazione")
    st.write("Modello:", os.getenv("OPENAI_MODEL", "gpt-6-luna"))
    st.divider()
    st.write("**Come funziona**")
    st.write("1. Riceve la domanda")
    st.write("2. Decide se usare la ricerca web")
    st.write("3. Cerca informazioni aggiornate")
    st.write("4. Analizza le fonti")
    st.write("5. Restituisce una risposta")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            with st.expander("Fonti"):
                for source in message["sources"]:
                    st.markdown(f"- [{source['title']}]({source['url']})")

question = st.chat_input("Es. Qual è l'ultima versione di Shopify CLI?")

if question:
    st.session_state.messages.append({
        "role": "user",
        "content": question,
    })

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Ricerca e analisi in corso..."):
            try:
                answer, sources = ask_agent(question)
                st.markdown(answer)

                if sources:
                    with st.expander("Fonti utilizzate"):
                        for source in sources:
                            st.markdown(
                                f"- [{source['title']}]({source['url']})"
                            )

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                })

            except Exception as exc:
                error = f"Errore: {exc}"
                st.error(error)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error,
                    "sources": [],
                })
