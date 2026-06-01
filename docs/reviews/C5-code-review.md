# Revue de code adversariale — Story C5

- **Story** : C5 — Tests unitaires déterministes + notebook de calibration
- **Statut entrant** : `review`
- **Date** : 2026-06-01
- **Reviewer** : agent BMAD `bmad-code-review` (couches Blind Hunter / Edge Case Hunter / Acceptance Auditor + triage)
- **Mode** : non-interactif, lecture seule
- **Périmètre revu (uniquement)** :
  - `tests/test_scaling.py` — ajouts C5 : tests de déterminisme N=200 (`scale`/`scale_eggs`/`scale_time`), scénarios paramétrés ×2/÷2/×4, monotonie/réduction, repère backlog temps ×4.
  - `notebooks/calibration_scaling.ipynb` — notebook de calibration amorcé (moteur vs ×N naïf).
- **Hors périmètre (non revu)** : `app/scaling/*` (C1-C4, done/approuvés), tests C1-C4 existants.

---

## Vérifications empiriques

| Contrôle | Commande / méthode | Résultat |
|---|---|---|
| pytest vert sans skip | `pytest tests/test_scaling.py -v` | **38 passed / 0 skipped** |
| Aucun `skip`/`xfail`/`pytestmark` | grep ciblé | Seule occurrence : le mot « skip » en prose dans la docstring de module. Aucun marqueur. |
| Notebook = JSON nbformat v4 valide | `json.load` + inspection | nbformat **4.5**, 7 cellules (markdown, 5×code, markdown). JSON valide. |
| Notebook exécutable « Run All » | `exec` séquentiel des cellules code | **OK** bout-à-bout, sans erreur ; assertion linéaire==naïf passe. |
| Accents UTF-8 | chargement `encoding='utf-8'` | é, œ, ×, ÷, →, «» corrects dans le fichier source (les `?` console = cp1252 Windows, pas un défaut fichier). |
| `notebooks/.gitkeep` préexistant | `Test-Path` | Présent (non recréé, conforme archi §10). |

## Conformité des valeurs attendues à la table de scaling

Valeurs recalculées depuis `docs/scaling/table-scaling-sale.json` et comparées aux assertions :

| Cas | Table | Calcul | Test C5 | Verdict |
|---|---|---|---|---|
| sel ×2 (c.a.c) | coeff 0.75 | `1×2^0.75 = 1.6818` | `approx(1.68, abs=0.01)` | ✓ |
| sel 200g ×2 | coeff 0.75 | `200×2^0.75 = 336.36` | `approx(200×k^0.75)` + notebook « ~336 » | ✓ |
| tomate ×k | défaut linear | `200×k` | `approx(200×k)` | ✓ |
| température | fixed | `180` ∀ k | `==180`, `fixed is True` | ✓ |
| œufs 3 ×2 | round down + RZ1 | 6→5 (œuf liant) | `==5` | ✓ |
| œufs 3 ×4 | RZ1 | 12→11 | `==11` | ✓ |
| œufs 3 ÷2 | floor | `floor(1.5)=1` | `==1` | ✓ |
| œufs 2 ×1.5 | floor | `floor(3.0)=3` | `==3` | ✓ |
| temps ×2 | exponent 0.6667 | `20×2^0.6667 = 31.75` | `approx(32, abs=0.5)` | ✓ |
| temps ×4 | exponent 0.6667 | `20×4^0.6667 = 50.40` | `approx(50.4, abs=0.5)` | ✓ |
| temps ÷2 | exponent 0.6667 | `20×0.5^0.6667 = 12.60` | `approx(12.6, abs=0.5)` | ✓ |

Aucun coefficient n'est codé en dur de façon erronée. Les exposants/coeffs sont soit lus par le moteur (que les tests appellent), soit répliqués comme attendus avec commentaire de provenance. Le couplage est correct : les attendus correspondent à la table.

## Robustesse du test de déterminisme (point de vigilance #1)

Les tests de déterminisme ne sont **pas** des tests « toujours verts » triviaux :

- N=200 exécutions (≥ 100 requis par AC2).
- Double vérrouillage : (a) collecte des snapshots structurels figés dans un `set` puis `assert len(snapshots) == 1` — un seul snapshot distinct toléré ; (b) égalité dataclass `==` complète (debug inclus) sur les 200 runs.
- Snapshot porteur de sens : `name/value/unit/type/fixed/notes/reserve` (et équivalents eggs/time), `reserve` dict normalisé via `tuple(sorted(...))`.
- Le test échouerait réellement si une source de non-déterminisme était introduite (ex. ordre de `set`, horodatage, `random`) : le `set` de snapshots aurait > 1 élément. Test probant.

## Findings (par sévérité)

### Bloquants
Aucun.

### Majeurs
Aucun.

### Mineurs / observations (non bloquants, `defer` ou `dismiss`)

1. **[Observation — dismiss] Hétérogénéité sémantique de la colonne « écart » dans le notebook.**
   Pour `oeuf`, l'écart compare un *nombre d'œufs* (5 vs 6) ; pour `temps`, des *minutes* (31.75 vs 40). Mélanger ces unités dans une seule colonne « écart » est imprécis. **Dismiss** : c'est l'amorce explicitement codée en dur (cellule Markdown « Amorce sprint 1 »), la version corpus-réel post-S0.6 structurera les comparaisons par ingrédient réel. Documenté, conforme AC4.

2. **[Patch trivial — defer] Double appel de `classify(name)` par ligne dans `comparer()`.**
   `comparer` appelle `classify(name)` pour la colonne `type` alors que `moteur_value` l'a déjà appelé. `classify` est caché (table chargée une fois), impact nul. **Defer** : micro-nettoyage cosmétique, hors enjeu de correction.

3. **[Observation — dismiss] `scale_time` non comparé à `÷2` dans une assertion dédiée au repère chiffré.**
   `test_scenario_temps_x4_repere_backlog` couvre ×4 et ×2 mais pas ÷2 en repère explicite ; toutefois `test_scenario_temps_geometrique[0.5]` asserte déjà `≈12.6`. **Dismiss** : couverture ÷2 présente via le test paramétré.

## Couverture des Acceptance Criteria

- **AC1** (pytest vert sans skip) : ✓ 38 passed / 0 skipped, aucun marqueur skip/xfail.
- **AC2** (déterminisme N≥100) : ✓ N=200 sur scale/scale_eggs/scale_time, égalité structurelle stricte + snapshots figés.
- **AC3** (×2/÷2/×4 ingrédients représentatifs) : ✓ tomate(linear)/sel(sublinear)/température(fixed)/œuf(discrete)/temps(geometric), monotonie + réduction k=0.5 + fixed inchangé, repères chiffrés corrects.
- **AC4** (notebook amorcé moteur vs ×N naïf) : ✓ nbformat v4 valide, Run-All OK, table `qty_base|×N_naïf|moteur|écart`, disclaimer `meta.disclaimer` rappelé, cellule « complet après S0.6 → F2/E3 ».

DoD (sprint-status) : intégralement satisfaite.

## Verdict

**APPROUVÉE — 0 bloquant / 0 majeur.** Les findings restants sont mineurs (1 defer cosmétique, 2 dismiss). La suite est verte sans skip, le déterminisme est réellement probant, les valeurs attendues correspondent à la table, et le notebook est valide/exécutable.

**Recommandation : C5 peut passer en `done`.**

## Note de cohérence sprint 1

C1 (done, approuvée), C2 (done), C3 (done), C4 (done) et C5 (cette revue, approuvée) constituent un sprint 1 cohérent : `app/scaling/` est pur et déterministe, et C5 le prouve par les tests (déterminisme N=200 + ×2/÷2/×4) sans réimplémenter de logique métier ni toucher `app/scaling/*`. La partie « corpus réel » du notebook est correctement différée à post-S0.6 (sprint 2), conforme aux dépendances déclarées (`C5.deps = [C1,C2,C3,C4,S0.6]`).
