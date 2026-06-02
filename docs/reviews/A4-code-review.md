# Revue de code adversariale — Story A4

- **Story** : A4 — Traduction FR → clé Epicure (snake_case EN) (couche 1, associations) — **lève RZ3**
- **Statut entrant** : `review`
- **Date** : 2026-06-02
- **Reviewer** : agent BMAD `bmad-code-review` (couches Blind Hunter / Edge Case Hunter / Acceptance Auditor + triage)
- **Mode** : non-interactif, lecture seule (seul fichier écrit : la présente revue)
- **Périmètre revu (uniquement les ajouts A4)** :
  - `app/epicure/translate.py` — `translate(term)->str`, `translate_many(terms)->list[str]`, variante non-levante optionnelle `try_translate(term)->str|None`, helpers `_strip_accents`/`_normalize`/`_normalize_term`, chargement `_load_index` (`lru_cache`).
  - `app/epicure/fr_aliases.json` — table versionnée `{ alias_FR : clé_Epicure }` (66 alias → 39 clés cibles).
  - `tests/test_translate.py` — 9 tests A4.
  - `docs/stories/A4.md` — AC + DoD audités.
- **Hors périmètre (non revu, sauf non-régression)** : code A3 (`filter.py`, `diet_exclusions.json`, `test_filter.py`), `loader.py`, `__init__.py`, `app/knowledge/*`, `app/scaling/*`, `docs/epicure/vocab.csv` (lecture seule), `recipes/`.

---

## Vérifications empiriques

| Contrôle | Commande / méthode | Résultat |
|---|---|---|
| pytest suite complète | `python -m pytest -q` | **93 passed / 0 skipped** (0 régression ; baseline 68 + A3 + 9 A4) |
| pytest module A4 | `python -m pytest tests/test_translate.py -q` | **9 passed** |
| AC1 — chargement unique (`lru_cache`) | `_load_index() is _load_index()` | `True` — table chargée une seule fois ✓ |
| AC1 — `translate_many` ordonné | `translate_many(['ail','basilic','poivre noir'])` | `['garlic','basil','black_pepper']` ✓ |
| AC2 — assertions chiffrées noyau | appels réels | `huile d'olive→olive_oil`, `ail→garlic`, `basilic→basil`, `poivre noir→black_pepper`, `parmesan râpé→parmesan_cheese`, `guanciale→pancetta` ✓ |
| AC2 — échantillon large | `[translate(t) ...]` | `tonnarelli→pasta`, `riz carnaroli→rice`, `cèpes séchés→porcini_mushroom`, `haricots blancs cuits→cannellini_bean`, `zeste de citron→lemon`, `vin blanc sec→white_wine`, `tomates san marzano→tomato` ✓ |
| AC3 — casse + apostrophe droite | `translate("Huile d'Olive")` == `translate("huile d'olive")` | `olive_oil` == `olive_oil` ✓ |
| AC3 — apostrophe typographique U+2019 | `translate("Huile d’Olive")` | `olive_oil` (converge vers U+0027) ✓ |
| AC3 — casse pure | `translate("BASILIC")` | `basil` ✓ |
| AC3 — espaces + accents | `translate("  câpres  ")` | `caper` ✓ |
| AC4 — fallback terme inconnu | `translate("ingrédient_bidon")` | `KeyError: "Ingrédient inconnu du vocabulaire FR→Epicure : 'ingrédient_bidon' (à ajouter dans fr_aliases.json)"` ✓ |
| AC5(a) — déterminisme | 50 exécutions (5 termes/itération) | **1 seul snapshot distinct** (stable) ✓ |
| AC5(b) — intégrité table↔vocab (contrôle INDÉPENDANT) | lecture directe `fr_aliases.json` + `vocab.csv` | **39 clés cibles, 0 manquante** dans la colonne `name` (1790 entrées) ✓ |
| AC5(b) — `guanciale` absent du vocab | `'guanciale' in names` / `'pancetta' in names` | `False` / `True` — justifie `guanciale→pancetta` ✓ |
| Règle inter-couches (archi §3.1) | grep `import.*app\.(knowledge|scaling)` dans `translate.py` | **Aucun import** (helpers recopiés, documenté) ✓ |
| `__init__.py` / `loader.py` non modifiés par A4 | `git log` / working tree | non touchés (untracked uniquement : `translate.py`, `fr_aliases.json`, `test_translate.py`) ✓ |

## Conformité à la signature prescrite (archi §4.1, §9.1 / R4)

| Signature prescrite | Implémentation A4 | Verdict |
|---|---|---|
| `translate(term: str) -> str` (FR → clé Epicure snake_case EN) | signature exacte (`translate.py:84`), lookup sur forme normalisée, retourne la clé EN | ✓ |
| `translate_many(terms: Iterable[str]) -> list[str]` (mapping ordonné, même politique d'erreur) | présent (`translate.py:103`), liste ordonnée, propage `KeyError` (pas de traduction partielle silencieuse) | ✓ |
| Fallback = `KeyError` clair, cohérent avec `EpicureIndex.neighbors` | `loader.py:39` lève `KeyError(f"Ingredient absent du vocabulaire Epicure : {name!r}")` ; A4 lève `KeyError(...{terme}... fr_aliases.json)`. Même contrat → remontée homogène vers le 422 (archi §9.1) | ✓ |
| Variante non-levante optionnelle | `try_translate(term) -> str | None` livrée et documentée comme optionnelle ; contrat principal reste `KeyError` | ✓ |

Le module est **pur/déterministe** : `json`, `unicodedata`, `pathlib`, `functools`, `typing` seulement (aucune nouvelle dépendance, `requirements.txt` figé). Le JSON est chargé une seule fois via `@lru_cache(maxsize=1)` sur `_load_index()` et n'est jamais muté (l'index normalisé est construit à la volée à partir de `raw`).

## A4 lève bien RZ3 (point central)

RZ3 = « Story manquante : traduction FR → clé Epicure (snake_case EN) ». A4 **est** cette story. Vérifié empiriquement que les deux conditions de levée sont réelles :

1. **Le noyau du corpus est couvert.** Les 13 recettes `recipes/*.cook` (corpus S0.6) sont adossées à 39 clés cibles, **toutes présentes dans `vocab.csv`** (contrôle indépendant ci-dessus). Les 6 assertions chiffrées de l'AC2 passent. `neighbors(hero, k)` recevra donc une clé valide pour le noyau italien.
2. **Le fallback est honnête.** Terme hors table → `KeyError` clair FR, **même contrat** que `EpicureIndex.neighbors`, qui alimente le 422 explicite (archi §9.1 / R4). La couche aval (E1) convertira ce `KeyError` en 422 sans traitement spécial.

La table reste « À COMPLÉTER » (extensibilité OA3/F1), mais le noyau + le fallback honnête suffisent à lever RZ3 pour la v1, conformément à l'AC2. **A4 ne modifie pas `sprint-status.yaml`** (l'orchestrateur passera RZ3 `open → resolved` après revue) — conforme à la consigne de la story.

## Le test de fallback est probant (non tautologique)

`test_fallback_keyword_inconnu_keyerror` asserte `pytest.raises(KeyError)` sur « licorne » **et** vérifie que le message contient le terme `"licorne"` ET la chaîne `"fr_aliases.json"`. J'ai confirmé indépendamment que « licorne » est réellement absent de la table : si la table le contenait, `translate` retournerait une clé sans lever → `pytest.raises` échouerait. Le test **échouerait réellement** sous une table polluée : il est probant. Le double contrôle du message (terme + nom de fichier) verrouille aussi la clarté du message (AC4) et évite un test qui passerait sur un `KeyError` accidentel à mauvais message.

## Normalisation (Edge Case Hunter)

Le `_normalize_term` applique, dans l'ordre : apostrophe typographique U+2019 → droite U+0027 ; réduction des espaces multiples + `strip()` ; puis `_strip_accents` (NFKD + suppression des combinantes) + `lower()`. La normalisation est appliquée **des deux côtés** (alias à la construction de l'index, terme saisi au lookup), donc le JSON garde des alias lisibles sans mutation. Cas vérifiés empiriquement :

```
"Huile d'Olive"   -> olive_oil      # casse
"Huile d’Olive"   -> olive_oil      # apostrophe typographique U+2019 -> U+0027
"BASILIC"         -> basil          # casse pure
"  câpres  "      -> caper          # espaces de bord + accents
"  ail   "        -> garlic         # espaces multiples internes réduits
""                -> KeyError       # terme vide : pas de crash, fallback propre
```

### Point d'attention — ligature « œ » non décomposée par NFKD (couvert par double-entrée JSON, voir finding mineur #1)

Contrôle adversarial du Edge Case Hunter : **`unicodedata.normalize("NFKD", "œ")` ne décompose PAS la ligature** (reste `"œ"`, longueur 1 ; idem « æ »). Donc `_normalize_term("œufs")` == `"œufs"` ≠ `_normalize_term("oeufs")` == `"oeufs"` : la normalisation **ne fait pas converger** « œufs » et « oeufs ». Le module fonctionne uniquement parce que le dev a **explicitement stocké les deux variantes** dans le JSON (`"œufs"`/`"oeufs"`, `"bœuf"`/`"boeuf"`). Vérifié :

```
translate("œufs")            -> egg
translate("bouillon de bœuf") -> meat_stock
```

C'est correct sur les données actuelles, mais la robustesse face à la ligature **repose sur la donnée, pas sur le code** (contrairement aux accents et à l'apostrophe, gérés par le code). Tout futur alias contenant « œ »/« æ » devra penser à la double-entrée. Le dev le documente honnêtement dans les Completion Notes. Risque réel **faible** (seuls « œufs » et « bœuf » concernés, tous deux dédoublés et testés indirectement). **Finding mineur #1 (defer).**

### Doublons d'alias / collisions de clé normalisée

Contrôle indépendant : aucune clé normalisée ne pointe vers **deux** clés Epicure différentes (0 collision). Les « doublons » du JSON (`"capres"`/`"câpres"`, `"echalote"`/`"échalote"`, etc.) se normalisent vers la même entrée d'index et mappent la **même** clé cible : la déduplication par `dict` est inoffensive (idempotente). Aucun risque de mapping ambigu silencieux.

### JSON mal formé / fichier absent

`_load_index` ne capture pas `JSONDecodeError`/`FileNotFoundError` : un JSON corrompu ferait remonter l'exception au premier appel. C'est un comportement acceptable (fail-fast) pour une table versionnée commitée et couverte par CI ; non exigé par les AC. Aucune action.

## Pas de faux positif (lookup exact, pas de sous-chaîne)

A4 fait un **lookup exact** sur la forme normalisée complète du terme (l'alias entier est la clé), conformément à la note de la story : pas de tokenisation, pas de matching de sous-chaîne. Il n'y a donc structurellement **aucun risque de faux positif** type « ail » ⊂ « vol-au-vent » (qui concernait C1/B4, matching multi-mots). Un terme non listé tombe dans le fallback `KeyError`. C'est le bon contrat pour une traduction FR→clé.

## AC5 — Couverture de test

- **AC5(a) déterminisme** : `test_determinisme` (100 exécutions de `translate("huile d'olive")` → set `{"olive_oil"}`). J'ai complété avec 50 exécutions sur 5 termes : 1 snapshot distinct. Probant.
- **AC5(b) intégrité table↔vocab** : `test_toutes_les_valeurs_dans_vocab` — gardé par `VOCAB_CSV.exists()` → `pytest.skip("docs/epicure/vocab.csv absent")` propre si absent ; sinon vérifie `{v for v in raw.values() if v not in noms}` vide. **J'ai refait le contrôle indépendamment** (sans le test du dev) : 0 valeur manquante sur 39. Honnête.
- **AC2 couverture noyau** : `test_corpus_italien_noyau` asserte les 6 valeurs chiffrées + `NOYAU_CLES <= set(raw.values())` + `len(NOYAU_CLES) >= 38` (NOYAU compte 39 éléments). Non tautologique (échoue si un alias du noyau disparaît).
- **AC3** : `test_normalisation_casse_accents_apostrophe` (casse, apostrophe droite ET typographique U+2019, accents, espaces de bord).
- **AC1/AC2 alias multiples** : `test_alias_multiples_meme_cle` (spaghetti/penne/tonnarelli/trofie/pâtes courtes → `pasta` ; riz arborio/carnaroli → `rice`).
- **AC4** : `test_fallback_keyword_inconnu_keyerror` (probant, cf. ci-dessus) + `test_translate_many_terme_inconnu_keyerror` (propagation `KeyError`, pas de traduction partielle) + `test_try_translate_variante_non_levante` (clé / `None`).
- **AC1** : `test_translate_many_ordre` (ordre préservé).

Couverture honnête et non fragile (clés/sets/`KeyError`, pas de wording instable). Réserve d'observation : aucun test ne verrouille la non-régression de la **ligature œ** (cf. finding #1) ni un terme à espaces internes multiples ; couverts empiriquement par la revue, à défaut d'un test dédié.

## Non-régression (hors périmètre, vérifiée)

- Suite complète : **93 passed, 0 régression** (baseline 68 → 68 + A3 + 9 A4). Le module A4 n'impacte aucun autre test.
- Règle inter-couches : aucun import `app.knowledge`/`app.scaling` dans `translate.py` (grep). Helpers `_strip_accents`/`_normalize` recopiés du patron `app/scaling/table.py:52-60` — duplication volontaire et documentée (même choix qu'en B3/B4).
- `app/epicure/__init__.py` et `app/epicure/loader.py` **non modifiés** par A4 (fusion des exports = travail orchestrateur, hors périmètre dev). Conforme à la règle anti-conflit ; **noté sans le compter comme défaut**. Les tests importent `app.epicure.translate` **directement**, pas via le package — cohérent.
- Exactement trois fichiers de code créés (`translate.py`, `fr_aliases.json`, `test_translate.py`) + mise à jour de `docs/stories/A4.md`. Aucun autre fichier touché.

## Couverture des Acceptance Criteria

- **AC1** (module `translate` + `translate_many`, table `fr_aliases.json`, chargement unique `lru_cache`, alias multiples → même clé) : ✓ signatures exactes, `_load_index()` mis en cache (identité vérifiée), `pasta`/`rice` multi-alias.
- **AC2** (corpus italien couvert, assertions chiffrées, ≥ 38 clés cibles) : ✓ 6 assertions chiffrées + 39 clés cibles toutes produites et toutes présentes au vocab.
- **AC3** (normalisation casse/accents/apostrophe droite+typographique/espaces) : ✓ vérifié empiriquement sur tous les cas de l'AC. Réserve : ligature œ gérée par donnée, pas par code (finding #1).
- **AC4** (fallback `KeyError` clair FR, cohérent `neighbors` → 422 ; variante non-levante optionnelle) : ✓ message clair vérifié, `try_translate` livré et documenté.
- **AC5** (déterminisme + intégrité table↔vocab gardée + suite verte) : ✓ déterminisme confirmé, intégrité revérifiée indépendamment (0 manquante), 93 passed 0 régression, test d'intégrité `skip` propre si `vocab.csv` absent.

DoD (tâches 0–3 cochées, périmètre 3 fichiers de code + story, `__init__.py`/`loader.py`/`vocab.csv`/`sprint-status.yaml`/`requirements.txt` non touchés, aucune nouvelle dépendance) : satisfaite.

## Findings (par sévérité)

### Bloquants
Aucun.

### Majeurs
Aucun. (A4 lève réellement RZ3 : noyau corpus couvert + fallback `KeyError` honnête et probant ; `translate`/`translate_many` respectent le contrat archi §4.1/§9.1/R4 ; intégrité table↔vocab revérifiée indépendamment, 0 manquante.)

### Mineurs / observations

1. **[defer] Robustesse à la ligature « œ »/« æ » assurée par la donnée, pas par le code.**
   `unicodedata.normalize("NFKD", "œ")` ne décompose pas la ligature, donc `_normalize_term("œufs") != _normalize_term("oeufs")`. Le bon fonctionnement repose sur la présence des **deux** variantes dans `fr_aliases.json` (`"œufs"`/`"oeufs"`, `"bœuf"`/`"boeuf"`), pratique actuellement complète et testée indirectement. Risque réel **faible** (2 alias concernés). À surveiller : tout futur alias avec « œ »/« æ » devra penser à la double-entrée — ou ajouter un remplacement explicite `œ→oe`/`æ→ae` dans `_normalize_term` (≈ 1 ligne). Documenté par le dev. **Defer.**

2. **[defer] Aucun test ne verrouille la non-régression de la ligature ni les espaces internes multiples.**
   `translate("œufs")` et `translate("  ail   ")` (espaces internes réduits) sont corrects mais non couverts par un test dédié (vérifiés en revue). Un test d'ancrage éviterait une régression silencieuse si un futur refactor du JSON ou de `_normalize_term` cassait l'un des deux. Couverture par ailleurs honnête et probante. **Defer.**

## Verdict

**APPROUVÉE — 0 bloquant / 0 majeur / 2 mineurs (defer).**

A4 réalise le mapping FR → clé Epicure snake_case EN attendu : `translate`/`translate_many` respectent la signature et le contrat d'erreur prescrits (archi §4.1, §9.1, R4), avec un fallback `KeyError` clair en français cohérent avec `EpicureIndex.neighbors` (remontée homogène vers le 422). La normalisation (casse, accents NFKD, apostrophe droite ET typographique U+2019, espaces) est vérifiée empiriquement sur tous les cas des AC. **L'intégrité table↔vocab a été recontrôlée indépendamment du test du dev** : les 39 clés cibles existent toutes dans `vocab.csv` (0 manquante), et `guanciale` est bien absent du vocab — justifiant le mapping documenté `guanciale → pancetta` (substitut présent). Le test de fallback est probant (échouerait sur table polluée). La règle inter-couches est respectée (aucun import `app.knowledge`/`app.scaling` ; helpers recopiés). Module pur/déterministe, chargement unique `lru_cache`, aucune nouvelle dépendance. Suite complète : **93 passed, 0 régression**.

Les 2 findings mineurs `defer` concernent la ligature « œ » (gérée par double-entrée JSON plutôt que par le code, risque réel faible) et l'absence d'un test d'ancrage pour ce cas et les espaces internes ; aucun ne remet en cause un AC.

**RZ3 est levée** (noyau corpus couvert + fallback honnête). **Recommandation : A4 peut passer en `done`** ; l'orchestrateur fusionne ensuite les exports dans `app/epicure/__init__.py` et passe RZ3 `open → resolved`.
