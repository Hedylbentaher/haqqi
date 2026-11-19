# Résultats de l'évaluation Haqqi

- Date : 2026-11-19 09:18 UTC
- Questions : 78 (69 avec réponse, 9 hors sujet)
- Modèle d'embeddings : `intfloat/multilingual-e5-small`
- Fiches : 1070

## Recherche (toutes langues)

| Méthode | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR | ms / question |
|---|---|---|---|---|---|---|
| bm25 | 25.4 % | 44.9 % | 53.6 % | 60.1 % | 0.416 | 0.5 |
| vector | 40.6 % | 60.1 % | 68.1 % | 76.1 % | 0.564 | 42.2 |
| hybrid | 39.1 % | 62.3 % | 65.2 % | 71.0 % | 0.549 | 39.4 |

## Recherche par langue de la question (Recall@5 · MRR)

| Méthode | arabe | français | anglais |
|---|---|---|---|
| bm25 | 78.3 % · 0.661 | 63.0 % · 0.425 | 19.6 % · 0.163 |
| vector | 87.0 % · 0.704 | 67.4 % · 0.597 | 50.0 % · 0.393 |
| hybrid | 87.0 % · 0.773 | 65.2 % · 0.562 | 43.5 % · 0.314 |

## Recherche par type de question (Recall@5)

| Méthode | cross_doc | factual | version |
|---|---|---|---|
| bm25 | 44.4 % | 62.2 % | 33.3 % |
| vector | 44.4 % | 84.4 % | 33.3 % |
| hybrid | 44.4 % | 80.0 % | 33.3 % |

## Réponses de l'agent (LLM : `gemini-flash-lite-latest`)

| Mesure | Valeur |
|---|---|
| Au moins une citation correcte | 68.1 % |
| Précision des citations | 57.5 % |
| Information attendue présente | 68.2 % |
| Réponse dans la langue de la question | 100.0 % |
| Questions hors sujet : refus de répondre | 100.0 % |
| Secondes par question | 1.38 |

| Langue | Citation correcte | Information présente | Bonne langue |
|---|---|---|---|
| ar | 91.3 % | 86.4 % | 100.0 % |
| fr | 69.6 % | 77.3 % | 100.0 % |
| en | 43.5 % | 40.9 % | 100.0 % |
