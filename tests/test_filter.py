"""Tests de `app.epicure.filter` (story A3).

Import DIRECT du module (`app.epicure.filter`), PAS via le package `app.epicure`
dont l'`__init__` ne contient pas encore les exports A3 (fusion par
l'orchestrateur après le dev — règle anti-conflit avec A4).

Couvre AC1 (signature/type), AC2 (cuisine souple + dégradation gracieuse), AC3
(rejet dur régime avec/sans contrainte + casse/accents + régime inconnu no-op),
AC4 (tuples (name, score, reason) pour FR7), AC5 (déterminisme + ordre préservé).
"""

from __future__ import annotations

import app.epicure.filter as flt
from app.epicure.filter import Constraints, FilteredNeighbors, KeptNeighbor, filter_neighbors

# Fixtures : clés Epicure DÉJÀ RÉSOLUES (snake_case EN), comme la sortie de
# EpicureIndex.neighbors. A3 ne traduit pas.
_CANDIDATES = [
    ("tomato", 0.91),
    ("basil", 0.88),
    ("chicken", 0.42),
    ("olive_oil", 0.77),
]
_CUISINE = "italian_savory_v1"


# --------------------------------------------------------------------------- #
# AC1 — Signature exacte + type de sortie                                      #
# --------------------------------------------------------------------------- #


def test_signature_et_type_sortie():
    result = filter_neighbors(_CANDIDATES, _CUISINE, Constraints())
    assert isinstance(result, FilteredNeighbors)
    assert isinstance(result.kept, list)
    assert isinstance(result.rejected, list)
    # Invariant central.
    assert len(result.kept) + len(result.rejected) == len(_CANDIDATES)


def test_candidates_vide_tout_vide():
    result = filter_neighbors([], _CUISINE, Constraints())
    assert result.kept == []
    assert result.rejected == []


# --------------------------------------------------------------------------- #
# AC2 — Filtrage cuisine SOUPLE + dégradation gracieuse (D14)                  #
# --------------------------------------------------------------------------- #


def test_cuisine_souple_aucun_voisin_supprime():
    # Sans contrainte de régime, AUCUN voisin n'est écarté.
    result = filter_neighbors(_CANDIDATES, _CUISINE, Constraints())
    assert len(result.kept) == len(_CANDIDATES)
    assert result.rejected == []
    # Annotation macro-région : cuisine italienne -> Mediterranean.
    for neighbor in result.kept:
        assert isinstance(neighbor, KeptNeighbor)
        assert neighbor.cuisine_context == "Mediterranean"


def test_cuisine_degradation_gracieuse_cuisine_inconnue():
    # Cuisine non résoluble -> annotation neutre, aucune exception, aucun rejet.
    result = filter_neighbors(_CANDIDATES, "klingon", Constraints())
    assert len(result.kept) == len(_CANDIDATES)
    assert result.rejected == []
    for neighbor in result.kept:
        assert neighbor.cuisine_context == "unknown"


def test_cuisine_degradation_gracieuse_donnees_absentes(monkeypatch):
    # Si les données cuisine sont absentes/illisibles -> annotation neutre,
    # jamais d'exception, aucun voisin supprimé. On simule un fichier illisible
    # en pointant le chemin sur un fichier inexistant ; le loader (lru_cache)
    # doit retomber sur un mapping vide sans lever d'exception.
    flt._load_macroregions.cache_clear()
    monkeypatch.setattr(flt, "_MACROREGIONS_PATH", flt.Path("does_not_exist_42.json"))
    try:
        result = filter_neighbors(_CANDIDATES, _CUISINE, Constraints())
        assert len(result.kept) == len(_CANDIDATES)
        assert result.rejected == []
        for neighbor in result.kept:
            assert neighbor.cuisine_context == "unknown"
    finally:
        flt._load_macroregions.cache_clear()


def test_invariant_avec_et_sans_donnees_cuisine():
    # len(kept)+len(rejected)==len(candidates) et aucun rejet de type cuisine.
    for cuisine in (_CUISINE, "klingon", ""):
        result = filter_neighbors(_CANDIDATES, cuisine, Constraints())
        assert len(result.kept) + len(result.rejected) == len(_CANDIDATES)
        for _name, _score, reason in result.rejected:
            assert "cuisine" not in reason.lower()


# --------------------------------------------------------------------------- #
# AC3 — Rejet DUR par régime alimentaire (déterministe)                        #
# --------------------------------------------------------------------------- #


def test_rejet_dur_vegetarien_exclut_chicken():
    result = filter_neighbors(_CANDIDATES, _CUISINE, Constraints(diet=["végétarien"]))
    kept_names = [n.name for n in result.kept]
    rejected_names = [name for name, _s, _r in result.rejected]
    assert "chicken" in rejected_names
    assert "chicken" not in kept_names
    # Les ingrédients végétariens restent retenus.
    assert "tomato" in kept_names
    assert "basil" in kept_names
    assert "olive_oil" in kept_names
    # Raison claire en français mentionnant le régime.
    reason = next(r for name, _s, r in result.rejected if name == "chicken")
    assert "régime" in reason
    assert "végétarien" in reason


def test_chicken_garde_sans_contrainte():
    result = filter_neighbors(_CANDIDATES, _CUISINE, Constraints())
    kept_names = [n.name for n in result.kept]
    assert "chicken" in kept_names
    assert result.rejected == []


def test_regime_insensible_casse_accents():
    expected = {name for name, _s, _r in
                filter_neighbors(_CANDIDATES, _CUISINE, Constraints(diet=["végétarien"])).rejected}
    for variante in ("Vegetarien", "VÉGÉTARIEN", "  Végétarien  ", "vegetarien"):
        rejected = {name for name, _s, _r in
                    filter_neighbors(_CANDIDATES, _CUISINE, Constraints(diet=[variante])).rejected}
        assert rejected == expected
        assert "chicken" in rejected


def test_regime_inconnu_no_op():
    result = filter_neighbors(_CANDIDATES, _CUISINE, Constraints(diet=["sans_gluten"]))
    assert result.rejected == []
    assert len(result.kept) == len(_CANDIDATES)


def test_vegan_exclut_produits_laitiers():
    candidates = [("tomato", 0.9), ("butter", 0.5), ("egg", 0.4), ("cheese", 0.3)]
    result = filter_neighbors(candidates, _CUISINE, Constraints(diet=["vegan"]))
    rejected_names = {name for name, _s, _r in result.rejected}
    assert {"butter", "egg", "cheese"} <= rejected_names
    assert [n.name for n in result.kept] == ["tomato"]


# --------------------------------------------------------------------------- #
# AC4 — `rejected` exploitable par FR7 (DebugInfo.epicure)                     #
# --------------------------------------------------------------------------- #


def test_rejected_tuples_pour_fr7():
    result = filter_neighbors(_CANDIDATES, _CUISINE, Constraints(diet=["végétarien"]))
    for entry in result.rejected:
        assert isinstance(entry, tuple) and len(entry) == 3
        name, score, reason = entry
        assert isinstance(name, str)
        assert isinstance(score, float)
        assert isinstance(reason, str) and reason
    # Le score est le score d'entrée préservé (chicken == 0.42).
    score_chicken = next(s for name, s, _r in result.rejected if name == "chicken")
    assert score_chicken == 0.42


def test_to_debug_serialisable():
    import json

    result = filter_neighbors(_CANDIDATES, _CUISINE, Constraints(diet=["végétarien"]))
    debug = result.to_debug()
    assert set(debug.keys()) == {"kept", "rejected"}
    # Sérialisable JSON sans erreur.
    json.dumps(debug)
    assert any(item["name"] == "chicken" for item in debug["rejected"])
    assert all("cuisine_context" in item for item in debug["kept"])


def test_score_preserve_dans_kept():
    result = filter_neighbors(_CANDIDATES, _CUISINE, Constraints())
    by_name = {n.name: n.score for n in result.kept}
    assert by_name["tomato"] == 0.91
    assert by_name["olive_oil"] == 0.77


# --------------------------------------------------------------------------- #
# AC5 — Déterminisme + ordre préservé                                          #
# --------------------------------------------------------------------------- #


def test_determinisme():
    constraints = Constraints(diet=["végétarien"])
    first = filter_neighbors(_CANDIDATES, _CUISINE, constraints)
    for _ in range(5):
        other = filter_neighbors(_CANDIDATES, _CUISINE, constraints)
        assert other.kept == first.kept
        assert other.rejected == first.rejected


def test_ordre_preserve():
    candidates = [("basil", 0.5), ("chicken", 0.4), ("tomato", 0.3), ("beef", 0.2)]
    result = filter_neighbors(candidates, _CUISINE, Constraints(diet=["végétarien"]))
    # kept conserve l'ordre d'entrée (basil avant tomato).
    assert [n.name for n in result.kept] == ["basil", "tomato"]
    # rejected conserve l'ordre d'entrée (chicken avant beef).
    assert [name for name, _s, _r in result.rejected] == ["chicken", "beef"]
