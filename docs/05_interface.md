# Étape 5 — L'interface web (expliquée simplement)

## 1. Le but en une phrase

Une page de chat où l'on pose une question dans sa langue, et où l'on voit la réponse,
**ses sources**, et **les versions** de l'article.

---

## 2. Ce que montre la page (`src/haqqi/ui/app.py`)

```
┌──────────── barre latérale ────────────┐┌──────────────── conversation ─────────────────┐
│ Haqqi · حقّي                            ││ Question (sens d'écriture automatique)         │
│ 1 070 fiches · ar · fr · en             ││ Réponse                                        │
│ LLM : gemini… · Embeddings : e5         ││ Langue · chemin · LLM                          │
│ Recherche : hybrid / bm25 / vector      ││ Sources ▸ [ct:53] Code du travail, art. 53     │
│ Exemples (6 boutons)                    ││          ▸ texte · badge « en vigueur »         │
│ Avertissement juridique                 ││          ▸ ☐ Comparer les versions             │
└─────────────────────────────────────────┘└────────────────────────────────────────────────┘
```

---

## 3. Trois détails importants

| Détail | Solution |
|---|---|
| Arabe de droite à gauche | bloc `dir="rtl"` pour tout texte arabe |
| « 63-2 » affiché « 2-63 » dans un texte arabe | numéros isolés avec `<bdi dir="ltr">` |
| Chargement lent du modèle | `st.cache_resource` : chargé une seule fois |

---

## 4. Commande

```bash
streamlit run src/haqqi/ui/app.py
```

La page s'ouvre sur http://localhost:8501.

---

## 5. Exemples réels (e5 + Gemini `gemini-flash-lite-latest`)

| Question | Chemin | Résultat |
|---|---|---|
| « ما هي المدة القصوى لفترة التجربة؟ » | recherche hybride | réponse en arabe, de droite à gauche : 6 mois renouvelables une fois `[ct:6-3]`, 30 jours pour les ouvriers agricoles permanents `[ct:370]` ✅ |
| « Qu'est-ce qui a changé pour les CDD avec la loi 2025-9 ? » | comparaison de versions | avant : CDD ou CDI ; depuis 2025 : durée indéterminée `[ct:6-2]` (source arabe, réponse en français) ✅ |
| « How long is the annual paid leave? » | recherche hybride | l'article 113 n'est pas trouvé (l'article 404, sur les journalistes, l'est) ; le LLM répond qu'il n'a pas assez d'informations, sans inventer ⚠️ |
| « Combien de jours de congé annuel payé un salarié peut-il avoir ? » | recherche hybride | l'article 113 est trouvé : 15 jours (cas général), 30 jours (moins de 18 ans), 22 jours (18 à 20 ans) ✅ |

**Leçon :** même question, même article, même LLM : trouvé en français, pas en anglais. Le point
faible est la recherche de l'anglais vers le français ou l'arabe (le corpus n'a de textes anglais que
pour la Convention 138), pas la rédaction. Piste : traduire la question avant la recherche.

---

## 6. Questions possibles du jury → réponses types

**Q : Pourquoi Streamlit ?**
R : Tout le projet est en Python ; Streamlit donne une page de chat en peu de code, et se teste
sans navigateur (`AppTest`, voir `tests/test_ui.py`).

**Q : Comment l'utilisateur vérifie-t-il une réponse ?**
R : Chaque citation s'ouvre sur le texte exact de l'article, avec sa version, sa page et un badge
« en vigueur » ou « remplacé ». La case « Comparer les versions » affiche l'avant et l'après côte à côte.

**Q : Votre système marche-t-il en anglais ?**
R : Oui, mais c'est la langue la plus difficile : une question anglaise sur le Code doit trouver un
article français ou arabe. Exemple réel : « annual paid leave » ne trouve pas l'article 113, alors que
la même question en français le trouve. Dans ce cas, Haqqi ne ment pas : il dit qu'il n'a pas assez
d'informations. L'évaluation (étape 6) mesure cet écart par langue.