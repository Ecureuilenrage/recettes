"""Point d'entree FastAPI (squelette - non branche).

Lancement (Phase 4) :
    uvicorn app.main:app --reload

A implementer (voir docs/backlog.md, Epic E) :
  - POST /generate : {hero, cuisine, constraints, servings} -> recette .cook + debug
  - UI minimale (formulaire + rendu + panneau debug scaling/Epicure)
"""

try:
    from fastapi import FastAPI
except ImportError:  # dependances non encore installees
    FastAPI = None

if FastAPI is not None:
    app = FastAPI(title="recettes - scaler Epicure", version="0.1.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "stage": "scaffold"}
