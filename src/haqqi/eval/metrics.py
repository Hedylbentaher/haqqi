"""Les mesures de l'évaluation.

┌────────────────────────────────────────────────────────────────────────────┐
│ Recall@k = (nb d'articles attendus présents dans les k premiers résultats) │
│            ──────────────────────────────────────────────────────────────  │
│                         nb d'articles attendus                             │
│                                                                            │
│ MRR = moyenne sur les questions de  1 / rang du 1er bon article            │
│       (0 si aucun bon article dans les résultats)                          │
└────────────────────────────────────────────────────────────────────────────┘

Exemple : attendus = {ct:53, c138:2}, résultats = [ct:54, ct:53, c138:7, …]
    Recall@1 = 0/2 = 0 · Recall@3 = 1/2 = 0,5 · rang du 1er bon = 2 → RR = 0,5
"""

from __future__ import annotations

import re

from ..ingestion.text_utils import normalize_for_search


def recall_at_k(ranked: list[str], gold: list[str], k: int) -> float:
    if not gold:
        return 0.0
    return len(set(ranked[:k]) & set(gold)) / len(set(gold))


def reciprocal_rank(ranked: list[str], gold: list[str]) -> float:
    for rank, key in enumerate(ranked, start=1):
        if key in gold:
            return 1.0 / rank
    return 0.0


def _normalize_answer(text: str) -> str:
    text = normalize_for_search(text)
    return re.sub(r"(?<=\d)[\s.,](?=\d{3}\b)", "", text)   # « 10 000 » ou « 10.000 » → « 10000 »


def facts_found(answer: str, facts: list[list[str]]) -> bool:
    """Vrai si CHAQUE groupe de faits a au moins une écriture présente dans la réponse.

    facts = [["16", "ستة عشر", "seize", "sixteen"]] → la réponse doit contenir l'une des quatre.
    """
    norm = _normalize_answer(answer)
    for group in facts:
        if not any(_normalize_answer(alt) in norm for alt in group):
            return False
    return True


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0