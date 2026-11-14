# Étape 1 — Ingestion des documents (expliquée simplement)

## 1. Le but en une phrase

Transformer de gros PDF de lois en **petites fiches propres**, une fiche par article,
avec une étiquette sur chaque fiche.

> **Analogie :** un bibliothécaire découpe un gros livre de lois en fiches.
> Sur chaque fiche il écrit : n° d'article, langue, version, page.
> Plus tard, quand quelqu'un pose une question, on cherche dans les fiches, pas dans le livre entier.

---

## 2. Le schéma

```
PDF / TXT
   → (1) extraction du texte, page par page
   → (2) nettoyage
   → (3) découpage en articles
   → (4) ajout des métadonnées (étiquettes)
   → (5) comparaison avec ce qui existe déjà (mises à jour)
   → articles.jsonl
```

---

## 3. Extraction (`pdf_extract.py`)

- On lit chaque page du PDF avec **PyMuPDF**.
- On enlève les **numéros de page** (« - 12 - »).
- On enlève les **en-têtes répétés** : une ligne présente sur au moins 30 % des pages
  (ex. « مجلة الشغل » en haut de chaque page).
- Si un PDF donne presque pas de texte → c'est un **scan** → avertissement « OCR nécessaire ».

---

## 4. Nettoyage (`text_utils.py`)

| Problème | Exemple avant | Après |
|---|---|---|
| Chiffres arabes-indiens | `الفصل ٢٣٤` | `الفصل 234` |
| Lettres « de présentation » du PDF | `ﻻ` (caractère U+FEFB) | `لا` |
| Nombre collé à un mot | `27قانون` | `27 قانون` |
| Mot français coupé en fin de ligne | `travail-⏎leurs` | `travailleurs` |
| Caractères invisibles (RLM, LRM…) | `الفصل` + U+200F (invisible) + ` 6` | `الفصل 6` |

Deux versions du texte sont gardées :

```
text       → pour l'AFFICHAGE et les citations (texte propre)
text_norm  → pour la RECHERCHE (sans voyelles arabes, sans accents, minuscules)
```

Exemple : `الأَجْرُ` et `الاجر` donnent le même `text_norm` → la recherche les trouve tous les deux.

---

## 5. Découpage en articles (`splitter.py`)

### Règle

```
┌──────────────────────────────────────────────┐
│  1 article de loi  =  1 morceau (chunk)      │
└──────────────────────────────────────────────┘
```

Pourquoi ?
- Un article est une **unité de sens complète**.
- C'est ce qu'on **cite** : « Code du travail, art. 6-4 ».
- C'est aussi la **bonne réponse** du benchmark → l'évaluation devient simple.

### Titres reconnus

| Langue | Exemples reconnus | Numéro obtenu |
|---|---|---|
| Français | `Article premier. - …` | `1` |
| Français | `Article 6-4 (nouveau). - …` | `6-4` (marqué nouveau) |
| Français | `Art. 234 bis : …` | `234bis` |
| Arabe | `الفصل الأول ـ …` | `1` |
| Arabe | `الفصل 234 مكرر ـ …` | `234bis` |
| Arabe (PDF inversé) | `1الفصل` | `1` |

`234 bis` et `234 مكرر` donnent **la même clé** `ct:234bis` → on peut aligner l'arabe et le français.

### Le piège : les références

```
… les sanctions prévues à
Article 234 du présent code …     ← ce n'est PAS un nouvel article !
```

Règle : après le numéro, il faut un **séparateur** (`.` `-` `:` `ـ`) ou la **fin de la ligne**.
Ici, après « 234 » vient « du » → ce n'est pas un titre.

### Les sections

Les lignes `LIVRE PREMIER`, `TITRE II`, `الباب الأول`… ne sont pas des articles.
Elles sont gardées comme étiquette `section` de chaque article :
`LIVRE PREMIER — DISPOSITIONS GÉNÉRALES > TITRE II — DES SANCTIONS`

### La loi de promulgation

Le PDF commence par une petite loi (1966) avec ses propres articles 1 à 4,
puis le code recommence à l'article 1.

```
Numérotation qui revient à 1  →  nouvelle « partie »
Partie avec le plus d'articles →  le code lui-même (clé ct:…)
Autres parties                 →  ct@partie1:…
```

---

## 6. Les versions (avant / après la loi 2025-9)

La loi 2025-9 contient de **nouvelles versions** d'articles du code, marquées « (nouveau) » / « (جديد) ».
Elles reçoivent la **même clé** que l'article d'origine.

Exemple réel pour `ct:6-4` (contrats à durée déterminée) :

| Langue | Version | Date | Historique | En vigueur ? |
|---|---|---|---|---|
| ar | edition_2004 | 2004 | ajouté par la loi n° 62 de 1996 | ❌ remplacé par loi_2025_9 |
| fr | revision_1996 | 1996-07-15 | — | ❌ remplacé par loi_2025_9 (texte arabe) |
| ar | loi_2025_9 | 2025-05-21 | (جديد) | ✅ |

Règle : pour une même clé et une même langue, **la date la plus récente est en vigueur**.

La loi 2025-9 n'existe ici qu'en arabe. Elle remplace pourtant aussi le texte français :
un article français plus ancien qu'une loi modificative (dans une autre langue) est marqué
remplacé, avec `replaced_lang = "ar"`.

Deux cas particuliers :
- **article abrogé** (« ألغي بالقانون … ») → plus en vigueur, `replaced_by = "abrogé"` ;
- **un seul paragraphe remplacé** (« الفصل 94-2 الفقرة الأولى (جديدة) ») → l'ancien article
  ET le nouveau paragraphe restent en vigueur.

---

## 7. Les mises à jour

Chaque article a une **empreinte** (hash) calculée sur son texte.

```
Fichier PDF identique         → on ne refait rien (statut « unchanged »)
Fichier PDF modifié           → on compare article par article :
    nouvel id                 → ajouté
    même id, empreinte ≠      → modifié
    id disparu                → supprimé
```

Exemple chiffré : on corrige l'article 30 et on supprime l'article 234 bis
→ rapport : `ajoutés 0 · modifiés 1 · supprimés 1`.

---

## 8. Résumé

| Étape | Fichier | Résultat |
|---|---|---|
| Extraction | `pdf_extract.py` | texte par page, sans en-têtes |
| Nettoyage | `text_utils.py` | `text` (affichage) + `text_norm` (recherche) |
| Découpage | `splitter.py` | 1 article = 1 morceau, + section |
| Métadonnées | `models.py` | id, clé, langue, version, page, hash |
| Orchestration | `pipeline.py` | `articles.jsonl` + `manifest.json` |
| Vérification | `show.py` | affichage d'un article dans toutes ses versions |

---

## 9. Les vrais PDF : problèmes rencontrés et solutions

Les tests sur les vrais textes (Code du travail 2004 et JORT 2025) ont montré 8 problèmes en arabe.

| # | Problème réel | Exemple | Solution |
|---|---|---|---|
| 1 | Mot coupé en deux lignes par le PDF | `الف` ⏎ `صل 4` | recoller les morceaux à la même hauteur |
| 2 | Segments inversés (JORT) | `نة␣ة غير معي␣يعتبر…لمد` | couper sur le caractère privé U+E825 et inverser |
| 3 | Tatweel de justification | `سببـــا لفســـخ` | supprimer `ـ` entre deux lettres |
| 4 | Note de modification sur 2 lignes | `الفصل 236) نقّح … لسنة` ⏎ `1994 …(` | recoller tant que la parenthèse n'est pas fermée |
| 5 | Plusieurs articles abrogés d'un coup | `الفصول 325 إلى 332) ألغيت …(` | créer une fiche « abrogé » par article |
| 6 | Le « : » est dans la parenthèse | `الفصل 28) جديد: (تمنع …` | accepter un titre sans séparateur après `:(` |
| 7 | Référence en début de ligne | `… اقتضاه` ⏎ `الفصل 359.` | « الفصل N. » sans texte = fin de phrase, pas un titre |
| 8 | Chadda dans le suffixe | `الفصل 14 مكرّر` | regex qui tolère les voyelles |

L'édition française (codification révisée au 15 juillet 1996) a montré 5 autres formats.

| # | Format réel | Exemple | Solution |
|---|---|---|---|
| 9 | Pas d'espace après « Art. » | `Art.123 : …` | espace facultatif |
| 10 | Pas de point après « Art » | `Art 430 - …` | point facultatif |
| 11 | Pas de séparateur | `Art. 168 Les membres …` | accepté seulement si c'est le numéro **attendu** (167 → 168) et suivi d'une majuscule |
| 12 | Articles abrogés entre crochets | `[Art. 9 - … ]` | crochets retirés, statut « abrogé » |
| 13 | Coquilles | `Art 14. quater`, `Art. 14 quinter` | point toléré, « quinter » = « quinquies » |

Le document anglais (Convention OIT n° 138) utilise « Article 1 », « Article 2 »… :
le même découpage marche sans changement.

Contrôle final :

```
Arabe    : numéros 1 à 446 → 100 % trouvés, 0 doublon, 516 fiches
Français : numéros 1 à 446 → 100 % trouvés, 0 doublon, 512 fiches
Anglais  : Convention n° 138 → articles 1 à 18, 18 fiches
Alignement : 512 / 512 articles français ont leur équivalent arabe (même clé)
Abrogés : 34 en arabe, 34 en français
```

> **À retenir pour l'oral :** on ne fait pas confiance à l'extraction PDF.
> On la **mesure** (numéros manquants, doublons, titres oubliés), puis on corrige cas par cas.
> Chaque cas réel corrigé a son test dans `tests/test_real_formats.py`.

---

## 10. Questions possibles du jury → réponses types

**Q : Pourquoi ne pas découper tous les 500 mots, comme dans beaucoup de RAG ?**
R : Parce qu'un découpage fixe coupe un article en deux ou mélange deux articles.
Un article est l'unité de sens et l'unité de citation. En plus, la bonne réponse du benchmark
est un numéro d'article, ce qui rend Recall@k et MRR faciles à calculer.

**Q : Comment gérez-vous les mises à jour des documents ?**
R : Chaque fichier et chaque article ont une empreinte SHA-256. Un fichier inchangé est ignoré.
Pour un fichier modifié, on compare les empreintes article par article et on compte
les ajouts, modifications et suppressions.

**Q : Comment savez-vous quelle version d'un article est en vigueur ?**
R : La loi 2025-9 donne une nouvelle version avec la même clé (`ct:6-4`).
Pour chaque clé et chaque langue, la version la plus récente est marquée `is_current = true`,
les autres `replaced_by = loi_2025_9`.

**Q : La loi 2025-9 n'existe qu'en arabe. Comment répondez-vous en français ?**
R : Les articles ont la même clé dans les deux langues. La nouvelle version arabe de `ct:6-4`
marque aussi l'ancien texte français comme remplacé. L'assistant retrouve le texte arabe en vigueur
et répond en français : c'est la recherche cross-lingue du projet 6.

**Q : Pourquoi une convention de l'OIT en anglais ?**
R : Le projet 6 demande des documents en arabe, en français et en anglais. Le Code du travail
n'a pas de version officielle en anglais. La Convention n° 138 sur l'âge minimum a été ratifiée
par la Tunisie le 19 octobre 1995 et traite du même sujet que l'article 53 du Code
(pas d'emploi avant 16 ans). Une question comme « Quel est l'âge minimum pour travailler ? »
trouve alors des réponses dans les trois langues.

**Q : Pourquoi normaliser l'arabe ?**
R : Le même mot peut s'écrire avec ou sans voyelles, avec `أ` ou `ا`, avec `ة` ou `ه`.
Sans normalisation, la recherche par mots-clés rate ces variantes.
On garde quand même le texte original pour l'affichage et les citations.v