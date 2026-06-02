# Revue de code adversariale — Story E1

- **Story** : E1 — FastAPI + endpoint `/generate` (l'ASSEMBLEUR du pipeline) — **PREMIÈRE story du sprint 5**
- **Statut entrant** : `review`
- **Date** : 2026-06-02
- **Reviewer** : agent BMAD `bmad-code-review` (rôle « code-review », INDÉPENDANT du dev — angles Blind Hunter / Edge Case Hunter / Acceptance Auditor + triage)
- **Mode** : non-interactif, lecture seule (seul fichier écrit : la présente revue ; le code N'EST PAS corrigé)
- **Périmètre revu (ajouts E1 uniquement)** :
  - `app/main.py` — RÉÉCRITURE : schémas Pydantic (+ fallback dataclasses), `run_pipeline`, exceptions d'orchestration, enveloppe FastAPI mince (`/health` + `POST /generate`), coutures `get_index`/`get_complete`, sanity-check.
  - `tests/test_main.py` — NOUVEAU, 10 tests (8 offline + 2 HTTP gardés).
  - `docs/stories/E1.md` — AC + Tasks + Dev Agent Record audités.
- **Hors périmètre (non revu, sauf non-régression §3.1)** : les 4 couches `app/epicure|knowledge|scaling|generator/*` et leurs `__init__.py`.

---

## Verdict

**CHANGES REQUESTED — 0 bloquant / 2 majeurs / 2 mineurs (defer).**

L'ossature de l'assembleur est solide et CONFORME sur l'essentiel : `app/main.py` est bien le SEUL module à importer les 4 couches (AST), les couches ne s'importent toujours pas entre elles au RUNTIME (le seul import inter-couches `generator → knowledge` est sous `TYPE_CHECKING`, donc hors runtime — non-régression OK), `run_pipeline` câble l'ordre §7 (rédaction AVANT scaling), la couture retry `validate=validate_recipe`/`max_retries=1` est en place, le mapping d'erreurs 422/502/500 est correct, et `run_pipeline` est testable OFFLINE (faux `complete` + faux `index`, aucun réseau/clé/donnée). Suite complète : **191 passed / 3 skipped, 0 régression**.

**MAIS** l'assemblage final des deux artefacts émis (`.cook` et Markdown) est **incohérent** : E1 passe la recette de BASE à `to_cooklang` et une recette PARTIELLEMENT scalée (ingrédients scalés mais `servings` inchangé) à `to_markdown`. Conséquences vérifiées empiriquement : (1) le frontmatter `.cook` (`servings: 2`) ET l'en-tête Markdown (`Portions : 2`) déclarent les portions de BASE alors que les quantités sont scalées vers la CIBLE (4) → sortie auto-contradictoire ; (2) les œufs valent 2 dans le `.cook` mais 3 dans le Markdown → les deux artefacts livrés se contredisent. Ces deux défauts touchent le livrable principal et bloquent un passage propre en `done`.

---

## Vérifications empiriques

| Contrôle | Commande / méthode | Résultat |
|---|---|---|
| pytest module E1 | `python -m pytest tests/test_main.py -q` | **8 passed / 2 skipped** (0.16 s) — 2 skip = TestClient gardés (`fastapi` absent) ✓ |
| pytest suite complète | `python -m pytest -q` | **191 passed / 3 skipped** (1.43 s) — 0 régression ✓ |
| Imports runtime `app/main.py` (AST indépendant) | `ast.walk` | `__future__, app.epicure, app.generator, app.knowledge, app.scaling, dataclasses, fastapi, pydantic, typing` — importe bien LES 4 COUCHES ✓ |
| Couches ⇏ couches (AST, hors `TYPE_CHECKING`) | `ast` en ignorant les blocs `if TYPE_CHECKING:` | epicure/knowledge/scaling/generator : **RUNTIME cross-layer = NONE** ✓ (l'import `generator/validate.py → app.knowledge.loader` est sous `TYPE_CHECKING`, annotations seules) |
| Signature `run_pipeline` | `inspect.signature` | `(request, *, complete=None, index=None) -> 'GenerationResponse'` — couture injectable conforme ✓ |
| Encodage / fins de ligne | lecture binaire | `app/main.py` + `tests/test_main.py` : UTF-8 **sans BOM**, **LF** ✓ |
| Signatures câblées (couches) | `inspect.signature` | `generate_recipe(prompt, complete, validate, max_retries)`, `scale(name,qty,unit,k)`, `scale_eggs(count,k)`, `to_cooklang(recipe, scaling_notes)`, `to_markdown(recipe)`, `validate_recipe(recipe, techniques, safety, forbidden)` — tous appelés conformément ✓ |
| Sortie réelle (succès, servings cible 4 / base 2) | exécution `run_pipeline` | spaghetti 200→**400** (linéaire), sel 10→**16.82** (sous-linéaire) ✓ ; **MAIS** `.cook` `servings: 2` + Markdown `Portions : 2` (cf. Majeur 1) ✗ |
| Sortie réelle (œufs discrets) | exécution `run_pipeline` | debug `type=discrete`, Markdown `- 3 oeufs` ; **MAIS** `.cook` `@oeufs{2%}` (cf. Majeur 2) ✗ |

## 1. Rôle assembleur (CRITIQUE, archi §3.1) — RESPECTÉ

Contrôle adversarial INDÉPENDANT par AST (et non par lecture seule) :

- `app/main.py` importe bien `app.epicure`, `app.knowledge`, `app.scaling`, `app.generator` — c'est le SEUL module qui assemble les 4 couches. ✓
- Non-régression de la règle « les couches ne s'importent pas entre elles » : analyse AST des 4 couches en **excluant les blocs `if TYPE_CHECKING:`**. Résultat : **aucun** import runtime inter-couches. Le seul import inter-couches trouvé (`app/generator/validate.py:64 → app.knowledge.loader import SafetyStandard, SafetyTable, Technique`) est SOUS `if TYPE_CHECKING:` (`validate.py:59`, `# pragma: no cover - annotations seulement`) : il n'est JAMAIS exécuté au runtime (les types sont reçus en paramètres, duck-typés). Conforme §3.1. ✓

## 2. ZÉRO logique métier dans E1 — GLOBALEMENT RESPECTÉ (une nuance)

- Aucun calcul de scaling maison (appel `scale`/`scale_eggs`), aucune validation maison (appel `validate_recipe`), aucun cosine, aucun parsing de température. ✓
- La « glu » est limitée à : lecture duck-typée de la requête (`_req_get`/`_read_constraints`), conversion vers les deux dataclasses `Constraints` (couche 1 + couche 2), assemblage du `DebugInfo`, mapping d'erreurs. Glu autorisée (§3.1). ✓
- **Nuance (liée aux majeurs)** : `_is_egg` (`main.py:215-222`) est une heuristique métier embryonnaire (détection « oeuf »). Elle est documentée et nécessaire à l'aiguillage `scale_eggs` vs `scale` côté orchestrateur ; ce n'est pas du calcul de quantités. Acceptable, mais c'est précisément ce branchement œuf qui introduit l'incohérence Majeur 2 (l'œuf n'est jamais ajouté aux `scaling_notes` du `.cook`).

## 3. Pipeline complet câblé + ORDRE rédaction-avant-scaling — RESPECTÉ (ordre OK ; assemblage final défaillant)

- L'ordre §7 est respecté : `translate` → vérif cuisine → `neighbors` → `filter_neighbors` → `techniques_for`/`forbidden_cookware`/`load_safety` → `build_prompt` → `generate_recipe(validate=…, max_retries=1)` → **scaling APRÈS rédaction** (`k = servings / recipe.servings`, `main.py:361-362`) → `to_cooklang`/`to_markdown` → `DebugInfo`. ✓ L'isolation du non-déterminisme LLM (OA1, §7) est respectée.
- **Défaut d'assemblage (cf. Majeurs 1 & 2)** : à l'étape (i), `to_cooklang` reçoit la recette de BASE (`recipe`, `main.py:413`) tandis que `to_markdown` reçoit `scaled_recipe` (`main.py:414`). Or `scaled_recipe = dataclasses.replace(recipe, ingredients=…)` (`main.py:408-410`) remplace les ingrédients SANS mettre à jour `servings`. Résultat : trois échelles cohabitent dans les sorties (frontmatter/portions de BASE, quantités non-œufs de la CIBLE dans le `.cook` via `scaling_notes`, quantités CIBLE dans le Markdown via `scaled_recipe`, mais œufs de BASE dans le `.cook`). Voir Findings.

## 4. `validate_recipe` câblé en callback de retry — RESPECTÉ

- `main.py:345-354` : `_validate(recipe) = validate_recipe(recipe, techniques, safety, forbidden_frozen)` est passé à `generate_recipe(prompt, complete=complete, validate=_validate, max_retries=1)`. La couture rejet → 1 retry → échec propre est bien déléguée à la couche 4 (qui l'implémente, `client.py`). ✓
- `test_violation_persistante_502` prouve empiriquement le chemin échec : un faux `complete` violant à CHAQUE appel (999 °C) → `RecipeValidationError` → `PipelineGenerationError`. ✓
- Observation (mineur, defer) : `_validate(recipe)` est ré-appelé une 2ᵉ fois pour le panneau debug (`main.py:432`). Sur la recette déjà validée avec succès, c'est déterministe et sans effet de bord → recalcul redondant, pas un bug.

## 5. Erreurs → codes HTTP — RESPECTÉ

- `translate` `KeyError` → `PipelineInputError` (`main.py:285-288`) ; cuisine absente de `load_cuisines()` → `PipelineInputError` (`main.py:292-296`) ; `neighbors` `KeyError` → `PipelineInputError` (`main.py:304-307`) ; `RecipeValidationError`/`RecipeGenerationError` → `PipelineGenerationError` (`main.py:355-358`). ✓
- Enveloppe FastAPI (`main.py:509-518`) : `PipelineInputError`→422, `PipelineGenerationError`→**502**, `Exception`→500, succès→200. ✓
- `GET /health` CONSERVÉ (`{status:"ok", stage:"pipeline"}`, `main.py:490-493`). ✓
- Tests : `test_hero_absent_vocab_422`, `test_hero_absent_index_422`, `test_cuisine_inconnue_422` (422) ; `test_violation_persistante_502` (502) ; `test_generate_endpoint` (200 + 422 via TestClient). ✓

## 6. Testabilité (R7) — RESPECTÉE

- `run_pipeline` est appelable SANS fastapi, SANS clé, SANS réseau, SANS données Epicure : faux `complete` + faux `index` injectés (`test_main.py`). ✓
- `index=None` → `EpicureIndex(model)` paresseux (jamais atteint en test) ; `complete=None` → Anthropic réel (jamais atteint en test). ✓
- Les 2 tests TestClient sont gardés `pytest.importorskip("fastapi")` (`test_main.py:254,270`) → skip propre (`fastapi` non installé ici) — comportement ATTENDU, pas un défaut. ✓
- AUCUN test n'exige `ANTHROPIC_API_KEY` ni `data/epicure/`. `test_aucune_logique_metier_ni_appel_reel` vérifie même `"anthropic" not in sys.modules` après exécution. ✓

## 7. Tests probants (non tautologiques) — GLOBALEMENT BONS (une lacune liée aux majeurs)

- `test_run_pipeline_succes` : asserts ciblés (titre dans le markdown, 4 sections debug, `validation.ok is True`). ✓
- `test_scaling_applique` : **chiffré** — spaghetti `type=linear`, valeur ≈ 400 (`abs(... - 400) < 1e-6`) ; sel `type=sublinear`, `10 < value < 20` (verrouille le sous-linéaire) ; `"400" in cooklang` ET `"400" in markdown`. Probant. ✓
- `test_scaling_oeufs_discrets` : œufs `type=discrete`, `value == 3.0`. Probant côté debug/markdown. ✓
- **Lacune (cause des majeurs non détectés)** : AUCUN test n'asserte le `servings`/`Portions` émis dans le `.cook` ou le Markdown, ni la cohérence de la quantité d'œufs ENTRE le `.cook` et le Markdown. `test_scaling_applique` ne vérifie « 400 » que pour le spaghetti (non-œuf, présent dans `scaling_notes`) ; `test_scaling_oeufs_discrets` ne lit que `debug.scaling`, jamais le `.cook`. Les deux incohérences (Majeurs 1 & 2) passent donc sous le radar des asserts existants.

## 8. Conventions — RESPECTÉES

- `from __future__ import annotations` ✓ ; PEP 585 (`list[dict]`, `str | None`) ✓ ; docstrings/commentaires FR accentués ✓ ; UTF-8 sans BOM, LF ✓ ; imports gardés fastapi/pydantic + fallback dataclasses ✓ ; bloc `if __name__ == "__main__":` (sanity-check hors réseau) ✓.
- Schémas §9.1 conformes (`Constraints`/`GenerationRequest`/`DebugInfo`/`GenerationResponse`, champs/défauts) sous import gardé + fallback dataclasses. ✓

## Findings (par sévérité)

### Bloquants
Aucun.

### Majeurs

1. **Portions émises incohérentes avec les quantités scalées (`.cook` ET Markdown).**
   `run_pipeline` scale les quantités vers la CIBLE (`k = servings / recipe.servings`) mais émet les deux artefacts avec le `servings` de BASE :
   - `to_cooklang(recipe, scaling_notes=…)` (`main.py:413`) reçoit la recette de BASE → frontmatter `servings: 2` ;
   - `to_markdown(scaled_recipe)` (`main.py:414`) où `scaled_recipe = dataclasses.replace(recipe, ingredients=…)` (`main.py:408-410`) ne met PAS à jour `servings` → en-tête `**Portions : 2**`.

   Vérification empirique (requête `servings=4`, recette de base `servings=2`) : le `.cook` affiche `servings: 2` avec `@spaghetti{400%g}` (quantité pour 4) et le Markdown affiche `**Portions : 2**` avec `- 400 g spaghetti`. **La sortie déclare 2 portions tout en listant des quantités pour 4** — auto-contradictoire et trompeur pour l'utilisateur. L'exemple `.cook` de l'archi §7 (frontmatter `servings: 4`) et le sens même du scaling (`servings_cible`, §7 étape 6) impliquent que la sortie reflète la CIBLE. **Correctif attendu (côté E1, sans toucher aux couches)** : passer une recette dont `servings` = `request.servings` aux émetteurs, p.ex. `dataclasses.replace(recipe, servings=servings, ingredients=…)` pour le Markdown, et fournir au `.cook` une recette à `servings` cible. À ajouter : un test ancrant `servings: 4` dans le `.cook` et `Portions : 4` dans le Markdown.

2. **Quantité d'œufs DIVERGENTE entre `.cook` (base) et Markdown (scalée).**
   Les œufs sont scalés via `scale_eggs` et l'ingrédient scalé n'est ajouté QU'À `scaled_ingredients` (→ Markdown), jamais à `scaled_quantities` (`main.py:385-387` vs la branche non-œuf `main.py:390`). Comme `to_cooklang` reçoit la recette de BASE et que la note de scaling des œufs n'est PAS dans `scaling_notes`, le `.cook` conserve la quantité de BASE.

   Vérification empirique (2 œufs, `k=2`) : Markdown → `- 3 oeufs` ; `.cook` → `@oeufs{2%}`. **Les deux artefacts livrés se contredisent sur la quantité d'œufs**, et le scaling discret RZ1 (la valeur clé du livrable) est PERDU dans le `.cook` — or le `.cook` est l'artefact téléchargeable/réutilisable (§7 étape 8). **Correctif attendu (côté E1)** : émettre le `.cook` à partir d'une recette aux ingrédients scalés (œufs inclus), ou injecter une note de scaling œufs dans `scaling_notes` ; ajouter un test comparant la quantité d'œufs entre `.cook` et Markdown.

> Cause racine commune : l'incohérence entre la recette passée à `to_cooklang` (BASE) et celle passée à `to_markdown` (ingrédients partiellement scalés, `servings` de base). Un correctif unique — construire UNE recette scalée canonique (`servings` cible + tous les ingrédients scalés, œufs inclus) et l'utiliser pour les DEUX émetteurs — règle les deux majeurs.

### Mineurs / observations (defer)

1. **[defer] Double appel de `validate_recipe`.** `_validate(recipe)` est ré-exécuté pour le panneau debug (`main.py:432`) après l'avoir été dans `generate_recipe`. Déterministe et sans effet de bord → recalcul redondant (coût négligeable). Pourrait être mémoïsé si `generate_recipe` exposait le `ValidationResult`. Non bloquant.

2. **[defer] `_is_egg` heuristique par sous-chaîne.** `"oeuf" in name.lower().replace("œ","oe")` (`main.py:215-222`) matcherait aussi un hypothétique « oeufs de lump » / « substitut d'œuf » comme un œuf à scaler en discret. Cas peu réaliste pour la v1 italienne ; décision documentée. À surveiller si le vocabulaire s'élargit. Non bloquant.

## Résultat pytest (réel)

- `python -m pytest tests/test_main.py -q` → **8 passed, 2 skipped** (0.16 s). Les 2 skip = `test_health` + `test_generate_endpoint` (gardés `pytest.importorskip("fastapi")`, `fastapi` non installé → skip propre, R7).
- `python -m pytest -q` → **191 passed, 3 skipped** (1.43 s) — conforme à l'attendu (160 baseline + 31 E1/E3 ; 3 skip = 1 intégration Claude + 2 TestClient gardés). **0 régression.**

Note : la suite est VERTE car aucun test n'asserte les portions émises ni la cohérence œufs `.cook`/Markdown — les deux majeurs sont des défauts de contrat de sortie non couverts, pas des cassures de test.

## Recommandation

**E1 ne peut PAS passer en `done` en l'état (CHANGES REQUESTED).** L'ossature de l'assembleur (règle §3.1, ordre §7, couture retry, mapping HTTP, testabilité R7) est conforme et la suite est verte sans régression, mais les **deux artefacts livrés sont mutuellement incohérents** (portions base vs quantités cible ; œufs 2 dans le `.cook` vs 3 dans le Markdown). Ces défauts touchent le livrable principal et la promesse du produit (scaling correct + `.cook` réutilisable).

Actions demandées au dev (toutes côté `app/main.py`, sans toucher aux 4 couches) :
1. Émettre `.cook` ET Markdown à partir d'UNE recette scalée canonique : `servings = request.servings` + tous les ingrédients scalés (**œufs inclus**). (Corrige Majeurs 1 & 2.)
2. Ajouter des tests d'ancrage : `servings: <cible>` dans le `.cook`, `Portions : <cible>` dans le Markdown, et égalité de la quantité d'œufs entre `.cook` et Markdown.

Une fois ces deux majeurs corrigés et la suite re-vérifiée verte, E1 pourra repasser en revue puis en `done`.

Étapes orchestrateur post-revue : **E1 reste en `review`** jusqu'à correction. À E1 `done` (après correctifs) → fusion éventuelle d'exports déjà faite (rien à fusionner ici, E1 ne crée pas d'export de couche) → **E2 (UI Jinja2) se débloque** (deps E1).

---

## 2e passe (re-revue après correctif) — 2026-06-02

- **Reviewer** : agent BMAD `bmad-code-review` (INDÉPENDANT du dev), 2e passe — vérification EMPIRIQUE (exécution réelle de `run_pipeline` + pytest + AST), sans se fier aux affirmations du dev.
- **Mode** : non-interactif, lecture seule (seul fichier écrit : la présente section). Le code n'est PAS corrigé.
- **Objet** : re-statuer les 2 MAJEURS de la 1re passe après le correctif annoncé (recette scalée canonique unique partagée par `to_cooklang` et `to_markdown`).

### Vérifications empiriques (2e passe)

| Contrôle | Méthode / commande | Résultat |
|---|---|---|
| **Major #1 — Portions = CIBLE des deux côtés** | exécution réelle `run_pipeline` (base `servings=2`, `request.servings=4`, faux `complete`+`index`) ; inspection `cooklang`/`markdown` | `.cook` → frontmatter `servings: 4` (PAS `servings: 2`) ; Markdown → `**Portions : 4**` (PAS `Portions : 2`). **MÊME valeur = CIBLE des deux côtés.** ✓ RÉSOLU |
| **Major #1 — code** | lecture `main.py:443-453` | `canonical_recipe = dataclasses.replace(recipe, servings=servings, ingredients=…)` (servings = `request.servings`) ; `to_cooklang(canonical_recipe, …)` ET `to_markdown(canonical_recipe)` reçoivent la MÊME recette canonique. ✓ |
| **Major #1 — test d'ancrage** | `pytest -k test_portions_emises_sont_la_cible` | présent (`test_main.py:230-245`), asserte `servings: 4` ∈ cook + `servings: 2` ∉ cook + `**Portions : 4**` ∈ md + `**Portions : 2**` ∉ md. **PASSED.** ✓ |
| **Major #2 — Œufs cohérents `.cook`/Markdown (RZ1)** | exécution réelle (3 œufs base, `k=2`) | `.cook` → `@oeufs{5%}` ; Markdown → `- 5 oeufs` ; `debug.scaling` value=5.0, type=`discrete`. **MÊME valeur (5) des deux côtés, reflète `scale_eggs` RZ1 (6 théoriques → 5).** ✓ RÉSOLU |
| **Major #2 — code (pas de double scaling)** | lecture `main.py:387-419` | œuf : `eggs = scale_eggs(qty.amount, k)` → `scaled_value = float(eggs.whole_eggs)` ; CETTE valeur entière sert à LA FOIS l'`amount` de l'ingrédient canonique (`scaled_ingredients`) ET le `ScaledQuantity.value` ajouté à `scaling_notes`. `scale_eggs` n'est appelé qu'UNE fois ; `to_cooklang` n'applique pas de coeff sur `scaling_notes`. Contrôle empirique : `@oeufs{6%}` ABSENT du `.cook`. **Aucun double scaling.** ✓ |
| **Major #2 — test d'ancrage** | `pytest -k test_coherence_oeufs_cook_markdown` | présent (`test_main.py:248-290`), asserte value=5.0 + `@oeufs{5%}` ∈ cook + `- 5 oeufs` ∈ md + base (`3`) ∉ des deux. **PASSED.** ✓ |
| **Pas de double scaling (ingrédient linéaire)** | exécution réelle (spaghetti 200 g, `k=2`) + `pytest -k test_coherence_quantites_cook_markdown` | `@spaghetti{400%g}` ∈ cook ET `- 400 g spaghetti` ∈ md ; `800` ABSENT du cook. Test présent (`test_main.py:293-302`). **PASSED.** ✓ |
| **Invariant — E1 SEUL à importer les 4 couches** | AST `app/main.py` (hors `TYPE_CHECKING`) | importe `app.epicure`, `app.generator`, `app.knowledge`, `app.scaling`. ✓ |
| **Invariant — couches ⇏ couches au runtime** | AST des 4 couches en excluant les blocs `if TYPE_CHECKING:` | epicure/knowledge/scaling/generator : **runtime cross-layer = NONE** (non-régression confirmée). ✓ |
| **Invariant — ZÉRO logique métier nouvelle** | lecture du correctif `main.py:386-453` | le correctif n'ajoute QUE `dataclasses.replace` + synthèse d'un `ScaledQuantity` portant la valeur DÉJÀ calculée par `scale_eggs`/`scale`. Aucun calcul de scaling maison ajouté. ✓ |
| **Invariant — mapping HTTP + `/health`** | lecture `main.py:529-557` | `PipelineInputError`→422, `PipelineGenerationError`→502, `Exception`→500, succès→200 ; `GET /health` (`{status:"ok", stage:"pipeline"}`) intact. ✓ |
| **Invariant — `run_pipeline` testable offline** | exécution réelle | faux `complete` + faux `index`, `anthropic` ABSENT de `sys.modules` après exécution. ✓ |
| **Invariant — tests TestClient gardés** | lecture `test_main.py:329,345` | `pytest.importorskip("fastapi")` conservé → 2 skips propres. ✓ |
| **pytest module E1** | `python -m pytest tests/test_main.py -q` | **11 passed, 2 skipped** (0.16 s) — conforme à l'attendu (8 d'origine + 3 d'ancrage ; 2 skip = TestClient `fastapi` absent). ✓ |
| **pytest suite complète** | `python -m pytest -q` | **194 passed, 3 skipped** (1.42 s) — conforme à l'attendu, **0 régression** (3 skip = 1 intégration Claude + 2 TestClient gardés). ✓ |

### Statut des findings de la 1re passe

- **Majeur 1 (Portions émises incohérentes avec les quantités scalées)** : **RÉSOLU.** Cause racine éliminée — recette canonique unique à `servings = request.servings` partagée par les deux émetteurs ; vérifié empiriquement (`servings: 4` / `Portions : 4`) + test d'ancrage `test_portions_emises_sont_la_cible` qui échouerait sur l'ancien comportement.
- **Majeur 2 (Quantité d'œufs divergente `.cook` vs Markdown)** : **RÉSOLU.** L'œuf scalé (`scale_eggs`) alimente à la fois l'ingrédient canonique et un `ScaledQuantity` synthétique dans `scaling_notes` ; vérifié empiriquement (`@oeufs{5%}` == `- 5 oeufs`, RZ1 3 → 5) + absence de double scaling (`@oeufs{6%}` non émis) + test `test_coherence_oeufs_cook_markdown`.
- **Mineur 1 (defer — double appel de `validate_recipe`)** : encore ouvert, **defer assumé** (déterministe, sans effet de bord, coût négligeable — `main.py:471`). Non bloquant.
- **Mineur 2 (defer — heuristique `_is_egg` par sous-chaîne)** : encore ouvert, **defer assumé** (décision documentée, cas peu réaliste en v1 italienne — `main.py:215-222`). Non bloquant.
- **Lacune de tests de la 1re passe (aucun assert sur portions/cohérence œufs)** : **COMBLÉE** par les 3 tests d'ancrage (portions cible, cohérence œufs, cohérence quantités linéaires).

### Verdict mis à jour

**APPROUVÉE — 0 bloquant / 0 majeur / 2 mineurs (defer assumé).**

Les deux majeurs de la 1re passe sont résolus, vérifiés EMPIRIQUEMENT (pas seulement par lecture du code ni par confiance dans le dev) : le `.cook` et le Markdown sont désormais émis depuis UNE recette scalée canonique unique, portions = cible des deux côtés, œufs cohérents reflétant le scaling discret RZ1, et AUCUN double scaling (linéaire 400 ≠ 800 ; œufs 5 ≠ 6). Le correctif est purement de l'assemblage (`dataclasses.replace` + synthèse d'un `ScaledQuantity` portant une valeur déjà calculée par la couche 3) : **zéro logique métier nouvelle**, conforme à la règle §3.1. Tous les invariants E1 de la 1re passe sont re-confirmés sans régression (E1 seul assembleur ; couches non couplées au runtime ; mapping 422/502/500 + `/health` intacts ; `run_pipeline` offline ; TestClient gardés). Suites vertes aux comptes attendus (11/2 et 194/3). Les 2 mineurs restants sont des `defer` documentés et non bloquants.

### Recommandation

**E1 peut passer en `done`.** Le livrable principal (deux artefacts `.cook`/Markdown mutuellement cohérents, scaling correct vers la cible, œufs RZ1 préservés dans l'artefact réutilisable) est désormais conforme. Aucun bloquant ni majeur restant.

Étapes orchestrateur : **E1 → `done`** → rien à fusionner (E1 ne crée pas d'export de couche) → **E2 (UI Jinja2) se débloque** (deps E1). Les 2 mineurs differés peuvent être consignés comme dette technique légère (non bloquante pour E2).

---

**VERDICT FINAL E1 : APPROUVÉE.** Les 2 majeurs sont RÉSOLUS (Majeur 1 portions = cible des deux côtés ; Majeur 2 œufs cohérents `.cook`/Markdown RZ1, sans double scaling), vérifiés empiriquement. **pytest : `tests/test_main.py` → 11 passed / 2 skipped ; suite complète → 194 passed / 3 skipped, 0 régression.**
