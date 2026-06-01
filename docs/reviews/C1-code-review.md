# Revue de code adversariale — Story C1

- **Story** : C1 — Types linear/sublinear/fixed + lecture de la table
- **Date** : 2026-06-01
- **Périmètre** : `app/scaling/table.py`, `app/scaling/engine.py` (classify + scale linear/sublinear/fixed uniquement), `tests/test_scaling.py`. Les stubs C2/C3/C4 sont hors périmètre.
- **Mode** : revue en lecture seule, non-interactif. Aucun fichier applicatif modifié.
- **Couches d'analyse** : Blind Hunter (diff seul), Edge Case Hunter (branches/bornes), Acceptance Auditor (AC/DoD).

## Verdict global

**APPROUVÉ — C1 peut passer en `done`.**

Les 6 AC sont satisfaits (vérifiés à l'exécution), la DoD « aucun coefficient codé en dur » est respectée, le contrat de pureté/déterminisme tient, et la suite de tests est verte (4 passed, 2 skipped C2/C3). Une seule réserve défensive non bloquante (mutabilité du cache) est consignée en `minor`.

## Vérifications à l'exécution (preuves)

| AC | Attendu | Mesuré | OK |
|----|---------|--------|----|
| AC1 lecture unique | `load_table()` chargée une fois | `load_table() is load_table()` → `True` (lru_cache) | ✅ |
| AC2 token entier | `vol-au-vent` ≠ `ail` | `classify("vol-au-vent")` → `linear` ; `classify("ail")` → `sublinear` | ✅ |
| AC2 casse/accents | `SEL`, `température` classés | `SEL`→`sublinear`, `température`→`fixed` | ✅ |
| AC3 sel sous-linéaire | < 2 (≈1.68) | `scale("sel",1,…,2.0).value` = `1.6818` | ✅ |
| AC4 tomate linéaire | 400 | `scale("tomate",200,"g",2.0).value` = `400.0` | ✅ |
| AC5 température figée | 180, fixed | `scale("four",180,…,2.0)` → `180`, `fixed=True` | ✅ |
| AC6 sortie structurée | name/value/unit/type/fixed/notes/debug | présents (+ `reserve` pour C4) | ✅ |

Robustesse complémentaire vérifiée : multi-mots contigus (`sauce soja`→sublinear ; `soja sauce` et `sauce de soja`→linear), accents (`température`→fixed), nom vide / espaces / numérique → `linear` (pas de crash), délégation discrete/geometric (oeuf/temps → valeur non scalée + note, sans planter), aucune régression sur la suite complète.

## Findings classés par sévérité

### Blocker
_Aucun._

### Major
_Aucun._

### Minor

- **M1 — Le cache `lru_cache` expose un dict mutable partagé (risque de corruption en lecture seule).**
  `load_table()` retourne à chaque appel **le même objet** dict. La DoD/AC1 exige « lecture seule, ne jamais muter la structure chargée ». Le module C1 lui-même ne mute jamais (correct), mais rien n'empêche un futur appelant (C2/C3/C4 ou un test) de muter `load_table()["categories"]` et de corrompre durablement le cache pour tout le process.
  Preuve : après `load_table()["categories"].append({...})`, l'élément persiste dans un nouvel appel `load_table()` (« mutation leaked: True »).
  Localisation : `app/scaling/table.py:80-86`.
  Correctif possible (non appliqué, hors mode lecture seule) : renvoyer une copie défensive (`copy.deepcopy`) ou figer la structure (types immuables / `MappingProxyType`) en sortie de cache. Défensif : n'affecte aucun AC de C1 aujourd'hui.

### Nit

- **N1 — `ScaledQuantity.value` peut être un `int` pour les types fixed/discrete/geometric.**
  Pour `linear`/`sublinear` la valeur est un `float` ; pour `fixed`/`discrete`/`geometric` elle est l'`qty` d'entrée telle quelle (donc `int` si l'appelant passe un `int`, ex. `scale("four",180,…)` → `value=180` de type `int`). Le type hint annonce `value: float`. Sans impact (les tests `== 180`/`== 400` passent), mais une normalisation `float(...)` homogénéiserait la sortie. `engine.py:62-71`.

- **N2 — `formula` est en français pour fixed/délégation (`"qty (inchange)"`, `"qty (non scale)"`) alors que les autres sont en pseudo-formule anglaise (`"qty * k"`).** Cohérence mineure du champ `debug.formula`. Convention projet : code/clés en anglais. `engine.py:60,65,70`.

- **N3 — `coeff is None` en sublinear retombe silencieusement sur `1.0` (→ comportement linéaire).** Garde-fou défensif raisonnable, mais si une catégorie sublinear de la table oubliait `coeff`, le scaling deviendrait linéaire sans signal. Aucune catégorie sublinear de la table actuelle n'est concernée (toutes ont un `coeff`). `engine.py:58`.

## Dismiss (bruit / faux positifs écartés)

- « Pas de validation de `k`/`qty` négatifs ou nuls » : hors périmètre C1 (le moteur est pur ; la validation d'entrée relève des couches appelantes). Déterminisme conservé.
- « `classify` ne gère pas les regex » : décision d'architecture explicite (§5.3 : mots-clés, pas regex). Conforme.
- « `reserve_pct` lu mais non appliqué » : volontaire — la réserve 10 % est C4 (documenté dans la story).
- « Pas d'`__init__.py` modifié » : conforme au périmètre (les 3 fichiers cibles uniquement ; docstring de cadrage conservée).

## Conformité DoD

- ✅ **Aucun coefficient codé en dur** : `coeff`, `exponent`, `nonlinearFlag`, `reserve_pct` tous lus depuis la table. Aucun littéral `0.75`/`0.6667` dans le code.
- ✅ **Lecture unique, lecture seule** : `@lru_cache(maxsize=1)`, le module ne mute jamais la table (cf. réserve défensive M1 côté appelants).
- ✅ **Pureté / déterminisme** : aucune I/O hors lecture table, pas d'état mutable global muté, même entrée → même sortie.
- ✅ **Matching token entier, insensible casse/accents** : NFKD + suppression combinantes + minuscule + tokenisation alphanumérique + comparaison de séquences contiguës.
- ✅ **Sortie `ScaledQuantity`** conforme à l'AC6 et à l'archi §5.6 (+ `reserve` prévu C4).
- ✅ **Tests** : skip global retiré ; 4 tests C1 verts ; 2 stubs C2/C3 en skip local. `pytest` global vert, aucune régression.
- ✅ **Périmètre** : `discrete`/`geometric` non implémentés mais routés en sécurité (valeur non scalée + note), API stable pour C2/C3.

## Recommandation

**C1 → `done`.** Aucun finding bloquant ni majeur. M1 (mutabilité défensive du cache) et N1–N3 sont à verser au backlog d'amélioration (idéalement traités quand C2/C3 consommeront `load_table()`), mais ne justifient pas de retenir C1.
