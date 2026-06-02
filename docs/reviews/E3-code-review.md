# Revue de code adversariale — Story E3

- **Story** : E3 — Jeu de validation scaling (corpus) — couche 3 (R&D / calibration), sprint 5
- **Statut entrant** : `review`
- **Date** : 2026-06-02
- **Reviewer** : agent BMAD `bmad-code-review` (rôle « code-review », INDÉPENDANT du dev — couches Blind Hunter / Edge Case Hunter / Acceptance Auditor + triage)
- **Mode** : non-interactif, lecture seule (seul fichier écrit : la présente revue ; le code N'EST PAS corrigé)
- **Périmètre revu (ajouts E3 uniquement)** :
  - `tests/test_scaling_validation.py` — NOUVEAU, 23 tests comparant le moteur déterministe au ×N naïf sur le corpus S0.6.
  - `notebooks/calibration_scaling.ipynb` — COMPLÉTÉ (+7 cellules après l'amorce C5 : 1 markdown intro, 5 code, 1 markdown conclusion).
  - `docs/stories/E3.md` — AC + Tasks + Dev Agent Record audités.
- **Hors périmètre (non revu, sauf non-régression)** : `app/scaling/engine.py`/`table.py` (moteur figé C1-C5, IMPORTÉ jamais modifié), `docs/scaling/table-scaling-sale.json` (table figée), `tests/test_scaling.py` (C1-C5), `recipes/*.cook` (corpus S0.6), `app/main.py`, `app/epicure/*`, `app/generator/*`, `app/knowledge/*`.

---

## Verdict

**APPROUVÉE — 0 bloquant / 0 majeur / 2 mineurs (defer).**

`tests/test_scaling_validation.py` est un jeu de validation DÉTERMINISTE et OFFLINE qui lit RÉELLEMENT le corpus `recipes/*.cook` (13 recettes, 148 ingrédients extraits) et compare le moteur (`scale`/`scale_eggs`/`scale_time`) au ×N naïf aux facteurs ×2 / ÷2 / ×4, en asserts CHIFFRÉS et déterministes (`pytest.approx` à tolérances explicites documentées). Le SENS de la divergence est correctement asserté par type (linéaire == naïf ; sous-linéaire < naïf pour k>1 et > naïf pour k<1 ; temps géométrique < naïf×temps ; œufs RZ1 `scale_eggs(3,2.0)==5` ; fixed inchangé). Le garde-fou anti-import (AST) interdit `anthropic`/`app.epicure`/`app.generator`/`app.knowledge`/`app.main` et n'autorise que `app.scaling`. Le notebook complété est JSON valide, UTF-8 sans BOM, et s'exécute de bout en bout offline (10/10 cellules code, asserts inclus). E3 ALIMENTE la calibration F2/RZ2 sans la résoudre : ni le moteur (`engine.py`/`table.py`) ni la table JSON ne sont touchés. Suite complète : **191 passed / 3 skipped, 0 régression**.

---

## Vérifications empiriques

| Contrôle | Commande / méthode | Résultat |
|---|---|---|
| pytest module E3 (ciblé) | `python -m pytest tests/test_scaling_validation.py -q` | **23 passed** (1.09 s) ✓ |
| pytest suite complète | `python -m pytest -q` | **191 passed / 3 skipped** (1.43 s) — 0 régression ✓ |
| Imports réels (AST, contrôle INDÉPENDANT) | `ast.walk` sur le source du fichier de test | `['__future__', 'app.scaling', 'ast', 'math', 'pathlib', 'pytest', 're']` — **aucun** import interdit, seul `app.scaling` en `app.*` ✓ |
| Garde-fous offline | recherche d'`anthropic`/`requests`/`socket`/`urllib`/`httpx`/`app.epicure`/`app.generator`/`app.knowledge`/`app.main` dans les imports AST | **aucun** ✓ |
| Corpus réellement lu | exécution de `_load_corpus()` sur `recipes/*.cook` | **13 recettes / 148 ingrédients** extraits ✓ |
| Répartition par type | `Counter(classify(...).type)` sur le corpus | `{linear: 87, sublinear: 53, geometric: 6, discrete: 1, fixed: 1}` ✓ |
| Notebook JSON valide + cellules | `json.load` + parcours | nbformat 4, **14 cellules** (10 code / 4 md), 7 amorce C5 + 7 ajoutées E3 ✓ |
| Notebook BOM / UTF-8 | lecture binaire | UTF-8 **sans BOM** ✓ |
| Notebook exécutable offline | `exec` séquentiel best-effort des 10 cellules code | **10/10 OK**, tous les asserts passent (corpus 13/148) ✓ |
| Moteur/table NON modifiés | `git diff --stat engine.py table.py table-scaling-sale.json test_scaling.py` | vide (untouched) ✓ |
| Table = « à calibrer » | `meta.disclaimer` de la table JSON | « Coefficients de DEPART… A CALIBRER » — inchangé ✓ |

---

## 1. Comparaison moteur vs ×N naïf sur le CORPUS (point de vigilance #1)

Le jeu lit **réellement** le corpus : `_load_corpus()` fait `sorted(RECIPES_DIR.glob("*.cook"))` puis `path.read_text(encoding="utf-8")` et parse chaque marqueur `@nom{[=]qty%unité}` via `RE_INGREDIENT_PARTS` (regex RECOPIÉE de `recipes/_check_cook.py` / `app/generator/cooklang.py`, conformément à AC1 — `recipes/` n'étant pas un package importable). Vérifié indépendamment : **13 recettes parsées, 148 ingrédients numériques** extraits, ce qui correspond exactement aux Dev Notes.

Les asserts portent bien sur des ingrédients TIRÉS du corpus, pas sur des constantes en dur :
- `test_lineaire_egale_x_n_naif_sur_le_corpus[k]` itère `ALL_INGREDIENTS` et asserte `q.value == pytest.approx(ing["qty"]*k, rel=1e-9)` sur **chaque** linéaire (87 occurrences), avec garde `linear_seen > 0`.
- `test_sous_lineaire_diverge_dans_le_bon_sens[k]` itère le corpus et asserte sur **chaque** sous-linéaire (53 occurrences), avec garde `sublinear_seen > 0`.
- `test_oeufs_du_corpus_ne_depassent_pas_le_x_n_naif[k]` itère les œufs du corpus (`discrete`), garde `eggs_seen > 0`.
- `test_couverture_corpus` verrouille la couverture : `len(CORPUS) >= 10`, présence de `linear` ET `sublinear`, `len(ALL_INGREDIENTS) > 40`.

**Couverture corpus réelle** : 13 recettes, 148 ingrédients, types `{linear:87, sublinear:53, geometric:6, discrete:1, fixed:1}`. Le jeu porte bien « sur le corpus ». ✓

## 2. Facteurs ×2 / ÷2 / ×4 — asserts chiffrés et SENS de la divergence (point #2)

`FACTEURS = (2.0, 0.5, 4.0)` est appliqué via `@pytest.mark.parametrize` aux tests linéaire / sous-linéaire / œufs / fixed. Le SENS est correctement asserté, chiffré :

- **Sous-linéaire** : `k>1 → q.value < naif` STRICT (le naïf sur-sale) ET borne `q.value >= qty - 1e-9` ; `k<1 → q.value > naif` STRICT (le naïf sous-sale) ET borne `q.value <= qty + 1e-9`. Le moteur reste donc **entre la base et le ×N naïf** — exactement l'exigence AC2. ✓
- **Linéaire** : `value ≈ qty*k` (rel `1e-9`). ✓
- **Temps géométrique** : `scale_time(20,2.0).minutes ≈ 20*2**(2/3) (~31.75) < 40` ; ÷2 `~12.6 > 10` ; ×4 `~50.4 < 80` ; `nonlinear is True`. Vérifié empiriquement par le notebook : `{0.5: 12.60>10, 2.0: 31.75<40, 4.0: 50.40<80}`. ✓
- **Fixed / température** : `scale("four",180,"°C",k).value == 180` et `scale("temperature",100,"°C",k).value == 100` pour tout k, `type == "fixed"`. ✓
- **Œufs RZ1** : `scale_eggs(3, 2.0).whole_eggs == 5` (PAS 6) + reste `grams ≈ 50.0`, `tbsp ≈ 3.0` ; cas fractionnaire `scale_eggs(2, 1.5).whole_eggs == 3` (plancher, pas de borne RZ1). ✓

**Edge Case Hunter — œufs du corpus** : `discrete` ne compte qu'**1 occurrence** (`oeufs`, 3.0, dans la carbonara). Le test `test_oeufs_du_corpus_ne_depassent_pas_le_x_n_naif[k]` est donc paramétré sur un seul ingrédient. Pour k=2 → 5≤6 et branche stricte `round(6)-1=5` ✓ ; k=4 → 11≤12 et `12-1=11` ✓ ; k=0.5 → `scale_eggs(3,0.5)` → `whole_eggs=1 ≤ ceil(1.5)=2` ✓ (la branche stricte RZ1 ne se déclenche pas, k<2). La couverture « œufs corpus » est donc **mince (1 ingrédient)** mais l'assert tient à tous les facteurs ; le cas franc RZ1 est par ailleurs verrouillé hors corpus par `test_oeufs_regle_rz1_chiffree`. Voir finding mineur #1.

## 3. Déterminisme (point #3)

`test_determinisme_sur_le_corpus` construit une `signature()` = liste de toutes les `value` (et `whole_eggs` pour les discrete, `minutes` pour un temps) sur tout le corpus × les 3 facteurs, puis vérifie `signature() == reference` sur **N=25** ré-exécutions. Ce n'est PAS un simple « ne plante pas » : c'est une égalité stricte de la signature complète. Probant. ✓

## 4. Aucun LLM / réseau / Epicure — garde-fou AST (point #4)

`test_aucun_import_intercouche` parse l'AST réel du fichier et asserte l'absence d'`anthropic`/`app.epicure`/`app.generator`/`app.knowledge`/`app.main`, et que `app_modules <= {"app", "app.scaling"}`. Contrôle adversarial INDÉPENDANT (mon propre `ast.walk`) : les imports réels sont `{__future__, app.scaling, ast, math, pathlib, pytest, re}` — **aucun** module interdit, aucun socket/requests/urllib/httpx. Le seul import métier est `app.scaling`. La seule I/O est la **lecture** locale de `recipes/*.cook`. ✓

Note Blind Hunter (non bloquant) : le garde-fou ne liste pas explicitement `requests`/`socket`/`urllib`/`httpx` dans `interdits`. Comme le module n'importe QUE de la stdlib pure + `app.scaling` (vérifié AST), il n'y a aucune fuite réseau possible ; l'extension de la liste noire serait un durcissement cosmétique. Voir finding mineur #2.

## 5. Notebook complété, exécutable offline (point #5)

- **Reprend bien APRÈS l'amorce C5** : l'amorce s'achève sur la cellule markdown « ## Suite : version complète après S0.6 » (cellule 6) ; E3 ajoute les cellules 7-13 sous le titre « ## Version complète (E3) — sur le corpus réel S0.6 ». L'amorce (cellules 0-6) est intacte. ✓
- **JSON valide** : `json.load` OK, nbformat 4, 14 cellules (7 amorce + 7 E3). ✓
- **UTF-8 sans BOM** ; accents corrects dans les cellules AJOUTÉES (intro, helpers, conclusion, tableau de synthèse markdown) — vérifié sur le source du fichier (les `�` observés en console proviennent du codepage Windows du terminal, PAS du fichier, dont la lecture binaire confirme UTF-8 sans BOM). ✓
- **Exécutable offline de bout en bout** : `exec` séquentiel best-effort des **10 cellules code → 10/10 OK**, tous les asserts inclus passent (×2 sous-linéaires écart < 0 ; linéaire écart nul ; ÷2 écart > 0 ; ×4 écart < 0 ; tableau temps cohérent). Corpus chargé : 13 recettes / 148 ingrédients. Réutilise `_here` de l'amorce et les fonctions déjà importées en cellule 1 (pas de réimport d'`app.scaling` métier inattendu). Tableau lisible (texte aligné, sans pandas) + conclusion markdown avec tableau de synthèse par type. ✓

## 6. RZ2 alimentée mais NON résolue (point #6)

- `git diff --stat` sur `app/scaling/engine.py`, `app/scaling/table.py`, `docs/scaling/table-scaling-sale.json`, `tests/test_scaling.py` → **vide** : aucun de ces fichiers n'est modifié. ✓
- `meta.disclaimer` de la table reste « Coefficients de DEPART… A CALIBRER » : aucun coefficient figé. ✓
- La story (Dev Notes + Change Log) et la conclusion du notebook affirment explicitement « RZ2 reste `open` (post-v1) », « alimente F2/RZ2 sans la résoudre ». Cohérent avec le code livré. ✓
- **Observation (hors périmètre E3, non comptée)** : `app/scaling/__init__.py` apparaît modifié (` M`). Le diff montre l'**assemblage de l'API publique** par l'orchestrateur (ré-export de `scale`/`scale_eggs`/`scale_time`/`classify`/dataclasses depuis `engine.py`/`table.py`, ajout d'`__all__`) — c'est le contrat qu'E3 IMPORTE (`from app.scaling import …`). Aucune logique métier modifiée ; même schéma de fusion par l'orchestrateur qu'en D4. Non imputable à E3 (qui ne touche que tests/ + notebooks/), non compté comme défaut.

## 7. Tolérances justifiées (point #7)

- `REL_LINEAR = 1e-9` documenté (« égalité stricte cross-plateforme ») — non masquant : sur le linéaire `value = qty*k` exactement, l'écart est de l'ordre de l'epsilon flottant. ✓
- `ABS_TIME = 0.1` documenté : le moteur applique l'exposant `0.6667` LU dans la table, qui diffère de `2/3 = 0.6666…` ; l'écart `scale_time(20,2.0)=31.7488` vs `20*2**(2/3)=31.7480` est ~0.0008 min, **largement sous 0.1**, donc la tolérance n'est pas masquante (elle ne « rattrape » pas une erreur de loi, juste l'écart d'exposant documenté). Légitime et chiffrée. ✓

## Conformité aux Acceptance Criteria (Acceptance Auditor)

| AC | Exigence | Verdict |
|---|---|---|
| AC1 | Parsing corpus regex recopiées + `_to_float` robuste (virgule FR, fraction, ignore q.s.) | ✓ — 13/148 extraits, regex recopiées, conversion robuste vérifiée |
| AC2 | Moteur vs ×N naïf par type aux ×2/÷2/×4, asserts chiffrés (linéaire ==, sous-linéaire sens strict + borne, œufs RZ1, temps k^2/3, fixed inchangé) | ✓ |
| AC3 | Déterminisme N≥20 (N=25), signature identique | ✓ |
| AC4 | Couverture ≥10 recettes, `linear`+`sublinear`, >40 ingrédients, assaisonnement nommé | ✓ |
| AC5 | Offline strict : seul `app.scaling`+stdlib, garde-fou AST, tolérances documentées, pas de random/horloge | ✓ |
| AC6 | Notebook complété après C5 + suite verte 0 régression | ✓ — notebook 10/10 cellules offline ; suite 191 passed / 3 skipped |

Note AC6 : la story cite une baseline « 160 passed / 1 skipped » dans son texte (héritée du moment de rédaction). À l'instant de la revue, la baseline réelle de l'environnement est **191 passed / 3 skipped** (les 3 skipped = 1 Claude + 2 TestClient E1, fastapi non installé). E3 n'AJOUTE que des tests et n'introduit **aucune** régression ; l'écart de chiffres reflète l'avancement parallèle du sprint, pas un défaut E3.

## Findings (par sévérité)

### Bloquants
Aucun.

### Majeurs
Aucun. (Corpus réellement lu ; asserts chiffrés et déterministes au bon SENS par type ; garde-fou AST offline solide vérifié indépendamment ; moteur/table NON modifiés — RZ2 alimentée sans être résolue ; notebook offline exécutable ; 0 régression.)

### Mineurs / observations

1. **[defer] Couverture « œufs du corpus » mince (1 seul ingrédient `discrete`).**
   Le corpus ne contient qu'**une** occurrence d'œufs (carbonara, 3.0). `test_oeufs_du_corpus_ne_depassent_pas_le_x_n_naif[k]` est donc, de fait, paramétré sur ce cas unique. L'assert tient aux trois facteurs et la branche RZ1 franche est par ailleurs verrouillée hors corpus (`test_oeufs_regle_rz1_chiffree`). Couverture corpus pour ce type intrinsèquement limitée par S0.6, pas par E3. **Defer** (rien à corriger côté E3 ; la couverture s'enrichira si le corpus gagne des recettes à œufs).

2. **[defer] La liste noire d'imports n'énumère pas explicitement `requests`/`socket`/`urllib`/`httpx`.**
   `test_aucun_import_intercouche` interdit `anthropic` + les couches métier et restreint `app.*` à `{app, app.scaling}`, mais ne nomme pas les modules réseau stdlib/tiers. Comme le module n'importe AUCun module hors `{stdlib pure, app.scaling}` (vérifié AST indépendamment), il n'existe aucune voie d'I/O réseau ; ajouter ces noms ne ferait que durcir un garde-fou déjà suffisant. **Defer.**

## Résultat pytest (réel)

- `python -m pytest tests/test_scaling_validation.py -q` → **23 passed** (1.09 s).
- `python -m pytest -q` → **191 passed, 3 skipped** (1.43 s) — 0 régression. Les 3 skipped = 1 test Claude (clé/API absente) + 2 TestClient E1 (fastapi non installé), conformes à l'attendu. E3 ne touche pas `tests/test_scaling.py`.

## Recommandation

**E3 peut passer en `done`.** Le jeu de validation lit réellement le corpus S0.6 (13 recettes / 148 ingrédients), compare le moteur au ×N naïf aux ×2/÷2/×4 en asserts chiffrés et déterministes au bon sens par type, est strictement offline (garde-fou AST revérifié indépendamment), et le notebook complété s'exécute de bout en bout sans réseau ni LLM. E3 ALIMENTE la calibration F2/RZ2 sans la résoudre : ni `app/scaling/*` ni la table JSON ne sont modifiés ; RZ2 reste `open`. Suite complète verte sans régression (191/3). Les 2 findings sont `defer` (mince couverture œufs imposée par le corpus, liste noire réseau redondante) et ne remettent en cause aucun AC.

Étapes orchestrateur post-revue : passer E3 en `done`. L'assemblage de `app/scaling/__init__.py` (API publique consommée par E3) est déjà fusionné par l'orchestrateur, hors périmètre E3.

---

**VERDICT : APPROUVÉE** — bloquants : **0**, majeurs : **0**, mineurs : **2** (defer). Pytest : **23 passed** (ciblé) / **191 passed, 3 skipped** (suite complète), 0 régression. Corpus couvert : **13 recettes / 148 ingrédients** (`{linear:87, sublinear:53, geometric:6, discrete:1, fixed:1}`).
