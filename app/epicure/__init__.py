"""Couche 1 — Associations d'ingredients via embeddings Epicure (local).

Epicure ne connait NI technique, NI temperature, NI quantite absolue : uniquement
des associations (cosine sur embeddings). Cette couche n'importe AUCUNE autre
couche metier (archi 3.1) ; les patrons de normalisation sont recopies, pas
importes.

API publique (assemblee ici par l'orchestrateur apres livraison des stories) :
  - EpicureIndex (A1)        : chargement local des embeddings + neighbors(name, k).
  - translate / translate_many / try_translate (A4) : traduction FR -> cle Epicure
    snake_case EN (table `fr_aliases.json`) ; `translate` leve KeyError (message
    clair) si le terme est absent du vocab FR (cf. R4 / archi 9.1). Leve RZ3.
  - filter_neighbors (A3)    : filtrage des voisins par cuisine (SOUPLE, D14 :
    annote, ne supprime pas) et par contraintes de regime (rejet DUR deterministe).
    Retourne `FilteredNeighbors` (kept + rejected[(name, score, reason)]) pour le
    panneau debug FR7 (DebugInfo.epicure).

Le cablage « saisie FR -> translate -> neighbors -> filter_neighbors » est assure
par l'orchestrateur / la couche web (E1) : A3 et A4 restent decouples.
"""

from __future__ import annotations

from app.epicure.filter import (
    Constraints,
    FilteredNeighbors,
    KeptNeighbor,
    filter_neighbors,
)
from app.epicure.loader import EpicureIndex
from app.epicure.translate import translate, translate_many, try_translate

__all__ = [
    "Constraints",
    "EpicureIndex",
    "FilteredNeighbors",
    "KeptNeighbor",
    "filter_neighbors",
    "translate",
    "translate_many",
    "try_translate",
]
