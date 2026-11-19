# Référence « sans modèle sémantique »

Résultats obtenus avec le modèle `hash-trigrams-512` (trigrammes de lettres, sans
téléchargement) et des réponses extractives (sans LLM).

Ils servent de point de comparaison : ils montrent ce que donne Haqqi SANS le modèle
multilingue. Les vrais résultats (modèle `intfloat/multilingual-e5-small` + LLM) sont
dans `results/` après la commande :

    python -m haqqi.eval.run --generation