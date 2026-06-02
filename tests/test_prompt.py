"""Tests PURS de ``build_prompt`` — barrière 1 (story D1, AC2/AC5/AC6).

Imports DIRECTS des sous-modules (jamais via le package ``app.generator`` — règle
anti-conflit : ``__init__.py`` est fusionné par l'orchestrateur après le dev).

Aucun réseau, aucun LLM : ``build_prompt`` est pur. On fabrique des faux objets
amont (voisins/techniques/sécurité) légers ; on peut aussi réutiliser les vrais
loaders en LECTURE pour des entrées réalistes (autorisé DANS le test seulement).
"""

from __future__ import annotations

import inspect

import pytest

from app.generator.models import ConstrainedPrompt
from app.generator.prompt import LLM_CONSTRAINTS, build_prompt


# --------------------------------------------------------------------------- #
# Faux objets amont minimaux (duck-typing : attributs attendus seulement).    #
# --------------------------------------------------------------------------- #


class FakeNeighbor:
    def __init__(self, name: str, score: float, cuisine_context: str = "Mediterranean") -> None:
        self.name = name
        self.score = score
        self.cuisine_context = cuisine_context


class FakeFilteredNeighbors:
    def __init__(self, kept: list[FakeNeighbor]) -> None:
        self.kept = kept
        self.rejected: list[tuple[str, float, str]] = []


class FakeTechnique:
    def __init__(self, tid, name, category, parameters, required_tools):
        self.id = tid
        self.name = name
        self.category = category
        self.parameters = parameters
        self.required_tools = required_tools


class FakeSafety:
    def __init__(self, food_type, c, f, rest, critical):
        self.food_type = food_type
        self.min_internal_c = c
        self.min_internal_f = f
        self.rest_minutes = rest
        self.critical = critical


def _sample_inputs():
    """Jeu d'entrées réaliste (valeurs reprises de la base italienne)."""
    req = {"hero": "tomate", "cuisine": "italian_savory_v1", "servings": 4}
    neighbors = FakeFilteredNeighbors(
        [FakeNeighbor("basilic", 0.91), FakeNeighbor("ail", 0.88)]
    )
    techniques = [
        FakeTechnique(
            "pasta_al_dente",
            "Pâtes al dente",
            "Ébullition",
            {"tempC": 100, "tempF": 212, "timeMinutes": "8-10"},
            ("grande casserole (>=4L)", "passoire"),
        ),
        FakeTechnique(
            "sugo_pomodoro",
            "Sugo di pomodoro",
            "Mijotage",
            {"tempC": "82-90", "timeMinutes": "30 minimum"},
            ("casserole à fond épais", "cuillère en bois"),
        ),
    ]
    safety = [FakeSafety("Volaille", 74, 165, 0, True)]
    forbidden = ["four", "blender"]
    return req, neighbors, techniques, safety, forbidden


# --------------------------------------------------------------------------- #
# AC2 — llmConstraints verbatim + étiquetage.                                  #
# --------------------------------------------------------------------------- #


def test_llm_constraints_verbatim():
    req, neighbors, techniques, safety, forbidden = _sample_inputs()
    prompt = build_prompt(req, neighbors, techniques, safety, forbidden)

    # Les 5 contraintes apparaissent VERBATIM (graphie source, sans accents).
    assert len(LLM_CONSTRAINTS) == 5
    for line in LLM_CONSTRAINTS:
        assert line in prompt.system

    # Quelques sous-chaînes de contrôle (verbatim sans accents).
    assert "NE JAMAIS inventer une temperature ou un temps" in prompt.system
    assert "[SECURITE] / [TECHNIQUE] / [PREFERENCE]" in prompt.system

    # Consigne d'étiquetage imposée (forme accentuée, prose FR).
    assert "[SÉCURITÉ]" in prompt.system
    assert "[TECHNIQUE]" in prompt.system
    assert "[PRÉFÉRENCE]" in prompt.system


def test_sortie_json_structuree_demandee():
    req, neighbors, techniques, safety, forbidden = _sample_inputs()
    prompt = build_prompt(req, neighbors, techniques, safety, forbidden)
    assert "JSON" in prompt.system
    assert '"title"' in prompt.system
    assert '"steps"' in prompt.system


# --------------------------------------------------------------------------- #
# AC2 — les 4 blocs injectés.                                                  #
# --------------------------------------------------------------------------- #


def test_quatre_blocs_injectes():
    req, neighbors, techniques, safety, forbidden = _sample_inputs()
    prompt = build_prompt(req, neighbors, techniques, safety, forbidden)
    full = prompt.system + "\n" + prompt.user

    # Bloc 1 : associations validées (noms des voisins).
    assert "basilic" in prompt.user
    assert "ail" in prompt.user

    # Bloc 2 : au moins une technique + un de ses parameters.
    assert "pasta_al_dente" in prompt.user
    assert "Pâtes al dente" in prompt.user
    assert "tempC=100" in prompt.user  # paramètre injecté

    # Bloc 3 : ligne de sécurité (protéine + min °C).
    assert "Volaille" in prompt.user
    assert "74" in prompt.user

    # Bloc 4 : ustensiles interdits.
    assert "four" in prompt.user
    assert "blender" in prompt.user

    # Les 4 en-têtes de blocs sont présents.
    assert "Bloc 1" in full and "Bloc 2" in full
    assert "Bloc 3" in full and "Bloc 4" in full


# --------------------------------------------------------------------------- #
# AC2 — frozensets allowed/forbidden.                                         #
# --------------------------------------------------------------------------- #


def test_allowed_et_forbidden_frozensets():
    req, neighbors, techniques, safety, forbidden = _sample_inputs()
    prompt = build_prompt(req, neighbors, techniques, safety, forbidden)

    # forbidden_cookware == frozenset(forbidden normalisé).
    assert prompt.forbidden_cookware == frozenset({"four", "blender"})

    # allowed_temperatures : valeurs des parameters ET des minima sécurité.
    assert 100.0 in prompt.allowed_temperatures  # tempC technique
    assert 212.0 in prompt.allowed_temperatures  # tempF technique
    assert 82.0 in prompt.allowed_temperatures   # borne basse de "82-90"
    assert 90.0 in prompt.allowed_temperatures   # borne haute de "82-90"
    assert 74.0 in prompt.allowed_temperatures   # min interne °C sécurité
    assert 165.0 in prompt.allowed_temperatures  # min interne °F sécurité

    # allowed_cookware : ustensiles requis normalisés (minuscule, sans accents).
    assert "passoire" in prompt.allowed_cookware
    assert "cuillere en bois" in prompt.allowed_cookware


def test_neighbors_accepte_tuples():
    """``neighbors`` accepte aussi une séquence de tuples ``(name, score)``."""
    req, _neighbors, techniques, safety, forbidden = _sample_inputs()
    prompt = build_prompt(req, [("basilic", 0.91), ("ail", 0.88)], techniques, safety, forbidden)
    assert "basilic" in prompt.user
    assert "ail" in prompt.user


def test_forbidden_provient_de_req_override_llm_constraints():
    """Si ``req`` fournit ``llm_constraints``, elles priment sur le défaut."""
    req = {"hero": "tomate", "cuisine": "x", "servings": 2, "llm_constraints": ["REGLE UNIQUE."]}
    prompt = build_prompt(req, [], [], [], [])
    assert "REGLE UNIQUE." in prompt.system
    # Le défaut n'est alors PAS injecté.
    assert LLM_CONSTRAINTS[0] not in prompt.system


# --------------------------------------------------------------------------- #
# AC6 — déterminisme.                                                          #
# --------------------------------------------------------------------------- #


def test_determinisme_build_prompt():
    req, neighbors, techniques, safety, forbidden = _sample_inputs()
    reference = build_prompt(req, neighbors, techniques, safety, forbidden)
    for _ in range(60):
        again = build_prompt(req, neighbors, techniques, safety, forbidden)
        assert again == reference
        assert again.system == reference.system
        assert again.user == reference.user
        assert again.allowed_temperatures == reference.allowed_temperatures
        assert again.allowed_cookware == reference.allowed_cookware
        assert again.forbidden_cookware == reference.forbidden_cookware


def test_resultat_est_constrainedprompt():
    req, neighbors, techniques, safety, forbidden = _sample_inputs()
    prompt = build_prompt(req, neighbors, techniques, safety, forbidden)
    assert isinstance(prompt, ConstrainedPrompt)


# --------------------------------------------------------------------------- #
# AC5 — aucun import inter-couches runtime dans models/prompt.                 #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("module_name", ["app.generator.models", "app.generator.prompt"])
def test_aucun_import_intercouche_runtime(module_name):
    import importlib

    module = importlib.import_module(module_name)
    source = inspect.getsource(module)
    # Aucune référence d'import runtime aux autres couches ni à anthropic.
    assert "import app.epicure" not in source
    assert "import app.knowledge" not in source
    assert "import app.scaling" not in source
    assert "from app.epicure" not in source
    assert "from app.knowledge" not in source
    assert "from app.scaling" not in source
    # Aucun import d'anthropic (le mot peut apparaître en docstring, mais pas
    # comme instruction d'import).
    assert "import anthropic" not in source
