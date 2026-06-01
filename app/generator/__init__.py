"""Couche 4 — Generateur LLM + sortie Cooklang.

A implementer (voir docs/backlog.md, Epic D) :
  - prompt contraint (associations Epicure-validees + techniques/temp de la base)
  - garde-fou : refus si hors base ; tests anti-hallucination
  - emission .cook (marqueurs @ / # / ~, '=', notes '--')
  - rendu Markdown lisible

LLM : Claude API (cle via variable d'environnement ANTHROPIC_API_KEY).
"""
