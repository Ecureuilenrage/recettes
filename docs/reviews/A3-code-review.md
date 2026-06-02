# Revue de code adversariale — Story A3

- **Story** : A3 — Filtrage des voisins par cuisine/contraintes (couche 1, associations Epicure)
- **Statut entrant** : `review`
- **Date** : 2026-06-02
- **Reviewer** : agent BMAD `bmad-code-review` (couches Blind Hunter / Edge Case Hunter / Acceptance Auditor + triage)
- **Mode** : non-interactif, lecture seule (seul fichier écrit : la présente revue)
- **Périmètre revu (uniquement les livrables A3)** :
  - `app/epicure/filter.py` (**nouveau**) — `filter_neighbors(...)`, `Constraints` local, dataclasses `KeptNeighbor` / `FilteredNeighbors` (+ `to_debug()`), helpers `_strip_accents` / `_normalize` recopiés, loaders JSON `lru_cache`, `_resolve_cuisine_context`.
  - `app/epicure/diet_exclusions.json` (**nouveau**) — table régime → clés Epicure exclues (`vegetarien`, `vegan`).
  - `tests/test_filter.py` (**nouveau**) — 16 tests (import direct de `app.epicure.filter`).
  - `docs/stories/A3.md` — AC + DoD audités.
- **Hors périmètre (non revu, sauf non-régression)** : A4 (`translate.py`, `fr_aliases.json`, `test_translate.py`), `app/epicure/loader.py`, `app/epicure/__init__.py`, `app/knowledge/*`, `app/scaling/*`.

---

## Vérifications empiriques

| Contrôle | Commande / méthode | Résultat |
|---|---|---|
| pytest suite complète | `python -m pytest -q` | **93 passed / 0 skipped** (0 régression ; baseline 68 + 16 A3 + 9 A4/sœurs) |
| pytest filtre A3 | `python -m pytest tests/test_filter.py -q` | **16 passed** |
| AC1 — signature exacte | `inspect.signature(filter_neighbors)` | `(candidates: list[tuple[str, float]], cuisine: str, constraints: Constraints) -> FilteredNeighbors` — conforme archi §4.1 ✓ |
| AC1 — `candidates=[]` | `filter_neighbors([], 'italian_savory_v1', Constraints())` | `FilteredNeighbors` ; `kept=[]`, `rejected=[]` (aucune erreur) ✓ |
| AC2 — invariant + aucun rejet cuisine | `filter_neighbors(4 cands, 'italian_savory_v1', Constraints())` | `len(kept)+len(rejected)==4`, `rejected==[]`, annotation `Mediterranean` sur les 4 ✓ |
| AC2 — dégradation cuisine inconnue | `cuisine='klingon'` | annotation `"unknown"`, aucun rejet, aucune exception ✓ |
| AC2 — dégradation cuisine vide | `cuisine=''` | annotation `"unknown"`, aucun rejet ✓ |
| AC2 — fichier macro absent | `_MACROREGIONS_PATH` → fichier inexistant | annotation `"unknown"`, aucune exception (OSError → mapping vide) ✓ |
| AC3 — `diet=['végétarien']` | appel réel | `chicken` dans `rejected` (raison FR), `tomato`/`basil`/`olive_oil` dans `kept` ✓ |
| AC3 — sans régime | `Constraints()` | `chicken` dans `kept`, `rejected==[]` ✓ |
| AC3 — casse/accents | `'VÉGÉTARIEN'` / `'vegetarien'` / `'Vegetarien'` / `'  Végétarien  '` | `chicken` rejeté dans les 4 variantes (résultats identiques) ✓ |
| AC3 — régime inconnu | `diet=['sans_gluten']` | `rejected==[]` (no-op) ✓ |
| AC4 — tuples sérialisables | inspection `rejected` | entrées `tuple` de longueur 3 ; `to_debug()` → `json.dumps` OK ✓ |
| AC4 — score préservé | score d'entrée vs `rejected`/`kept` | `chicken`=0.42 (rejeté), `tomato`=0.91 / `olive_oil`=0.77 (kept) inchangés ✓ |
| AC5 — déterminisme | 50 exécutions identiques | `FilteredNeighbors` identique à chaque rejeu ✓ |
| AC5 — ordre préservé | `[basil, chicken, tomato, beef]` + `diet=['vegetarien']` | `kept=[basil, tomato]`, `rejected=[chicken, beef]` (ordre d'entrée) ✓ |
| Règle inter-couches (archi §3.1) | grep `import app.knowledge` / `import app.scaling` dans `filter.py` | **Aucun import** (helpers recopiés, commentaire explicatif uniquement) ✓ |
| `__init__.py` intact | lecture `app/epicure/__init__.py` | non modifié ; ne ré-exporte pas `filter_neighbors` (attendu, fusion par l'orchestrateur, hors périmètre dev) ✓ |
| Clés de la table dans le vocab | diff `diet_exclusions.json` ∩ `docs/epicure/vocab.csv` | 0 clé orpheline (vegetarien + vegan toutes présentes ; `poultry`/`guanciale` exclus à raison) ✓ |

## Conformité à la signature prescrite (archi §4.1)

| Signature prescrite | Implémentation A3 | Verdict |
|---|---|---|
| `filter_neighbors(candidates: list[tuple[str, float]], cuisine: str, constraints: Constraints) -> FilteredNeighbors` | signature **exacte** (`filter.py:230-234`), aucune dérivation des noms/ordre de paramètres ni du type de retour | ✓ |
| `FilteredNeighbors` expose `kept` + `rejected[(name, score, reason)]` | dataclass stdlib `frozen` ; `kept: list[KeptNeighbor]` (`name`, `score`, `cuisine_context`), `rejected: list[tuple[str, float, str]]` ; `to_debug()` sérialisable FR7 | ✓ |
| `Constraints` local minimal aligné §9.1 | dataclass stdlib `diet`/`no_cookware`/`highlight` (listes via `default_factory`), **sans import** du `Constraints` de `app/knowledge` (découplage) | ✓ |

La signature prescrite est respectée au caractère près, y compris le commentaire d'intention en fin de signature. `filter_neighbors` est pure (aucun état mutable global ; les loaders sont `lru_cache` en lecture seule), ce qui satisfait l'exigence de déterminisme (archi §5.1).

## Décision D14 — filtrage cuisine SOUPLE (point central de la story)

Le cœur de A3 est l'hypothèse figée par l'archi §4.1 et D14 : **le filtrage cuisine n'écarte jamais un voisin, il l'annote**. C'est réellement le cas et c'est prouvé empiriquement.

- `_resolve_cuisine_context(cuisine)` résout `cuisine` → macro-région par une heuristique v1 documentée : on normalise `cuisine` (casse/accents) puis on teste si le **radical (4 lettres)** d'une tradition de `cuisine_macroregions.json` est contenu dans la cuisine normalisée. `Italian` → radical `ital` ⊂ `italian_savory_v1` → `Mediterranean`. Vérifié : les 4 voisins d'une cuisine italienne portent `cuisine_context == "Mediterranean"`.
- Cette résolution n'intervient **que dans l'annotation** : le `cuisine_context` est posé sur `KeptNeighbor`, jamais utilisé comme critère de rejet. La seule branche qui peuple `rejected` est le test `name in excluded_keys` (régime). Confirmé par lecture du corps de boucle (`filter.py:263-269`) et par le test `test_invariant_avec_et_sans_donnees_cuisine` qui asserte qu'**aucune** raison de rejet ne contient le mot « cuisine ».
- **Dégradation gracieuse réellement exercée** (D14, archi §8.1) : trois chemins de défaillance testés en vrai — cuisine inconnue (`"klingon"`), cuisine vide (`""`), et fichier `cuisine_macroregions.json` rendu introuvable (monkeypatch + `cache_clear()`). Les trois retournent `"unknown"` sans exception et sans supprimer un voisin. Le loader capture `(OSError, ValueError)` et retombe sur un mapping vide.

## Edge Case Hunter — sondes réelles

J'ai exécuté les scénarios limites demandés (résultats observés en direct, pas déduits) :

```
régime excluant TOUT      [chicken, beef] + vegetarien -> kept=[],   rejected=2   # kept vide OK
doublons                  [chicken, chicken, tomato]   -> rejected=[chicken, chicken], kept=[tomato]
score négatif / zéro      [(chicken,-0.5),(tomato,0.0)] -> chicken rejeté avec score -0.5 ; tomato kept 0.0
union multi-régimes       [egg, chicken, tomato] + [vegetarien, vegan] -> rejected={chicken, egg}  # union correcte
JSON diet malformé        '{not valid json'           -> rejected=[], kept=[chicken]   # no-op gracieux, pas d'exception
fichier macro absent      _MACROREGIONS_PATH inexistant -> cuisine_context="unknown"   # pas d'exception
```

- **kept vide** : géré nativement (l'invariant tient, `kept=[]`). La politique « que faire si tout est rejeté » est correctement documentée comme relevant de la couche 4/API, hors A3.
- **Doublons** : chaque occurrence est traitée indépendamment (pas de dédup) — comportement cohérent et déterministe ; non spécifié comme devant dédupliquer.
- **Score négatif / 0** : préservé tel quel (aucun recalcul), conforme AC4.
- **Clé de régime absente du JSON** : `exclusions.get(_normalize(diet), frozenset())` → ∅, no-op vérifié.
- **JSON `diet_exclusions.json` mal formé / clés non normalisées** : le loader ignore les clés `_`-préfixées et les valeurs non-listes, normalise chaque clé de régime, et capture `ValueError` → mapping vide. Robuste.

**Risque réel vs théorique sur l'heuristique cuisine (radical 4 lettres).** Le matching « radical ⊂ cuisine normalisée » est une heuristique grossière : un radical de 4 lettres pourrait en théorie produire une collision (ex. une cuisine future dont l'identifiant contiendrait par hasard une sous-chaîne `ital`/`thai`/`indi`). Comme l'annotation **ne participe pas à la sélection** (souple, D14), une mauvaise étiquette n'écarte **aucun** voisin : l'impact maximal est une annotation debug FR7 imprécise, jamais une perte d'association ni une exception. Risque **cosmétique** sur l'explicabilité, pas fonctionnel. Voir finding mineur #1 (defer).

## Couverture de test — probante et non tautologique

Les 16 tests couvrent AC1–AC5. J'ai vérifié qu'ils **échoueraient** si le comportement était cassé :

- `test_rejet_dur_vegetarien_exclut_chicken` asserte à la fois `chicken ∈ rejected` **et** `chicken ∉ kept` **et** la présence de `tomato`/`basil`/`olive_oil` dans `kept` : si la branche d'exclusion sautait, l'assertion `chicken in rejected_names` casserait ; si elle sur-filtrait, les assertions sur `kept` casseraient. Non tautologique.
- `test_cuisine_souple_aucun_voisin_supprime` verrouille `len(kept)==len(candidates)`, `rejected==[]` **et** `cuisine_context=="Mediterranean"` : casse si la cuisine devenait un critère de rejet ou si l'heuristique de radical était rompue.
- `test_invariant_avec_et_sans_donnees_cuisine` (3 cuisines) verrouille l'invariant et l'absence de raison « cuisine » — garde-fou direct de D14.
- `test_regime_insensible_casse_accents` compare 4 variantes au résultat de référence (égalité de set) : casse si `_normalize` cessait de neutraliser casse/accents.
- `test_cuisine_degradation_gracieuse_donnees_absentes` exerce **réellement** le chemin OSError (chemin monkeypatché + `cache_clear()` encadrant) plutôt qu'un stub — exerce le vrai `except`.
- `test_determinisme` (compare l'égalité de dataclass sur 5 rejeux) et `test_ordre_preserve` (kept et rejected dans l'ordre d'entrée) couvrent AC5.
- `test_to_debug_serialisable` + `test_rejected_tuples_pour_fr7` + `test_score_preserve_dans_kept` couvrent AC4 (sérialisation JSON réelle, forme du tuple, score d'origine).

Aucun test tautologique détecté. Les assertions portent sur des identifiants / cardinalités / sets, pas sur du wording fragile (la seule assertion textuelle, `"régime"` et `"végétarien"` ∈ reason, est cohérente avec le contrat AC3 d'une raison FR explicite).

## Modularité (OA3) et données

- `diet_exclusions.json` est une table de données pure : ajouter un régime ou un ingrédient = éditer le JSON. **Aucun régime ni ingrédient n'est codé en dur dans `filter.py`** (la raison de rejet est paramétrée par `constraints.diet`, le code reste agnostique du contenu). Vérifié.
- Les 30 clés de `vegetarien` et les 37 de `vegan` existent **toutes** dans `docs/epicure/vocab.csv` (0 clé orpheline) ; `poultry`/`guanciale` (absents du vocab) sont correctement exclus de la table → aucune entrée morte. Décision `vegan` (héritage des exclusions carnées + œuf/laitiers) documentée dans la story et les Completion Notes.

## Règle inter-couches & anti-conflit

- `app/epicure/filter.py` n'importe **ni** `app.knowledge` **ni** `app.scaling` (grep : aucun match). Les helpers `_strip_accents` / `_normalize` sont **recopiés** (commentaire explicatif renvoyant à `app/scaling/table.py:52-77`), conformément à la décision de découplage. Duplication volontaire et documentée.
- `app/epicure/__init__.py` est **intact** : il ne ré-exporte pas encore `filter_neighbors`/`FilteredNeighbors`/`Constraints`. C'est **attendu** (la fusion des exports publics est du ressort de l'orchestrateur, règle anti-conflit avec A4) et **hors périmètre dev A3** — ce n'est donc PAS un défaut. Les tests importent `app.epicure.filter` directement, ce qui les rend indépendants de cette fusion.
- `app/epicure/loader.py` non touché (lecture seule respectée). Périmètre 3 fichiers (`filter.py`, `diet_exclusions.json`, `test_filter.py`) respecté.

## Couverture des Acceptance Criteria

- **AC1** (signature exacte + `FilteredNeighbors{kept, rejected[(name,score,reason)]}` ; clés déjà résolues ; `candidates` vide → tout vide) : ✓ signature archi §4.1 exacte, vérifiée empiriquement.
- **AC2** (cuisine SOUPLE + dégradation gracieuse D14 ; `len(kept)+len(rejected)==len(candidates)` ; aucun rejet « cuisine » ; annotation neutre si données absentes) : ✓ annotation `Mediterranean`/`unknown`, trois chemins de dégradation testés, invariant verrouillé.
- **AC3** (rejet dur régime déterministe ; `chicken` rejeté sous `végétarien`, conservé sans contrainte ; insensible casse/accents ; régime inconnu = no-op) : ✓ tous les cas vérifiés en direct, test probant.
- **AC4** (`rejected` = tuples `(name, score, reason)` sérialisables FR7 ; score d'origine préservé ; représentation sérialisable via `to_debug()`) : ✓ `json.dumps(to_debug())` OK, score préservé.
- **AC5** (pure/déterministe ; ordre préservé ; tests importent `app.epicure.filter` directement ; suite verte sans régression) : ✓ 16 tests, `pytest -q` → **93 passed**, import direct confirmé.

DoD (tâches 0–5 cochées, périmètre 3 fichiers, `__init__.py`/`loader.py` non touchés, pas d'import inter-couches, aucune nouvelle dépendance) : satisfaite.

## Findings (par sévérité)

### Bloquants
Aucun.

### Majeurs
Aucun. (La signature prescrite est exacte ; D14 — filtrage cuisine souple — est réellement implémentée et prouvée ; le rejet dur de régime est déterministe, modulaire et insensible casse/accents ; aucun test n'est tautologique.)

### Mineurs / observations

1. **[defer] Heuristique cuisine par radical de 4 lettres — risque de collision cosmétique.**
   `_resolve_cuisine_context` matche si un radical de 4 lettres d'une tradition est contenu dans la cuisine normalisée. Une cuisine future dont l'identifiant contiendrait par hasard une telle sous-chaîne (`ital`, `thai`, `indi`…) pourrait recevoir une macro-région erronée. **Sans impact fonctionnel** : l'annotation cuisine est souple (D14), elle ne supprime jamais un voisin ; l'effet maximal est une étiquette debug FR7 imprécise, jamais une exception ni une perte d'association. Heuristique v1 explicitement documentée comme telle dans la story. **Defer** (à affiner si une vraie résolution de cuisine est requise par une story aval, ex. D1).

2. **[defer] `no_cookware` / `highlight` portés mais non utilisés par le filtrage.**
   `Constraints` expose `no_cookware` et `highlight` pour l'alignement de schéma §9.1, mais `filter_neighbors` ne les consulte pas (le cookware relève de la couche 2 / B4, et `highlight` est un signal couche 4). C'est **conforme** au périmètre A3 documenté (« A3 garde `no_cookware` pour l'alignement de schéma mais ne filtre pas dessus »). Simple observation, pas un défaut. **Defer.**

3. **[defer] Pas de déduplication des candidats en double.**
   Un même `(name, score)` présent deux fois est traité deux fois (deux rejets ou deux `kept`). Comportement déterministe et non spécifié comme devant dédupliquer ; en pratique `EpicureIndex.neighbors` ne produit pas de doublons. Aucun risque réel. **Defer.**

## Verdict

**APPROUVÉE — 0 bloquant / 0 majeur / 3 mineurs (defer).**

A3 livre exactement ce que prescrit l'archi §4.1 : `filter_neighbors(candidates, cuisine, constraints) -> FilteredNeighbors` avec la signature au caractère près, `kept` (voisins annotés) + `rejected[(name, score, reason)]` sérialisables pour FR7 (`DebugInfo.epicure`). La décision D14 — **filtrage cuisine SOUPLE** — est réellement implémentée : aucun voisin n'est jamais écarté pour la cuisine (annotation `Mediterranean`/`unknown` seulement), et la **dégradation gracieuse** est prouvée sur trois chemins (cuisine inconnue, cuisine vide, fichier `cuisine_macroregions.json` introuvable) sans jamais lever d'exception. Le **rejet dur de régime** est déterministe, piloté par la table versionnée `diet_exclusions.json` (modulaire OA3, 0 clé orpheline dans le vocab), insensible à la casse et aux accents (« VÉGÉTARIEN » = « vegetarien »), avec no-op sur régime inconnu et sur JSON malformé. Le score d'origine et l'ordre d'entrée sont préservés, l'invariant `len(kept)+len(rejected)==len(candidates)` tient. La règle inter-couches est respectée (aucun import `app.knowledge`/`app.scaling` ; helpers recopiés), `__init__.py`/`loader.py` sont intacts (fusion des exports déléguée à l'orchestrateur, attendu). Les 16 tests sont probants et non tautologiques. Suite complète : **93 passed, 0 régression** (baseline 68).

Les 3 findings restants sont mineurs et `defer` : heuristique cuisine cosmétique (sans impact fonctionnel car souple), `no_cookware`/`highlight` portés pour alignement de schéma (conforme au périmètre), absence de déduplication (non spécifiée, aucun risque réel). Aucun ne remet en cause un AC.

**Recommandation : A3 peut passer en `done`.**
