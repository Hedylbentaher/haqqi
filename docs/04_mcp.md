# Étape 4 — Le serveur MCP et l'appel d'outils (expliqués simplement)

## 1. Le but en une phrase

Rendre les fonctions de Haqqi **utilisables par n'importe quel client MCP** (un script, un agent,
Claude Desktop…), et montrer un LLM qui **décide lui-même** quels outils appeler.

> **Analogie :** MCP est une **prise électrique universelle**. Haqqi est l'appareil ;
> n'importe quel client compatible peut le brancher et utiliser ses outils.

---

## 2. Le schéma

```
client MCP (script / agent LangChain / Claude Desktop)
      │  protocole MCP (JSON-RPC sur stdio)
      ▼
serveur « haqqi » (server.py)
      │
      ▼
service.py  →  agent (étape 3) · recherche (étape 2) · pipeline (étape 1)
```

---

## 3. Les 5 outils (`server.py`)

| Outil | Entrée | Sortie |
|---|---|---|
| `search_by_language` ⭐ | question, langue des documents, k | articles classés (clé, version, texte) |
| `answer_with_citations` ⭐ | question | réponse + citations |
| `ingest_document` ⭐ | chemin PDF/TXT, langue, type | nb d'articles ajoutés / modifiés, vecteurs recalculés |
| `get_article` | clé (ex. `ct:53`) | l'article dans toutes ses langues |
| `compare_versions` | clé (ex. `ct:6-4`) | texte d'avant et texte en vigueur |

⭐ = les 3 outils demandés pour le projet 6 dans l'énoncé.

Les descriptions des outils (docstrings) sont envoyées au client : c'est ce que lit le LLM pour
choisir un outil.

---

## 4. Le client de démonstration (`client.py`)

```
① lance le serveur → ② liste les outils → ③ appelle search_by_language
   → ④ appelle compare_versions(ct:6-4) → ⑤ appelle answer_with_citations
```

## 5. L'agent à appel d'outils (`agent_mcp.py`)

```
question → LLM : « j'appelle search_by_language(…) » → serveur MCP → résultats
         → LLM : « j'appelle compare_versions(ct:6-4) » → …
         → LLM : réponse finale avec [citations]
```

- Outils chargés depuis le serveur avec **langchain-mcp-adapters**.
- Agent construit avec **LangChain `create_agent`** (qui tourne sur LangGraph).
- C'est le **Tool Calling** : le LLM choisit l'outil et ses arguments.
- Chaque résultat de recherche porte une étiquette `changed_by` (la loi qui a modifié l'article) ;
  la consigne impose `compare_versions` avant de répondre à une question sur un changement.
- Comme dans le graphe, une citation qui ne vient d'aucun outil est supprimée (`verify_citations`).

---

## 6. Commandes

```bash
python -m haqqi.mcp_server.client                                   # démo des outils
python -m haqqi.mcp_server.agent_mcp "Qu'est-ce qui a changé pour les CDD en 2025 ?"   # clé API nécessaire
mcp dev src/haqqi/mcp_server/server.py                              # inspecteur MCP (navigateur)
```

---

## 7. Résumé

| Exigence | Où |
|---|---|
| Serveur MCP, au moins 2 outils | `server.py` : 5 outils |
| Démonstration avec un client | `client.py` |
| Tool Calling | `agent_mcp.py` (le LLM appelle les outils MCP) |
| Mises à jour des documents | outil `ingest_document` |

Tests : `tests/test_mcp.py` lance le **vrai** serveur, un **vrai** client, et un agent dont le
LLM est simulé (il demande `get_article(ct:53)`, reçoit bien le texte, et sa citation inventée
`[ct:999]` est supprimée).

---

## 8. Exemples réels, difficultés et solutions

**Le client (e5 + Gemini).** Question en français, `search_by_language(doc_language="ar")` :
les articles arabes 55 et 56 (travail des enfants) sont trouvés → la recherche d'une langue à
l'autre fonctionne à travers MCP. Gemini n'ayant pas répondu à temps (3 essais de 60 s), la
réponse de l'étape ③ est passée en mode extractif : la protection a fonctionné.

**Blocage sous Windows.** Le serveur restait bloqué au premier appel d'outil : il chargeait
torch / e5 alors qu'il lisait déjà les messages du client. Solution : `service.get_agent()` est
appelé au démarrage, avant `mcp.run()`.

**L'agent à appel d'outils et la réforme de 2025.** Question : « Qu'est-ce qui a changé pour les CDD en 2025 ? »

| | Avant | Après |
|---|---|---|
| Outils appelés | 3 × `search_by_language` | `search_by_language`, puis `compare_versions` sur ct:94-2, ct:6-2, ct:6-4 |
| Réponse | « aucune modification » ❌ | la réforme expliquée : cas exceptionnels, requalification en CDI, pas de période d'essai, mêmes droits ✅ |
| Citations | non vérifiées | vérifiées |

Solutions : (1) l'étiquette `changed_by` dans les résultats de recherche ; (2) une procédure
explicite dans la consigne et dans la description de `compare_versions` ; (3) la vérification des
citations. Le choix des outils reste celui du LLM (le résultat peut varier d'un essai à l'autre) :
l'interface et l'évaluation utilisent donc le graphe de l'étape 3.

---

## 9. Questions possibles du jury → réponses types

**Q : Quelle différence entre l'agent de l'étape 3 et celui de l'étape 4 ?**
R : L'agent de l'étape 3 suit un graphe fixe (aiguillage par règles) : rapide et prévisible, il
sert à l'interface et à l'évaluation. L'agent de l'étape 4 laisse le LLM choisir les outils MCP :
plus flexible, mais plus lent et dépendant du LLM.

**Q : Pourquoi MCP plutôt que des fonctions Python ?**
R : Un serveur MCP est réutilisable par n'importe quel client compatible, sans modifier le code :
Claude Desktop, un autre agent, un autre langage. Les outils sont décrits de façon standard.

**Q : Comment l'outil d'ingestion gère-t-il les mises à jour ?**
R : Il copie le fichier, met à jour le catalogue, relance le pipeline seulement pour ce document
(empreintes) et recalcule seulement les vecteurs des articles nouveaux ou modifiés.

**Q : Le LLM choisit-il toujours le bon outil ?**
R : Non. Au début, Gemini (version légère) n'appelait pas `compare_versions` et concluait à tort
« aucun changement ». On ne peut pas forcer le LLM, mais on peut l'aider : une étiquette `changed_by`
dans les résultats, une procédure dans la consigne et un contrôle des citations. Après ces
changements, il compare bien les versions et explique la réforme de 2025.