---
titre: Architecture & Solution Design — Scaler de recettes Epicure
type: architecture
statut: v1
créé: 2026-06-01
tags: [architecture, solution-design, epicure, cooklang, scaling, fastapi, llm, anti-hallucination]
---

# Architecture & Solution Design — « Scaler de recettes honnête »

> Document de conception technique (méthode BMAD, solution-design). Destiné à l'agent dev
> qui implémentera les épics A→F du [`backlog.md`](./backlog.md). Toute la prose est en français ;
> le code, les identifiants, les signatures et les clés JSON restent en anglais (sauf les clés
> métier déjà actées dans les JSON existants, ex. `cuisine_pole_provenance`).
>
> Références croisées : [`PRD.md`](./PRD.md) (FR1-8, NFR, archi §6), [`pitch.md`](../pitch.md)
> (décisions actées, moteur de scaling), [`recherche-ouverte.md`](./recherche-ouverte.md)
> (points `[À VÉRIFIER]`), [`base-technique/schema.md`](./base-technique/schema.md).
>
> Convention de marquage : **[HYPOTHÈSE]** = décision raisonnable prise par l'architecte faute
> d'information explicite ; **[À TRANCHER]** = décision d'architecture ouverte (souvent un
> `[À VÉRIFIER]` du PRD reformulé en choix d'archi). Aucune valeur de température/temps/coefficient
> n'est inventée ici : toutes proviennent des JSON existants.

---

## 1. Résumé exécutif & objectifs d'architecture

### 1.1 Le produit en une phrase

Un **scaler de recettes honnête** : à partir d'un ingrédient « héros », d'une cuisine et de
contraintes, l'outil génère une recette salée cohérente en **Cooklang** (`.cook`), dont la **mise
à l'échelle est non-linéaire et crédible par ingrédient**, et dont **aucune température ni technique
n'est inventée** (grounded sécurité alimentaire). Cf. PRD §0.

### 1.2 Principe directeur de l'architecture

La valeur du projet n'est **pas** dans le LLM (commoditisé, interchangeable — cf. `etude-marche.md`
§4). Elle est dans **deux briques déterministes et testables** :

1. le **moteur de scaling non-linéaire** (couche 3, le cœur — FR5, Épic C) ;
2. le **garde-fou anti-hallucination** (couches 2 + 4 — FR3, NFR sécurité, Épic D2).

Conséquence architecturale forte : **le LLM est encadré, pas central**. Il est réduit au rôle de
**rédacteur sous contraintes**, et tout ce qui touche à la sécurité, aux quantités et aux
températures transite par des composants déterministes et vérifiables. Le LLM est la **seule**
source de non-déterminisme du système (NFR « déterminisme »).

### 1.3 Objectifs d'architecture (priorisés)

| # | Objectif | Origine | Mécanisme architectural |
|---|---|---|---|
| OA1 | **Déterminisme du cœur** : même entrée → même sortie pour le scaling | NFR déterminisme | `app/scaling/` = module pur, sans I/O, sans LLM, sans état ; tests `pytest` |
| OA2 | **Zéro hallucination de température/technique** | NFR sécurité, FR3 | Prompt contraint (entrées = base technique) + **validation post-génération** + tests anti-hallucination |
| OA3 | **Modularité par cuisine** | pitch, schema §4, Épic F | Loader générique qui découvre `cuisine-*.json` ; aucune logique cuisine en dur dans le code |
| OA4 | **Simplicité & local-first** | NFR simplicité | FastAPI mono-process, embeddings locaux (pas de MCP), démarrage en une commande |
| OA5 | **Traçabilité / explicabilité** | FR7, recommandation portfolio | Panneau debug : type de scaling par ingrédient + raisonnement + voisins Epicure retenus/rejetés |
| OA6 | **Séparation stricte des 4 couches** | PRD §6 | Dépendances unidirectionnelles ; chaque couche testable isolément |

### 1.4 État d'avancement de l'existant (point de départ du dev)

- **Couche 1 (Epicure)** : `app/epicure/loader.py` **implémenté et validé** (S0.1, S0.2). Classe
  `EpicureIndex`, méthode `neighbors(name, k)`, L2-normalisation, sanity-check OK. Reste : filtrage
  cuisine/contraintes (A3), benchmark `cooc` vs `core` (A2).
- **Couche 2 (knowledge)** : données prêtes (`safety-temperatures.json`, `cuisine-italienne.json`,
  `schema.md`). Code `app/knowledge/__init__.py` = **squelette** (docstring seulement).
- **Couche 3 (scaling)** : table `table-scaling-sale.json` prête. Code = **squelette**. Tests
  `tests/test_scaling.py` = **stubs `@pytest.mark.skip`**.
- **Couche 4 (generator)** : **squelette** (docstring).
- **Web** : `app/main.py` = squelette FastAPI avec `/health` uniquement.

> En clair : la couche 1 existe, les données des couches 2/3 existent, le reste est à coder en
> suivant ce document.

---

## 2. Stack technique

Confirmée d'après [`requirements.txt`](../requirements.txt) et le code réel.

| Composant | Choix | Version | Justification |
|---|---|---|---|
| Langage | **Python 3.10+** | [HYPOTHÈSE] 3.10+ requis | `loader.py` utilise `from __future__ import annotations` + syntaxe `list[tuple[...]]` / `dict[str, int]` (PEP 585) ; 3.10+ raisonnable. Pas de `python_requires` déclaré → **[À TRANCHER]** : figer dans un `pyproject.toml`/README. |
| Framework web | **FastAPI** | non épinglée | API typée (Pydantic), async, OpenAPI auto, léger ; idéal pour un seul endpoint local (FR / Épic E1). Confirmé `requirements.txt` + `app/main.py`. |
| Serveur ASGI | **uvicorn[standard]** | non épinglée | Serveur de dev standard FastAPI ; lancement `uvicorn app.main:app --reload` (cf. `main.py`). |
| Templating UI | **jinja2** | non épinglée | Rendu de l'UI minimale (formulaire + recette + panneau debug) côté serveur, sans build front. Cohérent avec OA4 (simplicité). |
| Upload form | **python-multipart** | non épinglée | Requis par FastAPI pour les formulaires `multipart/form-data` (UI). |
| Algèbre / embeddings | **numpy** | non épinglée | Chargement matrice (1790, 300) float32, L2-norm, cosine = produit scalaire. Déjà utilisé dans `loader.py`. |
| Format embeddings | **safetensors** | non épinglée | `embeddings.safetensors` clé `embeddings`. `load_file` (numpy backend) déjà utilisé. Le commentaire `requirements.txt` « selon le format réel » est **résolu** : safetensors confirmé. |
| Téléchargement modèles | **huggingface_hub** | non épinglée | Récupération des modèles `Kaikaku/epicure-{cooc,core,chem}` depuis HF (Phase 0). Données ensuite locales et gitignorées. |
| LLM | **anthropic** (Claude API) | non épinglée | Rédacteur sous contraintes (couche 4). Clé via `ANTHROPIC_API_KEY` (cf. docstring `generator`). Coût ~0,005–0,01 $/recette (NFR coût). |
| Tests | **pytest** | non épinglée | Tests déterministes du cœur (Épic C5, D2). |
| R&D / calibration | **jupyter** | non épinglée | Notebooks de calibration scaling (`notebooks/`, Épic C5, F2) et benchmark Epicure (A2). |

**Décisions de stack ouvertes**

- **[À TRANCHER] Épinglage des versions** : `requirements.txt` n'épingle aucune version. Pour la
  reproductibilité (NFR), recommandation : épingler à terme (`==`) ou migrer vers un
  `pyproject.toml` + lock. Non bloquant pour démarrer.
- **[À TRANCHER] Parseur Cooklang** (`[À VÉRIFIER] #3`) : voir §8.4 et §12 — décision retenue =
  **génération par templating + validation regex**, pas de binding Rust en v1.

---

## 3. Vue d'ensemble en 4 couches

Architecture confirmée par PRD §6 et pitch. Backend Python mono-process ; dépendances **strictement
unidirectionnelles** (l'orchestrateur appelle les couches, les couches ne se connaissent pas entre
elles, sauf la couche 4 qui consomme les sorties de 1/2/3).

```
┌──────────────────────────────────────────────────────────────────────────┐
│  NAVIGATEUR (UI minimale Jinja2)                                           │
│  Formulaire : héros · cuisine · contraintes · portions                     │
│  Rendu recette (.cook + Markdown) + PANNEAU DEBUG                          │
└───────────────────────────────┬────────────────────────────────────────────┘
                                 │  HTTP localhost  (POST /generate)
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  BACKEND FastAPI  ── app/main.py  (orchestrateur)                          │
│                                                                            │
│   GenerationRequest ──► pipeline ──► GenerationResponse (.cook + debug)     │
│                                                                            │
│  ┌────────────────────┐   ┌────────────────────┐                          │
│  │ Couche 1            │   │ Couche 2           │                          │
│  │ ASSOCIATIONS        │   │ BASE TECHNIQUE     │                          │
│  │ app/epicure/        │   │ (grounded)         │                          │
│  │ embeddings locaux   │   │ app/knowledge/     │                          │
│  │ cosine, cooc/core   │   │ JSON sécurité +    │                          │
│  │ neighbors(name,k)   │   │ cuisines modulaires│                          │
│  └─────────┬──────────┘   └─────────┬──────────┘                          │
│            │ associations            │ techniques + temp + cookware        │
│            │ validées                │ interdits + safety                  │
│            ▼                          ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐             │
│  │ Couche 4 · GÉNÉRATEUR LLM  ── app/generator/              │             │
│  │  prompt CONTRAINT (assoc. + base) → Claude API            │             │
│  │  → recette structurée → VALIDATION anti-hallucination     │             │
│  └───────────────────────────┬──────────────────────────────┘             │
│                               │ recette structurée (quantités de base)     │
│                               ▼                                            │
│  ┌──────────────────────────────────────────────────────────┐             │
│  │ Couche 3 · MOTEUR DE SCALING  ── app/scaling/  (LE CŒUR)  │             │
│  │  PUR · DÉTERMINISTE · TESTÉ                                │             │
│  │  linear / sublinear / discrete / geometric / fixed        │             │
│  │  table-scaling-sale.json · k^(2/3) · œufs · réserve 10%   │             │
│  └───────────────────────────┬──────────────────────────────┘             │
│                               ▼                                            │
│                  ÉMISSION .cook (= , notes --) + rendu Markdown            │
└──────────────────────────────────────────────────────────────────────────┘
                                 ▼
                    Sortie : recette.cook  +  Markdown  +  debug JSON
```

### 3.1 Responsabilités de chaque couche

| Couche | Module | Responsabilité | Ne fait PAS | Déterministe ? |
|---|---|---|---|---|
| **1 · Associations** | `app/epicure/` | Proposer/valider des associations d'ingrédients (cosine sur embeddings), filtrer par cuisine/contraintes | Aucune notion de technique, température ou quantité absolue (cf. docstring) | Oui (lecture pure) |
| **2 · Base technique** | `app/knowledge/` | Fournir techniques, températures, ustensiles requis, sécurité, mapping contraintes→cookware interdit | N'invente rien ; ne génère pas de texte | Oui (lecture JSON) |
| **3 · Scaling** | `app/scaling/` | Mettre à l'échelle chaque quantité selon son type, gérer œufs/temps/géométrie, poser flags & notes | Aucun I/O réseau, aucun LLM, aucun accès Epicure | **Oui (cœur pur)** |
| **4 · Générateur** | `app/generator/` | Orchestrer le LLM sous contraintes, valider la sortie, émettre `.cook` + Markdown | N'a pas le droit d'inventer temp/technique ; ne fait pas le calcul de scaling lui-même | Non (LLM) — mais sortie **validée** |
| **Web** | `app/main.py` | Exposer `POST /generate`, servir l'UI, assembler le pipeline | Aucune logique métier (uniquement orchestration) | n/a |

**Règle de dépendances** : `main` → {1, 2, 3, 4}. La couche 4 consomme les **sorties** de 1 et 2
(passées en paramètres), et le scaling (3) est appliqué **après** la rédaction LLM, sur les
quantités de base produites. Aucune couche n'importe une autre couche métier directement (testabilité).

---

## 4. Conception détaillée de chaque couche

> Les signatures ci-dessous sont **prescriptives** pour le dev. Celles de la couche 1 reflètent le
> code **déjà écrit** ; les autres sont à implémenter.

### 4.1 Couche 1 — Associations Epicure (`app/epicure/`) — Épic A

**Existant** (`loader.py`) :

```python
class EpicureIndex:
    def __init__(self, model: str = "cooc"): ...
    def neighbors(self, name: str, k: int = 6) -> list[tuple[str, float]]: ...
```

- Charge `data/epicure/epicure-{model}/embeddings.safetensors` (clé `embeddings`, matrice
  `(1790, 300)` float32), `vocab.json` (`{ingredient: id}`), `itos.json` (`{ "id": ingredient }`).
- L2-normalise à l'init → `cosine = self.E @ self.E[i]`.
- `neighbors` lève `KeyError` si l'ingrédient est absent du vocabulaire (1790 entrées, identifiants
  en `snake_case` anglais, ex. `olive_oil`, `black_pepper`).

**À ajouter** (A2, A3) — signatures prescrites :

```python
# A3 — filtrage par cuisine / contraintes
def filter_neighbors(
    candidates: list[tuple[str, float]],
    cuisine: str,
    constraints: Constraints,
) -> FilteredNeighbors:  # retenus + rejetés (avec raison) pour le panneau debug
    ...

# A2 — benchmark cooc vs core (R&D, produit une note de décision, pas du runtime)
def benchmark(models: list[str], queries: dict[str, list[str]], k: int) -> BenchmarkReport: ...
```

- **Filtrage cuisine** : `[À TRANCHER]` — la mécanique de rattachement « ingrédient → cuisine »
  n'est pas figée. Données disponibles pour l'implémenter : `docs/epicure/cuisine_macroregions.json`
  (macro-régions → traditions, ex. `Mediterranean` ⊃ `Italian`) et, dans chaque modèle,
  `cuisine_pole_provenance.json` + `modes.json` (pôles sémantiques). **[HYPOTHÈSE]** retenue pour la
  v1 italienne : filtrage *souple* — on ne supprime pas un voisin par défaut, on **annote** sa
  pertinence cuisine et on laisse le LLM/validation trancher ; le rejet dur est réservé aux
  contraintes matérielles/régime (déterministes). Décision à confirmer après A2.
- **`FilteredNeighbors`** doit exposer `kept` et `rejected[(name, score, reason)]` pour FR7.
- Le **choix du modèle par défaut** (`cooc` vs `core`) est `[À TRANCHER]` via le benchmark A2 ;
  choix de départ documenté = **`cooc`** (associations authentiques), `core` réservé à un futur
  mode « créatif » (FR8/Could, `recherche-ouverte.md` §B).

**Sortie consommée par** : la couche 4 (liste d'associations validées) et le panneau debug.

### 4.2 Couche 2 — Base technique (`app/knowledge/`) — Épic B

**À implémenter** (squelette actuel). Signatures prescrites (cf. `schema.md` §4) :

```python
def load_safety() -> SafetyTable: ...          # docs/base-technique/safety-temperatures.json
def load_cuisines() -> dict[str, Cuisine]: ...  # découvre tous docs/base-technique/cuisine-*.json

def techniques_for(
    cuisine: str,
    ingredient: str | None,
    constraints: Constraints,
) -> list[Technique]: ...   # techniques applicables, EXCLUT celles à ustensile interdit (B3)

def forbidden_cookware(cuisine: str, constraints: Constraints) -> set[str]: ...  # B4

def safety_for(food_type: str) -> SafetyStandard | None: ...  # ligne sécurité d'une protéine
```

**Détails d'implémentation**

- **Découverte modulaire** (OA3, Épic F1) : `load_cuisines()` scanne `docs/base-technique/` pour
  `cuisine-*.json`, clé = `meta.id` (ex. `italian_savory_v1`). Aucune cuisine en dur. Ajouter une
  cuisine = déposer un fichier conforme à `schema.md`, **sans toucher au code**.
- **Mapping contraintes → cookware interdit** (B4, FR4) : lit `cuisineConstraints.cookwareConstraints`
  (ex. `"pas_de_four": ["four", "moule a four", "cocotte au four"]`), produit l'ensemble des
  ustensiles interdits. Une technique dont `requiredTools` intersecte cet ensemble est **exclue**
  par `techniques_for` (ex. « pas de four » exclut `searing_braising` qui requiert `four`).
- **Trois niveaux d'autorité** propagés partout : `SÉCURITÉ` > `TECHNIQUE` > `PRÉFÉRENCE`
  (cf. `level` / `safetyClassification`). `safety-temperatures.json` est **autoritatif** et
  transverse ; `critical: true` ⇒ aucune flexibilité.
- **Format de sortie** : objets typés (Pydantic recommandé pour cohérence avec FastAPI) ou
  dataclasses. La couche 4 reçoit la liste des `Technique` autorisées + la table sécurité filtrée
  sur les protéines de la recette.

### 4.3 Couche 3 — Moteur de scaling (`app/scaling/`) — Épic C — **détaillée en §5**

Signatures prescrites (alignées sur les tests `tests/test_scaling.py` et les AC de l'Épic C) :

```python
def scale(name: str, qty: float, unit: str, k: float) -> ScaledQuantity: ...
def scale_eggs(count: int, k: float) -> ScaledEggs: ...
def scale_time(minutes: float, k: float) -> ScaledTime: ...
def classify(name: str) -> ScalingRule: ...   # lit table-scaling-sale.json, retourne le type/coeff
```

Voir **§5** pour la conception complète (le cœur).

### 4.4 Couche 4 — Générateur LLM (`app/generator/`) — Épic D — garde-fou détaillé en §6

Signatures prescrites :

```python
def build_prompt(req, neighbors, techniques, safety, forbidden) -> ConstrainedPrompt: ...  # D1
def generate_recipe(prompt) -> StructuredRecipe: ...                # appel Claude API
def validate_recipe(recipe, techniques, safety) -> ValidationResult: ...  # D2, garde-fou
def to_cooklang(recipe, scaling_notes) -> str: ...                  # D3 (.cook)
def to_markdown(recipe) -> str: ...                                 # D4 (rendu lisible)
```

- Le LLM reçoit **uniquement** : les associations validées (couche 1), les techniques autorisées et
  leurs `parameters` (couche 2), les lignes de sécurité applicables, et la liste des `#cookware`
  interdits. Il **choisit dedans** (FR3).
- La recette est demandée dans un **format structuré** (`[À TRANCHER]` : JSON via tool-use / sortie
  structurée Anthropic, recommandé) afin que la **validation** (§6) et le **scaling** (§5) puissent
  s'appliquer mécaniquement avant l'émission `.cook`.
- Émission `.cook` **après** scaling : le générateur reçoit les `ScaledQuantity`/notes du moteur
  (couche 3) et pose les marqueurs `@`/`#`/`~`, les verrous `=` et les notes `--`.

---

## 5. Conception du MOTEUR DE SCALING (le cœur) — Épic C

Source de vérité : [`docs/scaling/table-scaling-sale.json`](./scaling/table-scaling-sale.json).
**Aucune** valeur n'est codée en dur dans le module : tous les coefficients sont lus depuis la table
(versionnée, calibrable — Épic F2, `recherche-ouverte.md` §C).

### 5.1 Contrat de pureté (OA1)

`app/scaling/` est **pur** : pas d'I/O réseau, pas de LLM, pas d'état mutable global. Seule lecture
admise : la table JSON (chargée une fois, en lecture seule). Même `(name, qty, unit, k)` → même
`ScaledQuantity`. C'est la garantie qui rend le cœur testable (Épic C5).

### 5.2 Les cinq types de scaling (depuis `meta.scalingTypes`)

| Type | Formule | Usage | Source table |
|---|---|---|---|
| `linear` | `qty * k` | Ingrédients principaux (protéines, légumes, liquides, féculents) | `defaults.main_ingredients` |
| `sublinear` | `qty * k^coeff` (0<coeff<1) | Sel, poivre, piment, ail, gingembre, herbes, épices, acides | `categories[].coeff` |
| `discrete` | unités entières + reste en volume/poids, **arrondi bas** | Œufs | `categories[]` œuf |
| `geometric` | `t * k^(2/3)` | Temps de cuisson (diffusion surface/volume) | `categories[]` temps, `exponent: 0.6667` |
| `fixed` | inchangé → `=` Cooklang | Températures, taille d'ustensile | `categories[]` temperature/ustensile |

> Le doc l'appelle « sous-linéaire / discret / géométrique / figé ». La table nomme aussi `linear`.
> Le « géométrique » des consignes correspond au type `geometric` (temps) **et** au raisonnement
> profondeur/surface des ustensiles (`fixed` + note). Voir §5.5.

### 5.3 Classification d'un ingrédient (`classify`)

`classify(name)` parcourt `categories[]` et retourne la première règle dont un motif `match`
correspond au nom (insensible à la casse, FR + EN — la table fournit les deux, ex.
`["sel", "salt", ...]`). Si aucun match : défaut `linear` (`defaults.main_ingredients`).

**[HYPOTHÈSE] stratégie de matching** : la table liste des **mots-clés** (`"sel"`, `"ail"`, …),
pas des regex. Implémentation retenue : *normalisation* (minuscule, sans accent) + recherche par
inclusion de token sur le nom d'ingrédient. Risque d'ambiguïté (ex. « ail » contenu dans
« vol-au-vent ») → matcher sur tokens entiers, pas sous-chaîne. À durcir si faux positifs constatés.

### 5.4 Coefficients de départ (lus dans la table — **à calibrer**, ne pas présenter comme exacts)

| Catégorie | Type | Coeff/param | Raison (table) |
|---|---|---|---|
| sel / sauce soja | sublinear | `0.75` + `reserve_pct: 10` | perception non linéaire |
| poivre | sublinear | `0.70` | monte vite en intensité |
| piment / cayenne | sublinear | `0.60` + `nonlinearFlag` | composés volatils s'accumulent |
| ail | sublinear | `0.85` | arôme fort |
| gingembre | sublinear | `0.80` | arôme fort |
| herbes (basilic, origan, romarin, thym) | sublinear | `0.80` | aromates volatils |
| épices (cannelle, cumin, muscade) | sublinear | `0.70` | intensité non linéaire |
| acides (vinaigre, citron) | sublinear | `0.85` | acidité perçue |
| temps de cuisson | geometric | `exponent: 0.6667` + `nonlinearFlag` | k^(2/3) |
| œuf | discrete | `grams_per_unit: 50`, `tbsp_per_unit: 3`, `round: down` | unité non sécable |
| température / four / feu | fixed | — | jamais multipliée |
| taille ustensile / moule | fixed | — | géométrie, raisonner profondeur/surface |

> `meta.disclaimer` : coefficients **de départ** (recherche + physique), **à calibrer** par tests
> réels ×2/÷2. Le module les lit, ne les fige pas. La calibration (Épic F2) modifie la **table**,
> pas le code.

### 5.5 Cas particuliers

**Œufs (`scale_eggs`, C2)** — type `discrete` :

- Cible = `round(count * k)` puis **arrondi vers le bas** sur l'entier d'œufs. AC backlog :
  `scale_eggs(3, 2.0)` → **5** (pas 6), avec note. Le reste (différence vers la cible théorique) est
  exprimé en **volume/poids** : `grams_per_unit: 50`, `tbsp_per_unit: 3`, demi-œuf ≈ 25 g battu
  (`reason` de la table).
- Sortie `ScaledEggs` : `whole_eggs: int`, `remainder` (en g ou c.à.s), `note: str`.
- **[HYPOTHÈSE]** d'interprétation de l'AC : `3 × 2.0 = 6`, mais la table privilégie « pour 3
  doublés, essayer 5 plutôt que 6 » (sous-linéarité culinaire des œufs liants). L'algo prescrit :
  cible théorique `count*k`, puis **borne basse** appliquée par la règle « essayer N-1 si N paraît
  excessif ». Le dev doit fixer la règle exacte qui produit 5 et la couvrir par
  `test_oeufs_discrets`. La règle figée doit rester déterministe.

**Temps (`scale_time`, C3)** — type `geometric` :

- `t_scaled = t * k^(2/3)`. La table fournit `geometricTimeExamples` : ×1.5→1.31, ×2→1.59,
  ×3→2.08, ×4→2.52. AC backlog : `20 min × 2 → ~32 min` (pas 40). Cohérent : `20 × 1.59 = 31.8`.
- Sortie `ScaledTime` : `minutes`, `nonlinear: true`, `note` (ex. suggestion de contenant à fort
  facteur).

**Géométrie / contenant (règle, pas type dédié)** :

- Règle `rules[0]` : « raisonner profondeur/surface » (une sauce réduit plus lentement en cocotte
  qu'en poêle large). Le moteur **ne multiplie pas** la taille d'ustensile (`fixed`) mais **émet une
  note** `--` quand `k` est élevé (ex. `-- à 4×, cocotte large, réduction plus longue`).
- **[À TRANCHER]** : le seuil de `k` déclenchant la note de changement de contenant n'est pas chiffré
  dans la table. **[HYPOTHÈSE]** : aligné sur le flag de non-linéarité (~1.5–2×). À confirmer en
  calibration.

**Flag de non-linéarité (`nonlinearFlag`, C4)** :

- Catégories `piment`/`temps` portent `nonlinearFlag: true`. Au-delà de ~1.5–2× (règle `rules[2]`),
  le moteur attache la note « ne se double pas proprement au-delà de ~1.5–2× » à l'ingrédient/au plat.

**Réserve 10 % des assaisonnements (C4)** :

- `reserve_pct: 10` (sel). Règle `rules[1]` : réserver ~10 % et ajuster en fin de cuisson. Le moteur
  scinde la quantité scalée en **90 % à l'incorporation** + **10 % en ajustement final**, et émet une
  note `--`. **[HYPOTHÈSE]** : généraliser `reserve_pct` à toute catégorie qui le porte ; en l'état
  seul `sel` l'a → seul le sel reçoit la réserve en v1.

### 5.6 Sortie du moteur

`ScaledQuantity` (proposition de structure) : `name`, `value`, `unit`, `type` (linear/…),
`fixed: bool` (→ verrou `=`), `notes: list[str]` (→ notes `--`), `reserve` (optionnel),
`debug: {rule, coeff, formula, reasoning}` pour FR7. Ces objets alimentent à la fois l'émission
`.cook` (§8.4) et le panneau debug (§9).

---

## 6. Garde-fou anti-hallucination LLM — FR3, NFR sécurité, Épic D2

Objectif (OA2) : **aucune température/technique hors base** ne doit apparaître dans une recette
générée. Triple barrière :

### 6.1 Barrière 1 — Contrainte d'entrée (prompt)

Le prompt (`build_prompt`, D1) injecte **uniquement** :
- les **associations validées** par Epicure (couche 1),
- les **techniques autorisées** et leurs `parameters` (couche 2, déjà filtrées par contraintes),
- les **lignes de sécurité** applicables aux protéines (`safety-temperatures.json`),
- la **liste des `#cookware` interdits**.

Et les `llmConstraints` de `cuisine-italienne.json` sont reprises **verbatim** dans le prompt
système :
> « NE JAMAIS inventer une température ou un temps : choisir dans `parameters` ou
> `safety-temperatures.json` » · « Étiqueter chaque consigne `[SÉCURITÉ]/[TECHNIQUE]/[PRÉFÉRENCE]` »
> · « Pour toute protéine, citer la température de sécurité et le repos » · « Ne pas utiliser un
> ustensile interdit » · « Si une technique requise utilise un ustensile interdit, la remplacer ou
> refuser proprement ».

### 6.2 Barrière 2 — Validation post-génération (déterministe, le vrai garde-fou)

`validate_recipe(recipe, techniques, safety)` : **on ne fait pas confiance au prompt**. On vérifie
mécaniquement la sortie :

1. **Extraction** de toutes les valeurs numériques de température/temps de la recette générée.
2. **Appartenance** : chaque température citée doit correspondre à une valeur présente dans les
   `parameters` des techniques autorisées **ou** dans `safety-temperatures.json`. Toute valeur hors
   base = **violation**.
3. **Sécurité protéines** : pour toute protéine détectée, la ligne `safety-temperatures` applicable
   doit être citée et **jamais** une température inférieure au minimum (`critical: true` ⇒ rejet dur).
4. **Cookware** : aucun `#cookware` de la recette ne doit appartenir à l'ensemble interdit (couche 2).
5. **[À TRANCHER] politique en cas de violation** : rejet dur + **1 retry** avec feedback ciblé, puis
   échec propre si la 2ᵉ tentative viole encore. **[HYPOTHÈSE]** retenue : 1 retry maximum (coût/latence
   maîtrisés, NFR coût), sinon réponse d'erreur explicite côté API. Pas de « réparation » silencieuse.

> La barrière 2 est **déterministe et testable** : c'est elle qui *garantit* OA2, pas le prompt.

### 6.3 Barrière 3 — Tests anti-hallucination (Épic D2, C5)

- Test asserrant qu'**aucune** valeur de température/technique d'une recette générée n'est hors
  `cuisine-italienne.json` / `safety-temperatures.json` (AC D2).
- Pour rester déterministes malgré le LLM, ces tests s'appuient sur des **réponses LLM enregistrées
  (fixtures)** et/ou un **double de test** qui simule des sorties hallucinées → on vérifie que
  `validate_recipe` les **rejette**. **[HYPOTHÈSE]** : on teste le *validateur* sur des cas piégés
  plutôt que d'appeler l'API à chaque test (coût/flakiness). Un test d'intégration optionnel
  (marqué, non lancé en CI sans clé) peut appeler réellement Claude.

---

## 7. Flux de données bout-en-bout

De la requête UI au `.cook` (parcours principal, PRD §3) :

1. **UI → API** : `POST /generate` avec `{hero, cuisine, constraints, servings, model?}`.
2. **Couche 1** : `EpicureIndex(model).neighbors(hero, k)` → voisins ; `filter_neighbors(...)` →
   `kept` / `rejected` (debug). [Si `hero` absent du vocab → erreur 422 explicite.]
3. **Couche 2** : `techniques_for(cuisine, hero, constraints)` → techniques autorisées ;
   `forbidden_cookware(...)` → ustensiles interdits ; `safety_for(...)` pour les protéines.
4. **Couche 4 (rédaction)** : `build_prompt(...)` → `generate_recipe(prompt)` (Claude API) →
   `StructuredRecipe` avec **quantités de base** (servings de référence de la recette) + techniques
   choisies + températures **citées** depuis la base.
5. **Couche 4 (validation)** : `validate_recipe(...)` (§6.2). Violation → retry/échec.
6. **Couche 3 (scaling)** : pour `k = servings_cible / servings_base`, appliquer `scale` /
   `scale_eggs` / `scale_time` à chaque quantité → `ScaledQuantity[]` + notes + flags.
7. **Couche 4 (émission)** : `to_cooklang(recipe, scaling_notes)` → `.cook` (marqueurs `@`/`#`/`~`,
   `=` pour `fixed`, notes `--`) ; `to_markdown(recipe)` → rendu lisible.
8. **API → UI** : `GenerationResponse` = `{cooklang, markdown, debug}`. Le `.cook` est aussi
   téléchargeable (réutilisable dans Obsidian).

> **Ordre clé** : rédaction (4) **avant** scaling (3). Le LLM produit une recette à une échelle de
> base ; le moteur déterministe la met ensuite à l'échelle cible. Cela isole le non-déterminisme du
> LLM du calcul de quantités (OA1).

---

## 8. Structures de données & schémas

### 8.1 Embeddings Epicure (`data/epicure/epicure-{cooc,core,chem}/`)

Confirmé (S0.1, `config.json`, `loader.py`) :

- `embeddings.safetensors` : clé `embeddings`, matrice **(1790, 300) float32**. **Non normalisés**
  sur disque (`config.json.normalization = "raw skip-gram outputs; L2-normalise before cosine ops"`)
  → L2-normalisation à l'init.
- `vocab.json` : `{ ingredient: id }` (1790 entrées, `snake_case` EN).
- `itos.json` : `{ "id": ingredient }`.
- `config.json` : `architecture: metapath2vec_skipgram`, `d_model: 300`, `vocab_size: 1790`,
  `schema` (cooc/core/chem), `arxiv: 2605.22391`.
- Fichiers annexes présents mais **non requis** par le runtime v1 : `modes.json` (pôles
  sémantiques), `cuisine_pole_provenance.json`, `factor_pole_index.json`, `factor_poles.npy`,
  `supervised_poles.json`, `paper_slerp_results.csv`, `epicure.py` (loader HF de référence).
  Réserve pour le filtrage cuisine avancé (§4.1) ou un futur mode exploration.
- Données **gitignorées** (`.gitignore` : `data/epicure/`) — téléchargées via `huggingface_hub`.
- Index transverse : `docs/epicure/cuisine_macroregions.json`,
  `docs/epicure/canonical_vocabulary.parquet`, `docs/epicure/direction_arithmetic_full.parquet`,
  `docs/epicure/vocab.csv` (mapping `node_id` cooc/core/chem — utile car les ids peuvent différer
  entre modèles).

### 8.2 Base technique (`docs/base-technique/`)

- `safety-temperatures.json` : `meta` (authority USDA FSIS + ANSES, sources, disclaimer) +
  `standards[]` (`foodType`, `minInternalC/F`, `restMinutes`, `critical`, `source`, `note`) +
  `rules[]`. **Autoritatif**, transverse.
- `cuisine-italienne.json` (`meta.id = italian_savory_v1`) : `techniques[]` (5 :
  `pasta_al_dente`, `risotto`, `soffritto`, `sugo_pomodoro`, `searing_braising`), chacune avec
  `parameters` (températures/temps/ratios), `criticalPoints[].level`, `donenessIndicators`,
  `requiredTools`, `sources` ; + `cookwareConstraints` (mapping) + `llmConstraints`. Schéma complet :
  `schema.md`.

### 8.3 Table de scaling (`docs/scaling/table-scaling-sale.json`)

`meta.scalingTypes` (définitions), `defaults`, `categories[]` (`match`, `type`, `coeff`/params,
`reason`, `nonlinearFlag?`, `reserve_pct?`), `rules[]`, `geometricTimeExamples`. Voir §5.4.

### 8.4 Format Cooklang (`.cook`)

Texte brut (pitch §Format) — trois marqueurs : `@ingrédient{quantité%unité}`, `#ustensile`,
`~{durée}`. Frontmatter `servings`. Verrou `=` (figé), notes `--`.

```cook
---
servings: 4
---
Faire chauffer @huile d'olive{2%c.à.s} dans une #poêle à feu moyen.
Ajouter @ail{3%gousses}, émincé, et cuire ~{1%minute}.
Saler avec @sel{=1%c.à.c} -- ajusté au goût, réserver ~10% pour la fin
```

- Contraintes matérielles ↔ `#cookware` (FR4).
- `=` posé par le moteur pour `fixed` ; notes `--` portées par le moteur (scaling) et le LLM
  (étiquettes `[SÉCURITÉ]/[TECHNIQUE]/[PRÉFÉRENCE]`).
- **[À TRANCHER] (`[À VÉRIFIER] #3`)** : génération **par templating + validation regex** (décision
  retenue, `recherche-ouverte.md` §F) plutôt qu'un binding Rust (`cooklang-rs` via PyO3) — rester
  simple en v1. Une validation regex légère vérifie la bonne formation des marqueurs.

### 8.5 Schémas d'API (Pydantic) — voir §9.

---

## 9. API web (FastAPI) — Épic E

`app/main.py` (squelette actuel : `/health`). À ajouter (E1, E2) :

### 9.1 `POST /generate`

**Requête** :
```python
class Constraints(BaseModel):
    diet: list[str] = []            # ex. ["végétarien"]
    no_cookware: list[str] = []     # ex. ["pas_de_four"] -> mapping couche 2
    highlight: str | None = None    # ingrédient à mettre en avant

class GenerationRequest(BaseModel):
    hero: str                       # ingrédient héros (doit exister dans le vocab Epicure)
    cuisine: str = "italian_savory_v1"
    constraints: Constraints = Constraints()
    servings: int                   # portions cible
    model: str = "cooc"             # cooc | core (FR8)
```

**Réponse** :
```python
class DebugInfo(BaseModel):
    epicure: dict          # voisins retenus/rejetés + raisons (FR7)
    scaling: list[dict]    # par ingrédient : type, coeff, formule, raisonnement (FR7)
    techniques: list[dict] # techniques retenues / exclues (cookware interdit)
    validation: dict       # résultat du garde-fou (violations éventuelles)

class GenerationResponse(BaseModel):
    cooklang: str
    markdown: str
    debug: DebugInfo
```

- **Codes** : `200` succès ; `422` entrée invalide (héros absent du vocab, cuisine inconnue) ;
  `502`/`500` échec LLM ou violation persistante après retry (§6.2).
- **`GET /health`** : conservé (`{status, stage}`).

### 9.2 UI minimale (E2)

Page Jinja2 : formulaire (héros / cuisine / contraintes / portions) → rendu recette (`.cook` +
Markdown) + **panneau debug** (les 4 sections de `DebugInfo`). Local, navigateur (OA4). Le panneau
debug est la **vitrine portfolio** de l'explicabilité (recommandation `etude-marche.md` §6.1).

---

## 10. Structure des dossiers/fichiers (reflet de l'existant)

```
recettes/
├── app/
│   ├── __init__.py            # docstring archi 4 couches
│   ├── main.py                # FastAPI (squelette : /health) — Épic E
│   ├── epicure/               # COUCHE 1 — IMPLÉMENTÉE
│   │   ├── __init__.py
│   │   └── loader.py          # EpicureIndex.neighbors(name, k) ✔
│   ├── knowledge/             # COUCHE 2 — squelette (Épic B)
│   │   └── __init__.py
│   ├── scaling/               # COUCHE 3 — squelette (Épic C, le cœur)
│   │   └── __init__.py
│   └── generator/             # COUCHE 4 — squelette (Épic D)
│       └── __init__.py
├── tests/
│   └── test_scaling.py        # stubs @pytest.mark.skip (Épic C5)
├── notebooks/                 # calibration scaling + benchmark Epicure (.gitkeep)
├── recipes/                   # corpus de test italien via cook.md/ (.gitkeep, S0.6)
├── data/epicure/              # embeddings (GITIGNORÉ) : epicure-{cooc,core,chem}/
├── docs/
│   ├── PRD.md · pitch.md(racine) · etude-marche.md · backlog.md · recherche-ouverte.md
│   ├── architecture.md        # CE DOCUMENT
│   ├── base-technique/        # schema.md + safety-temperatures.json + cuisine-italienne.json
│   ├── scaling/               # table-scaling-sale.json
│   └── epicure/               # vocab.csv, cuisine_macroregions.json, *.parquet (index transverses)
├── requirements.txt
└── .gitignore                 # data/epicure/, .env, __pycache__/
```

> `pitch.md` est à la **racine** (pas dans `docs/`). `docs/epicure/` contient des index transverses
> aux modèles (mapping de node_id, macro-régions cuisine) distincts des poids dans `data/epicure/`.

**Modules/fichiers à créer (non encore présents)** : selon le besoin, `app/scaling/engine.py`,
`app/scaling/table.py`, `app/knowledge/loader.py`, `app/generator/prompt.py`,
`app/generator/validate.py`, `app/generator/cooklang.py`, `app/templates/` (Jinja2),
`tests/test_knowledge.py`, `tests/test_validation.py`, `tests/test_cooklang.py`. **[HYPOTHÈSE]** sur
ce découpage interne — non imposé par l'existant.

---

## 11. Stratégie de test — NFR déterminisme, Épics C5 / D2

| Cible | Type | Outil | AC / origine |
|---|---|---|---|
| Moteur de scaling | Unitaire **déterministe** (×2, ÷2, ×4) | pytest | C5 ; `test_scaling.py` (lever le `skip`) |
| `scale("sel",1,"c.à.c",2.0)` < 2 | Unitaire | pytest | C1 (sous-linéaire) |
| `scale_eggs(3, 2.0)` → 5 + note | Unitaire | pytest | C2 |
| `scale_time(20, 2.0)` ≈ 32 | Unitaire | pytest | C3 (k^(2/3)) |
| Température jamais multipliée (`fixed`) | Unitaire | pytest | C4 / `test_temperature_figee` |
| Flag non-linéarité + réserve 10 % | Unitaire | pytest | C4 |
| Loader knowledge + `techniques_for` exclut cookware interdit | Unitaire | pytest | B3/B4 |
| Validateur anti-hallucination rejette une temp/technique hors base | Unitaire (fixtures/doubles LLM) | pytest | **D2** (cœur sécurité) |
| `to_cooklang` produit un `.cook` valide (regex) | Unitaire | pytest | D3 |
| Benchmark `cooc` vs `core` (precision@k) | R&D | notebook | A2 |
| Calibration scaling (moteur vs ×N naïf) | R&D + cuisine réelle ×2/÷2 | notebook | C5, F2, `recherche-ouverte.md` §C |
| Ouverture `.cook` dans Obsidian | Manuel (capture) | — | S0.4, DoD |

**Principes** :
- Le **cœur** (scaling) et le **validateur** (sécurité) sont 100 % déterministes → couverture
  prioritaire. Le LLM, non déterministe, est **mocké** dans les tests (fixtures), sauf un test
  d'intégration optionnel marqué (clé API requise).
- **[À TRANCHER]** : CI (GitHub Actions ?) non spécifiée. **[HYPOTHÈSE]** : `pytest` local suffit en
  v1 (projet perso) ; CI = polish portfolio (Épic E/F).

---

## 12. Décisions techniques clés

| # | Décision | Options | Choix | Justification |
|---|---|---|---|---|
| D1 | Source des associations | MCP Epicure auto-hébergé / embeddings locaux | **Embeddings locaux** (numpy + safetensors) | ~2 Mo, pas d'infra, déjà implémenté (`loader.py`). pitch, `recherche-ouverte.md` §F |
| D2 | Modèle Epicure par défaut | `cooc` / `core` / `chem` | **`cooc`** (à confirmer par benchmark A2) | Associations authentiques ; `core` réservé mode « créatif » (FR8). `[À TRANCHER]` jusqu'à A2 |
| D3 | Similarité | cosine / euclidienne | **Cosine = dot-product après L2-norm** | Standard embeddings ; vecteurs bruts sur disque (`config.json`) |
| D4 | Format embeddings | safetensors / npy / csv | **safetensors** (clé `embeddings`) | Confirmé S0.1 ; le « `[A VERIFIER]` » de `requirements.txt` est levé |
| D5 | Parseur/émetteur Cooklang | binding Rust (`cooklang-rs`/PyO3) / TS / **templating maison + regex** | **Templating maison + validation regex** | Rester simple (OA4) ; éviter une dépendance native. `[À VÉRIFIER] #3` → tranché ainsi. `[À TRANCHER]` réversible si besoin |
| D6 | Moteur de scaling | natif Cooklang (`=`/×N binaire) / **moteur custom déterministe** | **Moteur custom** | Cooklang est binaire (figé/linéaire) ; la valeur du projet est le non-linéaire par ingrédient |
| D7 | Coefficients de scaling | codés en dur / **table JSON versionnée** | **Table JSON** (`table-scaling-sale.json`) | Calibrables sans toucher au code (F2) ; coeffs « de départ » à affiner |
| D8 | Rôle du LLM | générateur libre / **rédacteur sous contraintes** | **Sous contraintes** + validation post-génération | Anti-hallucination (OA2) ; LLM interchangeable (`etude-marche.md`) |
| D9 | Politique de violation LLM | réparer / **rejeter + 1 retry** / échouer | **Rejet + 1 retry, sinon erreur** `[HYPOTHÈSE]` | Coût/latence maîtrisés (NFR) ; pas de réparation silencieuse |
| D10 | Format de sortie LLM | texte libre / **structuré (JSON / tool-use)** | **Structuré** `[À TRANCHER]` | Permet validation + scaling mécaniques avant émission `.cook` |
| D11 | Modularité cuisines | code par cuisine / **loader générique `cuisine-*.json`** | **Loader générique** | OA3, Épic F1 ; ajout de cuisine sans code |
| D12 | Validation sécurité | confiance au prompt / **validation déterministe post-génération** | **Validation déterministe** | C'est elle qui *garantit* OA2, pas le prompt |
| D13 | Valeurs de sécurité | telles quelles / **vérifiées USDA/ANSES de 1ère main** | **À vérifier (S0.5)** `[À TRANCHER]` | `safety-temperatures.json` porte un disclaimer « A_VERIFIER » ; `[À VÉRIFIER] #4` ouvert |
| D14 | Filtrage cuisine des voisins | dur / **souple (annotation)** | **Souple en v1** `[HYPOTHÈSE]` | Rejet dur réservé aux contraintes matérielles/régime ; cuisine = annotation (A3) |
| D15 | Persistance des `.cook` | base de données / **fichiers + téléchargement** | **Fichiers** | Local-first ; réutilisables dans Obsidian (pas de stockage serveur) |

---

## 13. Risques & mitigations (niveau architecture)

| # | Risque | Impact | Probabilité | Mitigation architecturale |
|---|---|---|---|---|
| R1 | **Hallucination de température/technique** (sécurité) | Élevé (sécurité alimentaire) | Moyenne | Triple barrière §6 ; la **validation déterministe** (D12) est la garantie, pas le prompt ; tests D2 sur cas piégés |
| R2 | **Valeurs de sécurité non vérifiées** figées | Élevé | Réelle (disclaimer présent) | S0.5 : vérifier chaque ligne USDA/ANSES avant prod ; `critical: true` non négociable ; `[À VÉRIFIER] #4` |
| R3 | **Coefficients de scaling faux** (cœur peu crédible) | Moyen | Moyenne | Table versionnée (D7) + boucle de calibration (F2) + notebook vs ×N naïf + tests réels ×2/÷2 |
| R4 | **Héros / ingrédient hors vocabulaire Epicure** (1790 mots EN) | Moyen (UX) | Élevée | `neighbors` lève `KeyError` → API `422` explicite + suggestion ; mapping FR→EN à prévoir `[À TRANCHER]` (les noms sont en anglais `snake_case`) |
| R5 | **Sur-ingénierie** | Moyen | Moyenne | Garder le cœur = scaling + grounding ; UI minimale ; templating Cooklang plutôt que binding (D5) ; mono-process (OA4) |
| R6 | **Non-déterminisme du LLM contamine le cœur** | Moyen | Faible | Séparation stricte : rédaction (4) **avant** scaling (3) ; scaling pur sans LLM (OA1) |
| R7 | **Coût / latence LLM** | Faible | Faible | ~0,005–0,01 $/recette (NFR) ; retry limité à 1 (D9) ; pas d'appel LLM dans les tests unitaires |
| R8 | **Filtrage cuisine mal défini** (voisins hors cuisine) | Faible | Moyenne | Filtrage souple v1 (D14) ; données dispo (`cuisine_macroregions.json`, pôles) pour durcir post-A2 |
| R9 | **Ids divergents entre modèles** cooc/core/chem | Faible | Faible | `docs/epicure/vocab.csv` donne `node_id_{cooc,core,chem}` ; toujours résoudre via le `vocab.json` du modèle chargé |
| R10 | **Licence Epicure** (CC BY 4.0) non créditée | Faible (légal/portfolio) | Faible | Attribution dans README (Épic E4, DoD) : © 2026 J. Radzikowski & J. Chen, KAIKAKU.AI |

---

## Annexe — Traçabilité exigences → architecture

| Exigence | Couche / section |
|---|---|
| FR1 (saisie héros/cuisine/contraintes/portions) | §9.1 `GenerationRequest` |
| FR2 (N associations via cosine, filtrées) | Couche 1 §4.1 (A2/A3) |
| FR3 (aucune temp/technique inventée) | §6 garde-fou (D1/D2) |
| FR4 (contraintes → `#cookware` interdits) | Couche 2 §4.2 (B4) |
| FR5 (moteur de scaling + `=`/`--`) | Couche 3 §5 (Épic C) |
| FR6 (`.cook` + Markdown) | Couche 4 §8.4 (D3/D4) |
| FR7 (panneau debug) | §9.2, `DebugInfo` |
| FR8 (`cooc`/`core`) | §4.1, D2, `model` param |
| NFR sécurité | §6 (validation déterministe) |
| NFR déterminisme | §5.1, §11 |
| NFR simplicité / coût / licence | §2, OA4, R7, R10 |
