"""Tous les chemins et réglages du projet, au même endroit.

Les réglages modifiables se mettent dans un fichier ``.env`` à la racine
(voir ``.env.example``). Ce fichier n'est jamais envoyé sur GitHub.
"""
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]   # le dossier haqqi/

try:  # charge .env s'il existe (clé API, choix du modèle…)
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env")
except ImportError:  # python-dotenv pas installé : on lit seulement l'environnement
    pass

# --- Étape 1 : documents ---------------------------------------------------------------
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"                       # les PDF
PROCESSED_DIR = DATA_DIR / "processed"           # les fiches créées
SOURCES_FILE = DATA_DIR / "sources.json"         # le catalogue

ARTICLES_FILE = PROCESSED_DIR / "articles.jsonl"
MANIFEST_FILE = PROCESSED_DIR / "manifest.json"

SUPPORTED_EXTENSIONS = (".pdf", ".txt")          # formats acceptés dans data/raw

# --- Étape 2 : recherche -----------------------------------------------------------------
INDEX_DIR = Path(os.environ.get("HAQQI_INDEX_DIR", DATA_DIR / "index"))
VECTORS_FILE = INDEX_DIR / "vectors.npz"         # vecteurs des articles (cache)

# Modèle d'embeddings multilingue (arabe, français, anglais), téléchargé une seule fois.
EMBEDDING_MODEL = os.environ.get("HAQQI_EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
# "e5" = vrai modèle multilingue ; "hash" = modèle simple sans téléchargement (tests, dépannage)
EMBEDDER = os.environ.get("HAQQI_EMBEDDER", "e5")

# --- Étape 3 : modèle de langage ---------------------------------------------------------
# "gemini" (gratuit avec une clé Google AI Studio), "groq", ou "none" (réponses extractives)
LLM_PROVIDER = os.environ.get("HAQQI_LLM_PROVIDER", "gemini")
LLM_MODEL = os.environ.get("HAQQI_LLM_MODEL", "")  # vide = modèle par défaut du fournisseur

# --- Étape 6 : évaluation ----------------------------------------------------------------
EVAL_DIR = ROOT_DIR / "eval"
QUESTIONS_FILE = EVAL_DIR / "questions.jsonl"
RESULTS_DIR = ROOT_DIR / "results"