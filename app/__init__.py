"""Application 'recettes' — scaler de recettes Epicure.

Architecture en 4 couches (voir docs/PRD.md) :
  - epicure/   : associations d'ingredients (embeddings locaux, cosine)
  - knowledge/ : base technique grounded (securite + cuisines)
  - scaling/   : moteur de scaling non-lineaire (coeur deterministe)
  - generator/ : orchestration LLM + sortie Cooklang
"""
