---
titre: Décisions techniques — points de recherche tranchés
type: decisions
statut: v1
créé: 2026-06-01
tags: [decisions, epicure, cooklang, scaling, securite, benchmark]
---

# Décisions techniques

> Ce document **tranche** (autant que possible) les points `[À VÉRIFIER]` listés dans
> [`recherche-ouverte.md`](./recherche-ouverte.md), sans modifier ce dernier. Chaque section suit
> le format : **Question / Éléments factuels (+ sources) / Décision / Implications / Statut**.
>
> Légende des statuts : **TRANCHÉ ✅** · **EN ATTENTE ⏳** · **À VÉRIFIER MANUELLEMENT ⚠️**.
>
> Méthode : lecture de première main des fichiers du repo (données `data/epicure/`, code
> `app/epicure/loader.py`, JSON `docs/base-technique/`), reproduction empirique (chargement des
> trois modèles, benchmark cosine), puis sources web autoritatives pour Cooklang et la sécurité
> alimentaire. Aucune valeur n'est fabriquée : ce qui n'a pas pu être confirmé est marqué ⚠️.

---

## #1 & #2 — Format réel des embeddings Epicure (dimensions, normalisation, encodage)

### Question
Quel est le format exact des embeddings Epicure livrés dans `data/epicure/` (dimensions, type,
clé du tenseur, structure du vocabulaire) ? Faut-il une L2-normalisation avant le cosine ? Quelle
référence arXiv / architecture confirme l'origine des modèles ?

### Éléments factuels (vérifiés de première main)
Chargement empirique des trois modèles (`cooc`, `core`, `chem`) via `safetensors` + `numpy` :

| Modèle | Shape | dtype | Clé tenseur | Norme L2 min / max / moy. | Vocab |
|---|---|---|---|---|---|
| `epicure-cooc` | (1790, 300) | float32 | `embeddings` | 1,161 / 3,783 / 1,867 | 1790 |
| `epicure-core` | (1790, 300) | float32 | `embeddings` | 1,554 / 3,204 / 2,204 | 1790 |
| `epicure-chem` | (1790, 300) | float32 | `embeddings` | 1,378 / 4,911 / 2,264 | 1790 |

- **Encodage du vocabulaire** : `vocab.json` = dict `{ ingredient: id }` (1790 entrées, clés en
  `snake_case` anglais, ex. `abalone`, `olive_oil`, `black_pepper`) ; `itos.json` = inverse
  `{ "id": ingredient }`. Cohérent sur les trois modèles (mêmes clés, même ordre).
- **Normalisation** : les vecteurs **ne sont PAS normalisés sur disque** (normes nettement ≠ 1,
  étalées de ~1,16 à ~4,91). Le `config.json` le confirme explicitement :
  `"normalization": "raw skip-gram outputs; L2-normalise before cosine ops"`. Le README HF le
  redit : « Raw skip-gram outputs (not L2-normalised on disk) ».
- **Origine / archi** : `config.json` donne `architecture: "metapath2vec_skipgram"`, `d_model: 300`,
  `vocab_size: 1790`, `arxiv: "2605.22391"`, titre « Epicure: Navigating the Emergent Geometry of
  Food Ingredient Embeddings ». Licence **CC BY 4.0**, © Radzikowski & Chen (KAIKAKU.AI).
- **Implémentation conforme** : `app/epicure/loader.py` charge bien `load_file(...)["embeddings"]`
  puis fait `self.E = emb / np.linalg.norm(emb, axis=1, keepdims=True)` → cosine = produit scalaire.
  Le sanity-check (`tomato → onion/parsley/garlic/olive_oil`) est reproductible
  (`python -m app.epicure.loader`).

Sources : fichiers locaux `data/epicure/epicure-{cooc,core,chem}/{config.json,README.md,
embeddings.safetensors,vocab.json,itos.json}` ; HF <https://huggingface.co/Kaikaku/epicure-cooc> ;
arXiv <https://arxiv.org/abs/2605.22391>.

### Décision recommandée
**Figer le format** comme suit, sans plus de vérification : matrice `(1790, 300) float32`, clé
`embeddings`, vocabulaire `snake_case` anglais via `vocab.json`/`itos.json`. **La L2-normalisation
avant cosine est obligatoire** (faite une fois au chargement, comme dans `loader.py`). Pas besoin
de MCP : les 3 × ~2 Mo se chargent en local.

### Implications
- Toute requête doit normaliser le nom d'ingrédient en `snake_case` anglais (`olive_oil`, pas
  « huile d'olive ») → prévoir une **table de traduction FR→clé Epicure** dans la couche 1 (sinon
  `KeyError`). C'est le principal point d'intégration restant pour la couche associations.
- Le `loader.py` est correct tel quel ; conserver la normalisation au chargement (perf : O(N) une
  fois, puis cosine = un simple `E @ E[i]`).
- Pas d'autre format à supporter : les trois siblings partagent strictement la même structure.

### Statut
**TRANCHÉ ✅** (déjà acté dans `recherche-ouverte.md` #1/#2 ; ici **confirmé empiriquement** sur
les trois modèles et étendu d'une recommandation d'intégration FR→clé).

---

## #3 — Parseur Cooklang : templating maison vs binding d'une lib existante

### Question
Pour générer/valider du `.cook` en v1 (projet portfolio Python), faut-il un **templating maison +
validation regex** ou **binder/installer une lib Cooklang existante** ? Existe-t-il une lib Python
maintenue ?

### Éléments factuels
Paysage des parseurs Cooklang en Python (juin 2026) :

- **`cooklang/cooklang-py` (dépôt officiel, C-extension)** : **ARCHIVÉ par le propriétaire le
  10 mars 2025**, désormais en lecture seule. C'est une extension C (lex/yacc), non publiée sur
  PyPI de façon entretenue, et marquée « [WIP] ». **À éviter** (mort).
  Source : <https://github.com/cooklang/cooklang-py>.
- **`Net-Mist/cooklang-rs`** : binding **PyO3** du parseur Rust de référence ; expose
  `Metadata / Ingredient / Cookware / Timer`. Mais dépôt de faible activité (≈7 commits, aucune
  release publiée), installation par `maturin develop` (pas de wheel PyPI). → ajoute une **toolchain
  Rust** comme dépendance de build. Source : <https://github.com/Net-Mist/cooklang-rs>.
- **`cooklang-py` sur PyPI / readthedocs (≥ 0.3.2)** : présenté comme **parseur pur-Python**,
  requiert **Python ≥ 3.10**, installable `pip install cooklang-py`. Expose
  `Recipe / Metadata / Step / Ingredient / Cookware / Timing / Quantity`.
  Sources : <https://cooklang-py.readthedocs.io/en/latest/>, <https://libraries.io/pypi/cooklang-py>.
  ⚠️ **Ambiguïté de nommage** : même nom que le dépôt officiel archivé (qui, lui, était une
  C-extension). La fiche PyPI/readthedocs décrit un parseur pur-Python ≥3.10 ; l'identité exacte du
  mainteneur et la fraîcheur des releases **restent à confirmer manuellement** (cf. ⚠️ ci-dessous).
- **Parseur de référence** : `cooklang/cooklang-rs` (Rust) — robuste (erreurs riches, extensions,
  conversion d'unités, **scaling intégré**), mais le scaling Cooklang natif est **binaire**
  (linéaire ou figé), donc inadapté au cœur non-linéaire du projet. Le guide officiel d'intégration
  ne met en avant qu'**un seul** chemin Python : « py-cooklang ».
  Source : <https://cooklang.org/blog/44-cooklang-parser-integration-guide/>.

Rappel produit : le projet **génère** du `.cook` (ne consomme pas des recettes tierces en masse) et
applique **son propre** moteur de scaling. Le besoin de parsing est donc surtout : (a) **valider**
que la sortie LLM est un `.cook` bien formé, (b) éventuellement relire des recettes importées via
`cook.md/<url>` pour le corpus de test.

### Décision recommandée
**v1 : templating maison (génération) + validation légère**, avec un **garde-fou par
round-trip de parsing** quand une lib pure-Python est disponible sans coût de build.

Concrètement :
1. **Génération** : émettre le `.cook` par templating Python (chaînes + helpers pour `@`, `#`, `~`,
   `=`, notes `--`). C'est là que vivent les `=` et notes posés par le moteur de scaling — un
   parseur tiers ne sait pas faire ça pour nous.
2. **Validation** : valider la sortie au lieu de la regex fragile. **Préférer `pip install
   cooklang-py`** (pur-Python, zéro toolchain Rust) **si et seulement si** son identité/maintenance
   est confirmée (⚠️ #3-bis) ; sinon, rester sur une **validation regex maison** ciblée sur les
   marqueurs `@/#/~/{...}/=/--` (suffisante pour du `.cook` que *nous* produisons).
3. **NE PAS** binder `cooklang-rs` via PyO3 en v1 : la toolchain Rust + `maturin` est un coût de
   build/maintenance disproportionné pour un playground, et le scaling natif ne sert pas.

### Implications
- Zéro dépendance lourde par défaut → respecte la NFR « peu de dépendances, démarrage en une
  commande ». Le `.cook` que nous générons est simple et contrôlé.
- La story **S0.3** peut être marquée tranchée (décision écrite ici). **S0.4** (ouverture dans
  Obsidian) reste à faire — c'est le vrai test de conformité de bout en bout.
- Si l'import `cook.md/<url>` (point #5) produit du `.cook` non trivial à relire, ré-évaluer
  l'ajout de `cooklang-py` pur-Python pour le **parsing en lecture** uniquement.
- Garder le moteur de scaling **découplé** du format : il opère sur une structure interne, le
  templating n'est qu'une couche de sérialisation finale.

### Statut
**TRANCHÉ ✅** pour la stratégie (templating maison + validation, pas de binding Rust).
Sous-point **#3-bis ⚠️** : confirmer manuellement l'identité et la maintenance du paquet PyPI
`cooklang-py` (pur-Python ≥3.10) avant de l'ajouter comme dépendance de validation — le même nom
désigne un dépôt officiel **archivé** (C-extension), risque de confusion.

---

## #4 — Sourcing des températures de sécurité (USDA / ANSES)

### Question
Les valeurs de `docs/base-technique/safety-temperatures.json` sont-elles correctes au regard des
sources autoritatives (USDA FSIS / ANSES) ? Lesquelles sont confirmées, lesquelles restent à valider
manuellement ?

### Éléments factuels
Référence autoritative : **USDA FSIS — Safe Minimum Internal Temperature Chart**
(<https://www.fsis.usda.gov/food-safety/safe-food-handling-and-preparation/food-safety-basics/safe-temperature-chart>)
et **FoodSafety.gov**
(<https://www.foodsafety.gov/food-safety-charts/safe-minimum-internal-temperatures>).

Confrontation ligne à ligne du JSON aux valeurs USDA confirmées par recherche web :

| `foodType` (JSON) | JSON °F / °C / repos | USDA FSIS (référence) | Verdict |
|---|---|---|---|
| Volaille (toutes parts, haché) | 165 / 74 / 0 | **165 °F**, pas de repos | **CONFIRMÉ ✅** |
| Bœuf/veau/agneau/porc — pièces entières | 145 / 63 / **3 min** | **145 °F + repos 3 min** | **CONFIRMÉ ✅** |
| Bœuf/veau/agneau — haché | 160 / 71 / 0 | **160 °F** (viandes hachées) | **CONFIRMÉ ✅** |
| Porc — haché | 160 / 71 / 0 | **160 °F** (viandes hachées) | **CONFIRMÉ ✅** |
| Poisson / fruits de mer | 145 / 63 / 0 | **145 °F** (poisson à nageoires) | **CONFIRMÉ ✅** (nuance ⚠️) |
| Œufs & préparations à base d'œuf | 160 / 71 / 0 | œufs : « jaune+blanc fermes » ; **plats aux œufs 160 °F** | **À VÉRIFIER ⚠️** |
| Restes / réchauffage | 165 / 74 / 0 | **165 °F** (restes/casseroles) | **CONFIRMÉ ✅** |

Notes de nuance :
- **Poisson 145 °F** : valeur USDA correcte, mais l'indicateur alternatif (« opaque + s'effeuille »)
  est un repère technique, pas une garantie de sécurité — l'étiqueter `TECHNIQUE`, pas `SÉCURITÉ`.
- **Œufs** : l'USDA distingue « œufs » (cuire jusqu'à jaune **et** blanc fermes) des « plats aux
  œufs » (**160 °F**). La ligne JSON fusionne les deux ; le **160 °C/71 °C** correspond aux *plats*
  aux œufs. La mention « 60 °C maintenu 2 min (pasteurisation) » présente dans le JSON n'a **pas**
  été retrouvée telle quelle sur la page USDA grand public → à sourcer ou retirer.
- **ANSES** : la conversion « bœuf 63 °C / 145 °F » et « restes 75 °C » est plausible et alignée sur
  les barèmes français usuels, mais les sources ANSES exactes citées dans le `meta` du JSON
  (`paquethygiene.com`, `efsa.europa.eu/safe2eat`) **n'ont pas pu être ouvertes/vérifiées** ici
  (pas de lecture de première main) → marquer les références ANSES à confirmer.

### Décision recommandée
**Conserver les valeurs USDA, qui sont toutes confirmées** (volaille 165, pièces 145 + 3 min, haché
160, poisson 145, restes 165). **Figer** ces lignes (`critical: true`). Pour la robustesse côté
sécurité, **arrondir vers le haut en cas de doute** (jamais l'inverse). Avant figeage définitif
(`S0.5`), traiter trois corrections :
1. Reclasser l'indicateur « opaque / s'effeuille » du poisson en `TECHNIQUE` (pas sécurité).
2. Scinder/clarifier la ligne **œufs** : « plats aux œufs = 160 °F/71 °C » (confirmé) vs « œufs
   nature = blanc+jaune fermes » ; sourcer ou retirer le « 60 °C / 2 min ».
3. **Vérifier manuellement les URLs ANSES/EFSA** du `meta` (et idéalement remplacer par une page
   ANSES officielle citable), puis dater la vérification.

### Implications
- 5 des 7 lignes peuvent être figées immédiatement avec source USDA primaire.
- Le `meta.disclaimer` (« A_VERIFIER de premiere main… ») peut être levé pour les lignes USDA mais
  **maintenu** pour les références ANSES tant qu'elles ne sont pas ouvertes.
- Cela débloque la couche 2 (garde-fou anti-hallucination, story **D2**) : le LLM cite une ligne
  désormais sourcée.

### Statut
**TRANCHÉ ✅** pour les 5 valeurs USDA (volaille, pièces entières + repos, hachés, poisson, restes).
**À VÉRIFIER MANUELLEMENT ⚠️** : (a) la ligne œufs (scission « plats aux œufs 160 °F » + sourcing du
« 60 °C/2 min »), (b) l'ouverture/citation des sources ANSES/EFSA du `meta`.

---

## Point B — Benchmark `cooc` vs `core` (protocole de décision)

### Question
Quel modèle Epicure utiliser par défaut pour proposer/valider les associations d'un assistant
culinaire « classique » : `cooc` ou `core` ?

### Éléments factuels (benchmark reproduit)
Protocole appliqué (cf. `recherche-ouverte.md` §B) : jeu de requêtes « héros » avec voisins attendus
plausibles, top-8 cosine par modèle, mesure du recouvrement (recall) + inspection.

| Héros | Attendus | `cooc` top-8 (hits) | `core` top-8 (hits) |
|---|---|---|---|
| tomato | basil, garlic, onion, mozzarella, oregano | onion, parsley, garlic, olive_oil, bell_pepper, black_pepper, **oregano**, bay_leaf → **3/5** | bell_pepper, red_pepper, olive_oil, onion, red_onion, bean, garlic, black_olive → **2/5** |
| chicken | lemon, thyme, garlic, rosemary | garlic, onion, black_pepper, turkey, carrot, chicken_broth… → **1/4** | pork, beef, chicken_broth, peanut, cream_of_chicken_soup… → **0/4** |
| zucchini | mint, parmesan, garlic, lemon | olive_oil, eggplant, red_pepper, basil, garlic, onion… → **1/4** | pasta, olive_oil, eggplant, swiss_chard, vegetable_stock… → **0/4** |
| mushroom | garlic, parsley, thyme, cream | olive_oil, chive, italian_seasoning, black_pepper, carrot, onion, garlic… → **1/4** | bell_pepper, parmesan_cheese, pasta, green_bean… → **0/4** |
| **Total** | | **6/17 = 0,35** | **2/17 = 0,12** |

Lecture qualitative : `cooc` renvoie des **compagnons de recette authentiques** (oignon, ail,
persil, huile d'olive, origan) — exactement « ce qu'on cuisine ensemble ». `core` mélange la
chimie et renvoie davantage de **co-produits/plats** (pasta, broth, soupes, autres viandes) :
intéressant pour la **surprise/substitution**, moins pour un dressage classique. Cohérent avec le
README HF : ordre `Cooc ≤ Core ≤ Chem` sur les sondes supervisées, mais `cooc` est « the cleanest
recipe-context model » (le plus propre pour le contexte recette).

Reproductible : `python -c "from app.epicure.loader import EpicureIndex; ..."` (script du benchmark
ci-dessus). Source modèles : `data/epicure/`, README HF
<https://huggingface.co/Kaikaku/epicure-cooc>.

### Décision recommandée
**Modèle par défaut = `cooc`** pour proposer **et** valider les associations (recall ~3× supérieur,
voisins culinairement plus pertinents). **Garder `core` derrière un flag « mode exploration /
créatif »** (FR8 / A2) pour proposer des associations plus inattendues (parenté chimique). `chem`
reste hors v1 (chimie pure, pour exploration avancée seulement).

### Implications
- La couche 1 expose `EpicureIndex("cooc")` par défaut ; le mode créatif instancie `core`.
- Le panneau debug (FR7) peut afficher les deux listes côte à côte pour rendre la R&D visible.
- Limite à documenter : le corpus Epicure est ~½ est-asiatique, ~1/10 méditerranéen (README,
  §Limitations) → la qualité « italienne » des voisins est correcte mais pas optimale ; le filtrage
  par cuisine (story A3) reste nécessaire en aval.

### Statut
**TRANCHÉ ✅** : défaut `cooc`, `core` en mode exploration. (Story **A2** : note de décision
fournie ici ; le tableau precision@k ci-dessus en tient lieu.)

---

## Point #5 — Import `cook.md/<url>` (chantier ouvert)

### Question
La conversion d'une URL de recette en Cooklang via le préfixe `cook.md/<url>` fonctionne-t-elle de
façon fiable pour se constituer un corpus italien (story S0.6) ?

### Éléments factuels
Astuce documentée par Cooklang (préfixer une URL par `cook.md/`). **Non testée de première main**
ici (nécessite des URLs de recettes réelles et une vérification visuelle du `.cook` obtenu).

### Décision recommandée
**Reporter** à la constitution du corpus (S0.6). Tester sur 2–3 recettes italiennes simples
(ex. pasta aglio e olio, risotto, escalope), inspecter le `.cook` produit (marqueurs `@/#/~`,
quantités), et garder un **fallback de saisie manuelle** si la conversion est de qualité variable.

### Statut
**EN ATTENTE ⏳** (dépend de S0.6 ; aucune donnée de première main à figer).

---

## Récapitulatif des autres décisions de cadrage (rappel, déjà actées)

Ces points ne sont **pas** des `[À VÉRIFIER]` mais sont consolidés ici pour traçabilité (source :
`recherche-ouverte.md` §F, PRD §6) :

| Décision | Choix | Statut |
|---|---|---|
| Similarité | cosine = dot-product **après L2-norm** (confirmé #1) | TRANCHÉ ✅ |
| Chargement Epicure | local (3×~2 Mo), **pas de MCP** | TRANCHÉ ✅ |
| Modèle par défaut | `cooc` (benchmark ci-dessus) | TRANCHÉ ✅ |
| Parseur Cooklang | templating maison + validation (pas de binding Rust) | TRANCHÉ ✅ |
| Scaling | moteur custom déterministe (Cooklang natif = binaire) | TRANCHÉ ✅ |
| LLM | Claude API, sortie `.cook` contrainte | TRANCHÉ ✅ |

> **Point C (calibration des coefficients de scaling)** : reste un chantier **EN ATTENTE ⏳**
> par nature (exige des tests cuisine réels ×2/÷2, cf. stories C5/F2) — non tranchable sur dossier.

---

## Sources

- Epicure (données locales) : `data/epicure/epicure-{cooc,core,chem}/{config.json, README.md,
  embeddings.safetensors, vocab.json, itos.json}` · HF <https://huggingface.co/Kaikaku/epicure-cooc>
  · arXiv <https://arxiv.org/abs/2605.22391>
- Cooklang : <https://github.com/cooklang/cooklang-py> (archivé 2025-03-10) ·
  <https://github.com/Net-Mist/cooklang-rs> (binding PyO3) ·
  <https://cooklang-py.readthedocs.io/en/latest/> · <https://libraries.io/pypi/cooklang-py> ·
  <https://cooklang.org/blog/44-cooklang-parser-integration-guide/> · <https://cooklang.org/docs/spec/>
- Sécurité alimentaire : USDA FSIS
  <https://www.fsis.usda.gov/food-safety/safe-food-handling-and-preparation/food-safety-basics/safe-temperature-chart>
  · FoodSafety.gov <https://www.foodsafety.gov/food-safety-charts/safe-minimum-internal-temperatures>
  · (ANSES/EFSA : références du JSON à ouvrir/confirmer manuellement)
