# Revue de code adversariale — Story D1

- **Story** : D1 — Prompt contraint + intégration Claude API (couche 4 `app/generator/`) — **fige les contrats partagés du sprint 4**
- **Statut entrant** : `review`
- **Date** : 2026-06-02
- **Reviewer** : agent BMAD `bmad-code-review` (rôle code-review, INDÉPENDANT du développeur)
- **Mode** : non-interactif, adversarial mais juste, lecture seule (seul fichier écrit : la présente revue)
- **Périmètre revu (uniquement les ajouts D1)** :
  - `app/generator/models.py` — le CONTRAT figé (8 dataclasses stdlib `frozen`) + `parse_structured_recipe` (+ helpers `_coerce_*`/`_parse_*`).
  - `app/generator/prompt.py` — `build_prompt(req, neighbors, techniques, safety, forbidden) -> ConstrainedPrompt` (PUR), `LLM_CONSTRAINTS`, helpers de normalisation/extraction recopiés.
  - `app/generator/client.py` — `generate_recipe(...)`, `_default_complete` (Anthropic gardé), `RecipeGenerationError`/`RecipeValidationError`.
  - `tests/test_prompt.py` (10 tests), `tests/test_client.py` (9 tests dont 1 intégration `skipif`).
  - `docs/stories/D1.md` — AC + Dev Agent Record audités.
- **Hors périmètre (non revu, sauf non-régression)** : couches 1/2/3 (`app/epicure/*`, `app/knowledge/*`, `app/scaling/*`), `app/main.py`, `app/generator/__init__.py`, `docs/base-technique/*` (lecture seule), `sprint-status.yaml`, `requirements.txt`.

---

## Vérifications empiriques

| Contrôle | Commande / méthode | Résultat |
|---|---|---|
| pytest suite complète | `python -m pytest -q` | **111 passed / 1 skipped** en 0.24 s (= 93 baseline + 18 nouveaux passants ; le `skip` = `test_integration_reelle`) ✓ |
| Conformité au chiffre annoncé | comparaison Dev Agent Record (111 passed / 1 skipped) | **exact** ✓ |
| Aucune fuite inter-couches au runtime (AC5) | import des 3 modules puis inspection `sys.modules` | `LEAKED: []` (aucun `app.epicure`/`app.knowledge`/`app.scaling`) ; `anthropic in sys.modules: False` ✓ |
| Contrat des 8 dataclasses (AC1) | introspection `dataclasses.fields` + `__dataclass_params__.frozen` | tous champs/types PEP 585/défauts/`frozen=True` **VERBATIM** au contrat D1.md (détail ci-dessous) ✓ |
| `llmConstraints` VERBATIM (AC2/§6.1) | comparaison ligne à ligne `LLM_CONSTRAINTS` ↔ `cuisine-italienne.json:122-128` | **5/5 identiques** (graphie ASCII source conservée) ✓ |
| UTF-8 sans BOM + `from __future__` | lecture binaire des 5 fichiers | 5/5 `no-BOM` + `from __future__ import annotations` présent ✓ |
| Fichiers protégés non touchés (anti-conflit) | `git status --porcelain` | working tree = uniquement les 5 fichiers neufs + `docs/stories/D1.md` ; `__init__.py`/`main.py`/`sprint-status.yaml`/`requirements.txt` (tous tracked) **non modifiés** ✓ |
| Aucune nouvelle dépendance | `git show HEAD:requirements.txt` | `anthropic` déjà présent ; aucune autre ajoutée ✓ |
| Sanity-checks modules | `python -m app.generator.{models,prompt,client}` | s'exécutent sans réseau (cohérents avec le Debug Log) ✓ |

### Détail introspection du contrat (AC1) — conformité VERBATIM

```
Quantity(frozen)        : name:str, amount:float, unit:str, fixed:bool=False
Temperature(frozen)     : value:float, unit:str, label:str
Duration(frozen)        : value:float, unit:str
Step(frozen)            : text:str, cookware:tuple[str,...]=(), temperatures:tuple[Temperature,...]=(),
                          durations:tuple[Duration,...]=(), technique_id:str|None=None
StructuredRecipe(frozen): title:str, servings:int, ingredients:tuple[Quantity,...], steps:tuple[Step,...],
                          techniques:tuple[str,...]=(), notes:tuple[str,...]=()
ConstrainedPrompt(frozen): system:str, user:str, allowed_temperatures:frozenset[float]=frozenset(),
                          allowed_cookware:frozenset[str]=frozenset(), forbidden_cookware:frozenset[str]=frozenset()
Violation(frozen)       : kind:str, detail:str, severity:str
ValidationResult(frozen): ok:bool, violations:tuple[Violation,...]=(), feedback:str=""
```

Les 8 noms de classes, les noms de champs, les types (PEP 585), les valeurs par défaut et `frozen=True` correspondent **exactement** au contrat gravé dans `D1.md` (« Contrat de données figé »). **Aucune divergence** → D2/D3/D4 peuvent importer ce module en lecture seule sans risque. C'est le point le plus critique (un écart aurait été bloquant) : il est tenu.

## Point 1 — Contrat `models.py` (AC1)

Conforme et figé. Le helper `parse_structured_recipe(payload: dict) -> StructuredRecipe` est bien une **fonction de module** (décision D1 documentée, pas `@staticmethod` de `ValidationResult`), pur, tolérant (clés manquantes → défauts sûrs ; `_coerce_float`/`_coerce_int`/`_coerce_str_tuple` écartent correctement `bool` — sous-classe d'`int` — avant les branches numériques) et construit récursivement les tuples imbriqués `Quantity`/`Step`→`Temperature`/`Duration`. Une entrée non-dict produit une recette vide cohérente plutôt qu'une exception : choix défendable (la validité incombe à la barrière 2, D2), documenté dans la docstring. **Module PUR** (aucun import `anthropic`/inter-couches — vérifié par inspection + `sys.modules`).

## Point 2 — Règle inter-couches §3.1 (AC5, CRITIQUE)

Respectée. `models.py` n'importe que stdlib. `prompt.py` importe stdlib + `app.generator.models` (même couche, autorisé) ; les annotations vers les couches 1/2 passent par `if TYPE_CHECKING:` et le code consomme les entrées en **duck-typing** (`getattr`/`dict.get`), sans aucun import runtime d'une autre couche. `client.py` n'importe que stdlib + `app.generator.models` + `anthropic` (gardé). Contrôle empirique : après import des trois modules, **aucun** `app.epicure`/`app.knowledge`/`app.scaling` n'apparaît dans `sys.modules`. Les helpers de normalisation sont **recopiés** (≈ 8 lignes stdlib), pas importés — même choix documenté qu'en A4/B3/B4. **Aucun import runtime inter-couches.**

## Point 3 — `anthropic` gardé et confiné à `client.py` (AC5)

Respecté. L'import `try: import anthropic / except ImportError: anthropic = None` (patron `app/main.py:11-14`) est présent **uniquement** dans `client.py:42-45`. `models.py` et `prompt.py` ne contiennent aucune instruction `import anthropic` (vérifié par `inspect.getsource` dans `test_import_anthropic_garde`, et reconfirmé indépendamment). `_default_complete` lève une `RecipeGenerationError` claire en français si `anthropic is None` ou si `ANTHROPIC_API_KEY` est absente — jamais déclenché en test.

## Point 4 — Pureté / déterminisme de `build_prompt` (AC2/AC6)

Confirmé. `build_prompt` n'utilise ni `random`, ni horloge, ni I/O. L'ordre des blocs suit l'ordre d'entrée ; le rendu des `parameters` est trié (`_render_parameters` trie les clés) et `forbidden_list` est trié — donc stable. `allowed_temperatures`/`allowed_cookware`/`forbidden_cookware` sont des `frozenset` (égalité ensembliste insensible à l'ordre). Le test `test_determinisme_build_prompt` exécute **60 itérations** et compare `system`/`user` ET les trois frozensets champ par champ (pas seulement `==` global) : **non tautologique** (il échouerait sur toute non-déterminisme réintroduit, p. ex. un `set` rendu sans tri dans une chaîne).

## Point 5 — Barrière 1 : verbatim + étiquetage + 4 blocs + `allowed_temperatures` (AC2/§6.1)

- **Verbatim** : les 5 `LLM_CONSTRAINTS` sont **identiques caractère pour caractère** aux `llmConstraints` de `cuisine-italienne.json:122-128` (graphie ASCII source conservée — « temperature »/« securite »… — choix correct et explicitement documenté en commentaire et dans D1.md : « verbatim » = reproduire la base telle quelle ; la prose/les docstrings du code portent les accents). `test_llm_constraints_verbatim` asserte l'inclusion des 5 lignes **plus** la présence de la consigne d'étiquetage accentuée `[SÉCURITÉ]/[TECHNIQUE]/[PRÉFÉRENCE]` (forme contrat) — la distinction verbatim-base vs prose-accentuée est donc testée des deux côtés.
- **4 blocs injectés** : Bloc 1 (associations validées — noms+scores des voisins), Bloc 2 (techniques : `id`/`name`/`category` + `parameters` rendus), Bloc 3 (sécurité : `food_type` + min °C/°F + repos + flag critique), Bloc 4 (`#cookware` interdits normalisés). Les 4 en-têtes et le contenu sont vérifiés par `test_quatre_blocs_injectes`.
- **`allowed_temperatures`** : peuplé depuis les clés `*temp*` des `parameters` (y compris décomposition d'intervalles « 82-90 » → 82.0 et 90.0 via `_numbers_in`) ET depuis les minima sécurité °C/°F. `test_allowed_et_forbidden_frozensets` couvre 100/212/82/90 (techniques) + 74/165 (sécurité). `allowed_cookware` = `required_tools` normalisés ; `forbidden_cookware == frozenset(forbidden)` normalisé. Conforme.

## Point 6 — Couture injectable + retry + échec propre (AC3/AC4/§6.2)

Conforme et bien testé sans réseau :
- `generate_recipe(prompt, complete=fake)` renvoie un `StructuredRecipe` correct **sans clé ni réseau** (`test_generate_sans_reseau` vérifie titre/servings/ingrédients/steps/températures/durées). `complete` peut aussi renvoyer directement un `StructuredRecipe` (`_to_recipe`), couvert.
- **Retry borné** : `max_retries=1` par défaut → `1 + max_retries` appels de `complete` au pire. `test_retry_reussi` prouve le retry réussi (2 appels, **feedback ciblé** transmis au 2ᵉ appel, `None` au 1ᵉ) ; `test_echec_propre_apres_retry` prouve l'échec propre (`RecipeValidationError`, 2 appels, exception portant violations/feedback) ; `test_max_retries_zero_echec_immediat` (cas piégé : 0 relance) et `test_validate_none_une_seule_generation` (1 seul appel) complètent. **Pas de réparation silencieuse** : à l'épuisement, exception claire en français (§6.2/§9.1).
- Le `feedback` est réinjecté **sans muter** le `ConstrainedPrompt` figé (la mutation se fait dans `_default_complete` sur une copie locale `user_content` ; côté boucle, seul le `feedback` est passé en argument). Cohérent avec « prompt figé ».
- **Découplage D1⟂D2** : `validate` est injecté (callable), jamais importé ; D1 ne connaît pas `validate_recipe`. Le test d'intégration réel est correctement gardé par `@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), ...)` → `skip` propre (le `1 skipped` observé).

## Point 7 — Règle anti-conflit (AC / Project Structure)

Respectée. Working tree = exactement les **5 fichiers neufs** (`models.py`, `prompt.py`, `client.py`, `tests/test_prompt.py`, `tests/test_client.py`) + `docs/stories/D1.md` (Dev Agent Record, autorisé). `app/generator/__init__.py`, `app/main.py`, `sprint-status.yaml`, `requirements.txt` (tous suivis par git) **n'apparaissent pas** comme modifiés. Les tests importent les **sous-modules directement** (`from app.generator.prompt import ...`, `from app.generator.client import ...`, `from app.generator.models import ...`), jamais via le package. Conforme.

## Point 8 — Qualité des tests / couverture des AC

Honnête et probante, non fragile :
- **AC1** couvert indirectement (le contrat est exercé par les parsings/instanciations dans `test_client.py`) et directement par l'introspection de cette revue.
- **AC2** : `test_llm_constraints_verbatim`, `test_sortie_json_structuree_demandee`, `test_quatre_blocs_injectes`, `test_allowed_et_forbidden_frozensets`, `test_neighbors_accepte_tuples`, `test_forbidden_provient_de_req_override_llm_constraints` (l'override `llm_constraints` évince le défaut — cas piégé utile).
- **AC3/AC4** : 5 tests `client` couvrant génération, retour direct `StructuredRecipe`, retry réussi, échec propre, `max_retries=0`, `validate=None`, `validate` OK du premier coup. Compteurs d'appels + assertions sur le feedback → pas de faux positif.
- **AC5** : `test_aucun_import_intercouche_runtime` (paramétré models/prompt, inspection du source) + `test_import_anthropic_garde`. Robuste.
- **AC6** : déterminisme (60 itérations) + suite verte.

Réserve d'observation (non un défaut) : `test_aucun_import_intercouche_runtime` vérifie l'absence d'imports par **recherche de sous-chaîne dans le source** (`"import app.epicure" not in source`, etc.) plutôt que par l'état de `sys.modules`. C'est moins fort qu'un contrôle dynamique (un import indirect via un helper d'une autre couche ne serait pas détecté par substring), mais la revue a fait le contrôle dynamique `sys.modules` (négatif), donc la garantie réelle est tenue. Aucune action requise.

## Point 9 — Conventions

`from __future__ import annotations` en tête des 5 fichiers ; type hints PEP 585 (`tuple[str, ...]`, `frozenset[float]`, `str | None`) ; docstrings FR à accents corrects (exception verbatim documentée pour `LLM_CONSTRAINTS`) ; dataclasses stdlib `frozen` (pas de Pydantic) ; UTF-8 **sans BOM** (5/5) ; aucune nouvelle dépendance. Conforme.

## Non-régression (hors périmètre, vérifiée)

- Suite complète : **111 passed, 1 skipped, 0 régression** (93 baseline → 93 + 18 nouveaux passants). Les nouveaux modules n'impactent aucun test existant (couche isolée).
- Règle inter-couches confirmée par `sys.modules` (aucune fuite).
- Aucun fichier hors périmètre modifié.

## Findings (par sévérité)

### Bloquants
**Aucun.**

### Majeurs
**Aucun.** (Le contrat des 8 dataclasses est conforme VERBATIM ; aucun import runtime inter-couches ; `anthropic` gardé et confiné à `client.py` ; verbatim des 5 `llmConstraints` exact ; couture injectable + retry + échec propre conformes §6.2 ; déterminisme probant ; pytest 111/1 conforme à l'annonce.)

### Mineurs / observations (defer — aucun ne remet en cause un AC)

1. **[defer] Import inutilisé `field` dans `models.py`.**
   `from dataclasses import dataclass, field` (`models.py:25`) — `field` n'est pas utilisé (aucun `field(default_factory=...)` dans le contrat figé). Cosmétique (un linter le signalerait) ; sans impact fonctionnel. Retrait possible en 1 caractère. **Defer.**

2. **[defer] Le test inter-couches s'appuie sur une recherche de sous-chaîne du source plutôt que sur `sys.modules`.**
   `test_aucun_import_intercouche_runtime` détecterait un import direct mais pas un import inter-couches *indirect*. La garantie réelle est néanmoins établie (contrôle `sys.modules` négatif en revue). Un test dynamique d'ancrage (`assert not any(m.startswith(("app.epicure","app.knowledge","app.scaling")) for m in sys.modules)` après import frais) renforcerait le garde-fou AC5. **Defer.**

3. **[defer] `allowed_cookware` non assuré par un test « package-level » dédié.**
   Couvert par `test_allowed_et_forbidden_frozensets` (vérifie `passoire` et `cuillere en bois` normalisés) — donc l'AC est testé ; observation seulement : aucun test ne verrouille la normalisation d'un ustensile à casse/accents mixtes en entrée brute distincte. Couvert empiriquement. **Defer.**

4. **[observation] `_default_complete` (chemin réel Anthropic) n'est pas testé unitairement.**
   C'est **voulu et correct** (R7 : aucun appel LLM en test ; seul `test_integration_reelle`, gardé `skipif`, l'exercerait avec clé). Noté pour mémoire, **sans le compter comme défaut**.

## Verdict

**APPROUVÉE — 0 bloquant / 0 majeur / 3 mineurs (defer) + 1 observation.**

D1 livre proprement la fondation de la couche 4. Le **contrat figé** (`models.py`, 8 dataclasses `frozen`) est conforme **VERBATIM** au contrat de D1.md (introspection des champs/types PEP 585/défauts/`frozen=True`) : D2/D3/D4 peuvent l'importer en lecture seule sans risque de redéfinition. La **règle inter-couches §3.1** est strictement respectée (aucun import runtime de `app.epicure`/`app.knowledge`/`app.scaling` — confirmé par `sys.modules` vide ; annotations en `TYPE_CHECKING`, helpers recopiés). `anthropic` est importé de façon **gardée et uniquement dans `client.py`** ; `models.py`/`prompt.py` restent purs. La **Barrière 1** est correctement réalisée : 5 `llmConstraints` reprises **verbatim** du JSON source, étiquetage `[SÉCURITÉ]/[TECHNIQUE]/[PRÉFÉRENCE]`, 4 blocs injectés, `allowed_temperatures` peuplé depuis `parameters` (intervalles décomposés) + minima sécurité. `build_prompt` est **pur et déterministe** (test à 60 itérations, non tautologique). La **couture injectable** permet de tester `generate_recipe` sans réseau ni clé ; la **boucle retry (1 max)** réinjecte un feedback ciblé sans muter le prompt et échoue **proprement** (exception FR, pas de réparation silencieuse), avec test d'intégration réel correctement gardé par `skipif`. La règle **anti-conflit** est tenue (5 fichiers + story uniquement ; `__init__.py`/`main.py`/`sprint-status.yaml`/`requirements.txt` non touchés ; imports directs des sous-modules). Aucune nouvelle dépendance ; UTF-8 sans BOM ; `from __future__ import annotations` partout.

pytest réel : **111 passed, 1 skipped, 0 régression** — conforme à l'annonce du Dev Agent Record.

Les 3 findings mineurs (`field` inutilisé, test inter-couches par substring, ancrage `allowed_cookware`) sont cosmétiques/renforçants et ne remettent en cause aucun AC.

**Recommandation : D1 peut passer en `done`.** L'orchestrateur fusionnera ensuite les exports de la couche 4 dans `app/generator/__init__.py` (`Quantity`, `Temperature`, `Duration`, `Step`, `StructuredRecipe`, `ConstrainedPrompt`, `Violation`, `ValidationResult`, `parse_structured_recipe`, `build_prompt`, `LLM_CONSTRAINTS`, `generate_recipe`, `RecipeGenerationError`, `RecipeValidationError`) et débloquera D2/D3/D4.
