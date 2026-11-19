# Résultats de l'évaluation Haqqi

- Date : 2026-11-19 09:07 UTC
- Questions : 78 (69 avec réponse, 9 hors sujet)
- Modèle d'embeddings : `hash-trigrams-512`
- Fiches : 1070

## Recherche (toutes langues)

| Méthode | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | ms / question |
|---|---|---|---|---|---|---|
| bm25 | 25.4 % | 44.9 % | 53.6 % | 60.1 % | 0.416 | 0.4 |
| vector | 18.1 % | 29.0 % | 37.0 % | 40.6 % | 0.271 | 1.0 |
| hybrid | 21.7 % | 42.0 % | 47.1 % | 53.6 % | 0.369 | 1.2 |

## Recherche par langue de la question (Recall@5 · MRR)

| Méthode | arabe | français | anglais |
|---|---|---|---|
| bm25 | 78.3 % · 0.661 | 63.0 % · 0.425 | 19.6 % · 0.163 |
| vector | 65.2 % · 0.472 | 37.0 % · 0.270 | 8.7 % · 0.071 |
| hybrid | 73.9 % · 0.616 | 56.5 % · 0.357 | 10.9 % · 0.133 |

## Recherche par type de question (Recall@5)

| Méthode | cross_doc | factual | version |
|---|---|---|---|
| bm25 | 44.4 % | 62.2 % | 33.3 % |
| vector | 27.8 % | 42.2 % | 26.7 % |
| hybrid | 38.9 % | 55.6 % | 26.7 % |

## Réponses de l'agent (LLM : `aucun (mode extractif)`)

| Mesure | Valeur |
|---|---|
| Au moins une citation correcte | 46.4 % |
| Précision des citations | 24.6 % |
| Information attendue présente | 50.0 % |
| Réponse dans la langue de la question | 89.7 % |
| Questions hors sujet : refus de répondre | 0.0 % |
| Secondes par question | 0.0 |

| Langue | Citation correcte | Information présente | Bonne langue |
|---|---|---|---|
| ar | 73.9 % | 72.7 % | 100.0 % |
| fr | 47.8 % | 54.5 % | 92.3 % |
| en | 17.4 % | 22.7 % | 76.9 % |
