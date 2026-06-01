"""Couche 2 — Base technique grounded (securite + cuisines modulaires).

Fournit au generateur LLM (couche 4) une base de verite dans laquelle il
CHOISIT (techniques, temperatures, securite) sans jamais rien inventer :

  - load_safety()  : table de securite alimentaire (autoritatif, transverse).
  - load_cuisines(): cuisines decouvertes dynamiquement (cuisine-*.json, OA3).
  - techniques_for(cuisine, ingredient, constraints) : techniques applicables,
    excluant celles dont un ustensile requis est interdit par les contraintes.
  - forbidden_cookware(cuisine, constraints) : ensemble normalise des ustensiles
    #cookware interdits (API publique B4, FR4) consommee par techniques_for et
    par la couche 4 (prompt contraint, D1).
  - excluded_techniques(cuisine, ingredient, constraints) : raisons d'exclusion
    (technique + ustensile interdit + contrainte) pour le panneau debug FR7.
  - safety_for(food_type) : ligne de securite d'une proteine (ou None).

Module pur/deterministe (dataclasses stdlib). L'implementation vit dans
`app/knowledge/loader.py`. B4 promeut le helper interne B3 en API publique
`forbidden_cookware` et DURCIT le matching (sous-sequence de tokens : un
ustensile interdit multi-mots comme « robot culinaire » est desormais detecte).
"""

from __future__ import annotations

from app.knowledge.loader import (
    Constraints,
    Cuisine,
    Exclusion,
    SafetyStandard,
    SafetyTable,
    Technique,
    excluded_techniques,
    forbidden_cookware,
    load_cuisines,
    load_safety,
    safety_for,
    techniques_for,
)

__all__ = [
    "Constraints",
    "Cuisine",
    "Exclusion",
    "SafetyStandard",
    "SafetyTable",
    "Technique",
    "excluded_techniques",
    "forbidden_cookware",
    "load_cuisines",
    "load_safety",
    "safety_for",
    "techniques_for",
]
