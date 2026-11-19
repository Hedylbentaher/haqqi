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
python -m haqqi.eval.run                        # recherche : bm25, vector, hybrid_fixed, hybrid
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

**Pistes d'amélioration :** pondérer BM25 selon la langue de la question (réalisé : section 9) ;
traduire la question en arabe avant la recherche ; un modèle d'embeddings plus grand (e5-base, e5-large).

---

## 8. Résultats des réponses avec Gemini (étape 6.4)

Commande : `python -m haqqi.eval.run --generation` · LLM `gemini-flash-lite-latest` ·
1,38 seconde par question · 0 réponse « LLM indisponible ».

| Mesure (69 questions avec réponse) | sans LLM | Gemini |
|---|---|---|
| Au moins une citation correcte | 46,4 % | **68,1 %** |
| Précision des citations | 24,6 % | **57,5 %** |
| Information attendue présente | 50,0 % | **68,2 %** |
| Réponse dans la langue de la question | 89,7 % | **100 %** |
| Questions hors sujet : refus (9 questions) | 0 % | **100 %** |

| Langue | Citation correcte | Information présente | Bonne langue | Sans citation (sur 23) |
|---|---|---|---|---|
| arabe | 91,3 % | 86,4 % | 100 % | 1 |
| français | 69,6 % | 77,3 % | 100 % | 6 |
| anglais | 43,5 % | 40,9 % | 100 % | 12 |

| Les 69 réponses | Nombre |
|---|---|
| Au moins un bon article cité | 47 |
| Seulement de mauvais articles (q01-ar, q02-en, q11-fr) | 3 |
| Aucun article cité : l'agent dit qu'il n'a pas trouvé | 19 |

**Ce qu'on en tire :**
1. **Gemini améliore toutes les mesures** : citation correcte +21,7 points, information présente
   +18,2 points, bonne langue 100 %, et les 9 questions hors sujet sont refusées.
2. **Quand l'agent cite, il a presque toujours raison** : un bon article dans 47 réponses sur 50 (94 %).
   La précision (57,5 %) compte 0 pour une réponse sans citation ; sur les 50 réponses qui citent,
   environ 79 % des articles cités sont bons.
3. **L'agent préfère s'abstenir plutôt qu'inventer** : 19 réponses sans citation, dont 12 en anglais.
   La limite vient surtout de la recherche (Recall@5 = 50 % en anglais), pas du LLM : la vérification
   des citations empêche de citer un article absent des résultats.
4. **Par type de question** : citation correcte 80 % pour les questions factuelles (36/45), 55,6 % pour
   les questions Code + Convention (5/9), 40 % pour les questions de version (6/15).

---

## 9. Amélioration : BM25 selon la langue de la question (étape 6.5)

**Problème (section 7, conclusion 3)** : en anglais, BM25 ne trouve que les 18 fiches de la
Convention 138 (1,7 % du corpus) et les fait remonter dans la fusion.

**Règle** (`bm25_useful()` dans `retrieval/hybrid.py`) :
```
part des textes cherchés dans la langue de la question ≥ 10 % ?
   oui (arabe 50 %, français 48 %) → BM25 + vecteurs, comme avant
   non (anglais 2 %)               → vecteurs seuls
```
Le mode `hybrid_fixed` garde l'ancienne fusion pour comparer.

**Prédiction puis mesure** : rien ne change en arabe et en français, et en anglais le nouvel hybride
donne le classement des vecteurs. L'effet a donc été calculé à l'avance avec `retrieval_details.jsonl`,
puis mesuré : chiffres identiques.

| Recherche | hybride fixe (avant) | hybride selon la langue (après) |
|---|---|---|
| Recall@1 | 39,1 % | **43,5 %** |
| Recall@3 | **62,3 %** | 61,6 % |
| Recall@5 | 65,2 % | **67,4 %** |
| Recall@10 | 71,0 % | **73,9 %** |
| MRR | 0,549 | **0,576** |
| Recall@5 en anglais | 43,5 % | **50,0 %** |
| Recall@5, Code + Convention | **44,4 %** | 38,9 % |

| Réponses (Gemini) | avant | après |
|---|---|---|
| Citation correcte | 68,1 % | **72,5 %** |
| Information présente | 68,2 % | **75,8 %** |
| Citation correcte en anglais | 43,5 % | **52,2 %** |
| Bon article / mauvais / aucun (sur 69) | 47 / 3 / 19 | 50 / 8 / 11 |

**Ce qu'on en tire :**
1. L'hybride a maintenant le meilleur Recall@1 et le meilleur MRR des quatre méthodes.
2. Le gain anglais suit la recherche : les 3 questions que la recherche trouve désormais (q07-en,
   q09-en, q23-en) ont une citation correcte ; la question perdue (q08-en) a une mauvaise citation.
3. **Le LLM varie** : en arabe et en français, les fiches trouvées sont identiques, mais 5 réponses ont
   changé entre les deux exécutions. Un écart de 1 ou 2 questions par langue n'est pas significatif.
4. Contreparties : une question Code + Convention en anglais perd l'article de la C138, et l'agent
   s'abstient moins (19 → 11) mais se trompe plus (3 → 8).

---

## 10. Questions possibles du jury → réponses types

**Q : Pourquoi 78 questions et pas des questions générées automatiquement ?**
R : Le cours demande au moins 50 questions. Nous les avons écrites et vérifiées à la main
(bon article lu dans le texte), puis traduites dans les trois langues pour mesurer la recherche
cross-lingue question par question.

**Q : Pourquoi des questions hors sujet ?**
R : Pour mesurer si l'agent sait dire « je ne sais pas » au lieu d'inventer une réponse.

**Q : Quelle est la limite de votre évaluation ?**
R : 23 sujets seulement ; la vérification de l'information attendue se fait par mots-clés
et pas par un juge humain ; le quota gratuit du LLM limite le nombre d'essais (deux exécutions),
alors que le LLM varie d'une exécution à l'autre.

**Q : Pourquoi l'hybride était-il d'abord moins bon que e5 seul ?**
R : Pour les questions anglaises, BM25 ne trouve que les articles de la Convention 138, nos seuls textes
anglais : il ajoute du bruit, et RRF lui donne le même poids qu'au modèle multilingue. L'hybride reste le
meilleur pour classer en arabe (MRR 0,773). Nous avons donc ajouté une règle de langue (section 9) :
l'hybride passe à 67,4 % et obtient le meilleur MRR (0,576).

**Q : Comment savez-vous que le gain vient de la règle et pas du hasard ?**
R : La recherche est déterministe : nous avons calculé l'effet avant le test, puis la mesure a donné
exactement les mêmes chiffres. Pour les réponses, c'est moins sûr : le LLM varie (5 réponses ont changé
en arabe et en français avec les mêmes fiches). Il faudrait plusieurs exécutions pour le confirmer.

**Q : 72,5 % de citations correctes, n'est-ce pas faible ?**
R : Sur 69 réponses, 50 citent un bon article, 11 disent « je n'ai pas trouvé » au lieu d'inventer,
et 8 citent un mauvais article. Quand l'agent cite, il a raison 50 fois sur 58 (86 %). Pour un assistant
juridique, une abstention est moins grave qu'une mauvaise citation : c'est la mesure à surveiller.

**Q : Pourquoi l'anglais reste-t-il le point faible ?**
R : Le seul texte anglais est la Convention 138 ; tout le Code est en arabe et en français. Une question
anglaise dépend donc entièrement du modèle multilingue, qui ne trouve le bon article dans les
5 premiers résultats qu'une fois sur deux (Recall@5 = 50 %).