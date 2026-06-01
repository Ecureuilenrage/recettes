---
titre: Chantiers de recherche ouverts & points à vérifier
type: recherche
statut: v1
créé: 2026-06-01
tags: [recherche, a-verifier, benchmark, epicure, cooklang]
---

# Chantiers de recherche ouverts & points à vérifier

> Ce document liste ce qui reste à **confirmer de première main** (les agents de recherche ont
> renvoyé des détails plausibles mais non vérifiés) et les **protocoles** de R&D propres à
> l'ambition « exploratoire ». Traiter les `[À VÉRIFIER]` **avant** de coder une valeur en dur.

## A. Points `[À VÉRIFIER]` (Phase 0)

| # | Sujet | Statut | Détail |
|---|---|---|---|
| 1 | **Format des embeddings Epicure** | ✅ **RÉSOLU (2026-06-01)** | Téléchargés dans `data/epicure/{cooc,core,chem}`. `embeddings.safetensors` (clé `embeddings`), matrice **(1790, 300) float32** ; `vocab.json` = dict `{ingredient: id}` (1790, ex. `olive_oil`, `black_pepper`) ; `itos.json` inverse. **Non normalisés sur disque** (normes ~1,16–3,78) → L2-normaliser avant cosine (confirmé par `config.json.normalization`). Loader : `app/epicure/loader.py`. |
| 2 | **Référence arXiv & archi démo** | ✅ **RÉSOLU** | `config.json` confirme arXiv **2605.22391** « Epicure: Navigating the Emergent Geometry of Food Ingredient Embeddings », architecture `metapath2vec_skipgram`, d_model 300, vocab 1790. |
| 3 | **État du parseur Cooklang Python** | ⏳ ouvert | parseur officiel actif ou archivé ? binding Rust (PyO3) dispo ? → décider templating maison vs binding. |
| 4 | **Valeurs de sécurité** | ⏳ ouvert | confirmer chaque valeur USDA/FSIS & ANSES (°C/°F, repos) avant de figer `safety-temperatures.json`. |
| 5 | **Astuce d'import `cook.md/<url>`** | ⏳ ouvert | tester la conversion URL → Cooklang sur 2–3 recettes italiennes. |

**Sanity-check cosine (validé)** : `tomato → onion/parsley/garlic/olive_oil` ; `basil → parsley/olive_oil/parmesan` ; `zucchini → eggplant/basil/garlic` — associations culinairement plausibles. Reproduire : `python -m app.epicure.loader`.

**Licence confirmée** : CC BY 4.0, © 2026 Jakub Radzikowski & Josef Chen (KAIKAKU.AI). Attribution requise.

## B. Décision `cooc` vs `core` — protocole de benchmark

**Objectif** : trancher quel modèle Epicure utiliser pour proposer/valider les associations.

**Méthode**
1. Constituer un **jeu de requêtes types** (ingrédients « héros ») avec des voisins « attendus »
   plausibles, par ex. :
   - `tomate` → basilic, ail, oignon, mozzarella, origan
   - `poulet` → citron, thym, ail, romarin
   - `courgette` → menthe, parmesan, ail, citron
   - `champignon` → ail, persil, thym, crème
2. Pour chaque modèle (`cooc`, `core`), calculer le **top-k voisins** (cosine).
3. Scorer le **recouvrement** avec les voisins attendus (precision@k) + une **inspection manuelle**
   de pertinence culinaire (le quantitatif seul ne suffit pas).
4. Évaluer aussi la **diversité/surprise** (core peut proposer des associations plus créatives via
   la parenté chimique).
5. **Décision écrite** : modèle par défaut + cas où l'autre est préférable (ex. mode « créatif »).

**Critère de choix** : pour un assistant culinaire « classique », privilégier les **associations
authentiques** (probablement `cooc`) ; garder `core` pour un éventuel mode « exploration ».

## C. Calibration des coefficients de scaling — boucle principale

**Objectif** : passer des coefficients « de départ » (issus de la recherche + physique) à des
valeurs **validées par l'usage**.

**Méthode**
1. Partir de `docs/scaling/table-scaling-sale.json` (valeurs initiales).
2. Sélectionner 10–15 recettes italiennes de référence (corpus `recipes/`).
3. Appliquer le moteur en ×2 et ÷2, comparer aux versions « ×N naïf ».
4. **Tester réellement** au moins 1–2 recettes en cuisine (×2 ou ÷2) et noter les écarts perçus
   (trop salé ? temps trop long ? œufs mal arrondis ?).
5. Ajuster les coefficients, versionner, consigner dans `notebooks/`.

**Coefficients de départ à challenger** (cf. table) : sel ~0,75 ; cayenne ~0,60 ; poivre ~0,70 ;
ail/gingembre ~0,80–0,85 ; temps `k^(2/3)` ; œuf ≈ 50 g.

## D. Sourcing & figeage de la base technique

- Finaliser `safety-temperatures.json` (autoritatif) — distinguer ce qui est **sécurité** (non
  négociable) de ce qui est **technique** (indicatif) et **préférence** (subjectif).
- Compléter `cuisine-italienne.json` (module pilote, 5 techniques signature) et vérifier que le
  **schéma** (`schema.md`) permet d'ajouter une 2ᵉ cuisine sans toucher au code.

## E. Synthèse des sources techniques (deep-dive)

**Epicure**
- Hugging Face : https://huggingface.co/Kaikaku/epicure-cooc (+ variantes `-core`, `-chem`)
- arXiv (à confirmer) : https://arxiv.org/abs/2605.22391
- Démo : https://epicure.kaikaku.ai
- MCP (à éviter, auto-hébergement inutile) : repo `KAIKAKU-AI/epicure-mcp`

**Cooklang**
- Spec : https://cooklang.org/docs/spec/ · Conventions : https://cooklang.org/docs/conventions/
- Parseurs : `cooklang/cooklang-rs` (Rust, référence), `cooklang/cooklang-ts` (TS),
  parseur Python `[À VÉRIFIER]` (possiblement archivé)
- Plugin Obsidian : `cooklang/cooklang-obsidian`
- Import : préfixer une URL par `cook.md/`

**Scaling non-linéaire**
- Fond.kitchen : https://fond.kitchen/guides/recipe-scaling-tips/
- Cooklang blog (scaling) : https://cooklang.org/blog/
- PastryCal : https://pastrycal.com/articles/scaling-recipes

## F. Décisions techniques (synthèse)

| Décision | Choix de départ | Raison |
|---|---|---|
| Modèle Epicure | `cooc` (benchmark vs `core`) | associations authentiques |
| Format embeddings | charger localement (format `[À VÉRIFIER]`) | 2–4 Mo, pas de MCP |
| Similarité | cosine = dot-product après L2-norm | standard |
| Parseur Cooklang | génération par templating + validation regex en v1 | rester simple ; éviter sur-investissement |
| Scaling | moteur custom déterministe | Cooklang natif est binaire (figé/linéaire) |
| LLM | Claude API, sortie contrainte | rédacteur sous garde-fous |
