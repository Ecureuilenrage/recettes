"""Couche 3 — Moteur de scaling non-lineaire (coeur deterministe, teste).

A implementer (voir docs/backlog.md, Epic C) :
  - types : linear, sublinear (qty * k^coeff), discrete (oeufs), geometric (temps k^(2/3)), fixed
  - lecture de docs/scaling/table-scaling-sale.json
  - flags de non-linearite + reserve ~10% des assaisonnements
  - emission Cooklang : '=' (fixed) + notes '--' du moteur

Ce module DOIT rester pur/deterministe (meme entree -> meme sortie) pour etre testable.
"""
