---
titre: Check d'implémentation readiness — Scaler de recettes Epicure
type: readiness
statut: v1
créé: 2026-06-01
tags: [readiness, bmad, prd, architecture, backlog, sprint-planning]
---

# Check d'implémentation readiness

> Validation de la cohérence et de la complétude de l'ensemble **PRD + Architecture + Épics/Stories**
> avant de passer en implémentation (méthode BMAD). Réutilise les findings de
> [`validation-prd.md`](./validation-prd.md) et [`decisions-techniques.md`](./decisions-techniques.md)
> sans les refaire. Six portes de qualité, statut ✅ PRÊT / ⚠️ RÉSERVE / ❌ BLOQUANT.

---

## Verdict global : **PRÊT AVEC RÉSERVES** ✅⚠️

Le projet **peut entrer en sprint planning et démarrer l'implémentation** sur un large périmètre
(Phase 0 finalisation + Épic B + Épic C — le cœur). Le triptyque PRD / Architecture / Backlog est
cohérent, tracé et d'un niveau bien au-dessus de la moyenne pour un projet portfolio : problème net,
LLM correctement cantonné, cœur de valeur (scaling + garde-fou) identifié et conçu jusqu'aux
signatures de fonctions, traçabilité FR → couche → story quasi complète.

**Aucun bloqueur dur (❌) n'empêche de commencer à coder.** Les réserves sont de deux natures :
(a) quelques **ambiguïtés de spécification du cœur** qui doivent être tranchées *au moment* d'écrire
les stories C et D concernées (pas avant), et (b) des **décisions encore EN ATTENTE/⚠️** qui bloquent
des stories *précises et tardives* (D2, D3, A2/A3), mais pas le démarrage. Le détail story par story
est en §« Bloqueurs & réserves ».

---

## Tableau porte par porte

| # | Porte de qualité | Statut | Findings concrets |
|---|---|---|---|
| 1 | **PRD complet & testable** | ✅ PRÊT | Les corrections P0 de `validation-prd.md` sont **appliquées** dans le PRD v0.2 : FR3 est désormais une assertion testable (« 100 % des temp/temps/techniques de la base, sinon échec »), FR5 est scindée en **FR5a/b/c**, FR6 en **FR6a/b**, et les NFR sont chiffrées (déterminisme bit-à-bit, ≤ 12 dépendances runtime, une commande, < 3 s hors LLM) avec ajout de **Performance** et **Robustesse**. Reste 3 réserves *non bloquantes* héritées de la validation et **non encore traitées** : FR2 ne chiffre toujours pas `k`/`N` dans le tableau FR (la reformulation « k=8 par défaut » vit dans `validation-prd.md`, pas dans le PRD) ; FR7/FR8 conservent une part de subjectivité (« raisonnement » ; capacité UI vs R&D) ; le protocole chiffré de validation du scaling (critère succès n°1) reste renvoyé hors PRD. |
| 2 | **Architecture complète** | ✅ PRÊT | `architecture.md` couvre **chaque FR** (annexe de traçabilité §13/Annexe) avec couche + section, fournit les **signatures prescriptives** des 4 couches (`scale`, `scale_eggs`, `scale_time`, `classify`, `techniques_for`, `forbidden_cookware`, `safety_for`, `build_prompt`, `validate_recipe`, `to_cooklang`, `to_markdown`), les **schémas de données** (embeddings, JSON base technique, table scaling, `.cook`) et le **contrat d'API** Pydantic (`GenerationRequest`/`Constraints`/`GenerationResponse`/`DebugInfo`, codes 200/422/502). Le flux bout-en-bout §7 fige l'ordre clé (rédaction LLM **avant** scaling). Manques résiduels, tous marqués honnêtement `[À TRANCHER]`/`[HYPOTHÈSE]` : structure exacte de `ScaledQuantity`/`ScaledEggs`/`FilteredNeighbors` proposée mais non figée ; **table de traduction FR → clé Epicure** identifiée comme « principal point d'intégration restant » mais sans story dédiée (cf. porte 3) ; format de sortie LLM structuré (D10) recommandé mais ouvert. |
| 3 | **Cohérence croisée PRD ↔ Archi ↔ Backlog** | ⚠️ RÉSERVE | Cohérence de fond excellente, **deux écarts concrets** : (a) **le backlog n'a pas suivi la scission des FR** — il référence encore « FR5 » et « FR6 » globalement (stories C1-C4, D3, D4) alors que le PRD parle de FR5a/b/c et FR6a/b ; à resynchroniser pour une DoD propre, sans impact technique. (b) **La table de traduction FR→clé Epicure** (exigée par `decisions-techniques.md` #1, risque R4 de l'archi : « héros francophone absent du vocab anglais ») **n'a aucune story** dans le backlog ; c'est un trou de couverture réel sur la couche 1. Écarts mineurs déjà notés : FR8 « capacité UI vs R&D » non tranchée (A2 ne livre qu'une note, pas de sélecteur exposé) ; PRD §7 toujours « format à confirmer » alors que S0.1 l'a figé (cosmétique). Aucune contradiction de valeurs (températures/coefficients identiques partout). |
| 4 | **Décisions bloquantes** | ⚠️ RÉSERVE | Sur les points de `decisions-techniques.md` : #1/#2 (format embeddings) **TRANCHÉ**, #3 Cooklang **TRANCHÉ** (templating + regex), Point B benchmark **TRANCHÉ** (`cooc` par défaut). Restent **3 points ouverts mappés à des stories** : **#3-bis ⚠️** (identité/maintenance du paquet PyPI `cooklang-py`) → impacte **D3** (validation `.cook`) mais avec fallback regex, donc non bloquant ; **#4 ⚠️** (ligne œufs + sources ANSES de `safety-temperatures.json`) → impacte **S0.5** puis **D2** (le garde-fou cite ces lignes) — 5/7 lignes USDA sont figeables tout de suite, seules œufs + références ANSES restent ⚠️ ; **Point #5 ⏳** (import `cook.md/<url>`) → impacte **S0.6** (corpus), sans impact runtime. Voir mapping détaillé ci-dessous. |
| 5 | **Prêt pour le sprint planning** | ✅ PRÊT | Le découpage est actionnable : épics A-F, stories à grain fin, chacune avec critères d'acceptation **exploitables et souvent chiffrés** (`scale("sel",1,…,2.0) < 2`, `scale_eggs(3,2.0)→5`, `20 min ×2 → ~32 min`, « pas de four exclut `searing_braising` »). Les dépendances inter-stories sont déductibles de l'archi §7. Réserve : l'ordre n'est pas explicité dans le backlog (proposé ci-dessous) et il manque une story « traduction FR→Epicure » (porte 3). |
| 6 | **État de l'existant** | ✅ PRÊT | Vérifié sur le code réel : **Couche 1 (`app/epicure/loader.py`) implémentée et fonctionnelle** (`EpicureIndex.neighbors`, L2-norm, `KeyError` si absent, sanity-check intégré). **Données prêtes** : `data/epicure/{cooc,core,chem}`, `docs/base-technique/{safety-temperatures,cuisine-italienne}.json`, `docs/scaling/table-scaling-sale.json`. **Squelettes** (docstring seule) : `app/knowledge/`, `app/scaling/`, `app/generator/`, `app/main.py` (`/health` uniquement). `tests/test_scaling.py` = 4 stubs `@pytest.mark.skip`. L'archi §1.4 décrit cet état **fidèlement**. Le point de départ est donc : couche 1 et toutes les données acquises → l'effort réel commence à la couche 2/3. |

---

## Bloqueurs (❌) à lever avant de coder

**Aucun bloqueur dur.** Rien n'empêche de lancer le sprint planning ni de commencer à coder la
finalisation Phase 0, la couche 2 (Épic B) et le cœur scaling (Épic C). Les points ci-dessous sont
des **réserves (⚠️)** à traiter *au fil de l'eau*, chacune associée à sa/ses story(ies) :

| Réf | Réserve actionnable | Story(ies) concernée(s) | Quand la traiter |
|---|---|---|---|
| RZ1 | **Règle exacte des œufs** : l'AC `scale_eggs(3,2.0)→5` **contredit la formule pure** `round(3×2.0)=6` puis arrondi bas = 6. La règle « pour 3 doublés, essayer 5 plutôt que 6 » n'est encodée que dans le champ `reason` (texte) de la table, pas comme formule déterministe. Le dev doit **figer l'algorithme** qui produit 5 de façon reproductible et le couvrir par `test_oeufs_discrets`. | **C2** | Au moment d'écrire C2 |
| RZ2 | **Seuil de `k` déclenchant la note de changement de contenant / le flag non-linéarité** non chiffré dans la table (`[À TRANCHER]` archi §5.5) ; hypothèse ~1,5–2×. À figer comme constante lisible. | **C3, C4** | Au moment d'écrire C3/C4 |
| RZ3 | **Story manquante : traduction FR → clé Epicure** (`snake_case` anglais). Sans elle, un héros « courgette »/« huile d'olive » lève `KeyError` (R4). À **ajouter au backlog** (couche 1, Épic A) avant la mise en service de l'UI. | **nouvelle story A4** (préreq. de E1/E2) | Avant E1/E2 |
| RZ4 | **Valeurs de sécurité œufs + sources ANSES** non figées (#4 ⚠️) : 5/7 lignes USDA confirmées, mais la ligne œufs (scinder « plats aux œufs 160 °F » / sourcer le « 60 °C-2 min ») et les URLs ANSES/EFSA du `meta` restent à vérifier manuellement. Le garde-fou D2 cite ces lignes. | **S0.5** (préreq. de **D2**) | Avant D2 |
| RZ5 | **Identité/maintenance du paquet `cooklang-py` PyPI** (#3-bis ⚠️ — homonyme du dépôt officiel archivé). Décision : à confirmer avant ajout comme dépendance ; sinon **fallback validation regex maison** (déjà la stratégie tranchée). | **D3** | Au moment d'écrire D3 |
| RZ6 | **Resynchroniser le backlog** sur FR5a/b/c & FR6a/b (libellés FR5/FR6 obsolètes) et **trancher FR8** (sélecteur UI vs note R&D). Pur alignement documentaire. | **C1-C4, D3, D4, A2** | Avant figeage DoD |

> En résumé : **0 bloqueur**, **6 réserves**, dont 2 (RZ4, RZ3) sont des prérequis à des stories
> tardives (D2, E1/E2) et doivent juste être faites *avant ces stories-là*, pas avant le sprint.

---

## Graphe de dépendances des stories

```
SOCLE DONNÉES (déjà acquis)
  Couche 1 loader.py  ✔          data Epicure ✔   JSON base+scaling ✔
        │                              │                  │
        ▼                              ▼                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ S0.5 (valeurs sécurité USDA/ANSES) ──► débloque ──► D2                │
│ S0.3 Cooklang ✔(tranché doc) · S0.4 (Obsidian) ──► valide ──► D3      │
│ S0.6 corpus (cook.md) ──► alimente ──► E3 (validation), C5 notebook   │
└─────────────────────────────────────────────────────────────────────┘

ÉPIC C (CŒUR — indépendant, parallélisable, aucune dépendance LLM) :
  C1 (linear/sublinear/fixed + lecture table)
      ├─► C2 (œufs discrets)        ┐
      ├─► C3 (temps géométrique)    ├─► C5 (tests pytest + notebook calibration)
      └─► C4 (flags + réserve 10%)  ┘

ÉPIC B (couche 2, indépendant de C) :
  B3 (loader knowledge + techniques_for) ─► B4 (mapping contraintes → cookware interdit)

ÉPIC A (couche 1, complète l'existant) :
  A1 ✔(loader) · A2 (benchmark cooc/core — tranché doc) · A3 (filtrage cuisine/contraintes)
  + [A4 NOUVELLE] traduction FR→clé Epicure

ÉPIC D (générateur — dépend de A3 + B3/B4 + C + S0.5/S0.4) :
  D1 (prompt contraint) ─► D2 (garde-fou, requiert S0.5) ─► D3 (.cook, requiert C + S0.4) ─► D4 (markdown)

ÉPIC E (app — dépend de tout le pipeline) :
  E1 (endpoint /generate, requiert A4) ─► E2 (UI) · E3 (validation, requiert S0.6) · E4 (README)

ÉPIC F (extension, après v1) : F1 (2e cuisine) · F2 (calibration coeffs) · F3 (doc pâtisserie)
```

Chemin critique : **C → D → E**. L'Épic C (le cœur) n'a **aucune dépendance amont** (couche pure,
table déjà prête) → c'est le meilleur point de départ et il peut avancer **en parallèle** de B et de
la finalisation Phase 0.

---

## Ordre de réalisation recommandé (sprint)

En tenant compte que la **couche 1 est faite** et que l'**Épic C est le cœur** :

1. **C1** — moteur scaling : types `linear`/`sublinear`/`fixed` + lecture de `table-scaling-sale.json`.
   Aucune dépendance, AC chiffrée, débloque tout le cœur. *Point de départ idéal.*
2. **C2** — scaling discret des œufs (lever RZ1 : figer la règle produisant 5).
3. **C3** — scaling géométrique du temps `k^(2/3)` (lever RZ2 : seuil de contenant).
   *(puis C4 flags/réserve, C5 tests+notebook — clôture le cœur, `pytest` vert.)*
4. **En parallèle de C** : **B3** (loader knowledge + `techniques_for`) puis **B4** (mapping cookware),
   et **finalisation Phase 0** : **S0.5** (figer sécurité — prérequis D2), **S0.4** (Obsidian), **S0.6** (corpus).
5. **A3** (filtrage voisins) + **A4** (traduction FR→Epicure, RZ3) pour compléter la couche 1.
6. **Épic D** : D1 → D2 (après S0.5) → D3 (après C + S0.4, lever RZ5) → D4.
7. **Épic E** : E1 (après A4) → E2 → E3 (après S0.6) → E4.
8. **Épic F** : extension/polish, hors v1.

---

## Recommandation finale

**Oui — le sprint planning peut être lancé.** Le périmètre de démarrage recommandé est :

- **Sprint 1 (cœur)** : **C1 → C2 → C3 → C4 → C5** — l'Épic scaling, qui est la valeur du projet,
  est pur, déterministe, sans dépendance amont, avec des AC déjà chiffrées et des signatures
  prescrites. C'est le travail le plus sûr et le plus rentable à attaquer immédiatement.
- **En parallèle** : couche 2 (**B3, B4**) et finalisation Phase 0 (**S0.4, S0.5, S0.6**), pour
  débloquer l'Épic D ensuite.

Traiter les réserves **au moment d'écrire la story concernée** : RZ1 dans C2, RZ2 dans C3/C4, RZ4
(S0.5) avant D2, RZ3 (story A4) avant E1/E2, RZ5 dans D3. Resynchroniser le backlog sur FR5a/b/c et
FR6a/b et trancher FR8 (RZ6) avant de figer la DoD — opération documentaire de quelques minutes.

Le projet est dans un état de readiness rare pour un playground : conception poussée jusqu'aux
signatures, décisions techniques majoritairement tranchées avec preuves de première main, et un point
de départ propre (couche 1 + données acquises). Rien ne justifie d'attendre pour commencer à coder le
cœur.
