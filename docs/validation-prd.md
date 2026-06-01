---
titre: Rapport de validation du PRD — Générateur/scaler de recettes Epicure
type: validation
statut: v1
créé: 2026-06-01
tags: [validation, prd, qualite, tracabilite, bmad]
---

# Rapport de validation du PRD

> Validation rigoureuse (méthode BMAD) du document `docs/PRD.md` (statut « v1-cadrage »)
> contre une checklist de qualité produit. Objectif : améliorer, pas complimenter.
> Documents croisés : `docs/backlog.md`, `pitch.md`, `docs/etude-marche.md`.

## 1. Synthèse

**Verdict global : PRÊT AVEC RÉSERVES.**

**Score qualité indicatif : 78 / 100.**

Le PRD est nettement au-dessus de la moyenne pour un projet portfolio : problème clair,
positionnement honnête et aligné sur l'étude de marché, architecture en couches lisible,
traçabilité FR → backlog quasi complète, et un vrai sens de la priorisation (Must / Should /
Could). La pièce maîtresse (moteur de scaling) est correctement identifiée comme cœur de valeur
et bien couverte par les stories.

Les réserves sont concentrées sur **la testabilité des exigences** : plusieurs FR mélangent
plusieurs comportements (non atomiques) ou contiennent des termes subjectifs non testables
(« cohérente », « lisible », « crédible »), et **les exigences non-fonctionnelles manquent
presque toutes de seuils chiffrés vérifiables**. Les critères de succès reposent fortement sur de
l'« évaluation manuelle », ce qui est acceptable pour un playground mais doit être assumé et
encadré par un protocole. Ces points ne bloquent pas le démarrage de l'implémentation mais
doivent être corrigés avant de figer les critères d'acceptation des stories du cœur (Épic C/D).

## 2. Évaluation dimension par dimension

| # | Dimension | Statut | Observations concrètes |
|---|---|---|---|
| 1 | Clarté du problème & intention | ✅ | Problème énoncé en deux points nets (scaling naïf + hallucinations dangereuses), avec preuves (cas documentés). Intention explicite : projet perso/portfolio, pas payant. Le §0 « en une phrase » est excellent. Aucune ambiguïté sur le quoi/pourquoi. |
| 2 | Objectifs / non-objectifs | ⚠️ | Non-objectifs : excellents, exhaustifs, sans ambiguïté (pas de pâtisserie, mono-cuisine, pas d'auth, pas de nutrition). Objectifs : partiellement mesurables. « Prouver la valeur du moteur » et « rester exploratoire » ne sont pas des objectifs mesurables tant qu'on ne fixe pas de seuil (cf. critères de succès §7). « Ne jamais émettre une température hors base » est, lui, binaire et mesurable. |
| 3 | Utilisateur & cas d'usage | ✅ | Utilisateur unique bien cerné (l'auteur, à l'aise Obsidian/markdown). Parcours principal en 5 étapes, complet et cohérent avec l'architecture. Réserve mineure : aucun parcours alternatif/erreur décrit (héros inconnu d'Epicure, aucune association compatible après filtrage, contraintes contradictoires). Acceptable pour un playground mono-utilisateur mais à noter. |
| 4 | Exigences fonctionnelles FR1-8 | ⚠️ | 8 FR bien priorisées. Mais plusieurs ne sont pas atomiques (FR5, FR6 couvrent 2 livrables) et plusieurs contiennent des termes non testables (« cohérente » FR3, « lisible » FR6, « raisonnement » FR7). Détail et reformulations ci-dessous. |
| 5 | Exigences non-fonctionnelles | ❌ | C'est le point faible le plus net. Seuls « Coût » (~0,005–0,01 $/recette) et « Sécurité » (zéro = mesurable) sont vérifiables. « Déterminisme », « Simplicité » (« peu de dépendances », « une commande »), « Licence » manquent de critère chiffré ou d'assertion testable explicite. Pas de NFR de performance (latence de génération), ni de robustesse (comportement en cas d'échec API LLM). |
| 6 | Traçabilité FR → stories | ✅ | Les 8 FR sont toutes couvertes par au moins une story (tableau §3). Réserve : quelques stories n'ont pas de FR miroir explicite (corpus de test, benchmark, README, 2ᵉ cuisine) — légitimes mais cela révèle des objectifs présents dans le PRD sans FR dédiée. |
| 7 | Critères de succès | ⚠️ | Objectifs partiellement vérifiables. « Aucune recette hors base » (test auto) et « .cook s'ouvre dans Obsidian » sont objectifs. « Jugées plus justes qu'un ×N naïf » et « benchmark tranché » reposent sur une évaluation manuelle subjective sans protocole/seuil défini dans le PRD (le protocole est renvoyé à `recherche-ouverte.md`). Acceptable pour playground si le protocole est explicitement référencé et chiffré. |
| 8 | Hypothèses, dépendances, risques | ⚠️ | Hypothèses et dépendances claires (embeddings publics, clé API, Cooklang simple). Risques produit couverts. Manquent des risques d'exécution majeurs : (a) qualité/biais des embeddings Epicure (anglais, ~1790 ingrédients : héros francophone absent ?), (b) panne/coût/rate-limit de l'API LLM, (c) absence de jeu de données de référence « vérité terrain » pour valider le scaling (on valide contre un jugement humain — risque de biais de confirmation), (d) dépendance à des `[À VÉRIFIER]` encore ouverts (format embeddings, parseur Cooklang, valeurs sécurité non figées). |
| 9 | Cohérence interne (PRD vs pitch vs backlog) | ✅ | Forte cohérence. Le positionnement « scaler honnête / LLM rédacteur » du PRD reprend fidèlement le repositionnement de l'étude de marché. L'architecture 4 couches est identique dans le pitch (`pitch.md`) et le PRD. Le phasage PRD §11 correspond aux phases du pitch et aux épics A-F du backlog. Aucune contradiction de fond détectée (voir §5 pour 2 micro-écarts). |
| 10 | Complétude pour passage à l'implémentation | ⚠️ | Bon socle. Manquent pour « coder proprement » : un contrat de données d'entrée/sortie (schéma JSON de la requête `POST /generate` et de la réponse), la définition des plages/valeurs par défaut (N associations ? k voisins ?), le protocole de validation chiffré du scaling, et la résolution des `[À VÉRIFIER]` bloquants (S0.3, S0.5). Plusieurs sont dans le backlog mais pas tranchés. |

## 3. Tableau de traçabilité FR → épic / story

| FR | Intitulé (résumé) | Story(ies) couvrante(s) | Couverture |
|----|-------------------|--------------------------|------------|
| FR1 | Saisie héros + cuisine + contraintes + portions | E2 (UI formulaire), E1 (endpoint) | ✅ Couverte |
| FR2 | Proposer N associations Epicure filtrées | A1 (cosine top-k), A3 (filtrage cuisine/contraintes) | ✅ Couverte |
| FR3 | LLM rédige sous contraintes, rien d'inventé | D1 (prompt contraint), D2 (garde-fou anti-hallucination) | ✅ Couverte |
| FR4 | Mapping contraintes matérielles → `#cookware` interdits | B4 (mapping), B3 (techniques excluant ustensile interdit) | ✅ Couverte |
| FR5 | Moteur de scaling (types) + `=` + notes `--` | C1, C2, C3, C4 (types/discret/géométrie/flags), D3 (émission `=`/`--`) | ✅ Couverte (cœur) |
| FR6 | Fichier `.cook` valide + rendu Markdown | D3 (.cook valide), D4 (rendu Markdown) | ✅ Couverte |
| FR7 | Panneau debug (scaling par ingrédient + voisins) | E2 (panneau dans l'UI), A3 (voisins retenus/rejetés), C5/E3 (raisonnement) | ✅ Couverte |
| FR8 | Choisir modèle Epicure `cooc`/`core` + comparaison | A2 (benchmark + décision), E3 (validation) | ⚠️ Partielle — voir note |

**Notes de traçabilité**

- **FR8 partielle** : A2 produit un *benchmark* et une *note de décision* (choix figé), mais FR8
  demande de *« choisir le modèle … et exposer la comparaison »* (capacité runtime / UI). Aucune
  story ne livre explicitement un sélecteur `cooc`/`core` exposé à l'utilisateur. À clarifier :
  FR8 est-elle une capacité produit (sélecteur) ou un livrable de R&D (note) ? Le libellé du PRD
  (« exposer la comparaison ») suggère la première, le backlog ne livre que la seconde.
- **Aucune FR orpheline** : les 8 FR sont toutes adressées.
- **Stories sans FR miroir** (légitimes mais à noter) : S0.1–S0.6 (socle/vérifications),
  A2 (benchmark — relié à un objectif §2 et à un critère §8, pas à une FR), C5 (tests/calibration
  — relié à NFR déterminisme), E4 (README/attribution — relié à NFR licence), E3 (jeu de
  validation — relié au critère §8), F1–F3 (extension/différé — reliés aux non-objectifs et au
  phasage). Ces « objectifs sans FR » suggèrent que certains résultats attendus du PRD (benchmark,
  validation chiffrée du scaling) gagneraient à devenir des exigences explicites plutôt que de
  vivre uniquement dans les critères de succès.

## 4. Analyse détaillée des exigences fonctionnelles (atomicité / non-ambiguïté / testabilité)

| FR | Atomique | Non ambiguë | Testable | Verdict |
|----|----------|-------------|----------|---------|
| FR1 | ✅ | ✅ | ✅ | OK |
| FR2 | ⚠️ (« N » non défini) | ⚠️ | ⚠️ | À préciser |
| FR3 | ✅ | ❌ (« cohérente ») | ⚠️ | À reformuler |
| FR4 | ✅ | ✅ | ✅ | OK |
| FR5 | ❌ (5 comportements + émission) | ⚠️ | ⚠️ | À scinder |
| FR6 | ❌ (2 livrables) | ❌ (« lisible ») | ⚠️ | À scinder/préciser |
| FR7 | ⚠️ | ❌ (« raisonnement ») | ⚠️ | À préciser |
| FR8 | ✅ | ⚠️ (capacité vs R&D) | ⚠️ | À clarifier |

**Reformulations proposées**

- **FR2** — *Préciser le paramètre.* « Proposer **k** associations compatibles (k paramétrable,
  défaut = 8) via Epicure (similarité cosinus), filtrées par cuisine et contraintes ; **chaque
  association rejetée est tracée avec son motif**. » → rend testable (k contrôlable, log des rejets).
- **FR3** — *Remplacer « cohérente » par un critère vérifiable.* « Le LLM rédige une recette
  **dont 100 % des ingrédients clés figurent parmi les associations validées par Epicure** et
  **dont 100 % des températures/temps/techniques proviennent de la base** ; toute valeur hors base
  fait échouer la génération. » → directement testable (assertion sur les valeurs émises).
- **FR5** — *Scinder en exigences atomiques* : FR5a « appliquer le type de scaling déclaré par
  ingrédient (linéaire / sous-linéaire / discret / géométrique / figé) selon
  `table-scaling-sale.json` » ; FR5b « émettre les verrous `=` pour les ingrédients figés/non
  linéaires » ; FR5c « émettre une note `--` lisible par le moteur pour chaque ingrédient
  non-linéaire ou changement de contenant suggéré ». Chacune devient testable isolément (et mappe
  déjà C1–C4 / D3).
- **FR6** — *Scinder + définir « lisible ».* FR6a « produire un fichier `.cook` **qui passe la
  validation syntaxique Cooklang** (marqueurs `@`/`#`/`~`, `=`, `--`) » ; FR6b « produire un rendu
  Markdown **contenant titre, portions, liste d'ingrédients et étapes numérotées** ». → critères
  objectifs.
- **FR7** — *Définir le contenu minimal du panneau.* « Le panneau debug affiche, **par
  ingrédient** : le type de scaling appliqué, le facteur calculé et la note associée ; et **la
  liste des voisins Epicure retenus et rejetés avec leur score**. » → testable par présence de
  champs.
- **FR8** — *Trancher la nature.* Soit FR8 (Could) = « exposer un sélecteur `cooc`/`core` dans
  l'UI qui régénère les associations », soit la requalifier en objectif de R&D (et la sortir des
  FR pour la laisser comme story A2/critère §8). En l'état elle promet une capacité non livrée.

## 5. Exigences non-fonctionnelles — mesurabilité

| NFR | Mesurable en l'état ? | Correction recommandée |
|-----|------------------------|------------------------|
| Sécurité alimentaire | ✅ (zéro = binaire, test dédié) | RAS — déjà la meilleure NFR du document. |
| Déterminisme | ⚠️ | Rendre l'assertion explicite : « pour une même entrée, le module scaling produit une sortie **bit-à-bit identique** sur N exécutions (test auto) ». |
| Simplicité | ❌ | Chiffrer : « ≤ X dépendances runtime », « démarrage via **une seule commande documentée** », « pas de service externe hors API LLM ». |
| Coût | ✅ | Chiffré (0,005–0,01 $/recette). RAS, sinon préciser le modèle/tarif de référence. |
| Licence | ⚠️ | Transformer en critère vérifiable : « fichier `LICENSE`/`NOTICE` mentionnant Epicure CC BY 4.0 présent à la racine » (déjà couvert par E4). |
| **Performance (manquant)** | ❌ | Ajouter : latence cible de bout en bout (ex. « génération < N s hors latence LLM »). |
| **Robustesse (manquant)** | ❌ | Ajouter : comportement attendu si l'API LLM échoue (message d'erreur, pas de recette partielle), si le héros est absent d'Epicure, si aucune association ne survit au filtrage. |

**Micro-écarts de cohérence détectés (mineurs)**

- Le PRD §7 parle d'embeddings « format à confirmer `[À VÉRIFIER]` », alors que le backlog S0.1
  indique le format déjà inspecté (matrice (1790, 300) float32, fait le 2026-06-01). Le PRD est en
  léger retard sur le backlog → mettre à jour §7.
- Le pitch décrit 3 modèles (`cooc`, `chem`, `core`) ; le PRD ne mentionne que `cooc`/`core`
  (FR8) — cohérent avec le périmètre v1, mais préciser que `chem` est volontairement hors scope.

## 6. Corrections recommandées (priorisées)

### P0 — à corriger avant de figer les critères d'acceptation du cœur
1. **Rendre FR3 testable** : remplacer « cohérente » par l'assertion « 100 % des
   températures/temps/techniques proviennent de la base, sinon échec de génération » (aligne
   FR3 ↔ D2 et le critère de succès « zéro valeur hors base »).
2. **Scinder FR5 et FR6** en sous-exigences atomiques (FR5a/b/c, FR6a/b) avec critères objectifs
   (« passe la validation Cooklang », contenu Markdown minimal défini). Ce sont les exigences du
   cœur de valeur : leur testabilité conditionne la DoD.
3. **Chiffrer les NFR** Déterminisme, Simplicité, Licence et **ajouter** Performance + Robustesse
   (échec API LLM, héros absent, zéro association). Aujourd'hui non vérifiables.

### P1 — à corriger avant/pendant l'implémentation
4. **Définir le protocole de validation du scaling** dans le PRD (ou y référencer précisément la
   section de `recherche-ouverte.md`) : combien de recettes, quel barème « plus juste qu'un ×N »,
   combien de tests cuisine réels, qui juge. Sinon le critère de succès n°1 reste subjectif.
5. **Trancher FR8** (capacité UI vs livrable R&D) et aligner la story (ajouter une story
   « sélecteur de modèle » si capacité, sinon requalifier).
6. **Spécifier le contrat d'API** : schéma de la requête `POST /generate` (champs, types, valeurs
   par défaut : k voisins, N associations) et de la réponse (`.cook`, markdown, payload debug).
   Prérequis pour E1/E2.
7. **Compléter les risques** : qualité/couverture linguistique des embeddings Epicure (héros
   francophone), dépendance API LLM, biais de confirmation de la validation manuelle, et lier
   explicitement les risques aux `[À VÉRIFIER]` ouverts (S0.3, S0.5).

### P2 — polish / robustesse documentaire
8. **Synchroniser PRD §7** avec le résultat de S0.1 (format embeddings déjà connu) ; mentionner
   que `chem` est hors scope v1.
9. **Documenter au moins un parcours alternatif** (erreur/edge case) dans le §3 pour cadrer le
   comportement attendu en cas d'entrée invalide.
10. **Promouvoir certains objectifs en FR** (benchmark `cooc/core`, validation chiffrée du
    scaling) ou les déclarer explicitement « objectifs sans FR dédiée » pour clarifier la frontière
    exigence / critère de succès.

## 7. Conclusion

PRD solide et honnête, exemplaire sur le positionnement et le périmètre, avec une traçabilité
FR → backlog quasi parfaite. Il est **prêt à amorcer l'implémentation du socle (Phase 0)**, mais
**pas encore à figer les critères d'acceptation du cœur (Épic C/D)** tant que les FR du scaling et
de la génération ne sont pas atomisées/testables et que les NFR ne sont pas chiffrées. Les
corrections P0 sont peu coûteuses (réécriture d'exigences) et débloquent une DoD vérifiable.
