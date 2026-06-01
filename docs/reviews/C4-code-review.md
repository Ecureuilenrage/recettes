# Revue de code adversariale — Story C4

- **Story** : C4 — Flags de non-linéarité + réserve 10 % (`docs/stories/C4.md`, statut `review`)
- **Date** : 2026-06-01
- **Reviewer** : agent BMAD code-review (couches Blind Hunter / Edge Case Hunter / Acceptance Auditor)
- **Périmètre revu (strict)** : `app/scaling/engine.py` — constante `NONLINEAR_NOTE`, champ `ScaledQuantity.reserve`, couche de décoration C4 dans `scale(...)` (flag non-linéarité + réserve 10 %) ; et les 7 tests C4 dans `tests/test_scaling.py`.
- **Hors périmètre (non revu, déjà approuvés)** : C1 (`classify`/base `scale`/`load_table`/`table.py`), C2 (`scale_eggs`), C3 (`scale_time`/`K_NONLINEAR_THRESHOLD`).
- **Build/tests** : `pytest tests/test_scaling.py` → **18 passed / 0 skipped** (0.02 s).

---

## Findings par sévérité

### Bloquant (High)
*Aucun.*

### Moyen (Medium)
*Aucun.*

### Faible (Low)

**L1 — La garantie « `incorporate + reserve == value` » n'est pas une égalité binaire exacte.**
- Emplacement : `app/scaling/engine.py:175-181` ; tâche 3 de la story (« Garantir `incorporate + reserve == value` (tolérance flottante) »).
- Observation : pour certaines valeurs (ex. `scale("sel", 1, "u", 2.0)`), `incorporate + reserve` diffère de `value` au dernier bit (`1.681792830507429` vs `1.6817928305074292`). C'est inhérent à l'arithmétique flottante.
- Impact : **nul sur l'AC** — l'AC2 stipule explicitement « tolérance flottante » et le test `test_reserve_sel` vérifie via `pytest.approx` (correct). Le risque est purement documentaire : la formulation « sans perte / égale » peut induire en erreur un futur lecteur qui écrirait un test d'égalité stricte.
- Recommandation (optionnelle, non bloquante) : reformuler le commentaire en « somme conservée à la tolérance flottante près », ou dériver `incorporate = value - reserve_amount` pour réduire (sans éliminer) l'écart. Aucune action requise pour passer en `done`.

**L2 — `scale("temps", ...)` cumule la note de délégation C2/C3 et la note de non-linéarité C4.**
- Emplacement : `app/scaling/engine.py:138-142` (branche `else` → `"scaling geometric delegue a C2/C3"`) + `:162-166` (note non-linéaire).
- Observation : `scale("temps", 20, "min", 2.0).notes == ["scaling geometric delegue a C2/C3", "-- ne se double pas proprement au-delà de ~1.5–2×"]`. Le chemin `scale()` ne calcule pas le temps (valeur non scalée + note de délégation) mais émet quand même la note générique de non-linéarité, car la catégorie `temps` porte `nonlinearFlag:true`.
- Impact : **conforme à la story** (C4 décore `scale` ; le vrai calcul temps passe par `scale_time`, C3, inchangé). Pas de doublon de la note non-linéaire (idempotence OK, garde `if NONLINEAR_NOTE not in notes`). La Dev Note de C4 anticipe ce croisement et demande l'idempotence — respectée.
- Recommandation : aucune. Signalé pour traçabilité ; le consommateur réel du temps appelle `scale_time`, pas `scale`.

---

## Vérification des Acceptance Criteria

| AC | Exigence | Verdict | Preuve |
|----|----------|---------|--------|
| AC1 | Note exacte `-- ne se double pas proprement au-delà de ~1.5–2×` si `nonlinear_flag` ET `k ≥ K_NONLINEAR_THRESHOLD` ; absente si `k < seuil` | **PASS** | `engine.py:159-166` ; `NONLINEAR_NOTE` verbatim (`:37`, tiret cadratin U+2013 + `×` U+00D7) ; `test_flag_non_lineaire_actif` (piment k=2.0), `test_flag_non_lineaire_inactif` (k=1.2) |
| AC2 | Scission 90/10 sur la valeur scalée ; `reserve={incorporate,reserve,pct}` ; somme = valeur ; note `--` | **PASS** | `engine.py:172-185` ; `test_reserve_sel` (90/10, somme via `approx`, note présente) — cf. L1 sur la tolérance |
| AC3 | `notes` + `debug` (`nonlinear`, `threshold` systématiques ; `reserve_pct` si réserve) | **PASS** | `engine.py:160-161,182` ; `test_remontee_debug` (piment/tomate `nonlinear`+`threshold`, sel `reserve_pct`) |
| AC4 | Seuil = constante `K_NONLINEAR_THRESHOLD` (jamais `1.5` codé) ; `pct` lu dans la table (jamais `10` codé) | **PASS** | `engine.py:162` référence la constante (`:31`, définie une fois en C3) ; `:173-183` lit `rule.reserve_pct`. Aucun littéral `1.5`/`10`/`0.9`/`0.1` dans la logique métier ; seuls `100`/`0` (conversions %) présents, admis par D7 |
| AC5 | Déterminisme/idempotence ; non-régression C1 (`linear`/`sublinear`/`fixed`) et C3 (`scale_time`) | **PASS** | `test_c4_deterministe` (notes/reserve/debug identiques) ; `test_c1_non_regression_sel` (sel≈1.68) ; `test_pas_de_reserve_hors_categorie` (tomate=400) ; `test_temperature_figee` (four=180/fixed) inchangé ; `scale_time` non touché (`test_temps_*` verts, temps≈31.75) ; gardes idempotence `if ... not in notes` (`:165,184`) |

## Vérifications transverses (Blind / Edge)

- **Pas de coefficient/seuil codé en dur (D7)** : confirmé — seuil via constante, `pct` via `rule.reserve_pct`, flag via `rule.nonlinear_flag`. Conforme.
- **Source de vérité** : `table-scaling-sale.json` confirme `sel` → `reserve_pct:10` ; `piment`/`temps` → `nonlinearFlag:true`. `table.py:119-130` peuple bien `nonlinear_flag`/`reserve_pct` dans `ScalingRule` (hors-scope mais vérifié comme prérequis C1 → OK, aucune mutation nécessaire).
- **Généralisation maîtrisée** : réserve appliquée à toute catégorie portant `reserve_pct` (pas de test sur le nom « sel ») — `engine.py:173`. Conforme à l'hypothèse de la story.
- **Frontière du seuil** : `k >= K_NONLINEAR_THRESHOLD` (inclusif) — cohérent avec AC1 (« dès `k ≥ seuil` »).
- **Réserve indépendante du seuil k** : la réserve s'applique quel que soit `k` (y compris `k=1.0`). Conforme à AC2 (l'AC ne conditionne pas la réserve à un seuil ; seul le flag de non-linéarité l'est).
- **Champ `ScaledQuantity.reserve`** : typé `dict | None`, défaut `None` (`engine.py:57`) — aucun appelant existant ne le lit, pas de rupture C1.
- **Contrat de pureté (OA1/§5.1)** : aucune I/O, aucun état mutable global ajouté par C4. Déterminisme vérifié.
- **Hors-scope respecté** : `table.py` et la table JSON non modifiés ; logique C2/C3 intacte.

---

## Verdict global

**APPROUVÉ.** L'implémentation C4 satisfait l'intégralité des AC1–AC5 et de la DoD (aucun seuil/taux codé en dur, remontée `notes`/`reserve`/`debug`, déterminisme/idempotence, non-régression C1/C3). Suite de tests verte (18/18). Les deux findings sont de sévérité **Faible** et purement informatifs/documentaires — aucun ne bloque la livraison.

## Recommandation

**C4 peut passer en `done`.** Aucune correction requise. Les points L1 (formulation de la garantie de somme) et L2 (cumul de notes sur `scale("temps")`) sont consignés pour information ; ils peuvent être traités opportunément (ex. lors de C5) mais ne conditionnent pas la clôture de C4.
