# Revue de code adversariale — Story B3

- **Story** : B3 — Loader knowledge + `techniques_for(...)` (couche 2, base technique)
- **Statut entrant** : `review`
- **Date** : 2026-06-01
- **Reviewer** : agent BMAD `bmad-code-review` (couches Blind Hunter / Edge Case Hunter / Acceptance Auditor + triage)
- **Mode** : non-interactif, lecture seule (seul fichier écrit : la présente revue)
- **Périmètre revu (uniquement)** :
  - `app/knowledge/loader.py` — dataclasses, helpers de normalisation, `load_safety`/`load_cuisines` (lru_cache), `safety_for`, `_forbidden_cookware` (interne), `techniques_for`.
  - `app/knowledge/__init__.py` — réexport de l'API publique + `__all__`.
  - `tests/test_knowledge.py` — 9 tests structurels/comportementaux.
  - `docs/stories/B3.md` — AC + DoD audités.
- **Hors périmètre (non revu)** : `app/scaling/*` (sprint 1, approuvé), `docs/base-technique/*` (édité par d'autres stories, lecture seule), corpus `recipes/`, `docs/cooklang/`.

---

## Vérifications empiriques

| Contrôle | Commande / méthode | Résultat |
|---|---|---|
| pytest vert sans régression | `python -m pytest tests/test_knowledge.py tests/test_scaling.py -q` | **47 passed / 0 skipped** (9 knowledge + 38 scaling, aucune régression) |
| AC3 — exclusion réelle « pas_de_four » | `techniques_for('italian_savory_v1', None, Constraints(no_cookware=['pas_de_four']))` | `['pasta_al_dente', 'risotto', 'soffritto', 'sugo_pomodoro']` — `searing_braising` **exclue**, 4 conservées ✓ |
| Sans contrainte | `Constraints()` | 5 techniques (les ids attendus) ✓ |
| Découverte modulaire (pas de hard-code) | grep cuisine en dur + `glob("cuisine-*.json")` indexé par `meta.id` | Aucune cuisine ni nom de fichier codé en dur ; `italian_savory_v1` découvert dynamiquement ✓ |
| Règle inter-couches (archi §3.1) | grep des imports de `app/knowledge/*` | Aucun import de `app.scaling` ni d'une autre couche ; seulement stdlib (`json`, `unicodedata`, `dataclasses`, `functools`, `pathlib`). Helpers de normalisation **recopiés**, pas importés ✓ |
| Matching casse/accents `safety_for` | `safety_for('VOLAILLE')`, `safety_for('boeuf')`, `safety_for('oeufs')` | Tous trouvent leur ligne (insensible casse + accents) ✓ |
| Cuisine inconnue | `techniques_for('cuisine_inexistante_v0', ...)` | `[]` (pas d'exception) ✓ |
| `ingredient=None` | `techniques_for(..., None, Constraints())` | 5 techniques (filtrage souple, non bloquant) ✓ |
| Contrainte inconnue | `Constraints(no_cookware=['pas_de_licorne'])` | 5 techniques (clé absente du mapping → ensemble interdit vide) ✓ |
| Déterminisme | 50–100 exécutions identiques (techniques + safety) | Résultat stable ✓ |
| Immuabilité dataclasses de sortie | tentative de mutation `SafetyStandard.critical`, `Cuisine.id` | `FrozenInstanceError` (dataclasses `frozen=True`) ✓ ; `techniques` est un `tuple` ✓ |
| Chargement unique | `load_safety() is load_safety()` ; `load_cuisines() is load_cuisines()` | Même objet (lru_cache maxsize=1) ✓ |

## Conformité aux signatures prescrites (archi §4.2)

| Signature prescrite | Implémentation B3 | Verdict |
|---|---|---|
| `load_safety() -> SafetyTable` | présente, `@lru_cache(maxsize=1)`, retourne `SafetyTable` (tuple de `SafetyStandard`) | ✓ |
| `load_cuisines() -> dict[str, Cuisine]` | présente, découverte `glob` triée, index `meta.id` | ✓ |
| `techniques_for(cuisine: str, ingredient: str \| None, constraints: Constraints) -> list[Technique]` | signature exacte | ✓ |
| `safety_for(food_type: str) -> SafetyStandard \| None` | présente, matching tokens normalisés | ✓ |
| `forbidden_cookware(...)` public | **volontairement absent** (réservé B4) ; helper interne `_forbidden_cookware` présent | ✓ (conforme au découpage B3/B4 documenté) |

Types de sortie en **dataclasses stdlib** (`SafetyStandard`, `SafetyTable`, `Technique`, `Cuisine`, `Constraints`), pas de Pydantic — conforme à la décision par défaut documentée (archi §4.2 « ou dataclasses »). Champs de `Constraints` (`diet`, `no_cookware`, `highlight`) alignés sur archi §9.1.

## Découverte modulaire (AC2 / OA3 / F1)

`load_cuisines()` scanne `BASE_TECHNIQUE_DIR.glob("cuisine-*.json")` (chemins triés → déterministe), charge chaque fichier et indexe par `meta.id`. Aucune cuisine ni nom de fichier en dur. Le test `test_load_cuisines_decouvre_italien` verrouille la découverte de `italian_savory_v1` + cardinalité 5. **Conclusion : ajouter un `cuisine-<x>.json` bien formé suffirait** ; aucun code à modifier. Conforme à schema.md §4.

## Robustesse de l'exclusion cookware (Edge Case Hunter)

Sortie réelle du helper interne et des tokens (consignée) :

```
_forbidden_cookware(italian, Constraints(no_cookware=['pas_de_four']))
  -> {'four', 'moule a four', 'cocotte au four'}
required_tools(searing_braising) (tokenisés)
  -> {'poele','en','fonte','cocotte','avec','couvercle','braise','thermometre',
      'a','lecture','instantanee','four','saisie'}
intersection -> {'four'}  => searing_braising EXCLUE  ✓ (cas normatif AC3)
```

L'exclusion AC3 **fonctionne correctement** parce que l'ustensile discriminant (« four ») est un **mot unique** : il apparaît à la fois comme entrée de l'ensemble interdit et comme token requis. Voir toutefois le finding mineur #1 sur l'asymétrie de représentation (un ustensile interdit **multi-mots** ne matche jamais).

Casse de la **clé** `no_cookware` : `Constraints(no_cookware=['PAS_DE_FOUR'])` (majuscules) → `_forbidden_cookware` renvoie `set()` (la clé n'est pas normalisée avant le `mapping.get`), donc **aucune exclusion**. Voir finding mineur #2. Non bloquant pour AC3 (l'exemple normatif et les tests utilisent la clé canonique en minuscules, conforme au JSON).

## Pureté / déterminisme / cache

- Pas d'I/O réseau, pas de `random`, pas d'horodatage : lecture JSON pure.
- `load_safety` / `load_cuisines` en `@lru_cache(maxsize=1)` : chargement unique, lecture seule.
- Dataclasses de sortie `frozen=True` (`SafetyStandard`, `SafetyTable`, `Technique`, `Cuisine`) ; `techniques`/`standards` en `tuple`. Bon réflexe d'immuabilité.
- **Réserve (finding mineur #3)** : `load_cuisines()` renvoie le **dict caché lui-même** (pas une copie) et l'attribut `cookware_constraints` est un `dict[str, list[str]]` **mutable partagé** avec le cache. Un appelant peut corrompre le cache (`load_cuisines()['x'] = ...` ou `cuisine.cookware_constraints['pas_de_four'].append(...)`), ce qui contamine tous les appels suivants dans le process. Vérifié empiriquement (la pollution persiste). Impact réel faible (les appelants couche 4 ne mutent pas ces structures), mais c'est une entorse au principe « table lue en lecture seule, jamais mutée ».

## Règle de dépendances inter-couches (archi §3.1)

Vérifiée par grep : `app/knowledge/` n'importe **que** la stdlib et son propre `loader`. Aucune dépendance vers `app.scaling` (couche 3) ni une autre couche. Les helpers `_strip_accents`/`_normalize`/`_tokenize` sont **recopiés** depuis le patron `app/scaling/table.py` (choix explicitement documenté et conforme : « les couches ne se connaissent pas entre elles »). ✓

## Qualité des tests (probants, non tautologiques)

- `test_techniques_for_exclut_four` asserte `"searing_braising" not in ids` **et** l'égalité exacte du set des 4 conservées : il **échouerait réellement** si l'exclusion cassait (ni faux positif ni faux négatif toléré). Probant.
- `test_techniques_for_sans_contrainte` verrouille les 5 ids + `isinstance(Technique)`.
- `test_load_cuisines_decouvre_italien` verrouille la découverte par glob + cardinalité.
- `test_safety_for_proteine` porte sur des **propriétés structurelles** (`critical is True`, `min_internal_c is not None`), **jamais** sur le wording — conforme à la contrainte « fichier édité en parallèle ».
- `test_load_safety_structure` vérifie le **chargement unique** (`load_safety() is table`).
- `test_determinisme` : 100 exécutions, techniques **et** safety.

Couverture honnête. **Manque** (finding mineur #4) : aucun test ne verrouille (a) l'insensibilité casse/accents de `safety_for` (ex. `safety_for("VOLAILLE")`), pourtant exigée par AC1, ni (b) le cas « contrainte inconnue ». Les deux comportements sont corrects empiriquement mais non régressés par la suite.

## Findings (par sévérité)

### Bloquants
Aucun.

### Majeurs
Aucun.

### Mineurs / observations

1. **[defer — vers B4] Asymétrie de représentation dans `_forbidden_cookware` → faux négatif latent sur les ustensiles interdits multi-mots.**
   `_forbidden_cookware` ajoute les ustensiles via `_normalize(tool)` (chaîne entière, ex. `'cocotte au four'`, `'moule a four'`, `'robot culinaire'`), alors que `techniques_for` compare cet ensemble à des **tokens** issus de `_tokenize` (mots seuls). L'intersection ne peut donc matcher que les entrées **mono-mot** (« four »). Conséquence : si une technique requérait exactement `'robot culinaire'` et que l'utilisateur coche `pas_de_robot` (mapping `['robot culinaire']`), elle **ne serait pas exclue** (vérifié : `{'robot culinaire'} & {'robot','culinaire'} == set()`). Les entrées multi-mots de l'ensemble interdit sont du **bruit inerte**. Cela ne casse pas AC3 (« four » est mono-mot, et aucune technique italienne ne requiert d'ustensile interdit multi-mots), et le matching robuste est **explicitement renvoyé à B4** par la story (Dev Notes « Périmètre B3 vs B4 »). **Defer** assumé, mais à corriger en B4 : soit tokeniser aussi l'ensemble interdit (`forbidden.update(_tokenize(tool))`), soit comparer par sous-chaîne — sinon B4 héritera d'un helper trompeur. À documenter dans la story B4.

2. **[defer — vers B4] La clé `no_cookware` n'est pas normalisée avant le `mapping.get`.**
   `Constraints(no_cookware=['PAS_DE_FOUR'])` (casse non canonique) → aucune exclusion (`mapping.get('PAS_DE_FOUR')` échoue). AC1/AC3 n'exigent l'insensibilité casse/accents que pour `safety_for` et l'ensemble des ustensiles, pas pour les **clés** de contrainte (qui proviennent de l'enum API). Non bloquant ; le durcissement (tolérance casse/accents « poussée ») est du ressort de B4. **Defer.**

3. **[defer] `load_cuisines()` expose des structures mutables partagées avec le cache.**
   Le dict retourné et les `cookware_constraints`/`parameters`/`raw` internes sont les objets cachés eux-mêmes (pollution du cache vérifiée empiriquement). Aucun appelant actuel ne les mute, et les dataclasses elles-mêmes sont `frozen`, mais le principe « lecture seule, jamais muté » n'est garanti que par convention. Durcissement possible (copies défensives ou `MappingProxyType`) — non requis par les AC. **Defer.**

4. **[defer] Couverture de test incomplète sur deux comportements pourtant spécifiés.**
   AC1 exige un matching `safety_for` insensible casse/accents : aucun test ne le verrouille (seul `safety_for("volaille")` minuscule est testé). De même, le cas « contrainte `no_cookware` inconnue → aucune exclusion » n'est pas couvert. Comportements corrects empiriquement mais non régressés. Ajout de 2 asserts trivial. **Defer.**

5. **[dismiss] `_required_tools_normalized` accepte `technique` mais est appelée correctement.**
   Lors d'un test manuel, l'helper attend un `Technique` (et non une cuisine) ; signature et usages internes cohérents. Aucune action. **Dismiss.**

## Couverture des Acceptance Criteria

- **AC1** (chargement sécurité lecture seule/unique + `safety_for` casse/accents) : ✓ `load_safety` en lru_cache, `SafetyTable` typée, matching insensible casse/accents vérifié empiriquement, schéma de clés stable respecté (mapping tolérant aux clés manquantes). Réserve mineure : insensibilité casse/accents non couverte par un test (finding #4).
- **AC2** (découverte modulaire OA3, aucune cuisine en dur) : ✓ `glob("cuisine-*.json")` trié, index `meta.id`, aucun hard-code, lru_cache. Ajout d'une cuisine = déposer un fichier.
- **AC3** (`techniques_for` exclut technique à ustensile interdit) : ✓ exemple normatif `pas_de_four` → `searing_braising` exclue + 4 conservées, vérifié et verrouillé par test probant. Limite multi-mots (finding #1) explicitement hors périmètre B3.
- **AC4** (dataclasses stdlib + module pur/déterministe, aucune nouvelle dépendance) : ✓ 5 dataclasses stdlib, `frozen` pour les sorties, déterminisme N=100, seulement stdlib (`requirements.txt` non touché).

DoD (tâches 1–5 cochées, périmètre 3 fichiers respecté, aucune touche à `app/scaling/*`, `docs/base-technique/*`, `sprint-status.yaml`, `requirements.txt`) : satisfaite.

## Verdict

**APPROUVÉE — 0 bloquant / 0 majeur.** Les loaders sont purs, déterministes, modulaires (découverte par glob, aucune cuisine en dur) ; l'exclusion cookware d'AC3 fonctionne et est verrouillée par un test probant ; la règle inter-couches est respectée (aucun import de `app.scaling`) ; les dataclasses de sortie sont `frozen`. Les 4 findings restants sont mineurs : trois relèvent du durcissement explicitement délégué à B4 (asymétrie multi-mots, clé non normalisée, structures mutables du cache) et un est une lacune de couverture de test trivialement comblable. Aucun ne remet en cause un AC.

**Recommandation : B3 peut passer en `done`.**

**Note de continuité pour B4** : lors de la promotion de `_forbidden_cookware` → `forbidden_cookware` public, corriger l'asymétrie de représentation (finding #1) — tokeniser l'ensemble interdit ou passer à un matching par sous-chaîne/synonymes — et normaliser la clé `no_cookware` (finding #2). C'est précisément le « matching plus robuste » prévu par la story ; le helper B3 ne doit pas être promu tel quel sans ce correctif sous peine de faux négatifs silencieux sur les ustensiles multi-mots.
