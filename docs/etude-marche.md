---
titre: Étude de marché & état de l'art
type: recherche
statut: v1
créé: 2026-06-01
tags: [marche, etat-de-l-art, concurrents, verdict]
---

# Étude de marché & état de l'art

> Objectif : répondre honnêtement à « ce projet est-il réellement utile ? » avant d'investir du
> temps. Méthode : recherche web (agents) sur les générateurs de recettes IA, le scaling de
> recettes, les flavor networks, la sécurité alimentaire IA, et l'écosystème Cooklang.
>
> ⚠️ Certaines données chiffrées issues de la recherche (financements, parts, métriques) sont
> **indicatives** et non auditées. Les conclusions qualitatives, elles, sont robustes.

## 1. Verdict en une ligne

**Pour un usage perso + portfolio : utile et intéressant.** Comme produit commercial : **non
défendable** (pas de moat, pain point de niche, espace LLM commoditisé). Ce verdict est **aligné**
avec l'intention « rester simple, pas payant ».

## 2. Cartographie des concurrents

| Outil | Approche | Forces | Limites |
|---|---|---|---|
| **ChatGPT / Recipe GPTs** | LLM généraliste | Flexible, gratuit/cheap, conversationnel | Hallucinations (parfois dangereuses), non testé, incohérent |
| **DishGen** | LLM + contrôle de sécurité | Générateur dédié, bloque combos toxiques | Pas de scaling intelligent, pas d'associations flavor |
| **ChefGPT** | LLM fine-tuné | UI intuitive, personnalisation, mobile | Boîte noire, pas de flavor reasoning |
| **Plant Jammer** | Embeddings flavor + LLM | Pionnier flavor mass-market, substitutions | Engagement utilisateur faible (malgré ~4 M€ levés) |
| **Samsung Food (Whisk)** | Base recettes + ML + IoT | Écosystème Samsung, meal planner, nutrition | Plateforme fermée, reco non flavor-native |
| **SuperCook** | Moteur de recherche par ingrédients | Anti-gaspi, ciblé, transparent | Pas de génération (juste matching) |
| **Foodpairing.com** | Flavor networks (molécules), B2B | Scientifique, 14 ans de données | Premium B2B, adoption consommateur faible, pas de génération |
| **Fond.kitchen** | Recipe manager + scaling | Règles non-linéaires basiques (~75 % épices), Cooklang en interne | Scaling **uniforme**, pas par ingrédient |
| **PastryCal** | Calculateur (baker's %) | Très précis pour la boulangerie | Boulangerie only, pas IA, statique |
| **IBM Chef Watson** † | Réseaux neuronaux recettes (2014+) | Preuve historique d'utilité | Mort / archivé |

## 3. Analyse de gap par brique

### 3.1 Scaling de recettes intelligent — **vrai gap**
- L'existant fait au mieux une **règle uniforme** (Fond.kitchen ~75 % sur « épices ») ou du baker's %
  réservé à la farine (PastryCal). Les calculateurs génériques font « tout ×N ».
- **Aucun outil grand public** ne modélise finement : sel sous-linéaire, épices fortes très
  sous-linéaires, œufs en unités discrètes, **temps de cuisson non-linéaire** (géométrie
  surface/volume).
- Douleur réelle et documentée (doubler la cayenne « écrase » le plat ; le temps ne double pas).

→ **C'est la pièce maîtresse différenciante du projet.**

### 3.2 Associations d'ingrédients (flavor networks) — feature « cool », pas driver
- Base scientifique solide (réseaux de composés aromatiques). Foodpairing (B2B) et Plant Jammer
  (grand public) l'exploitent, mais **l'engagement reste faible**.
- Pour ce projet : excellent **différenciateur portfolio** (ML), à utiliser comme **couche de
  validation** d'associations, pas comme cœur de valeur.

### 3.3 Validation grounded / anti-hallucination — nécessaire, pas un moat
- Risques réels documentés (recettes IA suggérant des températures non sûres).
- Bon pour la **crédibilité et la sécurité**, mais deviendra **table-stakes** (les autres copieront).

### 3.4 Format Cooklang — niche tech, bonne interop
- Écosystème de parseurs multi-langages, plugin Obsidian, mais **micro-niche** (devs / markdown).
- **Zéro impact commercial**, mais format de sortie **naturel** ici (texte brut, scaling natif,
  liste de courses, minuteurs, sous-recettes).

## 4. Repositionnement recommandé

Ne pas se présenter comme « **encore un générateur de recettes IA** » (commoditisé). Assumer
l'angle : **« le scaler de recettes honnête »** — un moteur **déterministe** de mise à l'échelle
non-linéaire, **grounded** sur la sécurité, avec **Epicure en validation** d'associations et le
**LLM réduit au rôle de rédacteur** sous contraintes. La valeur est dans le **maths du scaling** et
le **grounding** ; le LLM est interchangeable.

## 5. Quand ça marche / quand ça échoue

**Ça a du sens si** : portfolio technique (LLM API + embeddings ML + maths de scaling + format
ouvert), hyper-focus scaling, usage perso, sortie Cooklang pour Obsidian.

**Ça échoue si** : objectif de remplacer ChatGPT/Whisk, monétisation grand public, miser sur les
flavor networks comme feature d'usage, ou viser le « plus sûr des générateurs IA ».

## 6. Recommandations de différenciation (si on avance)

1. **Hyper-focus scaling** : le moteur non-linéaire par ingrédient est l'argument. Le rendre
   visible (panneau debug qui explique chaque choix).
2. **Couche de validation Epicure** : flaguer les associations absurdes proposées par le LLM.
3. **Grounding assumé et sourcé** : distinguer `[SÉCURITÉ]` / `[TECHNIQUE]` / `[PRÉFÉRENCE]`.
4. **Mini-benchmark de scaling** : comparer le moteur vs « ×N naïf » vs Fond.kitchen sur un petit
   jeu de recettes → preuve mesurable (et matière à un bon README).
5. **Honnêteté sécurité** : ne pas promettre « IA sûre » ; promettre « maths déterministe + temp
   sourcées USDA/ANSES, jamais devinées ».

## 7. Conclusion honnête

- **Utile techniquement** : oui — le scaling par ingrédient est un vrai gap.
- **Utile pour le portfolio** : oui — combine plusieurs compétences (ML, LLM, maths, format ouvert).
- **Viable commercialement** : non — pas de willingness-to-pay, espace saturé, format de niche.

> Pourquoi Plant Jammer (financé, flavor networks, IA) reste petit ? Parce que la génération de
> recettes sans pain point urgent est une **feature, pas un business**. À faire **pour la science
> et le portfolio**, sans attendre de traction virale.

## 8. Sources (sélection)

**Concurrents / marché**
- SideChef — Best AI Recipe Generators 2025 : https://www.sidechef.com/business/recipe-ai/best-ai-recipe-generators
- Fritz AI — 6 Best AI Recipe Generators : https://fritz.ai/best-ai-recipe-generators/
- ChefGPT : https://www.chefgpt.xyz/ · DishGen : https://www.dishgen.com/ · SuperCook : https://www.supercook.com/
- Samsung Food (Whisk) : https://samsungfood.com/

**Sécurité alimentaire & hallucinations IA**
- OPB — « AI can generate recipes that can be deadly » : https://www.opb.org/article/2024/09/23/ai-can-generate-recipes-that-can-be-deadly-food-bloggers-are-not-happy/
- NPR — dangers des recettes hallucinées par IA : https://www.npr.org/2024/09/23/g-s1-23843/artificial-intelligence-recipes-food-cooking-apple
- Meatingplace — Food Safety Hallucinations : https://www.meatingplace.com/the-danger-of-ai-food-safety-hallucinations/

**Scaling**
- Fond.kitchen — Recipe Scaling Tips : https://fond.kitchen/guides/recipe-scaling-tips/
- PastryCal — Scaling Recipes : https://pastrycal.com/articles/scaling-recipes
- Cooklang blog — scaling : https://cooklang.org/blog/

**Flavor networks**
- Foodpairing : https://www.foodpairing.com/
- Nature (Ahn et al., 2011) — Flavor network and food pairing : https://www.nature.com/articles/srep00196
- Plant Jammer (couverture) : https://thespoon.tech/plantjammer-uses-ai-to-create-instant-flavor-mapped-recipes-for-home-cooks/

**Epicure / Cooklang** : voir `recherche-ouverte.md` (deep-dive technique + sources).
