"""Tests de la traduction FR → clé Epicure (story A4, lève RZ3).

Import DIRECT du module (``app.epicure.translate``), pas via le package
``app.epicure`` (règle anti-conflit multi-agents : __init__.py est fusionné par
l'orchestrateur après le dev).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from app.epicure.translate import (
    FR_ALIASES_PATH,
    translate,
    translate_many,
    try_translate,
)

# Les ≥ 38 clés cibles du noyau (table de référence A4, toutes vérifiées dans vocab.csv).
NOYAU_CLES = {
    "garlic", "basil", "butter", "meat_stock", "vegetable_stock", "chicken_broth",
    "caper", "carrot", "celery", "porcini_mushroom", "mushroom", "zucchini",
    "chicken", "water", "shallot", "salt", "pancetta", "cannellini_bean",
    "green_bean", "olive_oil", "veal", "egg", "onion", "black_olive",
    "parmesan_cheese", "pasta", "pecorino_cheese", "pine_nut", "chili_pepper",
    "black_pepper", "potato", "rice", "rosemary", "saffron", "sugar", "thyme",
    "tomato", "white_wine", "lemon",
}

VOCAB_CSV = Path(__file__).resolve().parents[1] / "docs" / "epicure" / "vocab.csv"


def test_corpus_italien_noyau() -> None:
    """AC2 — assertions chiffrées + couverture des ≥ 38 clés cibles du noyau."""
    assert translate("huile d'olive") == "olive_oil"
    assert translate("ail") == "garlic"
    assert translate("basilic") == "basil"
    assert translate("poivre noir") == "black_pepper"
    assert translate("parmesan râpé") == "parmesan_cheese"
    assert translate("guanciale") == "pancetta"

    # ≥ 38 clés cibles : chacune produite par au moins un alias de la table.
    raw = json.loads(FR_ALIASES_PATH.read_text(encoding="utf-8"))
    produites = set(raw.values())
    assert NOYAU_CLES <= produites
    assert len(NOYAU_CLES) >= 38


def test_normalisation_casse_accents_apostrophe() -> None:
    """AC3 — casse / accents / apostrophe (droite ET typographique) / espaces."""
    assert translate("Huile d'Olive") == "olive_oil"
    assert translate("huile d'olive") == "olive_oil"
    # Apostrophe typographique U+2019 doit converger vers la droite U+0027.
    assert translate("Huile d’Olive") == "olive_oil"
    assert translate("BASILIC") == "basil"
    assert translate("  câpres  ") == "caper"
    assert translate("capres") == "caper"


def test_alias_multiples_meme_cle() -> None:
    """AC1/AC2 — plusieurs alias FR pointent vers la même clé Epicure."""
    for alias in ["spaghetti", "penne", "tonnarelli", "trofie", "pâtes courtes"]:
        assert translate(alias) == "pasta"
    assert translate("riz arborio") == "rice"
    assert translate("riz carnaroli") == "rice"


def test_fallback_keyword_inconnu_keyerror() -> None:
    """AC4 — terme absent → KeyError, message clair (terme + fr_aliases.json)."""
    with pytest.raises(KeyError) as exc_info:
        translate("licorne")
    message = str(exc_info.value)
    assert "licorne" in message
    assert "fr_aliases.json" in message


def test_determinisme() -> None:
    """AC5a — même terme → même clé sur 100 exécutions (module pur)."""
    resultats = {translate("huile d'olive") for _ in range(100)}
    assert resultats == {"olive_oil"}


def test_toutes_les_valeurs_dans_vocab() -> None:
    """AC5b — intégrité table↔vocab, gardée par l'existence de vocab.csv."""
    if not VOCAB_CSV.exists():
        pytest.skip("docs/epicure/vocab.csv absent")
    with VOCAB_CSV.open(encoding="utf-8", newline="") as fh:
        noms = {row["name"] for row in csv.DictReader(fh)}
    raw = json.loads(FR_ALIASES_PATH.read_text(encoding="utf-8"))
    manquantes = {v for v in raw.values() if v not in noms}
    assert not manquantes, f"Clés absentes de vocab.csv : {sorted(manquantes)}"


def test_translate_many_ordre() -> None:
    """AC1 — translate_many préserve l'ordre des termes."""
    assert translate_many(["ail", "basilic"]) == ["garlic", "basil"]


def test_translate_many_terme_inconnu_keyerror() -> None:
    """AC4 — translate_many propage KeyError sur un terme inconnu."""
    with pytest.raises(KeyError):
        translate_many(["ail", "licorne"])


def test_try_translate_variante_non_levante() -> None:
    """AC4 (optionnel) — variante non-levante : clé connue / None inconnu."""
    assert try_translate("ail") == "garlic"
    assert try_translate("licorne") is None
