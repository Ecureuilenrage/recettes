# Revue de code adversariale — Story D4

- **Story** : D4 — Rendu Markdown lisible (`to_markdown`) (couche 4, générateur LLM) — **DERNIÈRE story du sprint 4**
- **Statut entrant** : `review`
- **Date** : 2026-06-02
- **Reviewer** : agent BMAD `bmad-code-review` (rôle « code-review », INDÉPENDANT du dev — couches Blind Hunter / Edge Case Hunter / Acceptance Auditor + triage)
- **Mode** : non-interactif, lecture seule (seul fichier écrit : la présente revue ; le code N'EST PAS corrigé)
- **Périmètre revu (ajouts D4 uniquement)** :
  - `app/generator/markdown.py` — `to_markdown(recipe) -> str` + helpers privés `_format_number`, `_format_quantity`, `_format_temperature`, `_format_duration`, `_step_detail_lines`.
  - `tests/test_markdown.py` — 11 tests D4.
  - `docs/stories/D4.md` — AC + Tasks + Dev Agent Record audités.
- **Hors périmètre (non revu, sauf non-régression)** : `app/generator/models.py` (contrat figé D1), `app/generator/cooklang.py`/`validate.py`/`prompt.py`/`client.py` (autres stories), `app/generator/__init__.py` (lecture seule), `app/scaling/*`, `app/knowledge/*`, `app/epicure/*`.

---

## Verdict

**APPROUVÉE — 0 bloquant / 0 majeur / 2 mineurs (defer).**

`to_markdown` réalise le rendu Markdown lisible attendu (archi §4.4/§7/§9.1) avec une signature à 1 paramètre conforme, un module PUR/DÉTERMINISTE, la restitution VISIBLE des températures + étiquettes `[SÉCURITÉ]/[TECHNIQUE]/[PRÉFÉRENCE]` (vitrine d'explicabilité §9.2/§6.1), une robustesse sur recette minimale, et le respect STRICT de la règle inter-couches (§3.1). Suite complète : **160 passed / 1 skipped, 0 régression**.

---

## Vérifications empiriques

| Contrôle | Commande / méthode | Résultat |
|---|---|---|
| pytest module D4 | `python -m pytest tests/test_markdown.py -q` | **11 passed** (0.02 s) ✓ |
| pytest suite complète | `python -m pytest -q` | **160 passed / 1 skipped** (0.26 s) — 0 régression ✓ |
| Imports runtime réels (AST, contrôle INDÉPENDANT) | `ast.walk` sur le source de `markdown.py` | `['__future__', 'app.generator.models']` — **AUCUN** autre import ✓ |
| Signature 1 paramètre | `inspect.signature(to_markdown).parameters` | `['recipe']` — pas de `scaling_notes` ✓ |
| Encodage / fins de ligne | lecture binaire | UTF-8 **sans BOM**, **LF** ✓ |
| Déterminisme | rendu identique sur exécutions répétées | stable (test 60 itérations + revue) ✓ |
| Rendu effectif | `python -m app.generator.markdown` | titre `#`, `**Portions : 4**`, `## Ingrédients` (puces), `## Préparation` (numérotée), sous-puces température[+étiquette]/durée/cookware, `## Techniques`, `## Notes` ✓ |

## Conformité à la signature prescrite (archi §4.4)

| Signature prescrite | Implémentation D4 | Verdict |
|---|---|---|
| `def to_markdown(recipe) -> str` (D4, rendu lisible — 1 paramètre) | `to_markdown(recipe: StructuredRecipe) -> str` (`markdown.py:167`), EXACTEMENT 1 paramètre, **pas** de `scaling_notes` (volontairement distinct de `to_cooklang(recipe, scaling_notes)`) | ✓ |

Le choix « 1 paramètre, rend la recette telle quelle » est documenté en docstring de module et de fonction (le scaling, s'il doit apparaître, est appliqué côté pipeline AVANT l'appel) — conforme §4.4 et au flux §7 (scaling avant émission). Décision figée cohérente.

## 1. Règle inter-couches (CRITIQUE, archi §3.1) — RESPECTÉE

Contrôle adversarial INDÉPENDANT du test du dev : analyse AST du source réel de `app.generator.markdown`. Les seules instructions d'import sont `from __future__ import annotations` et `from app.generator.models import (Duration, Quantity, Step, StructuredRecipe, Temperature)` (`markdown.py:41-49`). **AUCUN** import runtime de :

- `app/scaling/`, `app/knowledge/`, `app/epicure/` — absents ;
- `anthropic` — absent (le mot n'apparaît que dans la docstring « ce que le module N'importe PAS », pas dans une instruction d'import) ;
- les autres modules de la couche 4 (`cooklang.py`/`validate.py`/`prompt.py`/`client.py`) — absents ; le helper `_format_number` est bien **RECOPIÉ** (≈ 20 lignes stdlib, `markdown.py:58-77`) et non importé de `cooklang.py`.

Le module n'a même pas besoin de `re`/`unicodedata` (pas de regex, pas d'alignement par nom — D4 n'a pas de `scaling_notes` à réconcilier). Import runtime interdit = **aucun**. ✓

## 2. Contrat non modifié

- `app/generator/models.py` : non touché par D4 (untracked au même titre que les autres modules livrés par l'orchestrateur ; `to_markdown` consomme `StructuredRecipe`/`Quantity`/`Step`/`Temperature`/`Duration` en LECTURE SEULE, sans redéfinition). ✓
- `app/generator/__init__.py` : la modification git visible (` M`) **ne contient PAS** l'export `to_markdown` (diff vérifié : seuls les exports D1–D3 sont fusionnés). C'est donc un merge antérieur de l'orchestrateur, **pas** une modification D4 — conforme à la règle anti-conflit (l'orchestrateur fusionnera `to_markdown` APRÈS la revue). Noté sans le compter comme défaut D4. ✓
- Autres modules de la couche (`cooklang.py`/`validate.py`/`prompt.py`/`client.py`) : non touchés par D4. ✓

## 3. Signature — `to_markdown(recipe) -> str`

Exactement 1 paramètre (`inspect.signature` → `['recipe']`), pas de `scaling_notes`. Conforme §4.4. ✓ (cf. tableau ci-dessus)

## 4. Rendu correct (§4.4/§9.2)

Vérifié sur le rendu effectif et les tests :

- **Titre** `# {title}` (`markdown.py:202`) ✓
- **Portions** `**Portions : {servings}**` — portions de BASE (`markdown.py:204`) ✓
- **`## Ingrédients`** en liste à puces « quantité + unité + nom » (`- 2 c.à.s huile d'olive`, `- 3 œufs` unité vide, `- 10 g gros sel`) ✓
- **`## Préparation`** en liste numérotée `1.`/`2.` avec `Step.text` ✓
- **Restitution VISIBLE** des températures, durées, cookware en sous-puces ✓
- **Étiquettes** `[SÉCURITÉ]/[TECHNIQUE]/[PRÉFÉRENCE]` rendues avec graphie accentuée du contrat ; les températures de **sécurité** reçoivent un libellé dédié non ambigu « Température de sécurité : 74 °C [SÉCURITÉ] » (`markdown.py:148-153`) — vitrine d'explicabilité §9.2/§6.1 satisfaite ✓
- Unité « C »/« F » rendue `°C`/`°F` (`markdown.py:120`) ✓

## 5. Robustesse (recette minimale)

- Recette `StructuredRecipe(title="X", servings=2, ingredients=(), steps=())` → titre + portions toujours émis ; `## Ingrédients`/`## Préparation` présentes avec libellé sobre `_(aucun ingrédient)_` / `_(aucune étape)_` (pas d'en-tête orphelin) ; `## Techniques`/`## Notes` ABSENTES. ✓
- Sections `## Techniques`/`## Notes` conditionnelles (émises seulement si non vides), avec filtrage des entrées vides (`markdown.py:229,238`). ✓

## 6. Pureté / déterminisme

- Aucun `random`, aucune horloge, aucune I/O, aucun LLM (confirmé par AST + lecture). ✓
- Ordre d'entrée préservé (pas de tri non déterministe), terminaison par `"\n"` final stable (`markdown.py:246`). ✓
- `_format_number` déterministe : `2.0 → "2"`, `2.5 → "2.5"`, `format(.., "g")` + garde-fou exposant, garde `bool`/`int` explicite, aucune dépendance locale (`markdown.py:58-77`). ✓
- `test_determinisme` (60 itérations) est probant : il compare le rendu complet à une référence, pas une simple non-exception. ✓

## 7. Tests probants

11 tests, couvrant AC1–AC6, non tautologiques :

- `test_markdown_contient_titre_portions_ingredients_etapes` (AC1) — assertions ciblées sur titre, `Portions : 4`, puce exacte `- 2 c.à.s huile d'olive`, étapes numérotées.
- `test_etiquettes_securite_visibles` (AC3) — vérifie les 3 étiquettes ET le libellé dédié exact `Température de sécurité : 74 °C [SÉCURITÉ]` (échouerait si l'étiquette ou la valeur disparaissait — non tautologique).
- `test_durees_et_cookware_restitues` (AC3) — `5 minutes`, `45 minutes`, `grande poêle`.
- `test_determinisme` (AC2) — 60 itérations, égalité du rendu complet.
- `test_formatage_nombre_deterministe` (AC2) — assertion POSITIVE (`- 2 tasse farine`, `- 2.5 dl lait`) ET NÉGATIVE (`"2.0 tasse" not in md`) : verrouille réellement `2.0 → "2"`.
- `test_recette_minimale_valide` (AC4) — cas minimal présent, vérifie présence des libellés sobres ET absence de `## Techniques`/`## Notes`.
- `test_sections_optionnelles_absentes_si_vides` / `_presentes_si_non_vides` (AC4/AC1).
- `test_signature_un_seul_parametre` (AC5) — `inspect.signature`.
- `test_termine_par_newline_stable` (AC2).
- `test_aucun_import_intercouche_runtime` (AC6) — garde-fou par **AST** (et non texte brut / `sys.modules`), évitant les faux positifs/négatifs ; vérifie la présence de `app.generator.models` ET l'absence des préfixes interdits. Solide.

## 8. Anti-conflit

- **Exactement 2 fichiers** créés par D4 (`app/generator/markdown.py`, `tests/test_markdown.py`) + mise à jour de `docs/stories/D4.md`. ✓
- Les tests importent les sous-modules **DIRECTEMENT** (`from app.generator.markdown import to_markdown`, `from app.generator.models import ...`), pas via le package. ✓
- `sprint-status.yaml` est modifié (` M`) mais par l'orchestrateur (hors périmètre dev D4 — D4 n'y touche pas) ; les autres modules/couches ne sont pas touchés par D4. ✓

## 9. Conventions

- `from __future__ import annotations` ✓ ; type hints PEP 585 (`list[str]`) ✓ ; docstrings FR avec accents corrects ✓ ; UTF-8 **sans BOM**, LF ✓ ; **aucune nouvelle dépendance** (stdlib seule) ✓ ; bloc `if __name__ == "__main__":` de sanity-check ✓.

## Findings (par sévérité)

### Bloquants
Aucun.

### Majeurs
Aucun. (Règle inter-couches §3.1 respectée — vérifiée par AST indépendant ; signature §4.4 conforme ; explicabilité §9.2 visible ; déterminisme probant ; suite verte sans régression.)

### Mineurs / observations

1. **[defer] Indentation des sous-puces sous un item de liste numérotée.**
   Les détails d'étape sont rendus avec 2 espaces d'indentation (`  - Température : …`, `markdown.py:150-158`) sous un item numéroté `1. ` (dont le contenu démarre à la colonne 3). En CommonMark strict, l'imbrication d'une sous-liste sous un item ordonné aligne généralement à l'indentation du contenu parent (3 espaces ici) ; avec 2 espaces, certains parseurs peuvent traiter la sous-puce comme une liste « lâche » de même niveau plutôt qu'imbriquée. **Impact cosmétique uniquement** : le contenu (température, étiquette, sécurité, durée, cookware) reste TOUJOURS VISIBLE et lisible — l'exigence d'explicabilité §9.2 (AC3) est satisfaite. Aucun AC n'impose un niveau d'imbrication précis. **Defer** (à harmoniser éventuellement avec le rendu cible de l'UI E2 si besoin).

2. **[defer] Aucun test n'ancre le rendu d'un nombre à exposant ni d'une recette sans aucune section optionnelle ET sans détails d'étape.**
   Le garde-fou exposant de `_format_number` (`markdown.py:75-76`, `"1e-05" → décimale`) est correct mais non couvert par un test dédié (cas extrême peu réaliste pour des quantités culinaires). De même, le format d'ingrédient « quantité nulle + unité vide → nom seul » (`_format_quantity`, décision documentée) est implémenté mais non testé explicitement. Couverture par ailleurs honnête et probante. **Defer.**

## Résultat pytest (réel)

- `python -m pytest tests/test_markdown.py -q` → **11 passed** (0.02 s).
- `python -m pytest -q` → **160 passed, 1 skipped** (0.26 s) — baseline 149 passed / 1 skipped + 11 nouveaux tests, **0 régression**. Conforme à l'attendu.

## Recommandation

**D4 peut passer en `done`.** Le rendu Markdown lisible est conforme (archi §4.4/§7/§9.1), pur/déterministe, avec l'explicabilité visible (§9.2/§6.1) ; la règle inter-couches (§3.1) est respectée et revérifiée indépendamment par AST ; la règle anti-conflit est tenue (2 fichiers, imports directs, `__init__.py` non touché par D4). Les 2 findings mineurs sont `defer` (indentation cosmétique des sous-puces, tests d'ancrage de cas extrêmes) et ne remettent en cause aucun AC.

Étapes orchestrateur post-revue : fusionner l'export `to_markdown` (depuis `app.generator.markdown`) dans `app/generator/__init__.py`, passer D4 en `done`. **D4 `done` → fin du sprint 4** ; E1 (deps `[D4, A4]`, toutes `done`) se débloque.
