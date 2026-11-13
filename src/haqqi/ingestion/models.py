"""Structure d'un article découpé (= un "morceau" du RAG)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .text_utils import normalize_for_search


@dataclass
class Article:
    """Un article de loi, dans une langue et une version données.

    Exemple : l'article 6-4 du Code du travail, en arabe, version loi 2025-9.
    """

    doc_id: str            # document source, ex. "ct_ar"
    code: str              # texte de loi auquel l'article appartient, ex. "ct"
    article: str           # numéro canonique, ex. "6-4", "234bis", "1"
    lang: str              # "ar" | "fr" | "en"
    version: str           # ex. "edition_2004", "loi_2025_9"
    date: str              # date de la version (AAAA-MM-JJ), "" si inconnue
    text: str              # texte de l'article (propre, pour l'affichage)
    heading: str           # ligne de titre telle que trouvée dans le PDF
    section: str = ""      # ex. "Livre premier > Titre II > Chapitre 1"
    page: int | None = None
    source_file: str = ""
    title: str = ""        # titre du document source
    is_new: bool = False   # marqué « (nouveau) » / « (جديد) » dans le texte
    extra: dict = field(default_factory=dict)

    @property
    def article_key(self) -> str:
        """Clé indépendante de la langue et de la version → sert à aligner AR / FR / versions."""
        return f"{self.code}:{self.article}"

    @property
    def id(self) -> str:
        """Identifiant unique : document + clé d'article, ex. « ct_fr/ct:6-4 »."""
        return f"{self.doc_id}/{self.article_key}"

    @property
    def hash(self) -> str:
        """Empreinte du texte → permet de savoir si un article a changé (mises à jour)."""
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()[:16]

    def to_record(self) -> dict:
        return {
            "id": self.id,
            "article_key": self.article_key,
            "code": self.code,
            "article": self.article,
            "lang": self.lang,
            "version": self.version,
            "date": self.date,
            "is_current": None,  # calculé par le pipeline une fois tous les documents lus
            "is_new": self.is_new,
            "section": self.section,
            "heading": self.heading,
            "page": self.page,
            "doc_id": self.doc_id,
            "source_file": self.source_file,
            "title": self.title,
            "text": self.text,
            "text_norm": normalize_for_search(self.text),
            "hash": self.hash,
            **self.extra,
        }