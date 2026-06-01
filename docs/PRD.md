---
titre: PRD — Générateur/scaler de recettes Epicure
type: prd
statut: v1-cadrage
version: 0.2
créé: 2026-06-01
maj: 2026-06-01 (corrections P0 validation : FR3 testable, FR5/FR6 scindées, NFR chiffrées + Performance/Robustesse)
tags: [projet, cuisine, ia, epicure, cooklang, scaling]
---

# PRD — Générateur/scaler de recettes « Epicure »

> Document de référence produit. Pour le contexte stratégique et le verdict d'utilité, voir
> [`etude-marche.md`](./etude-marche.md). Pour les chantiers ouverts et les points `[À VÉRIFIER]`,
> voir [`recherche-ouverte.md`](./recherche-ouverte.md).

## 0. En une phrase

Un **scaler de recettes honnête** : à partir d'un ingrédient « héros », d'une cuisine et de
contraintes, l'outil génère une recette salée cohérente en **Cooklang**, dont la **mise à
l'échelle est non-linéaire et crédible** (par ingrédient), et dont **aucune température ni
technique n'est inventée** (grounded sécurité alimentaire).

## 1. Problème & intention

Les générateurs de recettes IA grand public souffrent de deux défauts :
1. **Scaling naïf** : doubler une recette = « tout ×N », ce qui sur-sale, sur-épice, et ignore que
   le temps de cuisson n'est pas linéaire. Aucun outil grand public ne fait un scaling fin par
   ingrédient.
2. **Hallucinations dangereuses** : des recettes IA ont recommandé des températures de cuisson
   non sûres (cas documentés). Rien ne garantit la sécurité alimentaire.

**Intention** : construire un projet **perso / playground / portfolio** (pas une app payante) qui
adresse précisément ces deux points, en s'appuyant sur :
- **Epicure** (embeddings d'associations d'ingrédients, KAIKAKU.AI, CC BY 4.0) pour proposer et
  **valider** les associations ;
- une **base technique grounded** (températures de sécurité USDA/ANSES + techniques sourcées) ;
- un **moteur de scaling déterministe** non-linéaire (la pièce maîtresse) ;
- un **LLM (Claude API)** réduit au rôle de **rédacteur sous contraintes**.

## 2. Objectifs & non-objectifs

**Objectifs (v1)**
- Prouver la valeur du moteur de scaling sur de la cuisine **italienne salée**.
- Ne jamais émettre une température/technique hors base (garde-fou testé).
- Sortie **Cooklang** (`.cook`) réutilisable dans Obsidian.
- Petite **app web locale** (backend Python + UI minimale).
- Rester **exploratoire** : benchmarks `cooc` vs `core`, calibration des coefficients par tests réels.

**Non-objectifs (v1)**
- Pas de pâtisserie (chimie → différée, seulement documentée).
- Pas de multi-cuisines (1 seule cuisine en v1 ; la 2ᵉ servira à valider la modularité).
- Pas de comptes / auth / paiement / déploiement cloud / mobile.
- Pas de calcul nutritionnel.
- Pas d'objectif de croissance ou de monétisation.

## 3. Utilisateur & cas d'usage

**Utilisateur** : une personne (l'auteur), curieuse/experte de cuisine, à l'aise avec Obsidian et
le markdown.

**Parcours principal**
1. L'utilisateur saisit : ingrédient **héros** (ex. « courgette »), **cuisine** (italienne),
   **contraintes** (régime, matériel interdit comme « pas de four », ingrédient à mettre en avant),
   **nombre de portions** cible.
2. L'outil propose des **associations** compatibles (Epicure) filtrées par la cuisine/les contraintes.
3. Le LLM rédige une recette **contrainte** (associations validées + techniques/temp de la base).
4. Le **moteur de scaling** ajuste les quantités au nombre de portions (par ingrédient).
5. L'outil produit un fichier **`.cook`** + un **rendu Markdown** lisible + un **panneau debug**
   expliquant le raisonnement de scaling et les voisins Epicure retenus/rejetés.

## 4. Exigences fonctionnelles

| ID | Exigence | Priorité |
|---|---|---|
| FR1 | Saisir héros + cuisine + contraintes (régime, matériel interdit, ingrédient mis en avant) + portions cible. | Must |
| FR2 | Proposer N associations compatibles via Epicure (similarité cosinus), filtrées par cuisine/contraintes. | Must |
| FR3 | Le LLM rédige une recette **dont 100 % des ingrédients clés figurent parmi les associations validées par Epicure** et **dont 100 % des températures / temps / techniques proviennent de la base** ; toute valeur hors base fait **échouer la génération** (assertion testable). | Must |
| FR4 | Mapper les contraintes matérielles (« pas de four/blender ») → ustensiles `#cookware` interdits ; le générateur ne peut pas les utiliser. | Must |
| FR5a | Appliquer, **par ingrédient**, le type de scaling déclaré (linéaire / sous-linéaire / discret / géométrique / figé) selon `table-scaling-sale.json`. | Must |
| FR5b | Émettre les verrous `=` pour les ingrédients figés ou non linéaires (température, assaisonnement verrouillé…). | Must |
| FR5c | Émettre une note `--` (lisible par le moteur) pour chaque ingrédient non-linéaire ou changement de contenant suggéré. | Must |
| FR6a | Produire un fichier `.cook` **qui passe la validation syntaxique Cooklang** (marqueurs `@`/`#`/`~`, `=`, notes `--`). | Must |
| FR6b | Produire un rendu Markdown **contenant au minimum : titre, portions, liste d'ingrédients et étapes numérotées**. | Must |
| FR7 | Panneau « debug » : type de scaling par ingrédient + raisonnement, + voisins Epicure retenus/rejetés. | Should (exploratoire) |
| FR8 | Choisir le modèle Epicure (`cooc`/`core`) et exposer la comparaison. | Could (R&D) |

## 5. Exigences non-fonctionnelles

- **Sécurité alimentaire** : zéro température critique devinée. Toute valeur sort de la base
  sourcée. Tests dédiés (cf. garde-fou). _Critère : 0 valeur hors base sur le jeu de tests._
- **Déterminisme** : le moteur de scaling est pur. _Critère : pour une même entrée, la sortie du
  module scaling est **identique bit-à-bit** sur N exécutions répétées (test automatisé)._ Le LLM
  est la seule partie non déterministe.
- **Simplicité** : tourne en local. _Critères : **≤ 12 dépendances runtime** (hors dev/test) ;
  **démarrage via une seule commande documentée** ; **aucun service externe** hors l'API LLM._
- **Performance** : _génération de bout en bout **< 3 s hors latence de l'API LLM** (chargement
  embeddings + cosine + scaling + émission `.cook`) sur une machine de dev standard._
- **Robustesse** : comportement déterministe en cas d'erreur. _Critères : si l'**API LLM échoue**,
  renvoyer une erreur explicite **sans recette partielle** ; si le **héros est absent d'Epicure**,
  message clair + suggestion ; si **aucune association ne survit au filtrage**, message clair (pas
  de génération silencieuse)._
- **Coût** : appel LLM ~0,005–0,01 $/recette — non bloquant.
- **Licence** : attribution Epicure (CC BY 4.0) présente dans le repo. _Critère : fichier
  `LICENSE`/`NOTICE` mentionnant « Epicure — CC BY 4.0 » présent à la racine (cf. E4)._

## 6. Architecture (4 couches)

```
Navigateur (UI minimale : formulaire + recette + panneau debug)
        │  HTTP (localhost)
        ▼
Backend Python — FastAPI
 ├── Couche 1 · Associations   → app/epicure/    (embeddings locaux, cosine, cooc/core)
 ├── Couche 2 · Base technique  → app/knowledge/  (charge les JSON de docs/base-technique)
 ├── Couche 3 · Scaling         → app/scaling/    (cœur déterministe, testé)
 └── Couche 4 · Générateur LLM  → app/generator/  (Claude API, sortie .cook contrainte)
        ▼
Sortie : .cook (Cooklang) + rendu Markdown
```

Voir le détail des décisions techniques (`[À VÉRIFIER]` inclus) dans le plan et `recherche-ouverte.md`.

## 7. Données

- **Embeddings Epicure** (`data/epicure/`) : ~1 790 ingrédients, 300 dims, ~2 Mo, CC BY 4.0.
  Format à confirmer (`[À VÉRIFIER]`). Cosine = dot-product après L2-normalisation.
- **Base technique** (`docs/base-technique/`) : `safety-temperatures.json` (sécurité, autoritatif),
  `cuisine-italienne.json` (module pilote, 5 techniques).
- **Table de scaling** (`docs/scaling/table-scaling-sale.json`) : multiplicateurs salés + flags.
- **Corpus de test** (`recipes/`) : 10–15 recettes italiennes salées importées via `cook.md/<url>`.

## 8. Critères de succès (playground)

- Le moteur de scaling produit, sur le corpus de référence, des quantités jugées **plus justes**
  qu'un ×N naïf (évaluation manuelle + ≥1–2 tests cuisine réels ×2/÷2).
- Le **benchmark `cooc` vs `core`** est tranché, avec justification écrite.
- **Aucune** recette générée ne contient une température/technique hors base (test automatisé).
- Une recette `.cook` **s'ouvre proprement dans Obsidian** (plugin Cooklang).

## 9. Hypothèses & dépendances

- Les embeddings Epicure sont publics et chargeables localement (à confirmer en Phase 0).
- Une clé API Claude est disponible (variable d'environnement).
- Cooklang reste un format texte simple à générer/valider sans parseur lourd.

## 10. Risques (résumé — détail dans le plan §10)

- Hallucination temp/technique → couche 2 (le LLM **choisit**, n'invente pas) + tests.
- Sécurité alimentaire → valeurs sourcées et figées, jamais devinées.
- Sur-ingénierie → rester « simple » ; le cœur est scaling + grounding, pas l'UI.
- Données de recherche non vérifiées → traiter les `[À VÉRIFIER]` avant de coder en dur.

## 11. Phasage (résumé)

Phase 0 (socle & vérifications) → Phase 1 (recherche : base technique, scaling, contraintes,
benchmark) → Phase 2 (moteur de scaling + tests) → Phase 3 (orchestration LLM + garde-fous) →
Phase 4 (sortie `.cook` + UI web) → Phase 5 (2ᵉ cuisine + polish). Détail dans
[`backlog.md`](./backlog.md).
