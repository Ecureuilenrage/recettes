# Revue de code adversariale — Story E2

- **Story** : E2 — UI minimale (formulaire + rendu + panneau debug) (épic E — API web & UI, `app/main.py` + `templates/`) — sprint 5
- **Statut entrant** : `review`
- **Date** : 2026-06-02
- **Reviewer** : agent BMAD `bmad-code-review` (rôle « code-review », INDÉPENDANT du dev — couches Blind Hunter / Edge Case Hunter / Acceptance Auditor + triage)
- **Mode** : non-interactif, lecture seule (seul fichier écrit : la présente revue ; le code N'EST PAS corrigé)
- **Périmètre revu (ajouts E2 uniquement)** :
  - `app/main.py` — portion UI : helper PUR `build_view_context(result, *, form=None, error=None)` + helpers `_debug_to_dict`/`_request_from_form` + constantes `DEFAULT_FORM`/`DEBUG_SECTION_LABELS` ; routes `GET /` (`ui_form`) et `POST /generate-ui` (`ui_generate`) sous garde `if FastAPI is not None:` puis `if Jinja2Templates is not None:` ; import GARDÉ `fastapi.templating.Jinja2Templates`.
  - `templates/base.html`, `templates/index.html`, `templates/result.html` — NOUVEAUX.
  - `tests/test_ui.py` — NOUVEAU (7 tests).
  - `docs/stories/E2.md` — AC + Tasks + Dev Agent Record audités.
- **Hors périmètre (non revu, sauf NON-RÉGRESSION)** : la logique E1 (`run_pipeline`, schémas Pydantic/dataclass, exceptions, `POST /generate`, `GET /health`) et les 4 couches métier (`app/epicure|knowledge|scaling|generator/*`), `tests/test_main.py`, `tests/test_scaling_validation.py`, `sprint-status.yaml`, `requirements.txt`, `README.md`/`NOTICE`.

---

## Verdict

**APPROUVÉE — 0 bloquant / 0 majeur / 3 mineurs (defer).**

L'UI minimale est conforme à l'archi §9.2 : `GET /` rend un formulaire héros/cuisine/contraintes/portions/modèle ; `POST /generate-ui` RÉUTILISE `run_pipeline` (aucune réécriture, aucune logique métier ajoutée) et rend une page avec le `.cook`, le Markdown ET un panneau debug présentant les **4 sections** `DebugInfo` (epicure / scaling / techniques / validation) — vitrine d'explicabilité. Le helper `build_view_context` est PUR et testable sans fastapi/jinja2 ; les imports fastapi/jinja2 sont GARDÉS ; les tests HTTP sont gardés par `pytest.importorskip`. Le chemin d'erreur (422/502/inattendu) affiche un message lisible en page 200 sans crash. E1 est NON régressée (run_pipeline / schémas / `/generate` / `/health` intacts ; `tests/test_main.py` 11 passed / 2 skipped). Suite complète : **197 passed / 7 skipped** (attendu en l'absence de fastapi/jinja2), **0 régression**.

---

## Vérifications empiriques

| Contrôle | Commande / méthode | Résultat |
|---|---|---|
| pytest module E2 | `python -m pytest tests/test_ui.py -q` | **3 passed / 4 skipped** (0.16 s) — 3 offline helper + 4 HTTP gardés `importorskip` ✓ |
| pytest suite complète | `python -m pytest -q` | **197 passed / 7 skipped** (1.46 s) — conforme à l'attendu (fastapi/jinja2 absents), 0 régression ✓ |
| Non-régression E1 | `python -m pytest tests/test_main.py -q` | **11 passed / 2 skipped** ✓ |
| 7 skips = composition attendue | lecture des gardes | 1 Claude (clé) + 2 TestClient E1 + 4 UI HTTP E2 = 7 ✓ |
| Imports runtime de `app/main.py` (AST, contrôle INDÉPENDANT) | `ast.walk` sur le source | `app.epicure`, `app.generator`, `app.knowledge`, `app.scaling` (les 4 couches) + `__future__`, `dataclasses`, `typing`, `os`, `fastapi`, `fastapi.responses`, `fastapi.templating`, `pydantic` — **AUCUN nouvel import de couche métier** par E2 ✓ |
| `app/main.py` SEUL à importer les 4 couches | AST scan des 4 packages | Aucun import inter-couches AU RUNTIME (le seul `app.knowledge.loader` dans `generator/validate.py` est sous `TYPE_CHECKING`, annotation statique uniquement — code D4 hors périmètre, correctement gardé) ✓ |
| Encodage / fins de ligne (6 fichiers E2) | lecture binaire | UTF-8 **sans BOM**, **LF** pour `main.py` + 3 templates + `test_ui.py` + `E2.md` ✓ |
| Accents FR templates | lecture | « Épicure », « Génération », « héros », « Préparation », « Sévérité » corrects ✓ |
| Autoescape (XSS reflété) | lecture + comportement Jinja2 | `Jinja2Templates` autoescape `.html` par défaut → `{{ error }}` et `{{ form.hero }}` (saisie réfléchie) échappés ✓ |
| Robustesse `build_view_context` (erreur / debug=None) | exécution offline | `error` → `ok=False`, sections debug vides `{}`/`[]` ; `debug=None` → aplati en 4 sections vides, **pas de KeyError** ✓ |

## 1. UI conforme §9.2 (formulaire → rendu + panneau debug 4 sections)

- **`GET /` (`ui_form`, `app/main.py:723-733`)** rend `index.html` avec `DEFAULT_FORM`. `templates/index.html` porte un `<form method="post" action="/generate-ui">` avec **héros** (`name="hero"`, requis), **cuisine** (`<select>` défaut `italian_savory_v1`), **portions** (`name="servings"`, nombre, défaut 4), **modèle** (`<select>` cooc/core) et les **contraintes** régime / sans-matériel / mettre-en-avant (champs texte). Conforme AC1. ✓
- **`POST /generate-ui` (`ui_generate`, `app/main.py:735-799`)** : lit le form via `Form(...)`, construit un `GenerationRequest` via `_request_from_form`, appelle `run_pipeline(gen_request, complete=..., index=...)` (RÉUTILISÉ via les coutures `Depends(get_index)`/`Depends(get_complete)` E1), puis rend `result.html` via `build_view_context`. Conforme AC2. ✓
- **Panneau debug 4 sections** : vérifié dans le helper ET le template.
  - `build_view_context` → `_debug_to_dict` (`app/main.py:572-585`) aplatit EXACTEMENT `epicure`/`scaling`/`techniques`/`validation` (lecture souple, aucun recalcul).
  - `templates/result.html` rend les 4 sections étiquetées : Section 1 Épicure (retenus/rejetés, `:29-54`), Section 2 Scaling (par ingrédient : type/coeff/formule/valeur/raisonnement, `:56-76`), Section 3 Techniques (retenues/exclues + outil interdit/contrainte, `:78-98`), Section 4 Validation (ok/violations/feedback, `:100-119`). Vitrine d'explicabilité satisfaite. ✓
- `.cook` et Markdown rendus en `<pre>` (`result.html:17-25`). Conforme à la décision sobre v1 documentée. ✓

## 2. E2 N'ajoute AUCUNE logique métier

- Aucun nouvel import de couche métier par E2 (AST : les 4 imports de couches sont ceux d'E1 ; E2 n'ajoute que `os`, `fastapi.templating`, `fastapi.Form/Request/responses`). ✓
- `build_view_context`/`_debug_to_dict` : pur APLATISSEMENT/présentation des champs déjà produits par `run_pipeline` (cooklang, markdown, 4 sections). Aucun scaling/validation/cosine réinventé. ✓
- `_request_from_form` (`app/main.py:642-673`) : glu de PRÉSENTATION uniquement (découpe `diet`/`no_cookware` par virgule/saut de ligne, `highlight` vide → `None`) ; la VALIDATION (héros hors vocab, cuisine inconnue) reste DÉLÉGUÉE à `run_pipeline`. ✓
- Templates : présentation pure (HTML/CSS + boucles d'affichage), aucun calcul. ✓

## 3. E1 NON régressée + règle inter-couches

- **`run_pipeline` (`app/main.py:244-505`)**, schémas (`Constraints`/`GenerationRequest`/`DebugInfo`/`GenerationResponse`, `:115-183`), exceptions (`PipelineInputError`/`PipelineGenerationError`, `:192-201`), `GET /health` (`:679-682`) et `POST /generate` (`:684-707`) sont INCHANGÉS : les ajouts E2 sont strictement additifs, placés APRÈS l'API JSON, sous la garde jinja2. Vérifié par lecture intégrale du fichier. ✓
- Non-régression confirmée empiriquement : `tests/test_main.py` **11 passed / 2 skipped** ; `test_health_et_generate_intacts` (E2) vert quand les deps sont installées (rapport dev 203 passed / 1 skipped — mentionné, non re-vérifié faute de deps). ✓
- **`app/main.py` reste le SEUL module important les 4 couches AU RUNTIME** (AST). Les couches ne s'importent pas entre elles au runtime ; le seul `app.knowledge.loader` repéré dans `generator/validate.py` est sous bloc `TYPE_CHECKING` (annotation statique, jamais exécuté — code D4 hors périmètre, conforme §3.1). ✓

## 4. Testabilité / garde fastapi-jinja2

- Import GARDÉ `try: from fastapi.templating import Jinja2Templates except ImportError: Jinja2Templates = None` (`app/main.py:97-100`) ; extension de la garde fastapi à `Form`/`Request`/`HTMLResponse` (`:82-90`). Si fastapi OU jinja2 absent, ni `app` ni pages HTML ne sont construits, mais `run_pipeline` ET `build_view_context` restent importables. ✓
- `build_view_context` est PUR (aucune I/O, aucun jinja2/HTTP) et testé OFFLINE (`test_build_view_context_*`, construit `GenerationResponse`/`DebugInfo` à la main). ✓
- Tests TestClient/HTTP gardés par `pytest.importorskip("fastapi")` (+ `jinja2`) → skip propre (constaté : 4 skips). ✓
- AUCUN appel LLM/réseau/clé : les tests POST injectent un faux `complete` + un faux `index` via `app.dependency_overrides` (patron `test_main.py`), `try/finally: clear()`. ✓

## 5. Robustesse UI (chemin d'erreur lisible, pas de crash)

- `ui_generate` enveloppe l'appel pipeline dans un `try/except` triple (`app/main.py:766-797`) :
  - `PipelineInputError` → message « Entrée invalide (422) … » ;
  - `PipelineGenerationError` → message « Échec de génération (502) … » ;
  - `Exception` (garde-fou) → « Erreur inattendue … » — aucune 500 nue.
- Dans tous les cas : `build_view_context(None, form=form_echo, error=…)` → `result.html` rendu en **HTTP 200** avec un message lisible (`<div class="alert">`) et la saisie CONSERVÉE (`result.html:8-14`), pas de recette. Conforme AC3. ✓
- Vérifié empiriquement : `build_view_context(None, error=…)` produit `ok=False` + sections debug vides ; `test_erreur_entree_affichee` confirme 200 + message « 422 »/« invalide ». ✓

## 6. Tests probants

7 tests, asserts CIBLÉS (pas « ne plante pas ») :

- `test_build_view_context_4_sections_debug` — vérifie cooklang/markdown ET les 4 sections aplaties avec valeurs précises (`debug["epicure"]["kept"][0]["name"] == "basil"`, `rejected[0]["reason"]`, `scaling[0]["type"]`, `techniques["kept"]`, `excluded[0]["forbidden_tool"]`, `validation["ok"]`) + libellés des 4 sections. Non tautologique. ✓
- `test_build_view_context_erreur_sans_crash` — `ok=False`, message contenant « 422 », saisie conservée, sections debug vides. ✓
- `test_build_view_context_form_par_defaut` — valeurs par défaut quand `form=None`. ✓
- `test_get_form` (gardé) — GET `/` → 200, présence de `<form`, `name="hero"`, `name="servings"`, `name="cuisine"`. ✓
- `test_post_form_rend_recette_et_debug` (gardé, faux deps) — 200 ; présence du titre Markdown « Spaghetti à la tomate », de la valeur scalée « 400 », ET des 4 libellés Épicure/Scaling/Techniques/Validation. ✓
- `test_erreur_entree_affichee` (gardé) — héros invalide → 200 + message lisible. ✓
- `test_health_et_generate_intacts` (gardé) — non-régression E1 : `/health` 200 + `/generate` JSON 200 avec les 4 sections debug. ✓

## 7. Conventions

- `from __future__ import annotations` ✓ ; type hints PEP 585 ✓ ; docstrings/commentaires FR accentués corrects ✓ ; identifiants snake_case ✓ ; UTF-8 sans BOM, LF (6 fichiers) ✓.
- Templates : `lang="fr"`, `charset="UTF-8"`, CSS inline sobre (portfolio), aucune dépendance front. ✓
- Aucune nouvelle dépendance (jinja2/python-multipart déjà dans `requirements.txt`, non modifié). ✓
- Règle anti-conflit : EXACTEMENT les 6 fichiers attendus touchés par E2 (`app/main.py` étendu + 3 templates + `tests/test_ui.py` + `docs/stories/E2.md`). Tests E2 importent `app.main` directement. ✓

## Findings (par sévérité)

### Bloquants
Aucun.

### Majeurs
Aucun. (UI conforme §9.2 avec panneau debug 4 sections ; aucune logique métier ajoutée ; E1 non régressée — vérifiée par lecture + AST + `test_main.py` vert ; chemin d'erreur lisible sans crash ; imports gardés ; tests probants ; suite verte sans régression.)

### Mineurs / observations

1. **[defer] Section `techniques` du panneau debug : la forme `dict` est la seule réellement supportée par le template.**
   Le schéma annonce `techniques: list[dict] | dict` (`DebugInfo`), mais `result.html` accède toujours à `debug.techniques.kept` / `.excluded` (`:82,88`). En pratique `run_pipeline` produit TOUJOURS un `dict {kept, excluded}` (`app/main.py:472-482`), donc aucun problème réel. Si la valeur était un jour une `list`, l'accès `.kept` rendrait `Undefined` (falsy) → branche « (aucune technique) » sans crash. **Impact nul en v1.** Defer (harmoniser l'annotation `list[dict] | dict` → `dict` un jour pour lever l'ambiguïté de contrat).

2. **[defer] Bornes `servings` uniquement côté client (HTML `min="1" max="100"`).**
   Le `<input type="number" min max>` (`index.html:22`) n'est qu'un garde-fou navigateur ; un POST direct hors bornes (ou `servings=0`) contourne la validation HTML. Le pipeline reste robuste (`base_servings = recipe.servings if recipe.servings else 1` évite la division par zéro côté recette ; un `servings` cible de 0 produirait simplement des quantités nulles, pas un crash). Aucun AC n'exige de validation serveur des portions. **Impact cosmétique/robustesse mineure.** Defer.

3. **[defer] `result.html` ne distingue pas visuellement le `.cook` du Markdown au-delà du titre `<h2>` ; les deux sont des `<pre>` au même rendu.**
   Décision sobre v1 documentée (Markdown affiché tel quel, pas de rendu HTML pour éviter une dépendance). Lisible et fidèle, mais un lecteur non averti pourrait confondre les deux blocs. **Cosmétique, conforme à la décision figée.** Defer (rendu Markdown HTML éventuel post-v1).

## Résultat pytest (réel)

- `python -m pytest tests/test_ui.py -q` → **3 passed / 4 skipped** (0.16 s) — 3 offline (helper) + 4 HTTP gardés `importorskip`.
- `python -m pytest tests/test_main.py -q` → **11 passed / 2 skipped** — non-régression E1 confirmée.
- `python -m pytest -q` → **197 passed / 7 skipped** (1.46 s) — baseline 194 passed + 3 nouveaux tests offline E2 ; 7 skips = 1 Claude (clé) + 2 TestClient E1 + 4 UI HTTP E2 (gardés `importorskip`, fastapi/jinja2 absents dans cet environnement). **0 régression.** Comportement ATTENDU (skip propre), PAS un défaut.
- Validation dev avec deps installées (fastapi 0.136.3 / jinja2 3.1.6 / starlette 1.2.1 / python-multipart) rapportée : `tests/test_ui.py` → **7 passed** ; suite → **203 passed / 1 skipped**. Mentionné sans re-vérification (deps non installées ici, conforme à la consigne).

## Recommandation

**E2 peut passer en `done`.** L'UI minimale est conforme à l'archi §9.2 (formulaire héros/cuisine/contraintes/portions → rendu `.cook` + Markdown + panneau debug 4 sections = vitrine d'explicabilité), RÉUTILISE `run_pipeline` (E1) sans le réécrire ni ajouter de logique métier, n'a pas régressé E1 (run_pipeline / schémas / `/generate` / `/health` intacts ; `test_main.py` vert), garde les imports fastapi/jinja2 (helper `build_view_context` pur et testable offline ; tests HTTP gardés par `importorskip`), affiche les erreurs pipeline lisiblement sans crash, et respecte la règle inter-couches (§3.1, AST) et anti-conflit (6 fichiers). Les 3 findings mineurs sont `defer` (annotation `techniques`, bornes `servings` serveur, distinction visuelle .cook/Markdown) et ne remettent en cause aucun AC.

Étapes orchestrateur post-revue : passer E2 en `done`. À E1, E2, E3, E4 tous `done` → **v1 livrable en local** (FastAPI + UI Jinja2 + validation + polish), **fin du sprint 5**.
