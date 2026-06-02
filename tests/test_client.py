"""Tests de ``generate_recipe`` avec couture injectée — story D1 (AC3/AC4/AC5/AC6).

Imports DIRECTS des sous-modules. Aucun appel API réel : on injecte un FAUX
``complete`` (et au besoin un FAUX ``validate``). Un test d'intégration réel
OPTIONNEL est gardé par ``skipif(not ANTHROPIC_API_KEY)``.
"""

from __future__ import annotations

import os

import pytest

from app.generator.client import (
    RecipeValidationError,
    generate_recipe,
)
from app.generator.models import (
    ConstrainedPrompt,
    StructuredRecipe,
    ValidationResult,
    Violation,
)


def _demo_prompt() -> ConstrainedPrompt:
    return ConstrainedPrompt(system="(système)", user="(utilisateur)")


def _valid_payload() -> dict:
    return {
        "title": "Spaghetti al pomodoro",
        "servings": 2,
        "ingredients": [
            {"name": "spaghetti", "amount": 200, "unit": "g"},
            {"name": "tomates", "amount": 400, "unit": "g"},
        ],
        "steps": [
            {
                "text": "[TECHNIQUE] Cuire les pâtes al dente.",
                "cookware": ["grande casserole"],
                "temperatures": [{"value": 100, "unit": "C", "label": "TECHNIQUE"}],
                "durations": [{"value": 9, "unit": "minute"}],
                "technique_id": "pasta_al_dente",
            }
        ],
        "techniques": ["pasta_al_dente"],
        "notes": ["Réserver de l'eau de cuisson."],
    }


# --------------------------------------------------------------------------- #
# AC3 — génération sans réseau via faux `complete`.                            #
# --------------------------------------------------------------------------- #


def test_generate_sans_reseau():
    payload = _valid_payload()

    def fake_complete(prompt, feedback=None):
        return payload

    recipe = generate_recipe(_demo_prompt(), complete=fake_complete)

    assert isinstance(recipe, StructuredRecipe)
    assert recipe.title == "Spaghetti al pomodoro"
    assert recipe.servings == 2
    assert len(recipe.ingredients) == 2
    assert recipe.ingredients[0].name == "spaghetti"
    assert recipe.ingredients[0].amount == 200.0
    assert len(recipe.steps) == 1
    assert recipe.steps[0].technique_id == "pasta_al_dente"
    assert recipe.steps[0].temperatures[0].value == 100.0
    assert recipe.steps[0].durations[0].value == 9.0
    assert recipe.techniques == ("pasta_al_dente",)


def test_complete_peut_renvoyer_directement_un_structuredrecipe():
    built = StructuredRecipe(title="X", servings=1, ingredients=(), steps=())

    def fake_complete(prompt, feedback=None):
        return built

    recipe = generate_recipe(_demo_prompt(), complete=fake_complete)
    assert recipe is built


# --------------------------------------------------------------------------- #
# AC4 — boucle retry (succès après 1 retry + feedback transmis).              #
# --------------------------------------------------------------------------- #


def test_retry_reussi():
    calls = {"complete": 0, "feedbacks": []}

    def fake_complete(prompt, feedback=None):
        calls["complete"] += 1
        calls["feedbacks"].append(feedback)
        return _valid_payload()

    validations = [
        ValidationResult(
            ok=False,
            violations=(Violation("temperature_hors_base", "120 C inconnu", "critical"),),
            feedback="Utilise une température présente dans la base.",
        ),
        ValidationResult(ok=True),
    ]

    def fake_validate(recipe):
        return validations.pop(0)

    recipe = generate_recipe(_demo_prompt(), complete=fake_complete, validate=fake_validate)

    assert isinstance(recipe, StructuredRecipe)
    assert calls["complete"] == 2  # 1 génération + 1 retry
    # Le 1er appel sans feedback, le 2e avec le feedback ciblé.
    assert calls["feedbacks"][0] is None
    assert calls["feedbacks"][1] == "Utilise une température présente dans la base."


# --------------------------------------------------------------------------- #
# AC4 — échec propre après max_retries.                                        #
# --------------------------------------------------------------------------- #


def test_echec_propre_apres_retry():
    calls = {"complete": 0}

    def fake_complete(prompt, feedback=None):
        calls["complete"] += 1
        return _valid_payload()

    def fake_validate(recipe):
        return ValidationResult(
            ok=False,
            violations=(Violation("cookware_interdit", "utilise le four", "critical"),),
            feedback="Le four est interdit.",
        )

    with pytest.raises(RecipeValidationError) as excinfo:
        generate_recipe(_demo_prompt(), complete=fake_complete, validate=fake_validate)

    # 1 génération + max_retries(=1) relances = 2 appels.
    assert calls["complete"] == 2
    # L'exception porte le feedback/les violations du dernier résultat.
    assert "four" in str(excinfo.value).lower()
    assert excinfo.value.result.ok is False


def test_max_retries_zero_echec_immediat():
    calls = {"complete": 0}

    def fake_complete(prompt, feedback=None):
        calls["complete"] += 1
        return _valid_payload()

    def fake_validate(recipe):
        return ValidationResult(ok=False, feedback="non")

    with pytest.raises(RecipeValidationError):
        generate_recipe(_demo_prompt(), complete=fake_complete, validate=fake_validate, max_retries=0)

    assert calls["complete"] == 1  # aucune relance


# --------------------------------------------------------------------------- #
# AC4 — validate=None : une seule génération.                                  #
# --------------------------------------------------------------------------- #


def test_validate_none_une_seule_generation():
    calls = {"complete": 0}

    def fake_complete(prompt, feedback=None):
        calls["complete"] += 1
        return _valid_payload()

    recipe = generate_recipe(_demo_prompt(), complete=fake_complete)
    assert isinstance(recipe, StructuredRecipe)
    assert calls["complete"] == 1


def test_validate_ok_du_premier_coup_pas_de_retry():
    calls = {"complete": 0}

    def fake_complete(prompt, feedback=None):
        calls["complete"] += 1
        return _valid_payload()

    def fake_validate(recipe):
        return ValidationResult(ok=True)

    generate_recipe(_demo_prompt(), complete=fake_complete, validate=fake_validate)
    assert calls["complete"] == 1


# --------------------------------------------------------------------------- #
# AC5 — import gardé d'anthropic (le module se charge même sans anthropic).    #
# --------------------------------------------------------------------------- #


def test_import_anthropic_garde():
    import inspect

    from app.generator import client

    # Le module se charge sans erreur (import gardé). `anthropic` peut être None.
    assert hasattr(client, "generate_recipe")
    # `anthropic` n'est IMPORTÉ que dans client.py (le mot peut apparaître en
    # docstring de models/prompt, mais jamais comme instruction d'import).
    from app.generator import models, prompt

    assert "import anthropic" not in inspect.getsource(models)
    assert "import anthropic" not in inspect.getsource(prompt)
    # ... mais bien présent (gardé) dans client.py.
    assert "import anthropic" in inspect.getsource(client)


# --------------------------------------------------------------------------- #
# AC6 — intégration réelle OPTIONNELLE (jamais lancée sans clé).               #
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY absente : test d'intégration réel ignoré.",
)
def test_integration_reelle():
    prompt = ConstrainedPrompt(
        system=(
            "Tu es un rédacteur de recettes. Réponds UNIQUEMENT par un objet JSON "
            'avec les clés title (str), servings (int), ingredients (liste), '
            "steps (liste). Pas de texte autour."
        ),
        user="Propose une recette très simple de pâtes à la tomate pour 2 personnes.",
    )
    recipe = generate_recipe(prompt)  # complete=None -> appel Anthropic réel
    assert isinstance(recipe, StructuredRecipe)
    assert recipe.title
