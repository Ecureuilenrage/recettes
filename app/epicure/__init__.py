"""Couche 1 — Associations d'ingredients via embeddings Epicure (local).

A implementer (voir docs/backlog.md, Epic A) :
  - chargement local des embeddings (format [A VERIFIER] : safetensors / npy / csv)
  - L2-normalisation + cosine = dot-product ; API neighbors(name, k)
  - filtrage par cuisine/contraintes
  - benchmark cooc vs core (docs/recherche-ouverte.md, section B)

Epicure ne connait NI technique, NI temperature, NI quantite absolue : uniquement des associations.
"""
