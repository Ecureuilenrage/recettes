---
titre: Schéma de la base technique (sécurité + cuisine)
type: schema
statut: v1
créé: 2026-06-01
tags: [schema, base-technique, securite, modularite]
---

# Schéma de la base technique

> But : donner au LLM une **base de vérité** dans laquelle il **choisit** (techniques, températures),
> sans jamais inventer. La base est **modulaire** : une cuisine = un fichier `cuisine-*.json`.
> Trois niveaux d'autorité sont distingués partout :
> `SÉCURITÉ` (non négociable, USDA/ANSES) > `TECHNIQUE` (indicatif, sources culinaires) >
> `PRÉFÉRENCE` (subjectif).

## Fichiers

| Fichier | Rôle | Autorité |
|---|---|---|
| `safety-temperatures.json` | Températures à cœur minimales sûres, transverses à toutes les cuisines | SÉCURITÉ |
| `cuisine-italienne.json` | Module pilote : techniques italiennes salées | TECHNIQUE / PRÉFÉRENCE |
| (futur) `cuisine-<nom>.json` | 2ᵉ cuisine — valide la modularité | TECHNIQUE / PRÉFÉRENCE |

## 1. `safety-temperatures.json`

```jsonc
{
  "meta": { "authority": "USDA FSIS + ANSES", "sources": ["url", "..."], "updated": "2026-06-01" },
  "standards": [
    {
      "foodType": "string",          // ex. "Volaille (toutes parts, haché)"
      "minInternalC": 74,             // température à cœur min (°C)
      "minInternalF": 165,            // idem (°F)
      "restMinutes": 0,               // temps de repos requis
      "critical": true,               // true = jamais d'exception possible
      "source": "USDA FSIS",
      "note": "string"
    }
  ]
}
```

**Règle moteur** : pour toute protéine, le générateur DOIT citer la ligne `safety-temperatures` et
ne JAMAIS proposer une température inférieure au minimum. `critical: true` ⇒ aucune flexibilité.

## 2. `cuisine-<nom>.json`

```jsonc
{
  "meta": {
    "id": "italian_savory_v1",
    "name": "Cuisine italienne (salé)",
    "scope": "Salé uniquement",
    "version": "1.0",
    "sources": ["url", "..."]
  },
  "techniques": [
    {
      "id": "pasta_al_dente",
      "name": "Pâtes al dente",
      "category": "Ébullition",
      "safetyClassification": "Faible risque",   // libre ; informatif
      "parameters": {
        "tempC": 100, "tempF": 212,                // température de la technique
        "ratios": { "eau_L_par_500g": "4-6", "sel_g_par_L": 30 },
        "timeMinutes": "paquet -1",                // plage ou consigne
        "heat": "feu vif"
      },
      "criticalPoints": [
        { "point": "Ne jamais rincer les pâtes", "reason": "amidon = adhérence sauce", "level": "TECHNIQUE" }
      ],
      "donenessIndicators": ["tendre dehors, légère résistance au cœur"],
      "requiredTools": ["grande casserole (>=4L)", "passoire"],
      "forbiddenIf": { "noCookware": ["four"] },   // optionnel : technique exclue si ustensile interdit
      "sources": ["url"]
    }
  ],
  "cookwareConstraints": {
    // mapping contrainte utilisateur -> ustensiles (#cookware) interdits
    "pas_de_four": ["four", "plaque de cuisson au four", "moule à four"],
    "pas_de_blender": ["blender", "mixeur plongeant"],
    "pas_de_robot": ["robot culinaire"]
  },
  "llmConstraints": [
    "NE JAMAIS inventer une température ou un temps : choisir dans `parameters` ou `safety-temperatures`.",
    "Étiqueter chaque consigne : [SÉCURITÉ] / [TECHNIQUE] / [PRÉFÉRENCE].",
    "Pour toute protéine, citer la température de sécurité et le repos.",
    "Ne pas utiliser un ustensile listé dans les `#cookware` interdits."
  ]
}
```

## 3. Champs — conventions

- **Températures** : toujours fournir `°C` ET `°F`.
- **Plages** : exprimées en chaîne (`"325-450"`) quand une fourchette a un sens culinaire.
- **`level` / `safetyClassification`** : pour piloter l'étiquetage `[SÉCURITÉ]/[TECHNIQUE]/[PRÉFÉRENCE]`.
- **`requiredTools`** : sert au mapping inverse des contraintes matérielles (une technique exigeant
  un « four » est exclue si l'utilisateur a coché « pas de four »).
- **`sources`** : URLs ; obligatoire pour les valeurs de sécurité.

## 4. Modularité (validation Phase 5)

Ajouter une cuisine = créer un `cuisine-<nom>.json` respectant ce schéma. Le loader (`app/knowledge/`)
découvre les fichiers et expose une API uniforme `techniques_for(cuisine, ingredient, constraints)`.
Aucun changement de code ne doit être nécessaire pour une nouvelle cuisine bien formée.
