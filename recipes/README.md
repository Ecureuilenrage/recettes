# Corpus de recettes italiennes salées (`recipes/`)

Corpus de référence **Phase 0** (story **S0.6**) : **13 recettes** italiennes **salées**
au format [Cooklang](https://cooklang.org/docs/spec/) (`.cook`). Pâtisserie **hors périmètre**.

Ce corpus est une **donnée d'entrée**, pas du code. Il alimente :

- **C5 / F2 — notebook de calibration** (`notebooks/calibration_scaling.ipynb`) : comparaison
  du **moteur de scaling** au **×N naïf** sur des recettes réelles (×2 / ÷2). Voir la cellule de
  clôture du notebook C5 (« comparaison sur corpus réel après S0.6 »).
- **E3 — jeu de validation scaling** : corpus + comparaison des sorties scalées.

> Réf. : `docs/recherche-ouverte.md` §C (calibration : corpus 10-15, ×2/÷2),
> `docs/architecture.md` §10 (`recipes/` corpus italien), `docs/stories/S0.6.md`.

## Catalogue

| # | Fichier | Titre | Technique principale | Portions | Ingrédients-héros | Scaling notable |
|---|---------|-------|----------------------|----------|-------------------|-----------------|
| 01 | `01-spaghetti-aglio-e-olio.cook` | Spaghetti aglio e olio | `pasta_al_dente` | 4 | ail, huile d'olive, piment | sel, ail, **piment**, temps |
| 02 | `02-spaghetti-al-pomodoro.cook` | Spaghetti al pomodoro | `sugo_pomodoro` + `pasta_al_dente` | 4 | tomate, ail, basilic | sel, ail, **herbe**, temps |
| 03 | `03-cacio-e-pepe.cook` | Cacio e pepe | `pasta_al_dente` | 2 | pecorino, poivre noir | sel, **poivre**, temps |
| 04 | `04-spaghetti-alla-carbonara.cook` | Spaghetti alla carbonara | `pasta_al_dente` | 4 | guanciale, œufs, pecorino | **œufs (discret)**, poivre, temps |
| 05 | `05-pasta-al-pesto-genovese.cook` | Pasta al pesto genovese | `pasta_al_dente` | 4 | basilic, pignons, parmesan | sel, ail, **herbe (basilic)**, temps |
| 06 | `06-penne-all-arrabbiata.cook` | Penne all'arrabbiata | `sugo_pomodoro` + `pasta_al_dente` | 4 | tomate, **piment**, ail | sel, ail, **piment (non linéaire)**, temps |
| 07 | `07-risotto-alla-milanese.cook` | Risotto alla milanese | `risotto` | 4 | riz arborio, safran, parmesan | sel (réserve 10 %), temps |
| 08 | `08-risotto-ai-funghi.cook` | Risotto ai funghi | `risotto` | 4 | riz carnaroli, champignons, thym | sel, ail, **herbe (thym)**, temps |
| 09 | `09-soffritto-base.cook` | Soffritto (base aromatique) | `soffritto` | 6 | oignon, carotte, céleri | sel, ail, temps |
| 10 | `10-sugo-di-pomodoro.cook` | Sugo di pomodoro | `sugo_pomodoro` | 6 | tomate San Marzano, ail, basilic | sel (réserve 10 %), ail, **herbe**, temps long |
| 11 | `11-minestrone.cook` | Minestrone | `soffritto` + mijotage | 6 | légumes, haricots, romarin | sel, ail, **herbe**, poivre, temps |
| 12 | `12-osso-buco-alla-milanese.cook` | Osso buco alla milanese | `searing_braising` + `soffritto` | 4 | **jarret de veau**, vin, gremolata | **protéine 63 °C + repos 3 min**, four `=163 °C`, temps long |
| 13 | `13-pollo-alla-cacciatora.cook` | Pollo alla cacciatora | `searing_braising` + `soffritto` | 4 | **poulet**, tomate, olives | **protéine 74 °C**, piment, sel, temps |

### Couverture des 5 techniques signature (`docs/base-technique/cuisine-italienne.json`)

| Technique | Recettes |
|---|---|
| `pasta_al_dente` | 01, 02, 03, 04, 05, 06 |
| `risotto` | 07, 08 |
| `soffritto` | 09, 11, 12, 13 |
| `sugo_pomodoro` | 02, 06, 10 |
| `searing_braising` | 12, 13 |

Les **5 techniques** sont couvertes. Plusieurs recettes en combinent deux (ex. osso buco =
`searing_braising` + `soffritto`), ce qui reflète la réalité culinaire.

### Couverture des types de scaling (`docs/scaling/table-scaling-sale.json`)

- **sublinear** : `sel` (toutes), `poivre` (03, 04, 11), `piment` / non linéaire (01, 06, 13),
  `ail` (la plupart), herbes `basilic` / `thym` / `romarin` (02, 05, 08, 10, 11, 13),
  acide `zeste de citron` (12).
- **discrete (œufs)** : `04-carbonara` (`@oeufs{3%}`).
- **geometric (temps)** : tous les `~{…%minutes}` (de `~{1%minute}` à `~{135%minutes}` en braise).
- **fixed (verrou `=`)** : températures de cuisson figées — eau `=100 °C`, four `=163 °C`,
  saisie `=240 °C`, sécurité protéines `=71 °C` (œuf), etc.

## Cohérence sécurité (protéines)

Les recettes contenant une protéine citent une température **issue de**
`docs/base-technique/safety-temperatures.json` (aucune valeur inventée) :

| Recette | Protéine | Température sécurité citée | Repos | Source (`safety-temperatures.json`) |
|---|---|---|---|---|
| 12 — osso buco | jarret de veau (pièce entière) | **63 °C** à cœur | **3 min** (ici 15 min) | « Bœuf/veau/agneau/porc — pièces entières », `critical` |
| 13 — pollo cacciatora | poulet (parts) | **74 °C** à cœur | 0 | « Volaille (entière, parts, hachée) », `critical` |
| 04 — carbonara | préparation à base d'œuf | **71 °C** (rappel, liaison hors feu) | 0 | « Œufs et préparations à base d'œuf » |

Les consignes sont **étiquetées** `[SÉCURITÉ]` / `[TECHNIQUE]` / `[PRÉFÉRENCE]` (cohérent avec
`cuisine-italienne.json#llmConstraints`), et les valeurs figées portent le **verrou `=`** Cooklang.

## Provenance

- **Méthode retenue** : recettes **rédigées à la main en Cooklang par templating** (saisie manuelle
  contrôlée), avec marqueurs `@`/`#`/`~`, verrous `=` et notes `--`. Conforme à la **décision #3**
  (`docs/decisions-techniques.md` : *templating maison + validation*, pas de binding Rust).
- **Alternative différée — `cook.md/<url>`** : l'astuce d'import Cooklang (préfixer une URL de
  recette par `cook.md/`) est **documentée mais non testée de première main** (qualité variable,
  dépend d'URLs réelles). Conformément à la **décision #5** (`docs/decisions-techniques.md`,
  *EN ATTENTE ⏳*) et à `docs/recherche-ouverte.md` A.5, elle est **reportée** ; le **fallback de
  saisie manuelle** est le chemin par défaut de ce corpus. À ré-évaluer si un import de masse
  devient nécessaire.

## Contrôle de bonne formation

Script stdlib (aucune dépendance) : `recipes/_check_cook.py`. Vérifie pour chaque `.cook` le
frontmatter `servings`, la présence d'au moins un marqueur `@…{…%…}` et l'équilibre des `{}`.

```
python recipes/_check_cook.py
```

Dernier passage (2026-06-01) : **13 recettes, 13 bien formées, 0 erreur**.

## Notes

- `recipes/.gitkeep` a été **retiré** : devenu superflu dès que le dossier contient des fichiers
  versionnés.
- Coefficients de scaling = **valeurs de départ à calibrer** (cf. `meta.disclaimer` de
  `table-scaling-sale.json`). Les quantités/temps de ce corpus sont **réalistes** mais servent de
  base de comparaison, pas de vérité absolue.
- Cuisine couverte : `italian_savory_v1` (module pilote). Ajouter une cuisine = déposer un nouveau
  `cuisine-*.json` (loader générique, archi §4.2) — sans toucher à ce corpus.
