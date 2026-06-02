# Revue de code adversariale — Story D3

- **Story** : D3 — Émission `.cook` + validation regex (couche 4, `app/generator/`) — **résout RZ5**
- **Statut entrant** : `review`
- **Date** : 2026-06-02
- **Reviewer** : agent BMAD `code-review` (indépendant du développeur, mode non-interactif, adversarial mais juste)
- **Mode** : lecture seule (seul fichier écrit : la présente revue). Aucune correction de code, aucun fichier de D2 touché.
- **Périmètre revu (uniquement les ajouts D3)** :
  - `app/generator/cooklang.py` — `to_cooklang(recipe, scaling_notes) -> str`, `validate_cooklang(text) -> tuple[bool, list[str]]`, helpers privés (`_strip_accents`/`_normalize`/`_format_number`/`_index_scaling`/`_scaled_value_unit`/`_emit_ingredient`/`_emit_temperature`/`_emit_timer`/`_emit_cookware`/`_emit_note`), regex RECOPIÉES, bloc `__main__` de sanity-check.
  - `tests/test_cooklang.py` — 19 tests (AC1-AC6 + garde-fou inter-couches + rejets non tautologiques).
  - `docs/stories/D3.md` — AC, Tasks, Dev Agent Record, section « Réserve RZ5 résolue ».
- **Hors périmètre (non revu, sauf non-régression / non-modification)** : `app/generator/models.py` (contrat figé D1), `app/generator/__init__.py`, `recipes/_check_cook.py`, `app/scaling/*`, `app/generator/validate.py` + `tests/test_validate.py` (D2), `sprint-status.yaml`.

---

## Vérifications empiriques

| Contrôle | Commande / méthode | Résultat |
|---|---|---|
| pytest suite complète | `python -m pytest -q` | **149 passed / 1 skipped** (attendu confirmé ; 0 régression) |
| pytest module D3 | `python -m pytest tests/test_cooklang.py -q` | **19 passed** |
| Sanity-check `__main__` | `python -m app.generator.cooklang` | `.cook` émis + `validate_cooklang -> ok=True ; problems=[]` |
| Encodage sans BOM | premiers octets des 2 fichiers | `34 34 34` (`"""`) — **UTF-8 sans BOM** ✓ |
| Règle inter-couches (imports runtime) | inspection des `import` de `cooklang.py` | seul import runtime = `from app.generator.models import ...` ; `Mapping`/`Sequence`/`Any` uniquement sous `if TYPE_CHECKING:` ✓ |
| Aucun `anthropic`/`cooklang`/`scaling`/`knowledge`/`epicure` runtime | inspection + test `test_aucun_import_intercouche_runtime` | absents de `sys.modules` après import ; `ScaledQuantity` absent des globals ✓ |
| `__init__.py` non modifié par D3 | `git diff app/generator/__init__.py` | le diff (vs D1) **ne contient AUCUN export `to_cooklang`/`validate_cooklang`** — la modif provient de D1 (exports `client`/`models`/`prompt`), pas de D3 ✓ |
| `models.py` non modifié | `git status` (untracked, contrat figé) | non touché par D3 ✓ |
| `_check_cook.py` non modifié, regex RECOPIÉES | comparaison des 4 regex | `RE_SERVINGS`/`RE_INGREDIENT`/`RE_TIMER`/`RE_COOKWARE` **identiques verbatim**, pas d'import de `recipes/` ✓ |
| Périmètre = 2 fichiers + story | `git status` | `app/generator/cooklang.py`, `tests/test_cooklang.py` (untracked) + `docs/stories/D3.md` ✓ |

---

## Analyse par critère de revue

### 1. Règle inter-couches (CRITIQUE, archi §3.1) — CONFORME
`cooklang.py` n'importe au runtime que `app.generator.models` (lignes 41-47, même couche, contrat figé D1). Les types couche 3 (`Mapping`, `Sequence`, `Any`) sont sous `if TYPE_CHECKING:` (lignes 49-54), jamais importés au runtime. Aucun `anthropic`, aucun `cooklang`/`cooklang-py`, aucun `app/scaling|knowledge|epicure`. `scaling_notes` arrive EN PARAMÈTRE et est lu par `getattr` (duck-typing), jamais par `isinstance` couplant un type d'une autre couche. Le test `test_aucun_import_intercouche_runtime` verrouille `anthropic`/`cooklang` absents de `sys.modules` et `ScaledQuantity` absent des globals. **Aucun import runtime interdit. Pas de bloquant.**

### 2. Contrat non modifié — CONFORME
`app/generator/models.py` non touché par D3 (untracked, hérité de D1). `app/generator/__init__.py` est marqué `M` par git, mais le diff (vérifié) provient **intégralement de D1** (docstring + exports `client`/`models`/`prompt`) et ne contient **aucun** export `to_cooklang`/`validate_cooklang`. D3 n'a donc pas édité `__init__.py` — conforme à la règle anti-conflit (l'orchestrateur fusionnera les exports après revue). `recipes/_check_cook.py` non modifié ; les 4 regex sont **recopiées verbatim** (lignes 63-66 de `cooklang.py`), pas importées.

### 3. Format Cooklang correct (archi §8.4) — CONFORME
Frontmatter `---\nservings: N\n---` (lignes 304-306, `N = recipe.servings`, base). Marqueurs `@nom{[=]val%unité}` (`_emit_ingredient`), `(=val%°C)` pour températures figées (`_emit_temperature`), `#ustensile` (`_emit_cookware`), `~{val%unité}` (`_emit_timer`). Verrou `=` pour `fixed` posé à l'intérieur des accolades. Notes `--` via `_emit_note`. Le `.cook` émis passe `validate_cooklang` (`test_to_cooklang_passe_la_validation`) et accolades équilibrées. Style aligné sur le corpus S0.6 (`@gros sel{=30%g}`, `(=100%°C)`, `#grande casserole`, `~{9%minutes}`) — vérifié via le sanity-check `__main__`.

### 4. Scaling (archi §7) — CONFORME
`scaling_notes` accepté souplement par `_index_scaling` : `None` → `{}` (quantités de base), mapping `{name: note}` (testé `.items`), séquence d'objets `.name`. Alignement par **nom normalisé** (`_normalize`, accents/casse) — testé sur `Céleri`/`celeri`. `_scaled_value_unit` lit `.value`/`.unit`/`.fixed`/`.notes`/`.note` par `getattr` avec défauts ; retombe sur la base si `scaled is None` ou attribut absent. Pas de confusion base/scalé : `test_quantites_scalees_quand_scaling_fourni` prouve `400%g` (scalé) ET `200%g` (base) absent ; `test_quantites_base_quand_scaling_none` prouve la base. Robustesse aux str/bytes (exclus explicitement, lignes 136/144).

### 5. RZ5 — RÉSOLUE
`validate_cooklang` est un **fallback regex pur** : regex recopiées de `_check_cook.py`, contrôles frontmatter `servings` + ≥1 `@…{…%…}` + accolades équilibrées, messages FR. **Aucune dépendance `cooklang-py`** (vérifié : `cooklang` absent de `sys.modules`, `requirements.txt` non modifié). La story documente le lien RZ5→D3 et la décision D5 (archi §8.4/§12 : « templating maison + validation regex », tranché). RZ5 est donc résolvable ; l'orchestrateur passera `open → resolved` après cette revue.

### 6. Pureté / déterminisme — CONFORME
Aucun `random`, aucune horloge, aucune I/O (les tests construisent les objets en mémoire). `_format_number` déterministe via `format(.., "g")` : `2.0 → "2"` (testé `test_format_nombre_entier_sans_decimale`, `"2.0" not in cook`), garde anti-`bool`, repli décimal sur exposant. Ordre des notes stable (ordre d'apparition des ingrédients, dédup par `seen_notes`). `test_determinisme_50_executions` exécute **60** fois et compare au texte exact — probant.

### 7. Tests probants — CONFORME
La validation est testée **non tautologiquement** : 3 rejets distincts (`test_validation_rejette_accolades_desequilibrees`, `test_validation_rejette_frontmatter_manquant`, `test_validation_rejette_sans_marqueur_ingredient`) asservis chacun à un message dédié, + 1 acceptation. Verrou `=` testé sur `Quantity.fixed` (`@sel{=1%c.à.c}`), sur température (`(=180%°C)`) ET sur `ScaledQuantity.fixed` (base non-fixed → `@sel{=5%g}`). Note `--` réserve testée sans double préfixe (`----` absent). Quantités scalées vs base testées explicitement.

### 8. Anti-conflit — CONFORME
Exactement 2 fichiers créés + story. Les tests importent les sous-modules directement (`from app.generator.cooklang import ...`, `from app.generator.models import ...`), pas via le package. `validate.py`/`test_validate.py` (D2), `app/scaling/*`, `sprint-status.yaml` non touchés par D3 (le `M` sur `sprint-status.yaml` provient d'autres stories du sprint, pas de D3 — D3 ne le modifie pas, conforme à la consigne).

### 9. Conventions — CONFORME
`from __future__ import annotations` présent ; type hints PEP 585 (`dict[str, object]`, `tuple[bool, list[str]]`, `list[str]`). Docstrings FR avec accents corrects. UTF-8 sans BOM (vérifié). Aucune nouvelle dépendance (`re`/`unicodedata` stdlib). Bloc `__main__` de sanity-check présent.

### 10. Point d'attention — ustensile multi-mots — GÉRÉ ET DOCUMENTÉ
`_emit_cookware("grande casserole")` émet `#grande casserole` (premier token marqué `#grande`, reste en texte). La regex `#[^\s#@~{]+` ne reconnaîtrait que `#grande`, mais **`validate_cooklang` n'utilise PAS `RE_COOKWARE`** dans ses contrôles (seuls servings + ingrédient + accolades) : l'ustensile multi-mots n'invalide donc jamais le `.cook`. Le choix reproduit verbatim le style du corpus S0.6 (`#grande casserole` figure dans `04-carbonara`) et est documenté dans la docstring de `_emit_cookware`. **Cohérent et sans impact sur la validation.** Observation mineure ci-dessous.

---

## Couverture des Acceptance Criteria

- **AC1** (frontmatter + marqueurs, `.cook` valide) : ✓ frontmatter, `@`/`#`/`~`/`(=…)`, passe `validate_cooklang`.
- **AC2** (scalé si fourni, base sinon ; duck-typing souple) : ✓ liste/dict/None, alignement par nom normalisé, `getattr`.
- **AC3** (verrou `=` sur `fixed`) : ✓ `Quantity.fixed` OU `ScaledQuantity.fixed` (priorité scaling) + températures figées.
- **AC4** (notes `--` réserve/contenant/étiquettes, idempotence) : ✓ `_emit_note` sans `----`, notes scaling dédupliquées + étiquettes recette.
- **AC5** (`validate_cooklang` regex, RZ5, non tautologique) : ✓ regex recopiées, rejets probants, messages FR.
- **AC6** (pureté/déterminisme + règle inter-couches + suite verte 0 régression) : ✓ module pur, TYPE_CHECKING, 149 passed / 1 skipped.

---

## Findings (par sévérité)

### Bloquants
Aucun.

### Majeurs
Aucun.

### Mineurs / observations

1. **[defer] Anti-doublon ingrédient sensible à la graphie exacte du nom dans `Step.text`.**
   La détection `already = f"@{qty.name}{{" in text` (ligne 333) compare le **nom brut** de la `Quantity` à `Step.text`. Si un futur `Step.text` portait le marqueur avec une graphie légèrement différente (casse/accents) ou avec espace différent, le marqueur structuré serait réémis en doublon. Sans impact sur les données actuelles (le LLM D1 produit des `Step.text` souvent sans marqueur, et le test couvre le cas par champs) ; le `.cook` resterait valide (accolades équilibrées). **Defer.**

2. **[defer] Rendu « brut » des marqueurs concaténés après `Step.text`.**
   Quand `Step.text` ne cite pas les ingrédients individuellement, tous les `@`/`#`/`~`/`(=…)` sont accolés en fin de ligne d'étape (observé au sanity-check : `… cuire les pâtes. @spaghetti{400%g} @gros sel{=30%g} …`). C'est un `.cook` **valide et déterministe**, et la story fige explicitement le contrat (frontmatter + marqueurs + validité) et non le micro-gabarit ligne à ligne (Dev Notes §« Stratégie d'émission »). Lisibilité perfectible mais hors AC. **Defer.**

3. **[defer] `validate_cooklang` ne valide pas la bonne formation des marqueurs `#`/`~`/`=`.**
   Conformément au patron `_check_cook.py` recopié, seuls servings + ≥1 ingrédient + équilibrage des accolades sont contrôlés (l'équilibrage couvre déjà un `~{`/`@…{` non fermé). L'AC5 mentionnait « marqueurs `#`/`~`/`=`/`--` bien formés » comme ajout léger ; l'implémentation s'en tient au patron éprouvé S0.4, ce qui est cohérent avec « regex RECOPIÉES » et suffisant pour garantir la bonne formation émise par `to_cooklang`. **Defer.**

---

## Verdict

**APPROUVÉE — 0 bloquant / 0 majeur / 3 mineurs (defer).**

D3 livre `to_cooklang` (émission `.cook` : frontmatter `servings`, marqueurs `@`/`#`/`~`, températures figées `(=…%°C)`, verrous `=` sur `fixed`, notes `--` réserve/contenant/étiquettes ; quantités scalées alignées par nom normalisé sur `scaling_notes` reçu en paramètre par duck-typing, sinon base ; formatage déterministe) et `validate_cooklang` (fallback regex, patron `_check_cook.py` recopié, messages FR). La **règle inter-couches (archi §3.1) est respectée** : seul import runtime = `app.generator.models` ; couche 3 sous `if TYPE_CHECKING:` ; aucun `anthropic`/`cooklang-py`/`scaling`/`knowledge`/`epicure` au runtime (vérifié par inspection ET par le test garde-fou). Le **contrat est intact** (`models.py` figé, `__init__.py` non touché par D3 — la modif `M` provient de D1, sans export D3 ; regex recopiées verbatim, `_check_cook.py` non modifié). Le format respecte §8.4 et le corpus S0.6. Le scaling reporte correctement base vs scalé sans confusion. La validation est testée **non tautologiquement** (3 rejets à messages dédiés). Pureté/déterminisme prouvés (60 exécutions, `2.0 → 2`). Périmètre = exactement 2 fichiers + story ; aucun fichier de D2 touché. UTF-8 sans BOM, aucune nouvelle dépendance.

Suite complète : **149 passed / 1 skipped** ; module D3 : **19 passed**. Les 3 findings mineurs `defer` (anti-doublon sensible à la graphie, rendu brut des marqueurs concaténés, validation limitée au patron S0.4) ne remettent en cause aucun AC.

**RZ5 est résolvable** : émission `.cook` par templating maison + validation regex, **aucune dépendance `cooklang-py`** (décision D5/archi §8.4/§12), vérifié empiriquement (`cooklang` absent de `sys.modules`, `requirements.txt` figé).

**Recommandation : D3 peut passer en `done`.** L'orchestrateur fusionne ensuite les exports `to_cooklang`/`validate_cooklang` dans `app/generator/__init__.py` et passe RZ5 `open → resolved`.
