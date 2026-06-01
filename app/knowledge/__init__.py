"""Couche 2 — Base technique grounded (securite + cuisines).

A implementer (voir docs/backlog.md, Epic B) :
  - chargement de docs/base-technique/safety-temperatures.json (autoritatif)
  - chargement modulaire des docs/base-technique/cuisine-*.json
  - API techniques_for(cuisine, ingredient, constraints)
  - mapping contraintes materielles -> #cookware interdits

Le LLM CHOISIT dans cette base ; il n'invente jamais une temperature ou une technique.
"""
