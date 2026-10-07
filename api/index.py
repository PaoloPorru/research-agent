import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI


app = FastAPI(title="Research Agent")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask")
def ask(request: AskRequest):
    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="La domanda non può essere vuota.",
        )

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY non configurata.",
        )

    model = os.getenv("OPENAI_MODEL")

    if not model:
        raise HTTPException(
            status_code=500,
            detail="OPENAI_MODEL non configurato.",
        )

    client = OpenAI(api_key=api_key)

    try:
        response = client.responses.create(
            model=model,
            instructions=(
                "Sei un research agent. "
                "Rispondi alla domanda dell'utente usando la ricerca web quando "
                "sono necessarie informazioni aggiornate. "
                "Dai priorità a fonti ufficiali, primarie e affidabili. "
                "Non inventare informazioni. "
                "Distingui chiaramente fatti, interpretazioni e incertezze. "
                "Fornisci una risposta chiara e strutturata."
            ),
            input=question,
            tools=[
                {
                    "type": "web_search",
                }
            ],
        )

        return {
            "answer": response.output_text,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )