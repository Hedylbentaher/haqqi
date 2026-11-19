# Haqqi (حقّي) — Assistant trilingue du droit du travail tunisien

Projet de fin de cours **AI Engineering** (TEK-UP) — **Projet 6 : Arabic–French–English Document Assistant**.
Réalisé par **Hedyl Ben Taher** · encadrant : **Prof. Nadjib Bendaoud** · novembre 2026.

On pose une question en **arabe, français ou anglais**. Haqqi cherche dans les textes de loi
(en arabe, français et anglais), répond **dans la langue de la question** et **cite l'article exact**
(clé, langue, version, page). Il sait quelle version d'un article est **en vigueur** depuis la loi n° 2025-9.

> Haqqi donne une information sur les textes de loi, pas un conseil juridique.

---

## Architecture

```
data/raw (4 PDF)
  → [1] Ingestion : extraction → 1 article = 1 fiche → métadonnées (langue, version, page, empreinte)
  → [2] Recherche hybride : BM25 + vecteurs multilingues (e5) → fusion RRF
        (BM25 ignoré si moins de 10 % des textes sont dans la langue de la question)
  → [3] Agent LangGraph : langue → aiguillage (lecture / versions / recherche) → réponse → vérification des citations
  → [4] Serveur MCP (5 outils) ← client MCP · agent LangChain à appel d'outils
  → [5] Interface Streamlit (arabe de droite à gauche, sources, comparaison des versions)
  → [6] Évaluation : 78 questions trilingues · Recall@k · MRR · citations · langue · faits
```

## Exigences du cours → où les trouver

| Exigence | Dans Haqqi | Fichiers |
|---|---|---|
| Gestion documentaire : RAG, métadonnées, citations | 1 070 fiches avec langue, version, page, état ; citations vérifiées | `ingestion/`, `retrieval/`, `agent/graph.py` |
| Mises à jour des documents | empreintes SHA-256 : seuls les articles modifiés sont refaits (fiches et vecteurs) | `ingestion/pipeline.py`, `retrieval/embeddings.py` |
| Tool Calling / MCP | serveur MCP à 5 outils, client, agent qui appelle les outils | `mcp_server/` |
| LangChain / LangGraph | graphe LangGraph ; agent LangChain `create_agent` | `agent/graph.py`, `mcp_server/agent_mcp.py` |
| Benchmarking | 78 questions, Recall@1/3/5/10, MRR, qualité des réponses | `eval/`, `src/haqqi/eval/`, `results/` |
| Interface web | Streamlit trilingue | `ui/app.py` |
| Fine-tuning (optionnel) | non réalisé : piste d'amélioration | — |

## Le corpus (`data/raw/`)

| Fichier | Document | Langue | Fiches |
|---|---|---|---|
| `code_travail_ar.pdf` | مجلة الشغل, édition 2004 de l'Imprimerie officielle | arabe | 516 |
| `code_travail_fr.pdf` | Code du travail, codification révisée au 15 juillet 1996 | français | 512 |
| `loi_2025_9_ar.pdf` | Loi n° 2025-9 du 21 mai 2025 (JORT n° 61) : CDD, sous-traitance | arabe | 24 |
| `convention_138_en.pdf` | Convention OIT n° 138 sur l'âge minimum, ratifiée par la Tunisie en 1995 | anglais | 18 |

---

## Installation

Python 3.10 ou plus récent (testé avec Python 3.10 sous Windows et Python 3.13).

```bash
python -m venv .venv
.venv\Scripts\activate            # Mac / Linux : source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
copy .env.example .env            # Mac / Linux : cp .env.example .env  → puis coller la clé Gemini
```

- La clé API va **uniquement** dans `.env`, qui est exclu de Git par `.gitignore`.
- Sous Windows, si le projet est dans OneDrive, créez l'environnement hors de OneDrive
  (par exemple `python -m venv C:\venvs\haqqi`) : l'installation est plus rapide et plus fiable.

## Utilisation

```bash
python -m haqqi.ingestion.pipeline              # 1. PDF → 1 070 fiches
python -m haqqi.retrieval.build                 # 2. vecteurs (1re fois : télécharge le modèle, ~470 Mo)
python -m haqqi.agent.ask "Quel est l'âge minimum pour travailler ?"   # 3. une question
python -m haqqi.mcp_server.client               # 4. démo du serveur MCP
python -m haqqi.mcp_server.agent_mcp "Qu'est-ce qui a changé pour les CDD en 2025 ?"
streamlit run src/haqqi/ui/app.py               # 5. interface web
python -m haqqi.eval.run --generation           # 6. évaluation complète → results/summary.md
pytest                                          # 75 tests
```

**Questions pour une démo**
- arabe : « ما هي مدة فترة التجربة؟ » (période d'essai)
- français : « Depuis 2025, peut-on encore signer un CDD pour un poste permanent ? » (cocher « Comparer les versions »)
- anglais : « What is the minimum age for admission to employment? »

## Résultats (78 questions, modèle `intfloat/multilingual-e5-small`, LLM `gemini-flash-lite-latest`)

| Recherche | Recall@1 | Recall@5 | MRR | Recall@5 en anglais |
|---|---|---|---|---|
| BM25 seul | 25,4 % | 53,6 % | 0,416 | 19,6 % |
| vecteurs e5 seuls | 40,6 % | **68,1 %** | 0,564 | 50,0 % |
| hybride, fusion fixe | 39,1 % | 65,2 % | 0,549 | 43,5 % |
| **hybride selon la langue** (version finale) | **43,5 %** | 67,4 % | **0,576** | **50,0 %** |

| Réponses de l'agent (Gemini) | Valeur |
|---|---|
| Au moins une citation correcte | 72,5 % (arabe 91,3 % · français 73,9 % · anglais 52,2 %) |
| Information attendue présente | 75,8 % |
| Réponse dans la langue de la question | 100 % |
| Questions hors sujet : refus de répondre | 100 % |
| Temps moyen | 1,45 s par question |

Sans modèle sémantique ni LLM (référence), la citation correcte n'est que de 46,4 % et l'agent ne refuse
jamais les questions hors sujet. Détails : [`results/summary.md`](results/summary.md),
[`results/baseline_sans_modele/`](results/baseline_sans_modele/) et la fiche
[`docs/06_evaluation.md`](docs/06_evaluation.md) (dont l'amélioration « BM25 selon la langue », avant / après).

## Documentation (une fiche par étape, avec les questions possibles du jury)

[`01_ingestion`](docs/01_ingestion.md) · [`02_recherche`](docs/02_recherche.md) · [`03_agent`](docs/03_agent.md) ·
[`04_mcp`](docs/04_mcp.md) · [`05_interface`](docs/05_interface.md) · [`06_evaluation`](docs/06_evaluation.md)

## Structure

```
haqqi/
├── data/sources.json · data/raw/        # catalogue + 4 PDF
├── docs/                                # explication de chaque étape
├── eval/                                # questions d'évaluation (78)
├── results/                             # résultats de l'évaluation
├── src/haqqi/
│   ├── config.py · service.py
│   ├── ingestion/   # étape 1 : text_utils, pdf_extract, splitter, pipeline, show
│   ├── retrieval/   # étape 2 : tokenize, bm25, embeddings, hybrid, build
│   ├── agent/       # étape 3 : llm, prompts, graph, ask
│   ├── mcp_server/  # étape 4 : server, client, agent_mcp
│   ├── ui/          # étape 5 : app (Streamlit)
│   └── eval/        # étape 6 : metrics, run
└── tests/                               # 75 tests
```

## Limites connues

- **L'anglais reste le point faible** (citation correcte 52,2 %) : le seul texte anglais est la Convention 138,
  donc une question anglaise dépend entièrement du modèle multilingue.
- **La loi 2025-9 n'existe qu'en arabe** : les questions sur les changements réussissent en arabe et
  échouent souvent en français et en anglais. Le texte français date de 1996 ; en cas de différence, l'arabe fait foi.
- **Le LLM varie** : avec les mêmes fiches trouvées, quelques réponses changent d'une exécution à l'autre.
- Le contrôle de l'information attendue se fait par mots-clés, pas par un juge humain.
- Le PDF du JORT n'encode pas toujours les espaces : quelques mots restent collés ou coupés.
- Pas de fine-tuning (optionnel dans l'énoncé) : piste d'amélioration, avec la traduction de la question en arabe.