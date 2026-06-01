---
titre: Générateur de recettes — projet Epicure
type: plan-projet
statut: cadrage
tags: [projet, cuisine, ia, epicure, cooklang, creative-lab]
créé: 2026-06-01
---

# Générateur de recettes — plan de projet

## Résumé

Construire un générateur de recettes qui s'appuie sur **Epicure** (cartes d'ingrédients de KAIKAKU.AI) pour la logique d'associations, sur une **base technique grounded** pour les cuissons et températures, et sur un **LLM via API** pour la rédaction. Sortie en **Cooklang** (`.cook`, texte brut compatible Obsidian). La pièce distinctive du projet est un **moteur de scaling intelligent** : un multiplicateur précis par ingrédient, au lieu d'un simple « tout × N ».

Statut : projet perso, avec un niveau de finition portfolio si l'exécution est propre.

---

## Le point de départ (contexte)

Epicure n'est **pas** un générateur de recettes. C'est une famille de trois modèles d'embeddings (`cooc`, `chem`, `core`), entraînés sur ~4,14 M de recettes en 7 langues, qui produisent une carte de 1 790 ingrédients en 300 dimensions (~2 Mo). Le modèle ne stocke aucune recette : il répond à des questions d'**association**, de **substitution** et d'**orientation cuisine**, sans génération de texte.

- `epicure-cooc` : « ce qu'on cuisine ensemble » (graphe de co-occurrence).
- `epicure-chem` : parenté chimique des arômes (FlavorDB).
- `epicure-core` : mélange des deux.

Points pratiques :
- Embeddings publics sur Hugging Face, licence **CC BY 4.0** → réutilisables.
- Le **corpus de 4,1 M de recettes n'est pas publié** (code d'entraînement non diffusé). On n'en a pas besoin.
- Un **MCP existe** mais à auto-héberger → trop lourd. À 2 Mo, on charge les vecteurs en local et on calcule la similarité cosinus soi-même.
- La démo officielle `epicure.kaikaku.ai` fait déjà exactement ce pattern : Epicure pour les associations + un LLM (Gemini/Imagen) pour rédiger la recette. C'est notre archi de référence.

---

## Décisions actées

| Sujet | Décision |
|---|---|
| Audience | Perso + portfolio si finition propre |
| Format de sortie | Fichier Markdown / Cooklang (`.cook`) |
| Entrées | Ingrédient(s), cuisine, contraintes (régime), contraintes matérielles (pas de four…), mise en avant d'un ingrédient « héros » |
| Base technique | Large à terme, mais **modulaire** : une cuisine d'abord, puis une seconde, etc. |
| Périmètre v1 | **Salé d'abord** — pâtisserie différée |
| Génération de texte | LLM via **API** (ex. Claude) |
| Données Epicure | Embeddings locaux, pas de MCP |

---

## Architecture (4 couches)

1. **Cerveau associations** — embeddings Epicure en local (`cooc` pour « ce qui se cuisine ensemble », ou `core` pour un mélange). Similarité cosinus. Sert à proposer des ingrédients compatibles autour du héros + cuisine, et à **valider** les choix du LLM.
2. **Base technique + températures + sécurité** — référence structurée, sourcée d'une autorité (jamais inventée). C'est le garde-fou : le LLM **choisit dedans**, il n'improvise aucune température ni technique.
3. **Moteur de scaling** — la table de multiplicateurs en JSON + arrondi des œufs + gestion temps/géométrie. La pièce maîtresse et différenciante.
4. **Générateur** — LLM via API qui assemble une recette **contrainte** par 1 + 2 + 3, et écrit du `.cook`.

---

## Format Cooklang

Texte brut avec trois marqueurs : `@` pour les ingrédients, `#` pour les ustensiles, `~` pour les minuteurs, le tout dans des instructions en langage naturel.

Exemple :
```cook
---
servings: 4
---
Faire chauffer @huile d'olive{2%c.à.s} dans une #poêle à feu moyen.
Ajouter @ail{3%gousses}, émincé, et cuire ~{1%minute}.
Saler avec @sel{=1%c.à.c} -- ajusté au goût
```

Pourquoi ça colle au projet :
- Les **contraintes matérielles** (pas de four, pas de blender) se mappent sur `#cookware`. On interdit un ustensile en amont ; le générateur n'a pas le droit de l'utiliser.
- Scaling natif : quantités multipliées par défaut, verrou `=` pour ce qui ne doit pas changer (`@sel{=1%c.à.c}`), temps de cuisson constants par défaut, taille d'ustensile non ajustée. **Mais ce verrou est binaire** (linéaire ou figé) — c'est là qu'intervient notre moteur de scaling.
- Bonus gratuits : liste de courses, minuteurs, possibilité de référencer une sous-recette (`@./Sauces/Salsa Verde{}`) qui s'agrège dans les courses.
- Astuce import : préfixer une URL de recette par `cook.md/` la convertit en Cooklang (utile pour se constituer un jeu de test).

---

## Moteur de scaling (v1 salé)

En salé, la cuisine est tolérante : peu d'effets de chimie. Les deux vrais sujets sont la **perception sensorielle** (sel/épices sous-linéaires) et la **géométrie/temps**. Multiplicateurs de départ pour un **×2**, à affiner ensuite :

| Catégorie | Multiplicateur ×2 | Raison |
|---|---|---|
| Ingrédients principaux (protéines, légumes, liquides, féculents) | ×2 (linéaire) | OK la plupart du temps |
| Sel & épices de fond | ~×1,5–1,75 | perception du goût non linéaire ; ×2 paraît trop salé |
| Arômes forts (ail, piment, herbes) | sous-linéaire, à goûter | montent vite en intensité |
| Œufs | unité discrète, arrondir vers le bas | pour 3 doublés, essayer 5 plutôt que 6 ; ½ œuf ≈ 25 g battu |
| Température (four/feu) | inchangée | jamais multipliée |
| Temps de cuisson | +10–25 % (même profondeur), puis vérifier | un plat doublé ne demande pas le double de temps |

Nuances à coder :
- **Géométrie > volume** : une sauce qui réduit en 10 min dans une poêle large prend bien plus longtemps dans une cocotte (ratio surface/volume différent). Le moteur doit raisonner profondeur/surface, pas seulement quantité.
- **Réserver ~10 %** des assaisonnements et ajuster en fin de cuisson plutôt qu'au début.
- **Flag de non-linéarité** : marquer « ne se double pas proprement au-delà de ~1,5–2× » sur les préparations sensibles.
- Émettre la sortie Cooklang avec les `=` et les notes `--` posés par le moteur (ex. `-- à 4×, utiliser une cocotte large, réduction plus longue`).

### Différé (pâtisserie — hors v1)
À documenter mais pas à implémenter tout de suite : levants (×1,5–1,75 ou ~75 % du linéaire, sinon levée puis effondrement + goût métallique), liquides en pâtisserie (retenir 10–15 %), cibles de température à cœur (pain 205–210 °F, gâteaux 200–205 °F). La pâtisserie est de la chimie → traitement séparé et plus rigoureux.

---

## Plan par phases

**Phase 0 — Socle**
- Charger les embeddings Epicure ; trancher `cooc` vs `core`.
- Valider Cooklang + un playground de test, se constituer un petit corpus de recettes salées de référence (via `cook.md/`).

**Phase 1 — Recherche (3 chantiers)**
- (a) **Base technique modulaire** : définir le schéma (technique → plages temp/temps, ustensiles requis, points de cuisson), + **températures de sécurité** depuis une source faisant autorité. Implémenter **une première cuisine** comme module pilote.
- (b) **Scaling** : formaliser la table salée ci-dessus en JSON.
- (c) **Contraintes matérielles** : cartographier « pas de four / blender / etc. » → ustensiles `#cookware` interdits.

**Phase 2 — Moteur de scaling** (code) : multiplicateurs par ingrédient, arrondi œufs, logique temps/géométrie, flags de non-linéarité.

**Phase 3 — Orchestration LLM + garde-fous** : le LLM ne propose que des associations validées par Epicure et des techniques/températures issues de la base. Schéma de sortie contraint.

**Phase 4 — Sortie `.cook`** : génération du fichier Cooklang + rendu Markdown lisible.

**Phase 5 — Extension & polish** : ajouter une 2ᵉ cuisine (valider la modularité), puis d'autres ; UI, exemples, démo portfolio.

---

## Chantiers de recherche ouverts

- **Sourcing de la base technique** : trouver des sources autoritatives pour les couples technique→température/temps et pour les températures de sécurité (à cœur). Décider du schéma de données et du format des modules par cuisine.
- **Quelle première cuisine ?** (à choisir — idéalement une cuisine bien documentée et bien représentée dans Epicure).
- **Affiner les multiplicateurs** de scaling par des tests réels (×2 et ÷2).
- **Choix `cooc` vs `core`** : à benchmarker sur quelques requêtes types.

---

## Risques / points de vigilance

- Hallucination de températures/techniques → traitée par la couche 2 (le LLM choisit, n'invente pas).
- Sécurité alimentaire → ne jamais laisser le modèle deviner une température de cuisson critique.
- Epicure ne connaît ni technique, ni température, ni quantité absolue → ne lui demander que des associations.

---

## Sources

- Epicure / KAIKAKU.AI : decrypt.co/369304, the-decoder.com (Epicure cooc/chem/core), huggingface.co/Kaikaku/epicure-cooc, epicure.kaikaku.ai, arXiv 2605.22391.
- Cooklang : cooklang.org/docs/spec, /docs/conventions, /blog (markup language, scaling).
- Scaling non-linéaire : cooklang.org/blog/26, fond.kitchen/guides/recipe-scaling-tips, kitchenaid.com (doubling), bloomcooking.com/tools/recipe-scaler, pastrycal.com/articles/scaling-recipes, kordu.tools.