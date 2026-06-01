# Revue de code adversariale — Story B4

- **Story** : B4 — Mapping contraintes matérielles → `#cookware` interdits (couche 2, base technique)
- **Statut entrant** : `review`
- **Date** : 2026-06-01
- **Reviewer** : agent BMAD `bmad-code-review` (couches Blind Hunter / Edge Case Hunter / Acceptance Auditor + triage)
- **Mode** : non-interactif, lecture seule (seul fichier écrit : la présente revue)
- **Périmètre revu (uniquement les ajouts B4)** :
  - `app/knowledge/loader.py` — `forbidden_cookware` (API publique), `_forbidden_mapping` (remplace `_forbidden_cookware` B3), matching durci (`_tool_is_forbidden`, `_is_subsequence`, `_forbidden_token_sequences`), `_technique_exclusion`, `excluded_techniques`, dataclass `Exclusion`, rebranchement de `techniques_for`.
  - `app/knowledge/__init__.py` — réexports + `__all__` (`forbidden_cookware`, `excluded_techniques`, `Exclusion`).
  - `tests/test_knowledge.py` — 13 tests B4 ajoutés.
  - `docs/stories/B4.md` — AC + DoD audités.
- **Hors périmètre (non revu)** : code B3 déjà approuvé (sauf vérification de non-régression), `app/scaling/*`, `docs/base-technique/*` (lecture seule), `recipes/`, `docs/cooklang/`.

---

## Vérifications empiriques

| Contrôle | Commande / méthode | Résultat |
|---|---|---|
| pytest suite complète | `python -m pytest -q` | **68 passed / 0 skipped** (0 régression) |
| pytest knowledge + scaling | `python -m pytest tests/test_knowledge.py tests/test_scaling.py -q` | **60 passed** (22 knowledge [9 B3 + 13 B4] + 38 scaling) |
| AC1 — `forbidden_cookware('italian_savory_v1', no_cookware=['pas_de_four'])` | appel réel | `{'cocotte au four', 'four', 'moule a four'}` — type `set`, normalisé ✓ |
| AC1 — union (deux contraintes) | `no_cookware=['pas_de_four','pas_de_robot']` | `{'cocotte au four', 'four', 'moule a four', 'robot culinaire'}` ✓ |
| AC1 — contrainte inconnue | `no_cookware=['pas_de_micro_ondes']` | `set()` ✓ |
| AC1 — `no_cookware` vide | `no_cookware=[]` | `set()` ✓ |
| AC1 — cuisine inconnue | `forbidden_cookware('nope', ...)` | `set()` (pas d'exception) ✓ |
| AC3/AC5(a) — exclusion `pas_de_four` | `techniques_for(..., no_cookware=['pas_de_four'])` | `['pasta_al_dente','risotto','soffritto','sugo_pomodoro']` — `searing_braising` **exclue**, 4 conservées ✓ |
| AC4/FR7 — info debug | `excluded_techniques(..., ['pas_de_four'])` | `[('searing_braising','four','pas_de_four')]` (technique + ustensile + contrainte) ✓ |
| Contrat B3 préservé | `isinstance(techniques_for(...), list)` + éléments `Technique` | `list[Technique]` inchangé ✓ |
| Règle inter-couches (archi §3.1) | grep `import.*app\.scaling` dans `app/knowledge/` | Aucun import ; unique occurrence = un **commentaire** explicatif (helpers recopiés, pas importés) ✓ |
| Déterminisme info debug | 50 exécutions `excluded_techniques` | 1 seul snapshot distinct (stable) ✓ |

## Conformité à la signature prescrite (archi §4.2)

| Signature prescrite | Implémentation B4 | Verdict |
|---|---|---|
| `forbidden_cookware(cuisine: str, constraints: Constraints) -> set[str]` | signature exacte (`loader.py:311`), retourne un `set[str]` normalisé (minuscule + accents supprimés), union sur plusieurs contraintes, `set()` sur clé/cuisine inconnue ou `no_cookware` vide | ✓ |
| `techniques_for(...) -> list[Technique]` (EXCLUT cookware interdit) | contrat de retour `list[Technique]` **inchangé** (B3 non cassé) ; l'info d'exclusion est exposée séparément par `excluded_techniques` | ✓ |
| `excluded_techniques(...) -> list[Exclusion]` (FR7, ajout B4) | présent ; dataclass `Exclusion{technique_id, forbidden_tool, via_constraint}` `frozen` | ✓ |

`forbidden_cookware` est exporté par `__init__.py` (`__all__`) → API publique stable pour D1 (prompt) et FR7. Conforme au découpage B3/B4 (le helper interne B3 `_forbidden_cookware` est promu : remplacé par `_forbidden_mapping`, source unique de vérité consommée par l'API publique **et** le matching).

## Correction réelle du finding B3 (multi-mots) — point central

Le finding mineur #1 de la revue B3 (asymétrie « chaîne entière interdite » vs « tokens requis » → faux négatif silencieux sur tout ustensile interdit **multi-mots**) était explicitement délégué à B4. **Il est réellement corrigé.**

### Preuve par scénario construit (cuisine fictive en mémoire)

J'ai construit une `Cuisine` fictive dont une technique requiert un ustensile **multi-mots** interdit (`'grand robot culinaire pro'` requis, `pas_de_robot` → `['robot culinaire']`) :

```
forbidden token sequences -> {('robot', 'culinaire'): 'pas_de_robot'}
kept ->  ['saute']        # puree_lisse (requiert 'grand robot culinaire pro') EST exclue ✓
exclusion puree_lisse -> Exclusion(technique_id='puree_lisse',
                                   forbidden_tool='grand robot culinaire pro',
                                   via_constraint='pas_de_robot')
```

Démonstration du bug B3 sur le **même** libellé (asymétrie chaîne entière vs tokens) :

```
{'robot culinaire'} & tokens('grand robot culinaire pro') -> set()
  => ancien B3 : intersection VIDE => puree_lisse N'aurait PAS été exclue (faux négatif)
nouveau B4 (_tool_is_forbidden) -> 'pas_de_robot'   # interdit correctement détecté
```

### Le test de régression est probant (non tautologique)

`test_matching_token_entier_multi_mots_regression_b3` asserte d'abord **explicitement le bug B3** (`{'robot culinaire'} & set(_tokenize(...)) == set()`) puis le comportement corrigé (`_tool_is_forbidden(...) == 'pas_de_robot'`). J'ai rejoué l'ancien algorithme B3 (intersection chaîne-entière/tokens) sur l'entrée du test :

```
ancien B3 matcherait "robot culinaire" dans "grand robot culinaire pro" ? False
  => sous l'ancien matching, l'assertion `== 'pas_de_robot'` ÉCHOUERAIT => test probant
nouveau B4 -> 'pas_de_robot'
```

Le test **échouerait réellement** si l'on remettait l'ancien matching : il n'est pas tautologique.

## Pas de faux positif (sous-chaîne)

Le matching opère par **token entier** (sous-séquence de tokens), pas par sous-chaîne. Contre-exemples testés :

```
'fourchette a fondue'  -> None     # « four » ⊄ « fourchette » (tokens distincts) ✓
'fourneau a bois'      -> None     # « four » ⊄ « fourneau » ✓
'cocotte au four'      -> pas_de_four   # « four » token entier présent ✓
'four'                 -> pas_de_four ✓
'le grand four a pizza' -> pas_de_four  # « four » token entier présent ✓
_is_subsequence(('four',), ['fourchette']) -> False
```

`test_matching_pas_de_faux_positif_sous_chaine` verrouille `fourchette`/`fourneau`/`four`/`cocotte au four` + le comportement de `_is_subsequence`. Aucun faux positif. Même garde anti-faux-positif que l'AC2 de C1 (« ail » ⊄ « vol-au-vent »).

## Sous-séquence contiguë vs sous-ensemble (Edge Case Hunter)

B4 matche par **sous-séquence contiguë** de tokens. J'ai cherché des cas où cela raterait un vrai interdit :

```
needle ('robot','culinaire') :
  'culinaire robot'             -> None   # ordre inversé : raté
  'robot de cuisine culinaire'  -> None   # tokens non contigus : raté
  'robot culinaire kenwood'     -> pas_de_robot   # contigu : matché ✓
```

**Analyse du risque (réel vs théorique).** Les seuls libellés multi-mots interdits dans la donnée réelle sont des **expressions figées** (`moule a four`, `cocotte au four`, `mixeur plongeant`, `robot culinaire`). Aucun `requiredTools` réel ne contiendrait ces composants en ordre inversé ou intercalé (vérifié sur les 5 techniques italiennes : le seul ustensile discriminant pour `pas_de_four` est « **four** », **mono-mot** donc insensible à la contiguïté). Le risque d'un faux **négatif** par non-contiguïté est donc **théorique sur les données actuelles** ; il deviendrait pertinent seulement si une cuisine future déclarait un interdit multi-mots dont les tokens apparaissent disjoints dans un `requiredTools`. La sous-séquence contiguë est par ailleurs le **bon compromis anti-faux-positif** : un sous-ensemble (tokens disjoints) ferait matcher « robot » + « culinaire » présents séparément dans deux contextes différents. Choix défendable et documenté. Voir finding mineur #1 (defer).

## AC5 — Couverture de test

- **AC5(a)** `test_techniques_for_exclut_searing_braising_conserve_les_4` : `searing_braising ∉ ids` **et** égalité exacte du set des 4 conservées. Probant (échoue si l'exclusion casse dans un sens ou l'autre).
- **AC5(b)** `test_contrainte_inconnue_no_op` + `test_forbidden_cookware_contrainte_inconnue_vide` : clé inconnue → `set()` / 5 techniques.
- **AC5(c)** `test_no_cookware_vide_conserve_les_5` + `test_forbidden_cookware_no_cookware_vide`.
- **AC5(d)** `test_b4_determinisme` : 100 itérations sur `forbidden_cookware`/`techniques_for`/`excluded_techniques`.
- `test_forbidden_cookware_union_plusieurs_contraintes`, `test_forbidden_cookware_cuisine_inconnue_vide`, `test_excluded_techniques_expose_la_raison`, `test_excluded_techniques_vide_sans_contrainte` : complètent AC1/AC4.

Couverture honnête et non fragile (ids/cardinalité/sets, pas de wording de valeurs).

## AC4 / FR7 — Information d'exclusion

`excluded_techniques(...) -> list[Exclusion]` expose, pour chaque technique écartée, `technique_id` + `forbidden_tool` (normalisé) + `via_constraint` (clé de contrainte d'origine). Déterministe (ordre de déclaration des techniques). Alimente `DebugInfo.techniques` (archi §9.1) et la barrière LLM (archi §6.1). La **suggestion d'alternative** (« remplacer ») est correctement documentée comme **hors périmètre B4** (différée couche 4 / D1). `_technique_exclusion` traite aussi `forbiddenIf.noCookware` (schema.md §2) s'il apparaît — générique (OA3 / F1), aucune cuisine en dur.

## Non-régression B3

- Les 9 tests B3 passent toujours (compris dans les 22 tests `test_knowledge.py`).
- `techniques_for` conserve son contrat `list[Technique]` (vérifié empiriquement).
- Règle inter-couches : aucun import de `app.scaling` (grep) ; helpers `_strip_accents`/`_normalize`/`_tokenize` recopiés (volontaire, documenté).
- `docs/base-technique/*`, `app/scaling/*`, `sprint-status.yaml` non touchés (périmètre 4 fichiers respecté).

## Findings (par sévérité)

### Bloquants
Aucun.

### Majeurs
Aucun. (Le finding central — correction du faux négatif multi-mots — **est** réellement implémenté et prouvé ; `forbidden_cookware` respecte la signature archi §4.2.)

### Mineurs / observations

1. **[defer] Le matching par sous-séquence *contiguë* peut rater un interdit multi-mots en ordre inversé ou avec tokens intercalés.**
   `('robot','culinaire')` ne matche pas `'culinaire robot'` ni `'robot de cuisine culinaire'`. **Sans impact sur les données actuelles** (le seul ustensile discriminant réel, « four », est mono-mot ; les libellés interdits sont des expressions figées non disloquées dans les `requiredTools`). Le choix contigu est par ailleurs un bon garde anti-faux-positif (vs sous-ensemble disjoint). Risque **théorique**, à surveiller si une cuisine future (F1) déclare des interdits multi-mots disloqués. **Defer.**

2. **[defer — hérité de B3 #2] La clé `no_cookware` n'est pas normalisée avant `mapping.get`.**
   `forbidden_cookware(..., no_cookware=['PAS_DE_FOUR'])` (majuscules) → `set()` (aucune exclusion). B4 ne corrige pas ce point, mais la story le documente explicitement comme hors périmètre : les clés proviennent de l'enum API (`Constraints.no_cookware`, archi §9.1), pas d'une saisie libre, et le finding B3 #2 était `defer` sans exiger de correction en B4 (contrairement au #1, central, qui l'était). Non bloquant. **Defer.**

3. **[defer — hérité de B3 #3] Structures mutables partagées avec le cache `load_cuisines()`.**
   `cookware_constraints` reste un `dict[str, list[str]]` mutable partagé avec le cache `lru_cache`. B4 ne le mute jamais (il lit et normalise dans des structures locales), donc n'aggrave pas le problème, mais ne le corrige pas non plus. Hors périmètre B4. **Defer.**

## Couverture des Acceptance Criteria

- **AC1** (API publique `forbidden_cookware`, set normalisé, union, clé/cuisine inconnue → `∅`) : ✓ signature archi §4.2 exacte, vérifiée empiriquement sur tous les cas.
- **AC2** (matching insensible casse/accents, token entier, gère l'inclusion, sans faux positif de sous-chaîne) : ✓ NFKD + tokenisation, sous-séquence de tokens ; « four » ⊂ « cocotte au four » mais ⊄ « fourchette »/« fourneau ». Réserve mineure : contiguïté (finding #1).
- **AC3** (`techniques_for` exclut les techniques à ustensile interdit ; `pas_de_four` ⇒ `searing_braising` exclue, 4 conservées) : ✓ vérifié + test probant.
- **AC4** (info d'exclusion exposée FR7 ; politique « remplacer/refuser » déléguée) : ✓ `excluded_techniques`/`Exclusion`, `forbiddenIf.noCookware` respecté, suggestion d'alternative documentée hors périmètre.
- **AC5** (tests : exclusion, contrainte inconnue no-op, vide, déterminisme, token entier sans faux positif) : ✓ 13 tests, `pytest tests/test_knowledge.py tests/test_scaling.py` → 60 passed.

DoD (tâches 0–4 cochées, périmètre 4 fichiers `loader.py`/`__init__.py`/`test_knowledge.py`/`B4.md`, aucune touche à `app/scaling/*`, `docs/base-technique/*`, `sprint-status.yaml`) : satisfaite.

## Verdict

**APPROUVÉE — 0 bloquant / 0 majeur / 3 mineurs (defer).**

Le point central de la story — corriger le faux négatif B3 sur les ustensiles interdits **multi-mots** — est **réellement implémenté** (matching par sous-séquence de tokens) et **prouvé empiriquement** : un scénario construit (technique requérant `'grand robot culinaire pro'` sous `pas_de_robot`) est désormais correctement exclu, là où l'ancien algorithme B3 produisait une intersection vide. Le test de régression est probant (échouerait sous l'ancien matching) et non tautologique. `forbidden_cookware` respecte la signature prescrite (archi §4.2), retourne un `set[str]` normalisé avec union et fallback `∅`. Aucun faux positif de sous-chaîne (« four » ⊄ « fourchette »). `techniques_for` conserve son contrat `list[Technique]` (B3 non régressé), l'info debug FR7 est exposée et déterministe, la règle inter-couches est respectée (aucun import `app.scaling`). Suite complète : **68 passed, 0 régression**.

Les 3 findings restants sont mineurs et `defer` : la non-contiguïté est un risque théorique sur les données actuelles, et deux sont hérités de B3 (clé non normalisée, structures mutables du cache) explicitement hors périmètre B4. Aucun ne remet en cause un AC.

**Recommandation : B4 peut passer en `done`.**
