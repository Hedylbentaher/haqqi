"""Tous les chemins du projet, au même endroit."""
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]   # le dossier haqqi/
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"                       # les PDF
PROCESSED_DIR = DATA_DIR / "processed"           # les fiches créées
SOURCES_FILE = DATA_DIR / "sources.json"         # le catalogue

ARTICLES_FILE = PROCESSED_DIR / "articles.jsonl"
MANIFEST_FILE = PROCESSED_DIR / "manifest.json"

SUPPORTED_EXTENSIONS = (".pdf", ".txt")          # formats acceptés dans data/raw
