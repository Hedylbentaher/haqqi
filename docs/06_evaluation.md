# Étape 6 — L'évaluation (expliquée simplement)

## 1. Le but en une phrase

Donner une **note chiffrée** à la recherche et aux réponses, avec des questions dont on
connaît la bonne réponse.

> **Analogie :** un examen blanc. On connaît le corrigé (les bons articles), on fait passer
> l'examen au système, on compte les points.

---

## 2. Les questions (`eval/questions.jsonl`)

**78 questions** = 23 questions × 3 langues + 3 questions hors sujet × 3 langues.

| Type | Nb | Exemple | Bon article |
|---|---|---|---|
| factual | 45 | « Quelle est la durée du congé de maternité ? » | ct:64 |
| version | 15 | « Depuis la réforme de 2025, quand peut-on conclure un CDD ? » | ct:6-4 |
| cross_doc | 9 | « Quel est l'âge minimum pour travailler ? » | ct:53 + c138:2 |
| out_of_scope | 9 | « Le télétravail est-il réglementé ? » | aucun |

Chaque bon article a été vérifié à la main dans les textes. Chaque question a aussi
**l'information attendue** (ex. « 30 jours » écrit 30, ثلاثين, trente ou thirty).

---

## 3. Les mesures de la recherche (`metrics.py`)

```
┌──────────────────────────────────────────────────────────────┐
│ Recall@k = nb de bons articles dans les k premiers           │
│            ─────────────────────────────────────            │
│                   nb de bons articles                         │
│                                                               │
│ MRR = moyenne de  1 / rang du premier bon article             │
└──────────────────────────────────────────────────────────────┘
```

Exemple : bons articles = {ct:53, c138:2} ; résultats = [ct:54, ct:53, c138:7, c138:2]
- Recall@1 = 0/2 = **0** · Recall@3 = 1/2 = **0,5** · Recall@5 = 2/2 = **1**
- premier bon article au rang 2 → RR = **0,5**

On compare les 3 méthodes : **BM25**, **vecteurs**, **hybride**, par langue et par type.

---

## 4. Les mesures des réponses

| Mesure | Question posée |
|---|---|
| Citation correcte | au moins une citation est un bon article ? |
| Précision des citations | quelle part des citations est bonne ? |
| Information présente | la réponse contient-elle l'information attendue ? |
| Bonne langue | la réponse est-elle dans la langue de la question ? |
| Refus hors sujet | pour une question sans réponse, l'agent s'abstient-il ? |

---

## 5. Commandes

```bash
python -m haqqi.eval.run                        # recherche : bm25, vector, hybrid
python -m haqqi.eval.run --generation           # + réponses (LLM du fichier .env), 10 à 20 min
```

Résultats : `results/summary.md` (tableaux), `results/retrieval.json`,
`results/retrieval_details.jsonl`, `results/generation.jsonl`.

La référence **sans modèle sémantique** est dans `results/baseline_sans_modele/` : elle montre
ce que vaut la recherche quand on ne comprend pas les traductions.

---

## 6. Ce que montre la référence sans modèle (Recall@5)

| Méthode | arabe | français | anglais |
|---|---|---|---|
| BM25 | 78,3 % | 63,0 % | 19,6 % |

Les questions anglaises échouent : les articles du Code n'existent qu'en arabe et en français,
et BM25 ne relie que des mots identiques. C'est exactement le problème que le modèle
multilingue doit résoudre (comparer avec `results/summary.md`).

---

## 7. Résultats de la recherche avec le modèle multilingue e5

| Méthode | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR |
|---|---|---|---|---|---|
| BM25 | 25,4 % | 44,9 % | 53,6 % | 60,1 % | 0,416 |
| vecteurs e5 | 40,6 % | 60,1 % | **68,1 %** | **76,1 %** | **0,564** |
| hybride (RRF) | 39,1 % | **62,3 %** | 65,2 % | 71,0 % | 0,549 |

| Recall@5 · MRR | arabe | français | anglais |
|---|---|---|---|
| BM25 | 78,3 % · 0,661 | 63,0 % · 0,425 | 19,6 % · 0,163 |
| vecteurs e5 | 87,0 % · 0,704 | 67,4 % · 0,597 | **50,0 %** · 0,393 |
| hybride | 87,0 % · **0,773** | 65,2 % · 0,562 | 43,5 % · 0,314 |

| Recall@5 | cross_doc | factual | version |
|---|---|---|---|
| BM25 | 44,4 % | 62,2 % | 33,3 % |
| vecteurs e5 | 44,4 % | 84,4 % | 33,3 % |
| hybride | 44,4 % | 80,0 % | 33,3 % |

**Ce qu'on en tire :**
1. **e5 améliore nettement la recherche** : Recall@5 de 53,6 % à 68,1 %, MRR de 0,416 à 0,564.
2. **L'anglais est multiplié par 2,5** (19,6 % → 50,0 %) : la recherche d'une langue à l'autre fonctionne,
   mais la moitié des questions anglaises échoue encore.
3. **L'hybride est un peu en dessous de e5 seul.** Pour les questions anglaises, les 5 premiers résultats
   de BM25 sont toujours des articles de la Convention 138 (les seuls textes anglais) : BM25 ajoute du
   bruit, et RRF lui donne le même poids qu'à e5. L'hybride reste le meilleur pour classer en arabe
   (MRR 0,773) et dans le top 3 (62,3 %).
4. **Les questions sur la loi 2025-9 sont les plus difficiles (33,3 %).** Les nouveaux textes n'existent
   qu'en arabe et les anciennes versions françaises sont écartées (filtre « en vigueur ») : les 5 questions
   arabes réussissent, les 10 questions françaises et anglaises échouent. Dans l'agent, le chemin
   « comparaison de versions » compense en partie ce problème.
5. **Les questions Code + Convention plafonnent à 44,4 %** : il faut trouver 2 articles, et la recherche
   n'en trouve souvent qu'un.

**Pistes d'amélioration :** pondérer BM25 selon la langue de la question ; traduire la question en
arabe avant la recherche ; un modèle d'embeddings plus grand (e5-base, e5-large).

Les résultats des réponses (e5 + Gemini) sont dans `results/summary.md` (étape 6.4).

---

## 8. Questions possibles du jury → réponses types

**Q : Pourquoi 78 questions et pas des questions générées automatiquement ?**
R : Le cours demande au moins 50 questions. Nous les avons écrites et vérifiées à la main
(bon article lu dans le texte), puis traduites dans les trois langues pour mesurer la recherche
cross-lingue question par question.

**Q : Pourquoi des questions hors sujet ?**
R : Pour mesurer si l'agent sait dire « je ne sais pas » au lieu d'inventer une réponse.

**Q : Quelle est la limite de votre évaluation ?**
R : 23 sujets seulement ; la vérification de l'information attendue se fait par mots-clés
et pas par un juge humain ; et le quota gratuit du LLM limite le nombre d'essais.

**Q : Pourquoi votre méthode hybride n'est-elle pas la meilleure ?**
R : Pour les questions anglaises, BM25 ne trouve que les articles de la Convention 138, nos seuls textes
anglais : il ajoute du bruit, et RRF lui donne le même poids qu'au modèle multilingue. L'hybride reste le
meilleur pour classer en arabe (MRR 0,773). Une amélioration serait de pondérer BM25 selon la langue.