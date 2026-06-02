# Revue de code adversariale — Story E4

- **Story** : E4 — README portfolio + attribution Epicure (CC BY 4.0) (Épic E, sprint 5) — **DOCUMENTAIRE**
- **Statut entrant** : `review`
- **Date** : 2026-06-02
- **Reviewer** : agent BMAD `bmad-code-review` (rôle « code-review », INDÉPENDANT du dev — angles : exactitude documentaire / complétude AC / conformité licence + triage)
- **Mode** : non-interactif, lecture seule (seul fichier écrit : la présente revue ; **aucun contenu n'est corrigé**)
- **Périmètre revu (ajouts E4 uniquement)** :
  - `README.md` — mis à jour en README portfolio (pitch, archi 4 couches, comment lancer, exemple `.cook` + panneau debug, périmètre v1, doc, crédits & licence).
  - `NOTICE` — NOUVEAU à la racine (attribution Epicure CC BY 4.0 + Cooklang).
  - `docs/stories/E4.md` — AC + Tasks + Dev Agent Record audités.
- **Hors périmètre (non revu — stories parallèles / orchestrateur)** : `app/main.py`, `app/scaling/__init__.py`, `notebooks/calibration_scaling.ipynb`, `tests/test_main.py`, `tests/test_scaling_validation.py`, `docs/stories/E1.md`, `docs/stories/E3.md` (modifs E1/E3, **PAS** E4 — voir §5). E4 est documentaire : aucun code, aucun test, aucun `pytest`.

---

## Verdict

**APPROUVÉE — 0 bloquant / 0 majeur / 2 mineurs (defer).**

L'attribution **Epicure CC BY 4.0** est **présente ET correcte dans le README ET dans `NOTICE`** (© 2026 Jakub Radzikowski & Josef Chen / KAIKAKU.AI, lien licence, HF `Kaikaku/epicure-cooc`, arXiv 2605.22391, « attribution requise », « corpus non redistribué — vecteurs publics seulement ») — critère DoD central (R10 / archi §13 / PRD §5) **satisfait**. Le fichier `NOTICE` existe à la racine et mentionne explicitement « Epicure — CC BY 4.0 ». Le README portfolio est complet (pitch, archi 4 couches + règle `main → {1,2,3,4}`, comment lancer, exemple `.cook` + panneau debug illustratif = vitrine §9.2, périmètre v1, crédits) et **techniquement exact** : corps JSON `POST /generate`, codes 200/422/502, 4 sections `DebugInfo`, marqueurs Cooklang vérifiés contre `app/main.py`, `docs/architecture.md` §3.1/§7/§9.1/§9.2 et le recipe réel. Périmètre documentaire respecté : E4 ne touche QUE `README.md` + `NOTICE` + `docs/stories/E4.md`. UTF-8 sans BOM, LF pour les 3 fichiers.

---

## Vérifications empiriques

| Contrôle | Commande / méthode | Résultat |
|---|---|---|
| Encodage / fins de ligne (3 fichiers) | lecture binaire (`head -c 3` + comptage `\r`) | `README.md` = `23 20 72` (`# r`, **pas de BOM**), `NOTICE` = `72 65 63` (`rec`, **pas de BOM**), `E4.md` = `23 20 53` ; **0 CRLF** → UTF-8 **sans BOM**, **LF** ✓ |
| Périmètre documentaire E4 | `git status` + `git diff --stat HEAD` | E4 = `README.md` (M) + `NOTICE` (untracked) + `docs/stories/E4.md` (untracked). Les autres modifs (`app/main.py`, `app/scaling`, `notebooks`, `tests/*`, `E1.md`, `E3.md`) proviennent de E1/E3/orchestrateur — **pas comptées contre E4** ✓ |
| Champs requête `POST /generate` | recoupement README ↔ `app/main.py:110-117` (`GenerationRequest`) | `hero/cuisine/constraints{diet,no_cookware,highlight}/servings/model` — **identiques** ✓ |
| Champs réponse | README ↔ `app/main.py:127-132` (`GenerationResponse`) | `{cooklang, markdown, debug}` ✓ |
| 4 sections `DebugInfo` | README ↔ `app/main.py:119-124` + archi §9.1 | `epicure / scaling / techniques / validation` — **les 4** ✓ |
| Codes HTTP | README ↔ `app/main.py:511-514` + archi §9.1/§9.2 | `200` / `422` / `502` (et `500` interne non exposé au README — acceptable) ✓ |
| `GET /health` | README ↔ `app/main.py:493` | `{"status": "ok", "stage": "pipeline"}` — **exact** ✓ |
| Règle inter-couches | README ↔ archi §3.1 (l.165-167) | `main → {1,2,3,4}` ; « couches ne s'importent pas entre elles » ✓ |
| Flux rédaction AVANT scaling | README ↔ archi §7 + `app/main.py:360` (« scaling APRÈS rédaction ») | concordant ✓ |
| Marqueur verrou `=` ingrédient (`@sel{=1%c.à.c}`) | README ↔ `app/generator/cooklang.py:201-209` | format **réellement émis** par `_emit_ingredient` — exact ✓ |
| Marqueurs `.cook` (frontmatter, `@`/`#`/`~`, `--`) | README ↔ `recipes/02-spaghetti-al-pomodoro.cook` | concordants ✓ |
| Attribution (README + NOTICE) | lecture des 2 fichiers | © 2026 Radzikowski & Chen (KAIKAKU.AI), CC BY 4.0, HF `Kaikaku/epicure-cooc`, arXiv 2605.22391, corpus non redistribué ✓ |
| pytest | — | **non lancé** (E4 ne crée aucun test) — conforme ✓ |

---

## 1. Attribution Epicure CC BY 4.0 (CRITÈRE DoD CENTRAL — R10 / archi §13 / PRD §5)

**Présente ET correcte dans le README ET dans `NOTICE`.**

**README** (« Crédits & licence », l.179-190) :
- « **Epicure** — embeddings d'ingrédients, **© 2026 Jakub Radzikowski & Josef Chen (KAIKAKU.AI)** » ✓ (noms et entité exacts, conformes à `data/epicure/epicure-cooc/LICENSE` cité dans la story)
- « licence **Creative Commons Attribution 4.0 (CC BY 4.0)** » + lien `https://creativecommons.org/licenses/by/4.0/` ✓
- « ([arXiv 2605.22391](https://arxiv.org/abs/2605.22391)) » ✓ (concorde avec archi §8.1 l.491 `arxiv: 2605.22391`)
- « **Attribution requise.** » ✓
- « ne redistribue **pas** le corpus … seulement les **vecteurs publics** (`Kaikaku/epicure-cooc`) » ✓
- renvoi explicite « Détail complet dans le fichier [`NOTICE`](./NOTICE). » ✓
- note finale (l.189-190) rappelant le critère PRD §5 / R10 / archi §13 ✓

**NOTICE** (l.9-31) : section dédiée « Embeddings Epicure (CC BY 4.0) » avec © 2026 Jakub Radzikowski & Josef Chen (KAIKAKU.AI), licence CC BY 4.0 + lien, source HF `Kaikaku/epicure-cooc`, citation arXiv exacte (« Epicure: Navigating the Emergent Geometry of Food Ingredient Embeddings. » arXiv:2605.22391), usage (vecteurs publics uniquement, matrice `(1790, 300)` float32, poids non modifiés, corpus ~4,14 M non publié → ni utilisé ni redistribué, vecteurs téléchargés à la demande). **Correct et complet.** ✓

Aucune affirmation fausse ou trompeuse. **Critère DoD satisfait.**

## 2. Fichier `NOTICE` à la racine (critère PRD §5)

- `NOTICE` **existe à la racine** (vérifié `git status` : untracked à la racine, pas dans `docs/`). ✓
- Mentionne explicitement « **Epicure — CC BY 4.0** » (titre de section + en-tête l.1-6 : « l'exigence d'attribution de la licence Creative Commons Attribution 4.0 (CC BY 4.0) des embeddings Epicure »). Satisfait le critère PRD §5 l.104-105 (« fichier `LICENSE`/`NOTICE` mentionnant « Epicure — CC BY 4.0 » présent à la racine »). ✓
- Bien formé (texte plat lisible, 3 sections : Epicure / Cooklang / Code du projet). Décision documentée de créer `NOTICE` plutôt que `LICENSE` (le critère PRD admet l'un OU l'autre ; `LICENSE` couvrirait le code, hors périmètre) — cohérente. ✓

## 3. Complétude README portfolio (AC1–AC4)

| Élément AC | Présent ? | Localisation |
|---|---|---|
| **Pitch** (scaler honnête, scaling déterministe non-linéaire, grounding sécurité, LLM = rédacteur sous contraintes) | ✓ | l.8-16 |
| **Architecture 4 couches** (Associations / Base technique / Scaling = pièce maîtresse / Générateur LLM) | ✓ | l.18-40 |
| **Règle de dépendances** `main → {1,2,3,4}` + couches non couplées (testabilité) | ✓ | l.20-23 |
| **Ordre du flux** (rédaction 4 AVANT scaling 3) | ✓ | l.38-40 |
| **Comment lancer en local** (`pip install`, embeddings via `huggingface_hub`/`Kaikaku/epicure-cooc` dans `data/epicure/`, `ANTHROPIC_API_KEY` + variante PowerShell, `uvicorn app.main:app --reload`) | ✓ | l.42-57 |
| **Exemple corps JSON `POST /generate`** + `GET /health` + codes 200/422/502 | ✓ | l.59-76 |
| **Tests offline** (`python -m pytest -q`, couture `complete`/`index` de `run_pipeline`) + **note honnête** (fastapi / données Epicure / clé requises pour l'app web réelle) | ✓ | l.78-94 |
| **Exemple `.cook` + panneau debug** (4 sections `DebugInfo`), marqué illustratif (vitrine §9.2) | ✓ | l.96-155 |
| **Périmètre v1** (in/out) | ✓ | l.157-163 |
| **Table de documentation** (liens `docs/`, `pitch.md`, `NOTICE`) | ✓ | l.165-177 |
| **Crédits & licence** (Epicure CC BY 4.0 + renvoi `NOTICE`, Cooklang) | ✓ | l.179-190 |

Tous les AC1–AC5 couverts. README portfolio **complet**.

## 4. Exactitude technique

- **Corps JSON `POST /generate`** (README l.64-72) : champs `hero/cuisine/constraints{diet,no_cookware,highlight}/servings/model` — **identiques** au schéma réel `GenerationRequest` (`app/main.py:110-117`) et à archi §9.1 (l.556-562). Valeurs exemple cohérentes (`cuisine: "italian_savory_v1"`, `model: "cooc"` = défauts réels `app/main.py:95-96`). ✓
- **Réponse** `{cooklang, markdown, debug}` (l.74) — conforme `GenerationResponse` (`app/main.py:127-132`). ✓
- **Codes** `200/422/502` (l.75-76) — concordent avec le mapping réel (`app/main.py:511-514`) et archi §9.1. (`500` interne non listé : acceptable pour un README ; `422`/`502` sont les codes métier documentés.) ✓
- **`GET /health`** (l.61) : `{"status": "ok", "stage": "pipeline"}` — **strictement exact** vs `app/main.py:493`. ✓
- **`.cook` d'exemple** (l.104-115) : frontmatter `servings: 4` ✓ ; marqueurs `@ingrédient{quantité%unité}`, `#ustensile`, `~{durée}` ✓ ; verrou `=` (`=85%°C visé`, `@sel{=1%c.à.c}`) — le verrou-ingrédient `@sel{=1%c.à.c}` correspond **exactement** au format émis par `_emit_ingredient` (`app/generator/cooklang.py:201-209`, docstring montrant `@sel{=1%c.à.c}`) ✓ ; notes `--` + étiquettes `[TECHNIQUE]` ✓. Exemple dérivé du réel `recipes/02-spaghetti-al-pomodoro.cook`. Bien formé.
- **Panneau debug** (l.125-149) : les **4 sections** `epicure / scaling / techniques / validation` reflètent `DebugInfo` (`app/main.py:119-124` + §9.1). Le contenu de `scaling` (`name/type/coeff/formula/reasoning/value`) reproduit exactement la structure construite dans `run_pipeline` (`app/main.py:375-401`) ; `techniques` (`kept`/`excluded` avec `technique_id/forbidden_tool/via_constraint`) concorde (`app/main.py:419-429`) ; `validation` (`ok/violations/feedback`) concorde (`app/main.py:433-444`). ✓
- **Marquage illustratif** : l'exemple recette + debug est **explicitement marqué « illustratif »** (l.98-100 : « Exemple **illustratif** … Les valeurs réelles proviennent à l'exécution des couches 1–4 »). ✓
- **Honnêteté** : la note (l.90-94) indique clairement que sans données Epicure locales **et** clé Anthropic « l'app web réelle ne génère pas », tout en précisant que la logique est testée offline. **Pas d'affirmation trompeuse** (ne prétend pas que l'app génère sans données/clé). ✓

Aucune affirmation fausse détectée.

## 5. Périmètre documentaire (anti-conflit)

`git status` + `git diff --stat HEAD` confirment que les fichiers attribuables à E4 sont **EXACTEMENT** : `README.md` (M), `NOTICE` (nouveau), `docs/stories/E4.md` (nouveau). Les autres entrées :
- `app/main.py`, `app/scaling/__init__.py`, `notebooks/calibration_scaling.ipynb`, `tests/test_main.py`, `tests/test_scaling_validation.py` → stories **E1** (assemblage pipeline) et **E3** (tests scaling/validation) ;
- `docs/stories/E1.md`, `docs/stories/E3.md` → stories parallèles.

Ces fichiers proviennent de E1/E3/orchestrateur et **ne sont pas comptés contre E4** (conformément aux consignes). **Aucun fichier de code/test n'est attribuable à E4.** Périmètre documentaire **strictement respecté**. ✓

## 6. Qualité (markdown, accents, encodage, liens)

- **UTF-8 sans BOM, LF** pour les 3 fichiers (vérifié en binaire — voir tableau). ✓
- **Accents français corrects** (lecture : « héros », « œufs », « réserve », « émise », « clé », « téléchargés », « rédacteur »… aucune mojibake). ✓
- **Markdown lisible** : titres `#`/`##`, listes, blocs de code annotés (`bash`, `json`, `jsonc`, `cook`), table de documentation bien formée. ✓
- **Liens internes** : pointent vers des cibles existantes — `docs/architecture.md`, `docs/PRD.md`, `pitch.md`, `docs/etude-marche.md`, `docs/backlog.md`, `docs/recherche-ouverte.md`, `docs/base-technique/`, `docs/scaling/`, `app/main.py`, `NOTICE` (tous présents au dépôt). ✓
- **Liens externes** : `creativecommons.org/licenses/by/4.0/`, `huggingface.co/Kaikaku/epicure-cooc`, `arxiv.org/abs/2605.22391`, `cooklang.org` — bien formés (non testés réseau, hors périmètre lecture seule). ✓

## Findings (par sévérité)

### Bloquants
Aucun. (Attribution CC BY 4.0 présente et correcte dans README **et** NOTICE ; `NOTICE` à la racine mentionnant « Epicure — CC BY 4.0 ».)

### Majeurs
Aucun. (Exactitude technique vérifiée champ par champ contre `app/main.py` et archi §9.1 ; périmètre documentaire respecté ; exemple marqué illustratif ; note honnête présente.)

### Mineurs / observations

1. **[defer] `docs/recherche-ouverte.md` listé dans la table de documentation — cible présente, mais à confirmer comme « doc portfolio ».**
   La table (l.174) référence `docs/recherche-ouverte.md` (points `[À VÉRIFIER]` + protocoles R&D). Le fichier existe (lien valide), mais ce document de R&D interne est un peu en marge d'une vitrine « portfolio livrable ». **Impact cosmétique** : aucun lien cassé, l'info reste véridique et utile. **Defer** (choix éditorial, aucun AC ne l'interdit).

2. **[defer] Code `500` non mentionné dans le README alors qu'il existe dans le mapping réel.**
   Le README documente `200/422/502` (conforme aux AC et aux codes métier). Le mapping réel ajoute un garde-fou `500` « erreur inattendue » (`app/main.py:515-518`). Archi §9.1 lui-même écrit « `502`/`500` ». **Impact nul** : `500` est un garde-fou générique, non un contrat métier ; son omission ne rend rien faux. **Defer** (mention facultative pour exhaustivité).

## Recommandation

**E4 peut passer en `done`.** Le critère DoD central — **attribution Epicure CC BY 4.0 présente et correcte dans le README ET dans `NOTICE`, fichier `NOTICE` à la racine mentionnant « Epicure — CC BY 4.0 »** (R10 / archi §13 / PRD §5) — est **pleinement satisfait**. Le README portfolio est complet (AC1–AC4), techniquement exact (corps JSON / réponse / codes / `health` / 4 sections `DebugInfo` / marqueurs `.cook` vérifiés contre le code réel et l'architecture), l'exemple est marqué illustratif et accompagné d'une note honnête sur les prérequis (données/clé). Le périmètre est strictement documentaire (`README.md` + `NOTICE` + `docs/stories/E4.md` ; aucun code/test attribuable à E4). UTF-8 sans BOM, LF, accents corrects, liens valides. Les 2 findings sont `defer` (choix éditorial sur la table de doc ; mention facultative du code `500`) et ne remettent en cause aucun AC.

---

**VERDICT : APPROUVÉE** — **0 bloquant / 0 majeur / 2 mineurs (defer)**.
**Attribution CC BY 4.0 : PRÉSENTE et CORRECTE dans `README.md` ET dans `NOTICE`** (© 2026 Jakub Radzikowski & Josef Chen / KAIKAKU.AI, CC BY 4.0 + lien, HF `Kaikaku/epicure-cooc`, arXiv 2605.22391, « attribution requise », « corpus non redistribué — vecteurs publics seulement »). Fichier `NOTICE` présent à la racine.
