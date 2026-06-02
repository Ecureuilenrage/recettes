# recettes — scaler de recettes « Epicure »

> **Statut : v1 livrable en local (2026-06-02).** Projet perso & portfolio — pas une app payante.
> Les 4 couches sont implémentées ; la logique (scaling, sécurité, émission) est **testée
> hors-ligne** (sans clé ni réseau). Avec les embeddings Epicure et une clé Anthropic, l'app web
> locale génère des recettes complètes.

Un **scaler de recettes honnête** : à partir d'un ingrédient « héros », d'une cuisine et de
contraintes, l'outil génère une recette salée en **Cooklang** (`.cook`) dont la **mise à l'échelle
est non-linéaire et crédible** (par ingrédient), et dont **aucune température ni technique n'est
inventée** (grounded sécurité alimentaire).

La valeur n'est pas « encore un générateur de recettes IA » (commoditisé) mais le **moteur de
scaling déterministe** + le **grounding sécurité**. Le LLM est réduit au rôle de **rédacteur sous
contraintes** : il choisit dans une base technique vérifiée, ne calcule pas les quantités, et sa
sortie passe par une **validation déterministe** avant émission.

## Les 4 couches

L'architecture est un **backend Python mono-process** à dépendances **strictement
unidirectionnelles** : seul l'orchestrateur (`app/main.py`) connaît les couches ; **les couches ne
s'importent jamais entre elles** (`main → {1, 2, 3, 4}`). Cette séparation rend chaque couche
**testable isolément** (cf. [`architecture.md`](./docs/architecture.md) §3.1).

1. **Associations** (`app/epicure/`) — embeddings
   [Epicure](https://huggingface.co/Kaikaku/epicure-cooc) en local (cosine) pour proposer/valider
   les ingrédients compatibles autour du héros, avec filtrage cuisine (souple) / régime (dur) et
   traduction FR→Epicure.
2. **Base technique grounded** (`app/knowledge/`) — températures de sécurité (USDA/ANSES) +
   techniques sourcées par cuisine ; le LLM **choisit dedans**, n'improvise jamais. Mapping
   contraintes matérielles → `#cookware` interdits.
3. **Moteur de scaling** (`app/scaling/`) — **la pièce maîtresse**, pure et déterministe :
   multiplicateur par ingrédient (sous-linéaire sel/épices, œufs discrets, temps géométrique
   `k^(2/3)`, températures figées), réserve 10 %, flags de non-linéarité.
4. **Générateur LLM** (`app/generator/`) — Claude API assemble une recette **contrainte** par
   1 + 2 + 3, sa sortie est **validée** (anti-hallucination), puis émise en `.cook` + Markdown.

> Ordre clé du flux (archi §7) : **rédaction (4) AVANT scaling (3)**. Le LLM produit une recette à
> une échelle de base ; le moteur déterministe la met ensuite à l'échelle cible. Cela isole le
> non-déterminisme du LLM du calcul des quantités.

## Comment lancer en local

```bash
# 1. Dépendances (FastAPI, uvicorn, numpy, safetensors, huggingface_hub, anthropic, pytest…)
pip install -r requirements.txt

# 2. Embeddings Epicure dans data/epicure/ (gitignoré) — téléchargés via huggingface_hub
python -c "from huggingface_hub import snapshot_download; \
  snapshot_download('Kaikaku/epicure-cooc', local_dir='data/epicure/epicure-cooc')"

# 3. Clé Anthropic (rédacteur LLM, couche 4)
export ANTHROPIC_API_KEY=sk-ant-...        # Windows PowerShell : $env:ANTHROPIC_API_KEY="sk-ant-..."

# 4. Lancer l'app web locale (UI + API)
uvicorn app.main:app --reload
```

**Endpoints** (archi §9) :

- `GET /health` — sonde de vivacité : `{"status": "ok", "stage": "pipeline"}`.
- `POST /generate` — génère une recette. Corps JSON :

  ```json
  {
    "hero": "basilic",
    "cuisine": "italian_savory_v1",
    "constraints": { "diet": [], "no_cookware": ["pas_de_four"], "highlight": "basilic" },
    "servings": 4,
    "model": "cooc"
  }
  ```

  Réponse `200` : `{ "cooklang": "...", "markdown": "...", "debug": { ... } }`.
  Codes d'erreur : `422` (héros hors vocabulaire Epicure, cuisine inconnue), `502` (échec LLM ou
  violation de sécurité persistante après retry).

### Tests : hors-ligne, sans clé ni réseau

```bash
python -m pytest -q
```

Le cœur testable est `run_pipeline(request, *, complete=None, index=None)` dans
[`app/main.py`](./app/main.py) : une fonction d'orchestration appelable **sans HTTP, sans appel LLM
réel et sans clé/fichier de données**, grâce aux **coutures injectables** `complete` (faux
rédacteur LLM déterministe) et `index` (faux index Epicure). Le moteur de scaling et le validateur
anti-hallucination sont 100 % déterministes → couverture prioritaire.

> **Notes honnêtes.** `fastapi`/`uvicorn` doivent être installés (déjà dans `requirements.txt`) pour
> l'app web ; sans eux, seuls les endpoints HTTP sont désactivés (`run_pipeline` reste appelable).
> Sans les **données Epicure locales** et une **clé Anthropic**, l'app web réelle ne génère pas —
> mais toute la logique métier (scaling, sécurité, émission `.cook`/Markdown) est **testée
> offline** via les coutures.

## Exemple de recette générée + panneau debug

> Exemple **illustratif** (cohérent avec la base italienne `italian_savory_v1`), pour montrer la
> sortie et la **vitrine d'explicabilité**. Les valeurs réelles proviennent à l'exécution des
> couches 1–4.

### Sortie `.cook` (extrait)

```cook
---
servings: 4
---
-- Techniques : sugo_pomodoro [TECHNIQUE] puis pasta_al_dente [TECHNIQUE].
Faire chauffer @huile d'olive{4%c.à.s} dans une #casserole à fond épais à feu doux (=85%°C visé).
Ajouter @ail{3%gousses} écrasé et le faire blondir ~{2%minutes} sans coloration -- [TECHNIQUE] feu doux, sinon amertume.
Verser @tomates pelées{800%g} et écraser à la #cuillère en bois.
Ajouter @sel{=1%c.à.c} et @basilic{6%feuilles} -- [TECHNIQUE] aromates volatils ; réserver ~10 % de sel pour la fin.
Mijoter à découvert ~{40%minutes} à très petit feu -- [TECHNIQUE] remuer toutes les 10-15 min.
Cuire @spaghetti{400%g} ~{9%minutes} -- al dente, goûter.
```

Marqueurs Cooklang : `@ingrédient{quantité%unité}`, `#ustensile`, `~{durée}`, frontmatter
`servings`, verrou `=` (valeur **figée**, ex. température), notes `--`. Le `.cook` est
téléchargeable et réutilisable dans Obsidian.

### Panneau debug — la vitrine d'explicabilité (archi §9.2)

Chaque génération renvoie un `DebugInfo` à 4 sections qui **montre le raisonnement** :

```jsonc
{
  "epicure": {                       // Couche 1 — associations
    "kept":    [["garlic", 0.88], ["tomato", 0.84], ["olive_oil", 0.82]],
    "rejected": [["sugar", 0.31, "hors cuisine italian_savory_v1"]]
  },
  "scaling": [                       // Couche 3 — par ingrédient : type/coeff/raisonnement
    { "name": "sel",        "type": "sublinear", "coeff": 0.75, "formula": "qty * k^0.75",
      "reasoning": "perception du goût non linéaire ; réserver ~10 % en fin de cuisson", "value": 1.68 },
    { "name": "spaghetti",  "type": "linear",    "coeff": 1.0,  "formula": "qty * k",
      "reasoning": "ingrédient principal (féculent)", "value": 800.0 },
    { "name": "oeufs",      "type": "discrete",  "coeff": null, "formula": "discrete (round down)",
      "reasoning": "unité non sécable ; pour 3 doublés, 5 plutôt que 6", "value": 5.0 }
  ],
  "techniques": {                    // Couche 2 — retenues / exclues (cookware interdit)
    "kept":     ["sugo_pomodoro", "pasta_al_dente"],
    "excluded": [{ "technique_id": "searing_braising", "forbidden_tool": "four",
                   "via_constraint": "pas_de_four" }]
  },
  "validation": {                    // Couche 4 — garde-fou anti-hallucination (déterministe)
    "ok": true,
    "violations": [],
    "feedback": null
  }
}
```

C'est l'**explicabilité** qui distingue le projet : on voit *pourquoi* tel voisin est retenu,
*pourquoi* le sel n'est pas multiplié linéairement, *pourquoi* une technique est exclue, et que la
recette **ne contient aucune température hors base** (sécurité garantie par validation, pas par le
prompt).

## Périmètre v1

- **In** : cuisine **italienne salée**, moteur de scaling non-linéaire, garde-fou sécurité
  (USDA/ANSES), associations Epicure (`cooc`), sortie **Cooklang** + Markdown, **app web locale**
  (FastAPI + UI), suite de tests déterministe hors-ligne.
- **Out** : pâtisserie (chimie → différée), multi-cuisines (extensible post-v1 sans toucher au
  code), comptes / paiement / cloud / mobile, nutrition.

## Documentation

| Document | Contenu |
|---|---|
| [`pitch.md`](./pitch.md) | Intention d'origine, décisions actées, format Cooklang |
| [`docs/PRD.md`](./docs/PRD.md) | Product Requirements Document |
| [`docs/architecture.md`](./docs/architecture.md) | Architecture 4 couches, flux, garde-fous, API |
| [`docs/etude-marche.md`](./docs/etude-marche.md) | État de l'art + verdict d'utilité |
| [`docs/backlog.md`](./docs/backlog.md) | Épics / stories / critères d'acceptation |
| [`docs/recherche-ouverte.md`](./docs/recherche-ouverte.md) | Points `[À VÉRIFIER]` + protocoles R&D |
| [`docs/base-technique/`](./docs/base-technique/) | Schéma + JSON sécurité + module cuisine italienne |
| [`docs/scaling/`](./docs/scaling/) | Table des multiplicateurs salés |
| [`NOTICE`](./NOTICE) | Attribution Epicure (CC BY 4.0) + format Cooklang |

## Crédits & licence

- **Epicure** — embeddings d'ingrédients, **© 2026 Jakub Radzikowski & Josef Chen (KAIKAKU.AI)**,
  licence **Creative Commons Attribution 4.0 (CC BY 4.0)** —
  https://creativecommons.org/licenses/by/4.0/ ([arXiv 2605.22391](https://arxiv.org/abs/2605.22391)).
  **Attribution requise.** Ce projet ne redistribue **pas** le corpus de recettes (non publié par
  les auteurs), seulement les **vecteurs publics** (`Kaikaku/epicure-cooc`), téléchargés en local
  (`data/epicure/`, gitignoré). Détail complet dans le fichier [`NOTICE`](./NOTICE).
- Format **Cooklang** : https://cooklang.org (format de sortie `.cook`).

> L'attribution Epicure CC BY 4.0 est requise (exigence R10 / archi §13, critère PRD §5 « Licence » :
> fichier `LICENSE`/`NOTICE` mentionnant « Epicure — CC BY 4.0 » à la racine). Voir [`NOTICE`](./NOTICE).
