# recettes — scaler de recettes « Epicure »

> **Statut : cadrage / playground (2026-06-01).** Projet perso & portfolio — pas une app payante.

Un **scaler de recettes honnête** : à partir d'un ingrédient « héros », d'une cuisine et de
contraintes, l'outil génère une recette salée en **Cooklang** (`.cook`) dont la **mise à l'échelle
est non-linéaire et crédible** (par ingrédient), et dont **aucune température ni technique n'est
inventée** (grounded sécurité alimentaire).

La valeur n'est pas « encore un générateur de recettes IA » (commoditisé) mais le **moteur de
scaling déterministe** + le **grounding sécurité**. Le LLM est réduit au rôle de rédacteur sous
contraintes.

## Les 4 couches

1. **Associations** — embeddings [Epicure](https://huggingface.co/Kaikaku/epicure-cooc) en local
   (cosine) pour proposer/valider les ingrédients compatibles.
2. **Base technique grounded** — températures de sécurité (USDA/ANSES) + techniques sourcées ; le
   LLM **choisit dedans**, n'improvise jamais.
3. **Moteur de scaling** — multiplicateur par ingrédient (sous-linéaire sel/épices, œufs discrets,
   temps géométrique, températures figées). **La pièce maîtresse.**
4. **Générateur LLM** — Claude API assemble une recette contrainte et écrit du `.cook`.

## Documentation

| Document | Contenu |
|---|---|
| [`pitch.md`](./pitch.md) | Intention d'origine |
| [`docs/PRD.md`](./docs/PRD.md) | Product Requirements Document |
| [`docs/etude-marche.md`](./docs/etude-marche.md) | État de l'art + verdict d'utilité |
| [`docs/backlog.md`](./docs/backlog.md) | Épics / stories / critères d'acceptation |
| [`docs/recherche-ouverte.md`](./docs/recherche-ouverte.md) | Points `[À VÉRIFIER]` + protocoles R&D |
| [`docs/base-technique/`](./docs/base-technique/) | Schéma + JSON sécurité + module cuisine italienne |
| [`docs/scaling/`](./docs/scaling/) | Table des multiplicateurs salés |

## Périmètre v1

- **In** : cuisine **italienne salée**, moteur de scaling, garde-fou sécurité, Epicure (`cooc`),
  sortie Cooklang, petite app web locale, benchmarks/calibration (ambition exploratoire).
- **Out** : pâtisserie (différée), multi-cuisines, comptes/paiement/cloud/mobile, nutrition.

## Démarrer (à venir — Phase 2+)

```bash
# Backend Python (FastAPI) + UI minimale locale
pip install -r requirements.txt
uvicorn app.main:app --reload
```

> Le code (`app/`) sera scaffolé puis implémenté selon le [backlog](./docs/backlog.md). La Phase 0
> (vérifications) précède tout codage de valeurs en dur.

## Crédits & licence

- **Epicure** — embeddings d'ingrédients, © 2026 Jakub Radzikowski & Josef Chen (KAIKAKU.AI),
  licence **CC BY 4.0** ([arXiv 2605.22391](https://arxiv.org/abs/2605.22391)). Attribution requise ;
  ce projet ne redistribue pas le corpus de recettes (non publié), seulement les vecteurs publics.
  Modèles téléchargés en local (`data/epicure/`, gitignored) — voir `app/epicure/loader.py`.
- Format **Cooklang** : https://cooklang.org
