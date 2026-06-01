"""Tests de structure de la table de sécurité (`safety-temperatures.json`, story S0.5).

But : verrouiller le **schéma** et la **validité** de la table sécurité, lue en
parallèle par la couche 2 (`load_safety()`, B3). Les assertions portent sur la
**structure** (clés, types, cohérence °C/°F, criticité), jamais sur le wording
exact des notes (qui peut évoluer) — tests robustes, non fragiles.

Lancer : pytest tests/test_safety_temperatures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Racine repo : tests/ -> parents[1]. Même patron que app/epicure/loader.py.
SAFETY_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "base-technique"
    / "safety-temperatures.json"
)

# Clés de schéma à préserver (B3 / load_safety lit ce fichier en parallèle).
META_KEYS = {"authority", "scope", "updated", "disclaimer", "sources"}
STANDARD_KEYS = {
    "foodType",
    "minInternalC",
    "minInternalF",
    "restMinutes",
    "critical",
    "source",
    "note",
}


@pytest.fixture(scope="module")
def safety() -> dict:
    """Charge la table sécurité (échoue clairement si le JSON est invalide)."""
    text = SAFETY_PATH.read_text(encoding="utf-8")
    return json.loads(text)


def test_json_chargeable(safety):
    # Le fichier doit être un JSON valide chargeable (donc par load_safety()).
    assert isinstance(safety, dict)


def test_blocs_racine_presents(safety):
    # Schéma racine : meta + standards[] + rules[].
    assert "meta" in safety
    assert "standards" in safety and isinstance(safety["standards"], list)
    assert "rules" in safety and isinstance(safety["rules"], list)
    assert len(safety["standards"]) >= 1
    assert len(safety["rules"]) >= 1


def test_meta_cles_schema(safety):
    # Les clés meta du schéma ne doivent pas avoir disparu (ajouts additifs OK).
    meta = safety["meta"]
    assert META_KEYS.issubset(set(meta.keys()))
    assert isinstance(meta["sources"], list) and len(meta["sources"]) >= 1
    assert isinstance(meta["updated"], str) and meta["updated"]


def test_standards_cles_schema(safety):
    # Chaque ligne standards[] porte les clés du schéma + les bons types.
    for std in safety["standards"]:
        assert STANDARD_KEYS.issubset(set(std.keys())), std.get("foodType")
        assert isinstance(std["foodType"], str) and std["foodType"]
        assert isinstance(std["minInternalC"], (int, float))
        assert isinstance(std["minInternalF"], (int, float))
        assert isinstance(std["restMinutes"], (int, float))
        assert isinstance(std["critical"], bool)
        assert isinstance(std["source"], str) and std["source"]
        assert isinstance(std["note"], str)


def test_toutes_proteines_critical_true(safety):
    # Toutes les lignes de la table sécurité sont des protéines critiques.
    for std in safety["standards"]:
        assert std["critical"] is True, std["foodType"]


def test_coherence_celsius_fahrenheit(safety):
    # F ≈ C * 9/5 + 32, tolérance large (arrondis ANSES/USDA) -> non fragile.
    for std in safety["standards"]:
        c = std["minInternalC"]
        f = std["minInternalF"]
        attendu_f = c * 9 / 5 + 32
        assert abs(f - attendu_f) <= 3, (std["foodType"], c, f, attendu_f)


def test_minimums_positifs_plausibles(safety):
    # Garde-fou de bon sens : minimums dans une plage de cuisson plausible.
    for std in safety["standards"]:
        assert 50 <= std["minInternalC"] <= 100, std["foodType"]
        assert 120 <= std["minInternalF"] <= 215, std["foodType"]
        assert std["restMinutes"] >= 0, std["foodType"]


def test_repos_mentionne_quand_present(safety):
    # Au moins une ligne porte un repos (pièces entières = 3 min) -> sanity table.
    assert any(std["restMinutes"] > 0 for std in safety["standards"])
