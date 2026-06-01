---
titre: Validation Obsidian d'un .cook minimal (S0.4)
type: validation
statut: review
créé: 2026-06-01
tags: [cooklang, obsidian, validation, smoke-test, S0.4]
---

# Validation Obsidian d'un `.cook` minimal — Story S0.4

> But : prouver de bout en bout que le format `.cook` produit par le **templating maison**
> (décision tranchée S0.3, cf. [`decisions-techniques.md`](../decisions-techniques.md) #3) est
> **bien formé** et **compatible** avec le plugin Obsidian `cooklang/cooklang-obsidian`.
>
> Ce rapport distingue explicitement **ce qui est vérifié programmatiquement** (auto-vérification
> structurelle déterministe, ci-dessous §b) de **l'étape manuelle finale** (ouverture réelle dans
> Obsidian + capture d'écran, §e) qui requiert un humain lançant l'application.

---

## (a) Le `.cook` de référence (commenté)

Fichier : [`smoke-test.cook`](./smoke-test.cook) — mini-recette italienne salée (*bruschetta al
pomodoro*), 4 portions, UTF-8 sans BOM. Elle est volontairement **minimale mais complète** : elle
exerce **tous** les marqueurs Cooklang retenus par le projet (architecture §8.4).

| Marqueur projet | Syntaxe | Occurrence dans le smoke-test |
|---|---|---|
| **Frontmatter `servings`** | bloc YAML `--- … ---` | `servings: 4` (+ `title`, `cuisine`) |
| **Ingrédient `@…{qty%unit}`** | `@nom{quantité%unité}` | `@tomates mûres{300%g}`, `@huile d'olive{2%c.à.s}`, `@sel{1%c.à.c}`, `@pain de campagne{4%tranches}`, `@ail{1%gousse}`, `@basilic frais{6%feuilles}`, `@ail{0.5%gousse}` |
| **Ustensile `#…`** | `#nom{}` | `#plaque de cuisson{}`, `#saladier{}`, `#poêle{}` |
| **Minuteur `~{durée}`** | `~{valeur%unité}` | `~{8%minutes}`, `~{1%minute}` |
| **Verrou `=` (valeur figée)** | `{=valeur%unité}` | `@four{=180%°C}` — température figée, jamais multipliée au scaling |
| **Note `--`** | `-- texte` | 5 notes, dont étiquettes `[SÉCURITÉ]` / `[TECHNIQUE]` (cf. `llmConstraints` couche 2) |

Choix de conception (décisions par défaut, mode non-interactif) :

- **Recette** : *bruschetta al pomodoro* plutôt que *pasta aglio e olio* — la bruschetta justifie
  **naturellement** une température de four figée (`=180%°C`), donnant un cas `=` réaliste sans
  artifice. Cuisine `italian_savory_v1`, cohérente avec `cuisine-italienne.json`.
- **Verrou `=` sur la température** : conforme à l'architecture (§5.2 type `fixed` → verrou `=`) et à
  la table de scaling (`categories[temperature].type = fixed`). C'est le marqueur que le **moteur de
  scaling** (couche 3, déjà livré C1-C5) posera en production ; on l'ancre ici dès le smoke-test.
- **Notes `--`** étiquetées `[SÉCURITÉ]`/`[TECHNIQUE]` : anticipe les `llmConstraints` de la couche 2
  (étiquetage des consignes) et la réserve 10 % du sel (C4). Le smoke-test reste néanmoins du
  Cooklang pur — ces étiquettes sont du texte de note libre, sans incidence sur le parsing.
- **`#cookware{}`** : accolades vides explicites pour lever toute ambiguïté de fin de token
  (le plugin accepte aussi `#mot` simple, mais `#nom à plusieurs mots{}` impose les accolades).

> Réserve de conformité connue : la **spec Cooklang canonique** veut une quantité **purement
> numérique** ou fractionnaire après `%`. Le smoke-test emploie des **unités françaises lisibles**
> (`c.à.s`, `c.à.c`, `gousse`, `tranches`, `feuilles`) — c'est volontaire (cohérence FR du projet,
> templating maison). Le plugin Obsidian rend ces unités comme **texte d'unité** ; aucune conversion
> automatique n'est attendue ni nécessaire (le scaling est fait en amont par notre moteur, pas par
> Cooklang). À confirmer visuellement en §e.

---

## (b) Auto-vérification structurelle déterministe (exécutée)

Contrôle **regex pur, sans dépendance**, qui sépare le frontmatter du corps puis vérifie la présence
et la bonne formation de chaque marqueur. Il est **déterministe** (même fichier → même verdict) et
constitue le pendant « validation légère » de la décision #3 (templating maison + validation regex,
en attendant la confirmation du paquet `cooklang-py`, réserve RZ5).

**Commande** (lancée depuis la racine du repo, le script complet est consigné dans le Debug Log de
[`../stories/S0.4.md`](../stories/S0.4.md)) :

```bash
python - <<'PY'
import re
from pathlib import Path
text = Path("docs/cooklang/smoke-test.cook").read_text(encoding="utf-8")
# frontmatter vs corps, puis regex sur @ {qty%unit} / # / ~ / {=…} / --
# (9 contrôles : servings, ingrédients, ustensiles, minuteurs, verrou =, notes,
#  accolades équilibrées, ingrédients bien formés, encodage UTF-8 + accents)
...
PY
```

**Sortie réelle consignée** (2026-06-01) :

```
=== AUTO-VÉRIFICATION STRUCTURELLE — smoke-test.cook ===

[OK ] frontmatter servings :: servings=4
[OK ] ingredients @{qty%unit} :: 8 trouvés: four==180°C, pain de campagne=4tranches, tomates mûres=300g, ail=1gousse, basilic frais=6feuilles, huile d'olive=2c.à.s, sel=1c.à.c, ail=0.5gousse
[OK ] cookware #ustensile :: 3 trouvés: plaque de cuisson, saladier, poêle
[OK ] timers ~{durée%unité} :: 2 trouvés: 8minutes, 1minute
[OK ] verrou = (valeur figée) :: 1 trouvés: 180°C
[OK ] notes -- :: 5 trouvées
[OK ] accolades équilibrées :: { =13 } =13
[OK ] ingrédients bien formés (@nom{...}) :: 8 blocs @ ; 8 avec %qty
[OK ] UTF-8 + accents présents :: 24 caractères accentués/spéciaux

RÉSULTAT GLOBAL : VALIDE — tous les marqueurs présents et bien formés
```

> Note d'exécution : la console Windows (code page `cp1252`) peut afficher des caractères de
> remplacement (mojibake) à l'écran ; le **fichier** est bien en **UTF-8 sans BOM** (vérifié :
> `read_bytes().decode("utf-8")` réussit, pas de BOM `EF BB BF`). La sortie ci-dessus est la version
> ré-encodée correctement.

Lecture du résultat : **9/9 contrôles OK**. Le `.cook` est **structurellement bien formé** au regard
des marqueurs du projet. Le marqueur `=` est correctement détecté à part (le verrou `@four{=180%°C}`
apparaît aussi dans la liste des ingrédients car c'est un ingrédient à quantité figée — comportement
attendu).

---

## (c) Procédure reproductible d'ouverture dans Obsidian

Plugin de référence : **`cooklang/cooklang-obsidian`** (Obsidian Community Plugin « Cooklang »).

1. **Installer Obsidian** (https://obsidian.md) et ouvrir (ou créer) un *vault* de test, par ex.
   `recettes-vault`.
2. **Installer le plugin Cooklang** :
   - `Paramètres → Modules complémentaires tiers` : activer les modules tiers (désactiver le *Safe
     mode* si demandé).
   - `Parcourir` → rechercher **« Cooklang »** → installer le plugin **`cooklang-obsidian`** →
     **Activer**.
   - *(Alternative manuelle)* : cloner `cooklang/cooklang-obsidian`, copier `main.js`,
     `manifest.json`, `styles.css` dans `<vault>/.obsidian/plugins/cooklang-obsidian/`, puis activer.
3. **Placer le fichier** : copier [`smoke-test.cook`](./smoke-test.cook) à la racine du vault (ou
   dans un sous-dossier `recettes/` **du vault de test** — ⚠️ pas le dossier `recipes/` du repo,
   réservé à S0.6). Le plugin associe l'extension `.cook`.
4. **Ouvrir le fichier** dans Obsidian : le plugin bascule en **vue recette** (rendu dédié) au lieu
   du texte brut.
5. **Basculer brut ↔ rendu** si besoin via l'icône de mode de vue (ou la commande
   *« Cooklang: Toggle … »* selon la version du plugin).

---

## (d) Checklist de rendu attendu (à cocher pendant la validation visuelle)

Dans la **vue recette** du plugin, vérifier que :

- [ ] **Portions** : « 4 servings » (ou équivalent) est lu depuis le frontmatter `servings: 4`.
- [ ] **Liste d'ingrédients** extraite automatiquement et regroupée, contenant au minimum :
      pain de campagne (4 tranches), tomates mûres (300 g), ail (1 gousse + 0,5 gousse), basilic
      frais (6 feuilles), huile d'olive (2 c.à.s), sel (1 c.à.c).
- [ ] **Ustensiles** (cookware) listés/surlignés : plaque de cuisson, saladier, poêle.
- [ ] **Minuteurs** rendus comme durées (potentiellement cliquables) : 8 minutes, 1 minute.
- [ ] **Température figée** `@four{=180%°C}` affichée **180 °C** (valeur non altérée ; le `=` est un
      détail de notre moteur, le plugin l'affiche comme quantité).
- [ ] **Étapes** : le corps de la recette est rendu en paragraphes lisibles, marqueurs interprétés.
- [ ] **Notes `--`** : présentes (rendues en commentaire/texte selon la version du plugin) ; aucune
      ne casse le rendu.
- [ ] **Accents** corrects à l'écran (é, è, à, û, ô, °) — pas de mojibake (preuve UTF-8 de bout en bout).
- [ ] **Aucune erreur de parsing** visible (pas de marqueur affiché en brut au milieu du rendu).

Si **tous** ces points passent → le format `.cook` du templating maison est **confirmé compatible**
Obsidian. Tout écart est à consigner en §(f) « Réserves ».

---

## (e) Capture (à réaliser manuellement)

> **Étape manuelle — nécessite un humain lançant Obsidian.** Elle ne peut pas être automatisée dans
> cet environnement (pas d'instance Obsidian/GUI). C'est le seul AC de S0.4 qui reste **non vérifié
> programmatiquement**.

À faire par l'utilisateur :

1. Exécuter la procédure §(c), ouvrir `smoke-test.cook` en **vue recette**.
2. Cocher la checklist §(d).
3. **Prendre une capture d'écran** de la vue recette rendue et l'enregistrer ici :

   **Emplacement réservé : `docs/cooklang/obsidian-render.png`**

4. *(Optionnel)* ajouter une seconde capture du mode brut côte à côte pour la démonstration portfolio.

Une fois la capture déposée, l'AC « capture » du backlog (S0.4) est satisfait et la story peut passer
de `review` à `done`. Tant que la capture n'est pas fournie, **la compatibilité reste attestée
structurellement (§b) mais pas visuellement**.

```
<!-- À insérer après capture :
![Rendu Obsidian du smoke-test Cooklang](./obsidian-render.png)
-->
```

---

## (f) Alternative d'import `cook.md/<url>` (différée)

Pour **constituer** des `.cook` à partir de pages web, Cooklang propose de préfixer une URL par
`cook.md/` (ex. `cook.md/https://exemple.com/recette`). Cette voie est **hors périmètre de S0.4** :

- Elle relève du **point ouvert #5** (`recherche-ouverte.md` §A#5) et de la story **S0.6**
  (constitution du corpus italien), qui tourne **en parallèle** dans `recipes/` (zone réservée).
- Décision (`decisions-techniques.md` #5) : **reporter** ; tester sur 2-3 recettes italiennes lors de
  S0.6, inspecter le `.cook` obtenu, garder un **fallback de saisie manuelle** si la qualité varie.
- S0.4 valide la voie **templating maison → Obsidian** (le chemin de production réel du projet, où le
  `.cook` est *généré* par nos couches 3/4), pas la voie d'import tierce.

---

## Conclusion

- **Vérifié programmatiquement (déterministe)** : le `.cook` produit par templating maison est
  **structurellement bien formé** et exerce **tous** les marqueurs du projet (9/9 contrôles OK, §b).
- **Reste manuel** : l'ouverture réelle dans Obsidian + la **capture** `obsidian-render.png` (§e),
  qui exige un humain lançant l'application.
- **Réserves de compatibilité** : (1) unités FR en clair (`c.à.s`, `gousse`, …) rendues comme texte
  d'unité — attendu, non bloquant ; (2) syntaxe `#cookware{}` à accolades pour les noms multi-mots ;
  (3) le verrou `=` est une convention **interne** de notre moteur de scaling — le plugin l'affiche
  comme une quantité, ce qui est acceptable. Aucune de ces réserves n'invalide le format ; elles
  seront définitivement levées par la capture visuelle (§e).

> Verdict S0.4 (en attente de la capture) : **format `.cook` validé structurellement, compatibilité
> Obsidian à confirmer par la capture manuelle.**
