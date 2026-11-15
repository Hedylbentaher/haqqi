"""Étape 2 — Recherche hybride : BM25 (mots) + vecteurs multilingues (sens).

    question ─┬─→ BM25     (mots exacts, après normalisation)  ─┐
              │                                                   ├─→ fusion RRF → articles classés
              └─→ vecteurs (sens, toutes langues)              ─┘
"""