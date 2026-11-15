"""BM25 (Okapi) écrit à la main, pour pouvoir l'expliquer.

Idée : un article est pertinent s'il contient les mots de la question,
surtout des mots RARES dans le corpus, sans être favorisé parce qu'il est long.

┌──────────────────────────────────────────────────────────────────────────┐
│ score(article, question) = Σ  IDF(mot) × tf × (k1 + 1)                   │
│                           mot   ─────────────────────────────────────── │
│                                 tf + k1 × (1 − b + b × longueur / moy.)  │
│                                                                          │
│ IDF(mot) = ln( 1 + (N − n + 0,5) / (n + 0,5) )                           │
│ tf = nb de fois où le mot est dans l'article · N = nb d'articles         │
│ n = nb d'articles qui contiennent le mot · k1 = 1,5 · b = 0,75           │
└──────────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import math
from collections import Counter

from .tokenize import tokenize


class BM25Index:
    def __init__(self, texts: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        docs = [tokenize(t) for t in texts]
        self.n_docs = len(docs)
        self.doc_len = [len(d) for d in docs]
        self.avg_len = (sum(self.doc_len) / self.n_docs) if self.n_docs else 0.0
        # index inversé : mot → [(n° d'article, tf), …]
        self.postings: dict[str, list[tuple[int, int]]] = {}
        for i, doc in enumerate(docs):
            for term, tf in Counter(doc).items():
                self.postings.setdefault(term, []).append((i, tf))
        self.idf = {
            term: math.log(1 + (self.n_docs - len(p) + 0.5) / (len(p) + 0.5))
            for term, p in self.postings.items()
        }

    def scores(self, query: str) -> list[float]:
        """Un score par article (0 si aucun mot en commun)."""
        scores = [0.0] * self.n_docs
        for term in set(tokenize(query)):
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i, tf in self.postings[term]:
                norm = tf + self.k1 * (1 - self.b + self.b * self.doc_len[i] / (self.avg_len or 1))
                scores[i] += idf * tf * (self.k1 + 1) / norm
        return scores