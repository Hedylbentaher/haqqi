"""Chargement des fiches (articles.jsonl) en mémoire."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .. import config


@dataclass
class ArticleStore:
    """Toutes les fiches, avec des accès rapides par id et par clé d'article."""

    records: list[dict]
    by_id: dict[str, dict] = field(init=False)
    by_key: dict[str, list[dict]] = field(init=False)

    def __post_init__(self) -> None:
        self.by_id = {r["id"]: r for r in self.records}
        self.by_key = {}
        for r in self.records:
            self.by_key.setdefault(r["article_key"], []).append(r)

    @classmethod
    def load(cls, path: Path = config.ARTICLES_FILE) -> "ArticleStore":
        if not path.exists():
            raise FileNotFoundError(
                f"{path} introuvable. Lancez d'abord : python -m haqqi.ingestion.pipeline"
            )
        with path.open(encoding="utf-8") as f:
            return cls([json.loads(line) for line in f if line.strip()])

    def __len__(self) -> int:
        return len(self.records)

    def versions(self, article_key: str) -> list[dict]:
        """Toutes les versions d'un article (langues et dates), de la plus ancienne à la plus récente."""
        return sorted(self.by_key.get(article_key, []), key=lambda r: (r["lang"], r.get("date") or ""))

    def current(self, article_key: str, lang: str | None = None) -> list[dict]:
        """Les versions en vigueur d'un article, éventuellement dans une seule langue."""
        return [r for r in self.by_key.get(article_key, [])
                if r.get("is_current") and (lang is None or r["lang"] == lang)]


def citation_label(rec: dict) -> str:
    """Texte court pour citer une fiche : « Code du travail, art. 6-4 (loi_2025_9, ar) »."""
    code, number = rec["article_key"].split(":", 1)
    names = {"ct": "Code du travail", "c138": "Convention OIT n° 138", "loi_2025_9": "Loi n° 2025-9"}
    name = names.get(code.split("@")[0], code)
    if "@" in code:
        name += " (loi de promulgation)"
    return f"{name}, art. {number} ({rec['version']}, {rec['lang']})"