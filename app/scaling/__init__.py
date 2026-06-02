"""Couche 3 — Moteur de scaling non-lineaire (coeur deterministe, teste).

Types couverts (table `docs/scaling/table-scaling-sale.json`) :
  - linear      : qty * k
  - sublinear   : qty * k^coeff (sel/epices, perception non lineaire)
  - discrete    : oeufs (unite non secable + reste, `scale_eggs`)
  - geometric   : temps de cuisson k^(2/3) (`scale_time`)
  - fixed       : temperature / verrou `=` Cooklang (inchange)

API publique (assemblee ici par l'orchestrateur apres livraison des stories C1-C5) :
  - `classify(name) -> ScalingRule` / `ScalingRule` (table.py, C1).
  - `scale(name, qty, unit, k) -> ScaledQuantity` (engine.py, C1 + flags/reserve C4).
  - `scale_eggs(count, k) -> ScaledEggs` (engine.py, C2 ; regle RZ1 'oeufs liants').
  - `scale_time(minutes, k) -> ScaledTime` (engine.py, C3 ; loi geometrique k^(2/3)).
  - Constantes partagees `K_NONLINEAR_THRESHOLD` (RZ2, seuil non-linearite) /
    `NONLINEAR_NOTE` (texte verbatim de la note `--`).

Ce module DOIT rester pur/deterministe (meme entree -> meme sortie) pour etre
testable. Il N'IMPORTE AUCUNE autre couche metier (archi 3.1) ; seule la couche
web (E1, `app/main.py`) assemble le pipeline et applique le scaling APRES la
redaction LLM, sur les quantites de base produites.
"""

from __future__ import annotations

from app.scaling.engine import (
    EPS,
    K_NONLINEAR_THRESHOLD,
    NONLINEAR_NOTE,
    ScaledEggs,
    ScaledQuantity,
    ScaledTime,
    scale,
    scale_eggs,
    scale_time,
)
from app.scaling.table import ScalingRule, classify

__all__ = [
    "EPS",
    "K_NONLINEAR_THRESHOLD",
    "NONLINEAR_NOTE",
    "ScaledEggs",
    "ScaledQuantity",
    "ScaledTime",
    "ScalingRule",
    "classify",
    "scale",
    "scale_eggs",
    "scale_time",
]
