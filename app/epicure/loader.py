"""Loader Epicure + similarite cosinus (couche 1).

Format CONFIRME (Phase 0, 2026-06-01) sur Kaikaku/epicure-{cooc,core,chem} :
  - embeddings.safetensors : cle 'embeddings', matrice (1790, 300) float32
  - vocab.json : dict { ingredient: id }  (1790 entrees, ex. 'olive_oil', 'black_pepper')
  - itos.json  : dict { "id": ingredient }
  - config.json: normalization = "raw skip-gram outputs; L2-normalise before cosine ops"
    => les vecteurs ne sont PAS normalises sur disque (normes ~1.16-3.78) : L2-normaliser avant cosine.

Dependances : numpy, safetensors. Donnees : data/epicure/<model>/ (gitignored).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from safetensors.numpy import load_file

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "epicure"


class EpicureIndex:
    """Charge un modele Epicure et expose les voisins par similarite cosinus."""

    def __init__(self, model: str = "cooc"):
        base = DATA_DIR / f"epicure-{model}"
        emb = load_file(base / "embeddings.safetensors")["embeddings"]  # (1790, 300)
        self.vocab: dict[str, int] = json.loads((base / "vocab.json").read_text(encoding="utf-8"))
        self.itos: dict[str, str] = json.loads((base / "itos.json").read_text(encoding="utf-8"))
        # L2-normalisation -> cosine = produit scalaire
        self.E = emb / np.linalg.norm(emb, axis=1, keepdims=True)
        self.model = model

    def neighbors(self, name: str, k: int = 6) -> list[tuple[str, float]]:
        i = self.vocab.get(name)
        if i is None:
            raise KeyError(f"Ingredient absent du vocabulaire Epicure : {name!r}")
        sims = self.E @ self.E[i]
        order = np.argsort(-sims)
        return [(self.itos[str(j)], round(float(sims[j]), 3)) for j in order if j != i][:k]


if __name__ == "__main__":
    # Sanity-check rapide : python -m app.epicure.loader
    idx = EpicureIndex("cooc")
    print(f"Modele epicure-{idx.model} : {len(idx.vocab)} ingredients, dim {idx.E.shape[1]}")
    for q in ["tomato", "chicken", "basil", "zucchini"]:
        print(f"  {q} -> {idx.neighbors(q)}")
