# Étape 2 — La recherche hybride (expliquée simplement)

## 1. Le but en une phrase

Pour une question, trouver **les articles qui contiennent la réponse**, même si la question
et l'article ne sont **pas dans la même langue**.

> **Analogie :** pour trouver un livre, on cherche par **le titre** (mots exacts) et par
> **le sujet** (le sens). Haqqi fait les deux, puis combine les deux listes.

---

## 2. Le schéma

```
question ─┬─→ BM25     : mots exacts (après normalisation)   ─┐
          │                                                    ├─→ fusion RRF → articles classés
          └─→ vecteurs : sens, dans toutes les langues        ─┘
```

Fichiers : `tokenize.py` · `bm25.py` · `embeddings.py` · `hybrid.py` · `build.py`

---

## 3. Les mots (`tokenize.py`)

| Opération | Exemple |
|---|---|
| Normalisation (étape 1) | « Congés payés » → « conges payes » ; « الأَجْرُ » → « الاجر » |
| Mots vides retirés | « le », « de », « في », « the » |
| Racinisation légère | « salariés » → « salari » ; « والعمال » → « عمال » |

---

## 4. BM25 (`bm25.py`)

Un article est pertinent s'il contient les mots de la question, surtout les mots **rares**.

```
┌──────────────────────────────────────────────────────────────┐
│ score = Σ  IDF(mot) × tf × (k1 + 1)                           │
│        mot  ─────────────────────────────────────────         │
│             tf + k1 × (1 − b + b × longueur / moyenne)        │
│                                                               │
│ IDF(mot) = ln(1 + (N − n + 0,5) / (n + 0,5))    k1=1,5  b=0,75 │
└──────────────────────────────────────────────────────────────┘
```

Exemple chiffré (vraies valeurs du corpus) : N = 1 070 fiches. La racine « cong » (congé, congés)
est dans 33 fiches, « maternit » dans 2.
- IDF(congé) = ln(1 + 1037,5 / 33,5) ≈ **3,46**
- IDF(maternité) = ln(1 + 1068,5 / 2,5) ≈ **6,06** → le mot rare compte presque deux fois plus.

**Limite :** BM25 ne relie pas « âge minimum » à « moins de 16 ans », ni le français à l'arabe.

---

## 5. Les vecteurs (`embeddings.py`)

Le modèle **multilingual-e5-small** transforme un texte en 384 nombres.
Deux textes de même sens ont des vecteurs proches, **quelle que soit la langue**.

```
« âge minimum pour travailler »   ─┐
« السن الدنيا للتشغيل »            ├─→ vecteurs proches → cosinus élevé
« minimum age for employment »    ─┘
```

```
┌──────────────────────────────────────────────┐
│ cosinus(q, a) = q · a   (vecteurs normalisés) │
└──────────────────────────────────────────────┘
```

- Préfixes du modèle E5 : `query:` pour la question, `passage:` pour l'article.
- **Mises à jour** : les vecteurs sont gardés dans `data/index/vectors.npz` avec l'empreinte
  de chaque article. Au lancement suivant, seuls les articles **nouveaux ou modifiés** sont recalculés.
- Modèle « hash » : version simple sans téléchargement, pour les tests. Il ne comprend pas les traductions.

---

## 6. La fusion RRF (`hybrid.py`)

Les scores BM25 (0 à 30) et les cosinus (−1 à 1) ne sont pas sur la même échelle.
On combine donc les **rangs**, pas les scores.

```
┌───────────────────────────────────────────────┐
│ RRF(article) = Σ   1 / (60 + rang)            │
│              méthodes                          │
└───────────────────────────────────────────────┘
```

Exemple : un article 1er en BM25 et 3e en vecteurs → 1/61 + 1/63 = 0,0164 + 0,0159 = **0,0323**.
Un article 2e en vecteurs seulement → 1/62 = **0,0161**. Le premier passe devant.

**Filtres :** langue des documents, versions en vigueur seulement (par défaut), texte (`ct`, `c138`).

---

## 7. Commandes

```bash
python -m haqqi.retrieval.build                                  # calcule les vecteurs (1re fois : télécharge le modèle)
python -m haqqi.retrieval.build --search "âge minimum pour travailler"
python -m haqqi.retrieval.build --search "مناولة اليد العاملة" --mode bm25
```

---

## 8. Résumé

| Méthode | Fort pour | Faible pour |
|---|---|---|
| BM25 | mots exacts, numéros, termes juridiques | traduction, synonymes |
| Vecteurs | sens, autre langue | chiffres précis, mots rares |
| Hybride (RRF) | les deux | un peu plus lent |

---

## 9. Exemple réel et limite observée

Question : « Quel est l'âge minimum pour travailler ? » (mode hybride, 10 résultats)

| Place | Article | BM25 | Vecteurs | Remarque |
|---|---|---|---|---|
| 1 | art. 58 | #6 | #4 | bien placé par les deux → 1er (1/66 + 1/64 = 0,0308) |
| 3 | art. 55 | #20 | #2 | sauvé par les vecteurs (le sens) |
| 8 | art. 373 | #5 | #31 | bruit de BM25, que RRF fait descendre |
| 10 | Convention 138, art. 3 (anglais) | #7 | #28 | trouvé depuis une question en français |

**Limite :** l'article 53 (la règle des 16 ans) n'est pas dans les 10 premiers. Il dit
« les enfants de moins de 16 ans ne peuvent être employés » : il exprime l'âge minimum sous forme
d'interdiction, sans les mots « âge minimum » (présents seulement dans le titre de sa section).
Les vecteurs mesurent une ressemblance, ils ne raisonnent pas.

**Pistes :** indexer aussi le titre de la section dans BM25 ; un modèle de vecteurs plus grand
(e5-base, e5-large) ; laisser le LLM (étape 3) lire plusieurs articles et raisonner.

---

## 10. Questions possibles du jury → réponses types

**Q : Pourquoi une recherche hybride et pas seulement des vecteurs ?**
R : Les vecteurs comprennent le sens et les autres langues, mais ratent parfois un terme juridique
exact (« مناولة », « préavis »). BM25 fait l'inverse. RRF combine les deux classements sans avoir à
régler des poids.

**Q : Comment trouvez-vous un article arabe avec une question en anglais ?**
R : Le modèle e5 est multilingue : la question anglaise et l'article arabe de même sens ont des
vecteurs proches. BM25 seul ne peut pas le faire ; l'évaluation le montre (étape 6).

**Q : Comment gérez-vous les mises à jour de l'index ?**
R : Chaque vecteur est stocké avec l'empreinte SHA-256 de l'article. Un article inchangé reprend
son vecteur du cache ; seuls les articles nouveaux ou modifiés sont recalculés.

**Q : Pourquoi RRF avec k = 60 ?**
R : C'est la valeur de l'article original (Cormack et al., 2009). Elle réduit l'écart entre le 1er
et le 2e rang, ce qui rend la fusion robuste.

**Q : La recherche par le sens est-elle parfaite ?**
R : Non. Elle mesure une ressemblance entre textes, elle ne raisonne pas. Exemple réel : l'article 53
(« moins de 16 ans ne peuvent être employés ») n'est pas trouvé pour « âge minimum pour travailler ».
C'est pourquoi la recherche ramène plusieurs articles, et le LLM les lit pour raisonner.