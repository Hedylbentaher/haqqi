# Étape 3 — L'agent LangGraph (expliqué simplement)

## 1. Le but en une phrase

Comprendre la question, choisir **le bon chemin**, rédiger une réponse **dans la langue de la
question**, et **vérifier** chaque citation.

> **Analogie :** un guichet avec un aiguilleur. Si vous donnez un numéro d'article, il va
> directement au bon tiroir. Si vous demandez « ce qui a changé », il sort l'ancienne et la
> nouvelle version. Sinon, il cherche.

---

## 2. Le graphe (`graph.py`)

```
START → langue → aiguillage ─┬─→ lecture   (« article 53 », « الفصل 6-4 »)  ─┐
                             ├─→ versions  (« réforme 2025 », « تنقيح »)     ├─→ rédaction → vérification → END
                             └─→ recherche (tout le reste)                   ─┘
```

| Case | Ce qu'elle fait |
|---|---|
| langue | arabe, français ou anglais (règle de l'étape 1) |
| aiguillage | repère un numéro d'article ou une question sur les versions |
| lecture | lit l'article cité, dans toutes ses langues |
| versions | prend toutes les versions d'un article (avant / après la loi 2025-9) |
| recherche | recherche hybride (étape 2), 6 fiches |
| rédaction | LLM (Gemini ou Groq) ; sans clé : réponse extractive |
| vérification | supprime toute citation qui ne vient pas des fiches trouvées |

L'état (`AgentState`) circule de case en case : question, langue, chemin, fiches, réponse, citations.

---

## 3. La consigne donnée au LLM (`prompts.py`)

1. Répondre **uniquement** à partir des articles fournis.
2. Répondre **dans la langue de la question**, même si l'article est dans une autre langue.
3. Citer chaque information avec la clé exacte : `[ct:6-4]`, `[c138:2]`.
4. Utiliser la version **EN VIGUEUR** ; signaler le changement si on demande l'avant / après.
5. Si les articles ne répondent pas : le dire, sans citer.
6. Répondre en 2 à 6 phrases, simplement.

Chaque article est donné avec un en-tête : clé, langue, version, état (en vigueur / remplacé).

---

## 4. La vérification des citations

```
Réponse du LLM : « … 16 ans [ct:53] … [ct:999] »
Fiches trouvées : {ct:53, c138:2, …}
      ↓
[ct:53]  → gardée   (vient des fiches)
[ct:999] → supprimée + avertissement (inventée)
```

Pas de citation du tout → l'agent considère que la réponse n'a pas été trouvée
(utile pour les questions hors sujet).

---

## 5. Sans clé API : le mode extractif

Si le LLM n'est pas configuré ou ne répond pas (quota, réseau), l'agent cite le texte des
articles trouvés : « D'après Code du travail, art. 53 : « … » [ct:53] ». La démo ne tombe jamais en panne.

---

## 6. Commandes

```bash
python -m haqqi.agent.ask "Quel est l'âge minimum pour travailler ?"
python -m haqqi.agent.ask "ما هي المدة القصوى لفترة التجربة؟"
python -m haqqi.agent.ask "What changed in article 6-4 with the 2025 reform?" --no-llm
```

---

## 7. Résumé

| Élément | Choix | Pourquoi |
|---|---|---|
| Framework | LangGraph (StateGraph) | chemins conditionnels visibles et testables |
| LLM | Gemini `gemini-flash-lite-latest` (gratuit), Groq en option | bon en arabe, clé gratuite, nom du modèle réglé dans `.env` |
| Langue | détection par règles | rapide, explicable, sans appel au LLM |
| Citations | clés d'articles vérifiées | pas de source inventée |
| Secours | mode extractif | démo fiable sans réseau |

---

## 8. Exemples réels (Gemini `gemini-flash-lite-latest`)

| Question | Chemin | Réponse obtenue |
|---|---|---|
| « ما هي المدة القصوى لفترة التجربة؟ » | search | en arabe : six mois, renouvelable une fois `[ct:6-3]` ; plus la disposition transitoire de la loi pour les contrats signés avant elle `[loi_2025_9:7]` |
| « Que dit l'article 53 ? » | lookup | pas d'emploi avant 16 ans `[ct:53]` |
| « Qu'est-ce qui a changé pour les CDD en 2025 ? » | compare | avant : CDD ou CDI ; depuis la loi 2025-9 : contrat à durée indéterminée `[ct:6-2]`. Question en français, source en arabe, réponse en français |
| « Que dit l'article 53 ? » (`--no-llm`) | lookup | mode extractif : le texte de l'article 53 est cité |

**Choix du modèle :** `gemini-flash-latest` était surchargé (erreur 503) et `gemini-2.5-flash` n'est plus
ouvert aux nouveaux comptes (erreur 404). La version légère `gemini-flash-lite-latest` suffit pour
des réponses courtes à partir d'articles fournis. Le nom du modèle est lu dans `.env`
(`HAQQI_LLM_MODEL`) : on peut en changer sans toucher au code. Les nouveaux essais sont limités
(`max_retries=2`, `timeout=60`) ; si le LLM ne répond pas, l'agent passe en mode extractif.

---

## 9. Questions possibles du jury → réponses types

**Q : Pourquoi un graphe et pas un seul appel au LLM ?**
R : Chaque étape a un rôle clair et se teste séparément. Les chemins « lecture » et « versions »
évitent une recherche inutile quand on connaît déjà l'article.

**Q : Comment évitez-vous les hallucinations ?**
R : Le LLM ne reçoit que les articles trouvés, doit citer leurs clés, et une case de
vérification supprime toute clé absente du contexte. Sans citation, la réponse est traitée
comme « pas trouvé ».

**Q : Comment répondre en français à partir d'un article arabe ?**
R : La consigne impose la langue de la question ; l'article arabe est dans le contexte avec sa
clé. La réponse est en français et cite `[ct:6-4]`, que l'interface affiche avec le texte arabe original.