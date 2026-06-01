---
titre: Backlog — épics, stories, critères d'acceptation
type: backlog
statut: v1
créé: 2026-06-01
tags: [backlog, epics, stories]
---

# Backlog

> Découpage actionnable. Convention : `[ ]` à faire, `[~]` en cours, `[x]` fait.
> Priorités : **P0** (socle/cœur), **P1** (v1 fonctionnelle), **P2** (polish/extension).

## Phase 0 — Socle & vérifications (P0)

- [x] **S0.1** Télécharger les embeddings Epicure (HF) et **inspecter le vrai format**. _Fait
  (2026-06-01)_ : `data/epicure/{cooc,core,chem}`, matrice (1790, 300) float32. Lève `[À VÉRIFIER] #1`+`#2`.
- [x] **S0.2** Charger en Python + cosine top-k. _Fait_ : `app/epicure/loader.py` ;
  `neighbors("tomato")` → onion/parsley/garlic/olive_oil (plausible).
- [ ] **S0.3** Trancher le parseur Cooklang (templating maison vs binding). _AC :_ décision écrite
  dans `recherche-ouverte.md`. Lève `[À VÉRIFIER] #3`.
- [ ] **S0.4** Valider qu'un `.cook` minimal s'ouvre dans Obsidian (plugin Cooklang). _AC :_ capture.
- [ ] **S0.5** Confirmer les valeurs de sécurité contre USDA/ANSES et figer `safety-temperatures.json`.
  _AC :_ chaque ligne a une source vérifiée. Lève `[À VÉRIFIER] #4`.
- [ ] **S0.6** Constituer un corpus de 10–15 recettes italiennes via `cook.md/<url>` dans `recipes/`.

## Épic A — Couche Epicure (associations) — P0/P1

- [ ] **A1** Loader embeddings local + cosine top-k. _AC :_ API `neighbors(name, k)` testée.
- [ ] **A2** Benchmark `cooc` vs `core` (protocole `recherche-ouverte.md` §B) + note de décision.
  _AC :_ tableau precision@k + choix justifié.
- [ ] **A3** Filtrage des voisins par cuisine/contraintes. _AC :_ les voisins hors cuisine/contraintes
  sont écartés ; visible dans le panneau debug.

## Épic B — Base technique (couche 2) — P0/P1

- [x] **B1** `safety-temperatures.json` (rédigé ; valeurs à valider en S0.5).
- [x] **B2** `schema.md` + `cuisine-italienne.json` (5 techniques).
- [ ] **B3** Loader knowledge + API `techniques_for(cuisine, ingredient, constraints)`. _AC :_ renvoie
  les techniques applicables, exclut celles à ustensile interdit.
- [ ] **B4** Mapping contraintes matérielles → `#cookware` interdits. _AC :_ « pas de four » exclut la
  technique `searing_braising` (ou propose une alternative).

## Épic C — Moteur de scaling (couche 3, **cœur**) — P0

- [ ] **C1** Types linéaire / sous-linéaire / figé + lecture de `table-scaling-sale.json`. _AC :_
  `scale("sel", 1, "c.à.c", 2.0)` < `2` (sous-linéaire) ; température figée.
- [ ] **C2** Scaling discret des œufs (entiers + reste volume/poids, arrondi bas). _AC :_
  `scale_eggs(3, 2.0)` propose 5 (pas 6) avec note ; fractions → volume.
- [ ] **C3** Scaling géométrique du temps `k^(2/3)` + raisonnement profondeur/surface. _AC :_
  20 min ×2 → ~32 min (pas 40) ; note si changement de contenant suggéré.
- [ ] **C4** Flags de non-linéarité + réserve 10 % des assaisonnements. _AC :_ une préparation
  sensible reçoit la note « ne se double pas proprement au-delà de ~1,5–2× ».
- [ ] **C5** Tests unitaires déterministes (×2, ÷2, ×4) + notebook de calibration. _AC :_ `pytest`
  vert ; notebook compare moteur vs ×N naïf sur le corpus.

## Épic D — Générateur LLM (couche 4) — P1

- [ ] **D1** Prompt contraint (associations Epicure + techniques/temp de la base) + intégration
  Claude API. _AC :_ génère une recette cohérente autour d'un héros.
- [ ] **D2** Garde-fou « jamais de temp/technique hors base » + tests anti-hallucination. _AC :_ test
  qui asserte qu'aucune valeur générée n'est hors `cuisine-italienne.json` / `safety-temperatures.json`.
- [ ] **D3** Émission `.cook` (marqueurs `@`/`#`/`~`, `=`, notes `--`) + validation. _AC :_ fichier
  `.cook` valide produit.
- [ ] **D4** Rendu Markdown lisible. _AC :_ aperçu humain propre à côté du `.cook`.

## Épic E — App web + R&D — P1/P2

- [ ] **E1** FastAPI + endpoint de génération. _AC :_ `POST /generate` renvoie recette + debug.
- [ ] **E2** UI minimale (formulaire héros/cuisine/contraintes/portions + rendu + panneau debug).
  _AC :_ utilisable dans le navigateur en local.
- [ ] **E3** Jeu de validation scaling (corpus + comparaison). _AC :_ résultats consignés.
- [ ] **E4** README portfolio + attribution Epicure (CC BY 4.0). _AC :_ how-to-run + crédits.

## Épic F — Extension & polish — P2

- [ ] **F1** Ajouter une 2ᵉ cuisine (`cuisine-<nom>.json`) **sans toucher au code** → valide la
  modularité. _AC :_ la nouvelle cuisine fonctionne via le loader générique.
- [ ] **F2** Affiner les coefficients de scaling via tests réels (×2/÷2). _AC :_ table versionnée + notes.
- [ ] **F3** Documenter le différé pâtisserie (chimie) sans l'implémenter.

## Définition de « terminé » (DoD)

- Code testé (unitaire pour le cœur déterministe), pas de température/technique hors base, `.cook`
  valide ouvrable dans Obsidian, attribution Epicure présente, README à jour.
