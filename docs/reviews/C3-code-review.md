# Revue de code adversariale — Story C3

- **Story** : C3 — Scaling géométrique du temps `k^(2/3)` (`docs/stories/C3.md`)
- **Statut entrée** : `review`
- **Date** : 2026-06-01
- **Reviewer** : workflow `bmad-code-review` (Blind Hunter + Edge Case Hunter + Acceptance Auditor)
- **Périmètre** : `K_NONLINEAR_THRESHOLD`, dataclass `ScaledTime`, fonction `scale_time` (`app/scaling/engine.py`) ; tests C3 `test_temps_geometrique`, `test_temps_note_contenant_au_seuil`, `test_temps_seuil_unique`, `test_temps_deterministe` (`tests/test_scaling.py`).
- **Hors périmètre (non revus)** : C1 (`classify`/`scale`/`load_table`/`table.py`) et C2 (`scale_eggs`/`ScaledEggs`), déjà approuvés.
- **Mode** : non-interactif, lecture seule (aucune modification de code).

## Vérifications factuelles

- `pytest tests/test_scaling.py` → **11 passed / 0 skipped / 0 failed**.
- `scale_time(20, 2.0).minutes = 31.7488` → ~32, dans `±0.5`, « pas 40 » (AC1, DoD).
- Exposant **lu dans la table** via `classify("temps").exponent` (= 0.6667). Aucun littéral `0.6667` dans le code de calcul d'`engine.py` (les 2 occurrences sont en docstring/commentaire). **D7 respecté.**
- `K_NONLINEAR_THRESHOLD = 1.5` défini **une seule fois** dans tout le repo (`engine.py:31`), niveau module, commenté `# RZ2 — a calibrer F2 — partage C3/C4`. Importable par C4. (AC2)
- Note `--` présente à `k=2.0` ET au seuil exact `k=1.5` (`>=`), absente à `k=1.2`. (AC3)
- `ScaledTime{minutes, nonlinear=True, notes: list[str], type, debug}` + property `note: str | None`. (AC4)
- Périmètre respecté : seuls `engine.py` et `test_scaling.py` touchés ; C1/C2 et la table intacts.

## Conformité AC / DoD

| Critère | Verdict | Preuve |
|---|---|---|
| AC1 — loi géométrique, exposant en table | CONFORME | `minutes=31.749` ; `exponent = rule.exponent` (engine.py:253) ; pas de `0.6667` codé |
| AC2 — constante seuil RZ2 unique, commentée, partagée C4 | CONFORME | engine.py:31, définition unique repo-wide |
| AC3 — note `--` quand `k ≥ seuil` | CONFORME | note à k=2.0 et k=1.5, absente à k=1.2 (engine.py:261 `>=`) |
| AC4 — sortie `ScaledTime{minutes, nonlinear, note}` | CONFORME | dataclass + property `note` alias scalaire |
| DoD | CONFORME | scale_time implémenté ; test ≈32 ±0.5 ; seuil unique commenté RZ2 ; 11 passed |

## Findings par sévérité (triage)

Aucun **Blocker**, aucun **Major bloquant** au regard du périmètre et des AC/DoD de C3.
Tous les findings de durcissement sont classés **`defer`** : légitimes mais hors AC/DoD C3, cohérents
avec le style des fonctions sœurs C1/C2 (déjà approuvées, sans validation d'entrées), et explicitement
renvoyés à C4/C5 par la story (validation d'entrées, scénarios ×N généralisés, déterminisme N exécutions).

### Defer (durcissements futurs — non bloquants)

1. **Entrées non validées** (`blind+edge`) — `k ≤ 0` → `k ** 0.6667` lève `ValueError`/`complex` ; `k=0` → 0 min ; `minutes < 0` → temps négatif silencieux ; `NaN`/`inf` propagés. `scale_time` (engine.py:233). Aligné sur l'absence de garde dans `scale`/`scale_eggs` (C1/C2 approuvés). → candidat C4/durcissement.
2. **Fallback exposant silencieux** (`blind+edge`) — si `classify("temps")` ne portait pas `exponent`, fallback `1.0` → scaling linéaire silencieux (20×2=40) avec `nonlinear=True`/`type="geometric"` incohérents. Non atteignable avec la table actuelle (catégorie temps présente). → garde `LookupError` recommandée à terme.
3. **Frontière `k = 1.5` non testée explicitement** (`blind+edge`) — comportement au seuil exact (`>=`) non verrouillé par un test ; vérifié manuellement CONFORME (note présente). → ajouter un test de frontière (C5).
4. **`test_temps_deterministe` à faible pouvoir de détection** (`blind+edge`) — deux appels même process sur fonction arithmétique pure : vert par construction. → renforcer avec assertion sur valeur littérale attendue (C5).
5. **Tolérance `±0.5` n'isole pas l'exposant 2/3** (`blind+edge`) — `[31.5, 32.5]` ; un exposant 0.66–0.70 passerait. Tolérance imposée par la DoD. → resserrer en C5 si souhaité.
6. **Asymétrie réductions `k < 1`** (`blind+edge`) — aucune note de contenant côté réduction. Hors AC3 (qui ne vise que `k ≥ seuil`). → évolution produit éventuelle.
7. **`nonlinear`/`type` codés en dur, non dérivés de `rule`** (`blind`) — `nonlinear = True` constant ; conforme à l'AC4 (« toujours True pour le temps ») mais ne reflète pas la règle. → cosmétique.
8. **Immutabilité non garantie** (`blind`) — `ScaledTime` non `frozen`, `debug`/`notes` mutables. Cohérent avec `ScaledQuantity`/`ScaledEggs` (non frozen). → harmonisation projet éventuelle.
9. **Formatage `k:g` / message FR codé en dur** (`blind`) — notation scientifique possible pour k extrêmes ; chaîne de note non externalisée. Cosmétique. → i18n future.

### Dismiss (bruit / faux positifs)

- **`note` (singulier) vs `notes` (list)** (`auditor`) — écart d'intitulé avec l'AC4, mais **explicitement autorisé/recommandé** par les Dev Notes de C3 (« une `list[str]` est recommandée pour homogénéité ») ; la property `note` fournit l'alias scalaire attendu. Non-finding.
- **`note` masque les notes au-delà de la 1re** (`blind`) — par design (alias de commodité) ; `notes` reste accessible. Non pertinent en C3 (au plus une note émise).

## Verdict

**APPROUVÉE.** Les 4 AC et la DoD de C3 sont satisfaits ; D7 (aucun coefficient codé en dur) et le contrat
de pureté/déterminisme sont respectés ; périmètre strictement tenu (C1/C2 intacts). 11 tests verts, 0 skip.
Les findings restants sont des durcissements `defer` (validation d'entrées, tests de frontière), non bloquants
et alignés sur les stories C4/C5.

**Recommandation : C3 peut passer en `done`.**
