"""Choix du modèle de langage (LLM), réglé dans le fichier .env.

    HAQQI_LLM_PROVIDER=gemini   + GOOGLE_API_KEY=…   (gratuit : aistudio.google.com)
    HAQQI_LLM_PROVIDER=groq     + GROQ_API_KEY=…     (gratuit : console.groq.com)
    HAQQI_LLM_PROVIDER=none     → pas de LLM : réponses « extractives » (citations du texte)

Sans clé, Haqqi fonctionne quand même en mode extractif : la démo ne tombe jamais en panne.
"""

from __future__ import annotations

import logging
import os

from .. import config

log = logging.getLogger(__name__)

DEFAULT_MODELS = {
    "gemini": "gemini-flash-latest",        # alias Google : toujours le dernier modèle Flash
    "groq": "llama-3.3-70b-versatile",
}


def get_chat_model(provider: str | None = None, model: str | None = None):
    """Retourne un modèle de chat LangChain, ou None (mode extractif)."""
    provider = (provider or config.LLM_PROVIDER).lower()
    model = model or config.LLM_MODEL or DEFAULT_MODELS.get(provider, "")
    if provider == "none":
        return None
    if provider == "gemini":
        if not os.environ.get("GOOGLE_API_KEY"):
            log.warning("GOOGLE_API_KEY absente du fichier .env : mode extractif (sans LLM).")
            return None
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model, temperature=0, max_retries=2, timeout=60)
    if provider == "groq":
        if not os.environ.get("GROQ_API_KEY"):
            log.warning("GROQ_API_KEY absente du fichier .env : mode extractif (sans LLM).")
            return None
        from langchain_groq import ChatGroq
        return ChatGroq(model=model, temperature=0, max_retries=2, timeout=60)
    raise ValueError(f"HAQQI_LLM_PROVIDER inconnu : {provider} (gemini, groq ou none)")


def describe(llm) -> str:
    """Nom lisible du modèle utilisé (pour l'interface et le rapport)."""
    if llm is None:
        return "aucun (mode extractif)"
    return getattr(llm, "model", None) or getattr(llm, "model_name", None) or type(llm).__name__