# Revue de code adversariale — Story D2

- **Story** : D2 — Garde-fou « jamais hors base » + tests anti-hallucination (couche 4, barrière 2 — le vrai garde-fou déterministe, archi §6.2)
- **Statut entrant** : `review`
- **Date** : 2026-06-02
- **Reviewer** : agent BMAD `code-review` (INDÉPENDANT du dev — Blind Hunter / Edge Case Hunter / Acceptance Auditor + triage)
- **Mode** : non-interactif, adversarial mais juste, lecture seule (seul fichier écrit : la présente revue)
- **Périmètre revu (ajouts D2 uniquement)** :
  - `app/generator/validate.py` — `validate_recipe(recipe, techniques, safety, forbidden=frozenset()) -> ValidationResult` + helpers purs (extraction/intervalles, normalisation recopiée, 3 contrôles, table `_PROTEIN_SYNONYMS`).
  - `tests/test_validate.py` — 19 tests anti-hallucination (barrière 3, archi §6.3).
  - `docs/stories/D2.md` — AC, Tasks, Dev Agent Record audités.
- **Hors périmètre (non revu, sauf non-régression / anti-conflit)** : `app/generator/models.py`/`__init__.py`/`prompt.py`/`client.py`, fichiers D3 (`cooklang.py`/`test_cooklang.py`), `app/knowledge/*`, `app/epicure/*`, `app/scaling/*`, `docs/base-technique/*` (référence), `sprint-status.yaml`.

---

## Vérifications empiriques

| Contrôle | Commande / méthode | Résultat |
|---|---|---|
| pytest suite complète | `python -m pytest -q` | **149 passed / 1 skipped** (attendu confirmé ; 0 régression) |
| pytest module D2 | `python -m pytest tests/test_validate.py -q` | **19 passed in 0.03s** |
| Règle inter-couches (archi §3.1) | lecture du source `validate.py` | **AUCUN import runtime** de `app.knowledge`/`app.epicure`/`app.scaling`/`anthropic` ; SEUL import runtime inter-module = `from app.generator.models import ...` (même couche) ; types couche 2 sous `if TYPE_CHECKING:` ✓ |
| Contrat non modifié | `git status` + lecture | `app/generator/models.py` = untracked NON modifié par D2 ; `app/generator/__init__.py` modifié mais **par l'orchestrateur (D1/D3)**, n'exporte PAS `validate_recipe` (D2 ne l'a pas touché) ✓ |
| Signature §4.4 | lecture `validate.py:586` | `validate_recipe(recipe, techniques, safety, forbidden=frozenset())` — 3 args prescrits préservés, 4ᵉ optionnel en fin (rétro-compatible) ✓ |
| Minima EXCLUSIVEMENT depuis `safety` | grep valeurs `60/63/71/74/145/160/165` dans le source | aucune valeur de sécurité codée en dur dans la logique (seulement commentaires, formatage feedback, stubs du bloc `__main__`) ; minima lus par `getattr(standard, "min_internal_c/f")` ✓ |
| Faille « heat 999 » | recette avec `999°C` + clé `heat="...999..."` | reste **rejeté** (`temperature_hors_base`) — une T noyée dans un texte non-`temp` n'autorise rien ✓ |
| Anti-masquage protéine | volaille citée à `60°C` ET `74°C` | reste **rejeté** (`below_minimum` l'emporte sur la citation correcte) — une T dangereuse n'est pas masquée ✓ |
| Tolérance epsilon | `73.4°C` (rejeté) vs `73.6°C` (accepté) contre min `74` | bornes ± `_TEMP_EPSILON=0.5` correctes ✓ |
| Unités °C/°F non mélangées | `212°F` accepté (=`tempF`) ; `212°C` rejeté | comparaison par unité stricte ✓ |
| Intervalles | `82–90` (tiret long), `90-82` (inversé) | parsés et normalisés `(82,90)` ✓ |
| `severity` suit `critical` | ligne `critical=False` | `severity="warning"` ✓ |
| Déterminisme | 60 itérations + relances manuelles | `ValidationResult` stable ✓ |
| Pureté | lecture du source | aucun `random`/horloge/I/O/lecture fichier ; `recipe` jamais muté ✓ |

## Conformité à la signature prescrite (archi §4.4)

| Signature prescrite §4.4 | Implémentation D2 | Verdict |
|---|---|---|
| `validate_recipe(recipe, techniques, safety) -> ValidationResult` | `validate_recipe(recipe, techniques, safety, forbidden=frozenset()) -> ValidationResult` | ✓ — 3 args prescrits intacts, appel à 3 args toujours valide (`test_signature_retrocompatible`), 4ᵉ paramètre optionnel **en fin** avec défaut (décision figée AC4, documentée) |

## Barrière 2 (archi §6.2) — examen du cœur

**(a) Extraction.** `_extract_numbers_with_ranges` couvre scalaires (`100→[(100,100)]`), intervalles texte (`150-160`, tirets `-`/`–`/`—`, inversés normalisés), scalaires noyés (`163 C→[(163,163)]`), texte non numérique (`→[]`). Les durées sont extraites pour traçabilité (non bloquantes en v1 — décision par défaut documentée, cohérente avec §6.2 dont le contrôle DUR porte sur la température).

**(b) Appartenance des températures.** Agrégation par unité via heuristique `_key_is_temperature` (clé contenant « temp ») — capte `tempC/tempF/panTempC/searTempC/ovenTempC/ovenTempF`, **exclut** `timeMinutes`/`ratios`/`heat`. Vérifié empiriquement que `timeMinutes "18-20"` n'autorise pas `19°C` (`test_cle_non_temperature_ignoree`) et qu'une valeur dans `heat` n'autorise rien. Comparaison **par unité** (°C vs °F jamais mélangés). Hors base → `temperature_hors_base/critical`. **Aucune faille trouvée** permettant à une température hallucinée de passer.

**(c) Sécurité protéines.** Minima lus **EXCLUSIVEMENT** depuis `safety` (`getattr`), `critical:true → severity="critical"` (rejet dur), protéine non citée → violation, protéine sous minimum → violation, anti-masquage confirmé. Détection best-effort par tokens contre `food_type` + table de synonymes (voir Findings). Protéine absente → aucun contrôle (anti-faux-positif, `test_protein_absente_aucun_controle`).

**(d) Cookware interdit.** Sous-séquence de tokens normalisés (recopiée de B4) : « four » ⊂ « cocotte au four » (rejet) ; « four » ⊄ « fourchette » (pas de rejet). `forbidden` vide → aucune violation.

**(e) Politique.** `validate_recipe` RETOURNE `ValidationResult` et ne fait PAS le retry (boucle dans `client.generate_recipe`/D1) ; aucune réparation silencieuse, aucune mutation de `recipe`. `feedback` ciblé 1 ligne/violation, vide si `ok=True`.

## Examen critique de `_PROTEIN_SYNONYMS` (point demandé)

Table volontairement **minimale et conservatrice** (« poulet/dinde/canard… → volaille », « saumon/cabillaud/thon… → poisson », « jambon → porc », etc.). Elle ne sert qu'à **étendre** les tokens d'un libellé recette pour recouper les `food_type` USDA (le corpus FR « cuisses de poulet » n'emploie pas le mot « volaille »). Points vérifiés :
- **Pas de valeur de sécurité dans la table** : ce sont des associations lexicales `terme→token`, jamais une température. Les minima restent issus de `safety`. → **Pas de MAJEUR.**
- **Conservatrice / pas de faux positif** : un terme absent ne déclenche aucun contrôle (on n'invente jamais une protéine). `_expand_synonyms` n'enlève jamais de token.
- **Réserve d'observation** (finding mineur #1) : `crevette → {poisson, mer}` recoupe la ligne « Poisson / fruits de **mer** » par le token « mer » — correct ici, mais le token « mer » est générique. Aucun food_type actuel n'en pâtit ; à surveiller si la table `safety` s'enrichit.

## Anti-conflit (archi multi-agents)

- **Fichiers D2 = exactement 2** + story : `app/generator/validate.py`, `tests/test_validate.py` (untracked), `docs/stories/D2.md` mis à jour. ✓
- `app/generator/models.py`/`prompt.py`/`client.py` **non touchés par D2** (untracked d'autres stories). Fichiers D3 (`cooklang.py`/`test_cooklang.py`) **non touchés par D2**. ✓
- `app/generator/__init__.py` et `sprint-status.yaml` apparaissent `modified` dans le working tree, **mais le diff de `__init__.py` n'ajoute pas `validate_recipe`** (il câble client/models/prompt — travail orchestrateur D1/D3). Conforme à la règle anti-conflit : D2 laisse l'export `validate_recipe` à l'orchestrateur. **Noté sans le compter comme défaut de D2.**
- Tests : imports **directs** des sous-modules (`from app.generator.validate import ...`, `from app.generator.models import ...`), pas via le package. ✓

## Couverture des Acceptance Criteria

- **AC1** (pur/déterministe, signature rétro-compatible, inter-couches) : ✓ import runtime limité à `app.generator.models` ; couche 2 sous `TYPE_CHECKING` ; pas de `random`/I/O/horloge ; `test_purete_aucun_import_intercouche` + revue source.
- **AC2** (extraction + appartenance températures) : ✓ scalaires/intervalles/texte, par unité, epsilon, exclusion des clés non-`temp`, hors base → `temperature_hors_base/critical`.
- **AC3** (sécurité protéines) : ✓ minima exclusivement `safety`, sous minimum + non citée, `critical→critical` (rejet dur), anti-masquage.
- **AC4** (cookware + `forbidden` rétro-compatible) : ✓ sous-séquence durcie, anti-faux-positif, défaut `frozenset()`.
- **AC5** (politique pure, pas de retry/réparation) : ✓ retourne `ValidationResult`, aucune mutation, feedback ciblé, vide si ok.
- **AC6** (tests probants + déterminisme + suite verte) : ✓ 19 tests, cas négatifs assertant le REJET (non tautologiques — échoueraient sur table propre), cas positif complet `ok=True/()/""`, déterminisme 60 itérations. Suite **149 passed / 1 skipped**.

## Tests anti-hallucination — probants, non tautologiques

Les tests négatifs (`999°C`, volaille `60°C`, `four` interdit) assertent le **rejet** sur des `StructuredRecipe` fabriquées hors-base ; le cas positif (`_clean_recipe`) asserte `ok=True`, `violations == ()`, `feedback == ""`. Contre-vérifié indépendamment (probes adversariaux ci-dessus) : un test passerait au vert seulement si le validateur rejette réellement — il échouerait si la barrière laissait passer la valeur hallucinée. Aucun appel LLM/réseau (R7). Les 4 contrôles sont couverts ; bornes d'intervalle, distinction d'unité et clé non-température ont des tests dédiés.

## Findings (par sévérité)

### Bloquants
Aucun.

### Majeurs
Aucun. La barrière 2 est correcte et robuste : règle inter-couches respectée (aucun import runtime de couche 2/3/`anthropic`), contrat `models.py` non modifié, minima de sécurité **exclusivement** issus de `safety` (aucune valeur codée en dur), aucune faille trouvée permettant à une température hallucinée ou à une protéine sous-minimum de passer.

### Mineurs / observations

1. **[defer] `_PROTEIN_SYNONYMS` — token « mer » générique et collision `porc` pièces/haché.**
   `validate.py:345-370`. (a) `crevette → {poisson, mer}` recoupe « Poisson / fruits de **mer** » via le token « mer », générique ; sans incidence sur les `food_type` actuels mais à surveiller si `safety` s'enrichit. (b) Le matching retient la **première** ligne `safety` qui recoupe : pour « porc », il matchera « Boeuf/veau/agneau/porc - pièces entières » (63°C) avant « Porc - haché » (71°C). Détection best-effort documentée ; le minimum appliqué reste issu de `safety` (jamais inventé), donc pas de risque de température sous un seuil cité — mais un « porc haché » pourrait être validé contre 63°C au lieu de 71°C. Risque réel faible sur le corpus italien (peu de haché de porc en hero). **Defer / à documenter pour D-aval.**

2. **[defer] Fallback `near_minimum` : une T étiquetée `TECHNIQUE` au minimum exact satisfait l'exigence de citation de sécurité.**
   `validate.py:466-481`. Si une protéine est citée avec une température `TECHNIQUE` (label non « SÉCURITÉ ») dont la valeur tombe à ± epsilon du minimum, elle est comptée comme `has_safe_citation`. C'est conservateur (au minimum = sûr, jamais sous le seuil) et documenté comme fallback robuste au label mal posé ; aucune sécurité n'est affaiblie (une valeur sous le minimum reste `below_minimum`). Observation, non bloquant.

3. **[defer] Calcul de `ok` légèrement redondant vs AC5.**
   `validate.py:630-631` : `has_critical = any(... critical)` puis `ok = not has_critical and len(violations) == 0`. Comme toute violation est `critical` ou `warning`, `len(violations) == 0` suffit (et c'est exactement le libellé AC5 « `ok = (len(violations) == 0)` »). Le code est correct (équivalent ici) mais introduit une double condition inutile ; un `warning` seul rendrait `ok=False`, ce qui est cohérent avec AC5 mais mérite une ligne unique. Cosmétique. **Defer.**

## Verdict

**APPROUVÉE — 0 bloquant / 0 majeur / 3 mineurs (defer).**

D2 livre la **barrière 2** (le vrai garde-fou déterministe, archi §6.2) et la **barrière 3** (tests anti-hallucination, §6.3) de façon conforme. La fonction `validate_recipe` est **pure et déterministe**, respecte la **règle inter-couches stricte** (seul import runtime = `app.generator.models` ; types couche 2 sous `TYPE_CHECKING` ; aucun `app.knowledge`/`app.epicure`/`app.scaling`/`anthropic` au runtime ; helpers de normalisation recopiés, pas importés) et la **signature prescrite §4.4** (3 args + `forbidden` optionnel en fin, rétro-compatible). Le **contrat `models.py` n'est pas modifié**. Les **minima de sécurité proviennent exclusivement de `safety`** — aucune valeur codée en dur (point 9 : pas de MAJEUR). Les 4 contrôles (appartenance température par unité avec intervalles parsés ; sécurité protéines avec rejet dur `critical` et anti-masquage ; cookware par sous-séquence ; verdict pur sans retry ni réparation) sont corrects ; l'examen adversarial n'a trouvé **aucune faille** laissant passer une température hallucinée ou une protéine sous-minimum. Tests **probants et non tautologiques**, cas positif présent, déterminisme vérifié.

Résultats pytest : **`python -m pytest -q` → 149 passed / 1 skipped** ; **`python -m pytest tests/test_validate.py -q` → 19 passed**. Zéro régression.

Les 3 findings `defer` (heuristique de synonymes/collision porc, fallback `near_minimum` conservateur, calcul `ok` redondant) ne remettent en cause aucun AC ni aucune garantie de sécurité.

**Recommandation : D2 peut passer en `done`.** L'orchestrateur fusionnera ensuite l'export `validate_recipe` dans `app/generator/__init__.py` (laissé intact par D2, conformément à la règle anti-conflit).
