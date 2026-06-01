---
titre: Plan de sprint — Scaler de recettes Epicure
type: sprint-plan
statut: v1
créé: 2026-06-01
tags: [sprint-plan, bmad, backlog, scaling, epicure]
---

# Plan de sprint

> Plan de sprint exploitable issu du sprint planning (méthode BMAD). Réutilise les conclusions du
> [`readiness-check.md`](./readiness-check.md) (verdict **PRÊT AVEC RÉSERVES**, 0 bloqueur dur,
> ordre recommandé **C1 → C2 → C3**), du [`backlog.md`](./backlog.md) (épics A-F, stories, AC) et
> des [`decisions-techniques.md`](./decisions-techniques.md). Convention statut : **Fait** /
> **À faire** / **Bloqué**. Priorités : **P0** (socle/cœur), **P1** (v1 fonctionnelle),
> **P2** (polish/extension).

---

## 1. Tableau de statut global des stories

Inclut la nouvelle story **A4** (traduction FR → clé Epicure), exigée par RZ3.

| ID | Intitulé court | Épic | Priorité | Statut | Dépendances | Sprint cible |
|---|---|---|---|---|---|---|
| **S0.1** | Télécharger embeddings Epicure + inspecter format | Phase 0 | P0 | **Fait** | — | — |
| **S0.2** | Charger en Python + cosine top-k | Phase 0 | P0 | **Fait** | S0.1 | — |
| **S0.3** | Trancher le parseur Cooklang (templating maison) | Phase 0 | P0 | **Fait** | — | — (acté doc) |
| **S0.4** | Valider un `.cook` minimal dans Obsidian | Phase 0 | P0 | À faire | S0.3 | Sprint 2 |
| **S0.5** | Confirmer valeurs sécurité USDA/ANSES + figer JSON | Phase 0 | P0 | À faire | B1 | Sprint 2 |
| **S0.6** | Constituer corpus 10-15 recettes italiennes (`cook.md`) | Phase 0 | P0 | À faire | S0.3 | Sprint 2 |
| **A1** | Loader embeddings + cosine top-k | A | P0 | **Fait** | S0.1, S0.2 | — |
| **A2** | Benchmark `cooc` vs `core` + note de décision | A | P1 | **Fait** | A1 | — (tranché doc) |
| **A3** | Filtrage des voisins par cuisine/contraintes | A | P1 | À faire | A1, B3 | Sprint 3 |
| **A4** | **Traduction FR → clé Epicure** (`snake_case` EN) | A | P1 | À faire | A1 | Sprint 3 |
| **B1** | `safety-temperatures.json` (rédigé) | B | P0 | **Fait** | — | — |
| **B2** | `schema.md` + `cuisine-italienne.json` | B | P0 | **Fait** | — | — |
| **B3** | Loader knowledge + `techniques_for(...)` | B | P1 | À faire | B2 | Sprint 2 |
| **B4** | Mapping contraintes matérielles → `#cookware` interdits | B | P1 | À faire | B3 | Sprint 2 |
| **C1** | Types linear/sublinear/fixed + lecture table | C | P0 | À faire | — (table prête) | **Sprint 1** |
| **C2** | Scaling discret des œufs (RZ1) | C | P0 | À faire | C1 | **Sprint 1** |
| **C3** | Scaling géométrique du temps `k^(2/3)` (RZ2) | C | P0 | À faire | C1 | **Sprint 1** |
| **C4** | Flags de non-linéarité + réserve 10 % (RZ2) | C | P0 | À faire | C1, C3 | **Sprint 1** |
| **C5** | Tests unitaires déterministes + notebook calibration | C | P0 | À faire | C1-C4, S0.6 | **Sprint 1** (notebook partiel) |
| **D1** | Prompt contraint + intégration Claude API | D | P1 | Bloqué | A3, B3/B4, C | Sprint 4 |
| **D2** | Garde-fou « jamais hors base » + tests anti-hallucination (RZ4) | D | P1 | Bloqué | D1, S0.5 | Sprint 4 |
| **D3** | Émission `.cook` + validation (RZ5) | D | P1 | Bloqué | D1, C, S0.4 | Sprint 4 |
| **D4** | Rendu Markdown lisible | D | P1 | Bloqué | D3 | Sprint 4 |
| **E1** | FastAPI + endpoint `/generate` | E | P1 | Bloqué | D, A4 | Sprint 5 |
| **E2** | UI minimale (formulaire + rendu + debug) | E | P1 | Bloqué | E1 | Sprint 5 |
| **E3** | Jeu de validation scaling (corpus) | E | P2 | Bloqué | C5, S0.6 | Sprint 5 |
| **E4** | README portfolio + attribution Epicure (CC BY 4.0) | E | P2 | À faire | — | Sprint 5 |
| **F1** | Ajouter une 2ᵉ cuisine (sans toucher au code) | F | P2 | Bloqué | B3, B4 | Post-v1 |
| **F2** | Affiner coefficients de scaling via tests réels | F | P2 | Bloqué | C5 | Post-v1 |
| **F3** | Documenter le différé pâtisserie (chimie) | F | P2 | À faire | — | Post-v1 |

> « Bloqué » = la story attend une dépendance non terminée ; elle se débloque mécaniquement dès que
> son prérequis passe à **Fait**. Aucune story n'est bloquée par une décision non tranchée.

---

## 2. Graphe / ordre de dépendances

Séquence réaliste tenant compte de l'existant (couche 1 + données acquises) et du chemin critique
**C → D → E**. L'Épic C n'a **aucune dépendance amont** : c'est le point de départ.

```
SOCLE ACQUIS (Fait) : loader.py (A1) · data Epicure · JSON base (B1,B2) · table scaling
       │
       ▼
ÉPIC C (CŒUR — pur/déterministe, parallélisable, indépendant)        ←── SPRINT 1
   C1 (linear/sublinear/fixed + lecture table)
       ├─► C2 (œufs discrets, RZ1)
       ├─► C3 (temps géométrique k^2/3, RZ2)
       └─► C4 (flags non-linéarité + réserve 10 %, RZ2)
                 └─► C5 (tests pytest verts + notebook calibration)

ÉPIC B (couche 2, indépendant de C)                                  ←── SPRINT 2 (//)
   B3 (loader knowledge + techniques_for) ─► B4 (mapping cookware interdit)

PHASE 0 finalisation                                                 ←── SPRINT 2 (//)
   S0.4 (Obsidian, débloque D3) · S0.5 (sécurité, RZ4, débloque D2) · S0.6 (corpus, alimente E3/C5)

ÉPIC A (complète couche 1)                                           ←── SPRINT 3
   A3 (filtrage cuisine/contraintes, dépend B3) · A4 (traduction FR→Epicure, RZ3, préreq E1)

ÉPIC D (générateur — requiert A3 + B3/B4 + C + S0.4/S0.5)            ←── SPRINT 4
   D1 (prompt contraint) ─► D2 (garde-fou, requiert S0.5, RZ4)
                          ─► D3 (.cook, requiert C + S0.4, RZ5) ─► D4 (markdown)

ÉPIC E (app — requiert tout le pipeline + A4)                        ←── SPRINT 5
   E1 (/generate, requiert A4) ─► E2 (UI) · E3 (validation, requiert S0.6) · E4 (README)

ÉPIC F (extension, hors v1)                                          ←── POST-V1
   F1 (2e cuisine) · F2 (calibration coeffs) · F3 (doc pâtisserie)
```

**Chemin critique : C → D → E.** B et la finalisation Phase 0 avancent en parallèle de C sans le
bloquer.

---

## 3. Découpage en sprints (projet solo, sprints thématiques courts)

| Sprint | Thème / objectif | Stories incluses | Sort le verrou de… |
|---|---|---|---|
| **Sprint 1** | **Le cœur : moteur de scaling déterministe et testé** | C1, C2, C3, C4, C5 | la valeur produit ; débloque D (scaling) |
| **Sprint 2** | Couche 2 (savoir technique) + finalisation Phase 0 | B3, B4, S0.4, S0.5, S0.6 | débloque D1/D2/D3 et alimente E3/C5 |
| **Sprint 3** | Couche 1 complète (associations exploitables) | A3, A4 | débloque E1 (héros FR) et le filtrage |
| **Sprint 4** | Générateur LLM sous contraintes | D1, D2, D3, D4 | produit la recette `.cook` + garde-fou |
| **Sprint 5** | App web + validation + portfolio | E1, E2, E3, E4 | livrable v1 utilisable en local |
| **Post-v1** | Extension & polish | F1, F2, F3 | modularité, calibration, doc différée |

> Les sprints 1 et 2 peuvent **se chevaucher** (C est indépendant de B et de la Phase 0). En solo, on
> attaque le cœur (Sprint 1) en priorité ; les tâches Phase 0 du Sprint 2 sont insérables dès qu'un
> créneau s'y prête sans casser le flow sur C.

---

## 4. Détail du SPRINT 1 (le cœur)

**Objectif** : livrer `app/scaling/` — un moteur de scaling **pur et déterministe** qui applique, par
ingrédient, le bon type de mise à l'échelle (linéaire / sous-linéaire / discret / géométrique / figé)
selon `docs/scaling/table-scaling-sale.json`, avec flags de non-linéarité, réserve d'assaisonnement,
et une suite `pytest` verte. À la fin du sprint, `pytest tests/test_scaling.py` passe (les 4 stubs
`@pytest.mark.skip` deviennent des tests actifs) et le moteur est prêt à être consommé par l'Épic D.

**Périmètre** : C1 → C2 → C3 → C4 → C5. Pas de LLM, pas d'I/O réseau, pas d'UI.

**Modules cibles communs** : `app/scaling/__init__.py` (squelette actuel), un module
d'implémentation `app/scaling/engine.py` (types `ScaledQuantity`, `ScaledEggs`, `ScaledTime`,
`ScalingRule` + fonctions `classify`, `scale`, `scale_eggs`, `scale_time`), un loader de table
`app/scaling/table.py` (lecture unique de `docs/scaling/table-scaling-sale.json`), et les tests
`tests/test_scaling.py`. Signatures **prescrites** par `architecture.md` §5 :

```python
def scale(name: str, qty: float, unit: str, k: float) -> ScaledQuantity: ...
def scale_eggs(count: int, k: float) -> ScaledEggs: ...
def scale_time(minutes: float, k: float) -> ScaledTime: ...
def classify(name: str) -> ScalingRule:   # lit table-scaling-sale.json, renvoie type/coeff
```

### Ordre d'exécution explicite

1. **C1** (fondations : table + `classify` + `scale` linear/sublinear/fixed) — *première story à coder*
2. **C2** (`scale_eggs`, discret — lever RZ1)
3. **C3** (`scale_time`, géométrique — poser la constante de seuil k, RZ2)
4. **C4** (flags non-linéarité + réserve 10 % — consomme le seuil k de RZ2)
5. **C5** (tests déterministes complets + amorce du notebook de calibration)

---

### C1 — Types linear/sublinear/fixed + lecture de la table  (P0, première story)

**Critères d'acceptation (affinés)**
- `classify(name)` lit `docs/scaling/table-scaling-sale.json` (chargée **une seule fois**, en
  lecture seule) et retourne la première règle dont un motif `match` correspond ; à défaut, la règle
  par défaut `linear` (`defaults.main_ingredients`). Matching insensible à la casse/accents, **par
  token entier** (FR + EN), pas par sous-chaîne (éviter « ail » dans « vol-au-vent »).
- `scale("sel", 1, "c.à.c", 2.0)` renvoie une valeur **< 2** (sous-linéaire, `coeff = 0.75` →
  `1 × 2^0.75 ≈ 1.68`) ; `type == "sublinear"`.
- Un ingrédient principal non listé (ex. « tomate ») → `linear` → `scale("tomate", 200, "g", 2.0)` = `400 g`.
- Une température (`"four"`, `"température"`) → `type == "fixed"`, `fixed == True`, valeur inchangée,
  destinée à porter le verrou `=` Cooklang.
- Sortie typée `ScaledQuantity` : `name`, `value`, `unit`, `type`, `fixed: bool`, `notes: list[str]`,
  `debug: {rule, coeff, formula, reasoning}`.

**Fichiers/modules cibles** : `app/scaling/table.py` (loader JSON + cache), `app/scaling/engine.py`
(`ScalingRule`, `ScaledQuantity`, `classify`, `scale`), `tests/test_scaling.py`
(`test_sel_sous_lineaire`, `test_temperature_figee`, + cas linéaire).

**Définition de « terminé »** : `classify` et `scale` (linear/sublinear/fixed) implémentés ;
`test_sel_sous_lineaire` et `test_temperature_figee` passent (skip retiré) ; déterminisme vérifié
(même entrée → même sortie sur N exécutions) ; aucun coefficient codé en dur (tout vient de la table).

---

### C2 — Scaling discret des œufs  (P0 — lève RZ1)

**Critères d'acceptation (affinés, intégrant RZ1)**
- `scale_eggs(3, 2.0)` → **5 œufs entiers** (pas 6), avec une **note** explicative, et le reste exprimé
  en volume/poids (`grams_per_unit: 50`, `tbsp_per_unit: 3`, demi-œuf ≈ 25 g battu).
- **RZ1 — règle déterministe à figer** : la formule pure `round(3 × 2.0) = 6` doit être corrigée. Algo
  prescrit et **à documenter en commentaire** : cible théorique `target = count * k` ; `whole = floor(target)` ;
  puis règle de borne basse « œufs liants » : si l'écart à l'entier supérieur est faible ET que le
  doublage rend la liaison excessive, retenir `whole - 1` et reporter la différence en `remainder`
  (g/c.à.s). Pour `(3, 2.0)` : `target = 6`, la règle de borne basse retient **5** + `remainder` ≈ 50 g
  (1 œuf battu) en note. La règle doit produire 5 **de façon reproductible** et être verrouillée par
  `test_oeufs_discrets`. Tester aussi un cas où l'arrondi bas suffit (ex. `scale_eggs(2, 1.5)` →
  `target = 3` → 3, pas de correction) pour cadrer le domaine de la règle.
- Sortie `ScaledEggs` : `whole_eggs: int`, `remainder` (g ou c.à.s), `note: str`.

**Fichiers/modules cibles** : `app/scaling/engine.py` (`ScaledEggs`, `scale_eggs`),
`tests/test_scaling.py` (`test_oeufs_discrets` + cas de non-correction).

**Définition de « terminé »** : règle œufs **écrite explicitement** (formule + condition de borne
basse) dans le code et un commentaire référant RZ1 ; `test_oeufs_discrets` passe et asserte `5` pour
`(3, 2.0)` ; comportement déterministe ; un cas sans correction couvert.

---

### C3 — Scaling géométrique du temps `k^(2/3)`  (P0 — touche RZ2)

**Critères d'acceptation (affinés, intégrant RZ2)**
- `scale_time(20, 2.0)` → **~32 min** (pas 40) : `20 × 2^(2/3) = 20 × 1.59 ≈ 31.8`. `exponent` lu dans
  la table (`0.6667`). Cohérence avec `geometricTimeExamples` (×1.5→1.31, ×2→1.59, ×3→2.08, ×4→2.52).
- Sortie `ScaledTime` : `minutes`, `nonlinear: True`, `note`.
- **RZ2 — seuil k à figer** : introduire une **constante lisible** `K_NONLINEAR_THRESHOLD = 1.5`
  (hypothèse archi §5.5 : ~1.5–2×, valeur basse retenue par prudence). Au-delà de ce seuil,
  `scale_time` attache une note `--` suggérant un changement de contenant (ex.
  `-- à 2×, surface de cuisson plus large, réduction plus longue`). La constante est **documentée**
  comme « à calibrer (F2) » et **partagée** avec C4.

**Fichiers/modules cibles** : `app/scaling/engine.py` (`ScaledTime`, `scale_time`, constante
`K_NONLINEAR_THRESHOLD`), `tests/test_scaling.py` (`test_temps_geometrique` + test du déclenchement de
note au-delà du seuil).

**Définition de « terminé »** : `scale_time` implémenté ; `test_temps_geometrique` passe (asserte
~32 pour `(20, 2.0)`, tolérance ±0.5) ; constante de seuil k définie une seule fois, commentée RZ2 ;
note émise quand `k ≥ K_NONLINEAR_THRESHOLD`.

---

### C4 — Flags de non-linéarité + réserve 10 %  (P0 — consomme RZ2)

**Critères d'acceptation (affinés)**
- Une catégorie portant `nonlinearFlag: true` (piment, temps) reçoit, dès `k ≥ K_NONLINEAR_THRESHOLD`
  (constante de C3, RZ2), la note `-- ne se double pas proprement au-delà de ~1.5–2×`.
- Le sel (`reserve_pct: 10`) est scindé par le moteur : **90 %** à l'incorporation + **10 %** réservé
  en ajustement final, avec une note `--` correspondante. Généralisation : toute catégorie portant
  `reserve_pct` reçoit ce traitement ; en v1 seul le sel le porte.
- Les notes et flags remontent dans `ScaledQuantity.notes` et `ScaledQuantity.debug`.

**Fichiers/modules cibles** : `app/scaling/engine.py` (logique flags + réserve dans `scale`),
`tests/test_scaling.py` (test flag piment à `k=2.0`, test réserve sel = 90/10).

**Définition de « terminé »** : flag non-linéarité émis correctement selon le seuil partagé ; réserve
10 % appliquée au sel et exprimée en note ; tests dédiés verts.

---

### C5 — Tests unitaires déterministes + notebook de calibration  (P0)

**Critères d'acceptation (affinés)**
- `pytest tests/test_scaling.py` **vert**, sans `skip` : les 4 stubs (`test_sel_sous_lineaire`,
  `test_oeufs_discrets`, `test_temps_geometrique`, `test_temperature_figee`) sont implémentés et
  passent, plus les cas ajoutés en C2/C3/C4.
- Un test de **déterminisme** explicite : même `(name, qty, unit, k)` → `ScaledQuantity` identique sur
  N exécutions (NFR déterminisme bit-à-bit du PRD §5).
- Tests de scénarios `×2`, `÷2`, `×4` sur quelques ingrédients représentatifs.
- Amorce du **notebook de calibration** comparant moteur vs `×N` naïf. *Note* : la comparaison sur le
  corpus complet dépend de S0.6 (Sprint 2) ; en Sprint 1 on livre le squelette du notebook + la
  comparaison sur 2-3 exemples codés en dur. Le notebook complet est finalisé après S0.6.

**Fichiers/modules cibles** : `tests/test_scaling.py` (suite complète), `notebooks/calibration_scaling.ipynb`
(amorce).

**Définition de « terminé »** : `pytest` vert ; test de déterminisme présent ; scénarios ×2/÷2/×4
couverts ; notebook amorcé (comparaison complète différée à S0.6).

---

## 5. Risques / réserves du sprint (RZ1-RZ6)

| Réf | Réserve | Story rattachée | Action de levée |
|---|---|---|---|
| **RZ1** | Règle des œufs `scale_eggs(3,2.0)→5` contredit `round(3×2.0)=6` | **C2** | Figer dans le code l'algo déterministe (cible théorique + borne basse « œufs liants ») produisant 5, le commenter RZ1 et le verrouiller par `test_oeufs_discrets`. **Traité dans ce sprint.** |
| **RZ2** | Seuil de `k` (note contenant / flag non-linéarité) non chiffré | **C3, C4** | Définir une constante `K_NONLINEAR_THRESHOLD = 1.5` (commentée « à calibrer F2 »), partagée par C3 et C4. **Traité dans ce sprint.** |
| **RZ3** | Story manquante : traduction FR → clé Epicure | **A4** (nouvelle) | A4 ajoutée au backlog/au tableau §1, planifiée **Sprint 3**, prérequis de E1/E2. Hors Sprint 1. |
| **RZ4** | Valeurs sécurité œufs + sources ANSES non figées | **S0.5** (préreq. D2) | Confirmer USDA/ANSES et figer `safety-temperatures.json` en **Sprint 2**, avant D2 (Sprint 4). Hors Sprint 1. |
| **RZ5** | Identité/maintenance du paquet `cooklang-py` PyPI | **D3** | Confirmer le paquet au moment de D3 (Sprint 4) ; sinon fallback validation regex maison (déjà tranché). Hors Sprint 1. |
| **RZ6** | Resync backlog FR5a/b/c & FR6a/b + trancher FR8 | **C1-C4, D3, D4, A2** | Alignement documentaire : mettre à jour les libellés FR dans le backlog et trancher FR8 (sélecteur UI vs note R&D) **avant de figer la DoD** ; à faire en marge du Sprint 1 (quelques minutes), n'impacte pas le code C. |

> Pour le Sprint 1, seules **RZ1** et **RZ2** sont actives et sont **levées dans les stories C2 et
> C3/C4**. RZ3/RZ4/RZ5 concernent des sprints ultérieurs ; RZ6 est un nettoyage documentaire à passer
> avant de figer la DoD globale.

---

## 6. Définition de « terminé » (DoD) du Sprint 1

Alignée sur la DoD du backlog (« code testé — unitaire pour le cœur déterministe ; pas de
température/technique hors base ; `.cook` valide ; attribution Epicure ; README à jour ») et restreinte
au périmètre du cœur scaling :

- **Code testé** : `pytest tests/test_scaling.py` vert, sans `@pytest.mark.skip` ; couverture des cas
  linéaire, sous-linéaire (sel), discret (œufs, RZ1), géométrique (temps, RZ2), figé (température),
  flags non-linéarité et réserve 10 %.
- **Déterminisme** (NFR PRD §5) : un test asserte une sortie identique sur exécutions répétées ; le
  module `app/scaling/` reste pur (aucune I/O réseau, aucun état mutable global, table lue une seule
  fois en lecture seule).
- **Pas de magie codée en dur** : tous les coefficients/paramètres proviennent de
  `table-scaling-sale.json` ; les seuils figés (RZ2) sont des constantes nommées et commentées.
- **Réserves levées** : RZ1 figée dans C2 ; RZ2 figée comme constante dans C3/C4.
- **Signatures conformes** à `architecture.md` §5 (`scale`, `scale_eggs`, `scale_time`, `classify`).
- **Documentation** : la règle œufs (RZ1) et le seuil k (RZ2) sont commentés dans le code ; le
  notebook de calibration est amorcé. RZ6 (resync backlog FR5a/b/c, FR6a/b ; trancher FR8) passé avant
  figeage de la DoD globale.
- **Prêt pour l'aval** : le moteur expose des `ScaledQuantity`/`ScaledEggs`/`ScaledTime` consommables
  par l'Épic D (émission `.cook` après scaling).

---

## 7. Lancement immédiat

Le plan permet de lancer tout de suite :

1. `create-story` sur **C1** (types linear/sublinear/fixed + lecture de la table).
2. puis `dev-story` sur la story C1 produite.

**Première story à implémenter : C1** — fichiers cibles `app/scaling/table.py`,
`app/scaling/engine.py`, tests `tests/test_scaling.py`.
