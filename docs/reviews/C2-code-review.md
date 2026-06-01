# Revue de code adversariale — Story C2

- **Story** : C2 — Scaling discret des œufs (`scale_eggs` + `ScaledEggs`)
- **Date** : 2026-06-01
- **Périmètre** : `app/scaling/engine.py` (dataclass `ScaledEggs` + fonction `scale_eggs` + `import math`/`EPS` uniquement), `tests/test_scaling.py` (`test_oeufs_discrets`, `test_oeufs_sans_correction`, `test_oeufs_deterministe`). Le code C1 (`classify`/`scale`/`load_table`/`table.py`) et les stubs C3/C4 sont **hors périmètre** (C1 déjà approuvée).
- **Mode** : revue en lecture seule, non-interactif. Aucun fichier applicatif modifié.
- **Couches d'analyse** : Blind Hunter (code seul), Edge Case Hunter (branches/bornes + accès projet), Acceptance Auditor (AC/DoD vs C2.md, sprint-status, table JSON).

## Verdict global

**APPROUVÉ — C2 peut passer en `done`.**

Les 4 AC sont satisfaits (vérifiés à l'exécution), la réserve **RZ1** est figée, transcrite fidèlement au pseudocode prescrit et commentée `# RZ1` au point de décision (formule + condition de la borne basse). La DoD « aucun coefficient codé en dur » est respectée (`grams_per_unit`/`tbsp_per_unit`/`round` lus via `classify("oeuf")`). Le contrat de pureté/déterminisme tient (égalité `ScaledEggs` reproductible). Suite verte : **7 passed, 1 skipped** (`test_temps_geometrique` laissé à C3). Aucune régression C1. Aucun finding **blocker** ni **major** ; deux réserves défensives non bloquantes consignées en `minor`/`nit`.

## Vérifications à l'exécution (preuves)

| AC / DoD | Attendu | Mesuré | OK |
|----------|---------|--------|----|
| AC1 cas doublé | `scale_eggs(3,2.0).whole_eggs == 5` (pas 6) | `5` | ✅ |
| AC1 reste volume/poids | `≈ 50 g / 3 c.à.s` | `{'grams': 50.0, 'tbsp': 3.0}` | ✅ |
| AC1 note explicative | note non vide | « 6 oeufs theoriques -> 5 entiers + ~50 g (3 c.a.s)… » | ✅ |
| AC2 RZ1 déterministe | algo figé + commenté `# RZ1` | présent (engine.py l.137-148), formule + condition borne basse | ✅ |
| AC3 cas sans correction | `scale_eggs(2,1.5).whole_eggs == 3`, reste nul | `3`, `{'grams': 0.0, 'tbsp': 0.0}` | ✅ |
| AC4 sortie structurée | `whole_eggs:int, remainder, note:str` | présents (+ `type="discrete"`, `debug` bonus, alignés sur `ScaledQuantity`) | ✅ |
| DoD D7 aucun coeff en dur | 50/3/down lus dans la table | `classify("oeuf")` → `discrete 50 3 down` ; aucun littéral 50/3/"down" dans `scale_eggs` | ✅ |
| Déterminisme | même entrée → même `ScaledEggs` | `scale_eggs(3,2.0) == scale_eggs(3,2.0)` → `True` | ✅ |

Robustesse complémentaire vérifiée : branche `else` (`k=1.5`) prend bien le plancher `math.floor` (`round:"down"` de la table) ; la condition borne basse exige simultanément cible ~entière (`< EPS`), `k` entier et `k ≥ 2` (cf. `k=1` → branche plancher, pas de retrait liant) ; arrondis explicites (`EPS`, `math.floor`) garantissant le déterminisme cross-plateforme ; périmètre fichiers respecté (table JSON, `table.py`, `app/scaling/__init__.py` non modifiés — docstring `__init__` conservée) ; aucune régression sur les 4 tests C1.

## Findings classés par sévérité

### Blocker
_Aucun._

### Major
_Aucun._

### Minor

- **M1 — Défaut silencieux `0.0` masquant une table incomplète.**
  `g = rule.grams_per_unit if rule.grams_per_unit is not None else 0.0` (idem `tbsp_per_unit`). Si la catégorie « œuf » perdait un jour ces champs dans la table, `scale_eggs` renverrait silencieusement `remainder = {grams: 0, tbsp: 0}` au lieu de signaler une table incomplète. Choix défensif **raisonnable** (évite un crash, reste déterministe) et inoffensif aujourd'hui (la table porte 50/3, testé). Réserve documentaire seulement — envisager un `debug`/note signalant le repli lorsque le champ attendu manque, si la robustesse de la table devient un sujet (cf. C5/validation). **Non bloquant.**

### Nit

- **N1 — Condition de borne basse pilotée par `k`, pas par `count`.**
  `if abs(target - round(target)) < EPS and float(k).is_integer() and k >= 2:` — un `count` fractionnaire avec un `k` entier ≥2 (ex. `scale_eggs(1.5, 4)` → `target=6.0`) déclencherait la borne basse. Ce cas n'est pas couvert par les AC (entrées attendues : `count` entier) et le comportement est **fidèle au pseudocode prescrit par RZ1** (qui teste explicitement `float(k).is_integer()`). Purement cosmétique / hors périmètre — aucune action requise.

## Findings écartés (bruit / faux positifs)

- **`int(round(target))` et le banker's rounding** : `round()` Python arrondit au pair, mais la branche n'est atteinte que si `target` est déjà à `< EPS` de son entier le plus proche → l'arrondi est sûr et déterministe. Faux positif.
- **`remainder`/`debug` dicts mutables** : instanciés par appel (pas de défaut mutable partagé via `field(default_factory=...)` côté `debug`, et `remainder` construit localement) → pas de partage d'état. Faux positif.
- **Littéraux `50`/`3` dans le test** (`pytest.approx(50)`, `pytest.approx(3)`) : assertions de test légitimes, pas une violation D7 (qui vise `engine.py`). Faux positif.
- **`k ≤ 0` → `whole_eggs` négatif** : aucun AC ne couvre `k ≤ 0` ; contrat moteur global (entrées `k > 0`), à traiter le cas échéant en validation C5, pas en C2. Hors périmètre.

## Triage (synthèse)

- `decision-needed` : 0
- `patch` : 0
- `defer` : 0 (M1/N1 consignés comme réserves documentaires non bloquantes)
- `dismiss` (bruit) : 4

## Recommandation

**C2 est conforme aux AC et à la DoD : passage en `done` recommandé.** Aucun correctif requis avant la fermeture de la story. La réserve **RZ1** est correctement résolue et documentée. Les points M1 (défaut silencieux) et N1 (condition sur `k`) sont des observations de robustesse/cosmétiques hors périmètre C2 ; ne pas bloquer la story pour eux.

---
_Revue menée selon le workflow `bmad-code-review` (3 couches adversariales + triage), périmètre limité à C2, en lecture seule._
