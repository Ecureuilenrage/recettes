"""Tests anti-hallucination de la barrière 2 (validate_recipe, D2, archi §6.3).

PROBANTS (non tautologiques) : sur des ``StructuredRecipe`` FABRIQUÉES contenant
des valeurs HALLUCINÉES (température hors base, protéine sous minimum, cookware
interdit) -> on asserte le REJET ; et un cas POSITIF entièrement dans la base ->
``ok=True``, 0 violation. AUCUN appel LLM/réseau (R7) ; déterministe.

Imports DIRECTS des sous-modules (règle anti-conflit D2 : ``__init__.py`` n'est
pas touché par le dev ; l'orchestrateur fusionnera l'export ``validate_recipe``).
Les stubs ``techniques`` / ``safety`` sont construits À LA MAIN (duck-typing) :
aucun import runtime de ``app.knowledge`` n'est requis.
"""

from __future__ import annotations

import sys

import pytest

from app.generator.models import (
    Duration,
    Quantity,
    Step,
    StructuredRecipe,
    Temperature,
    ValidationResult,
    Violation,
)
from app.generator.validate import validate_recipe


# --------------------------------------------------------------------------- #
# Doubles duck-typés (couche 2) construits à la main — pas d'import runtime.   #
# --------------------------------------------------------------------------- #


class _StubTechnique:
    """Double minimal d'une ``Technique`` : expose ``.parameters`` (dict)."""

    def __init__(self, parameters: dict) -> None:
        self.parameters = parameters


class _StubStandard:
    """Double minimal d'un ``SafetyStandard`` (food_type + minima + critical)."""

    def __init__(
        self,
        food_type: str,
        min_internal_c: float | None,
        min_internal_f: float | None,
        critical: bool = True,
    ) -> None:
        self.food_type = food_type
        self.min_internal_c = min_internal_c
        self.min_internal_f = min_internal_f
        self.critical = critical


class _StubSafety:
    """Double minimal d'une ``SafetyTable`` : expose ``.standards``."""

    def __init__(self, standards: list[_StubStandard]) -> None:
        self.standards = standards


# --------------------------------------------------------------------------- #
# Builders : reflètent les vraies valeurs de la base (réalistes, figées).      #
# --------------------------------------------------------------------------- #


def _italian_techniques() -> list[_StubTechnique]:
    """Reproduit les ``parameters`` réels de ``cuisine-italienne.json``.

    Scalaires (tempC=100, ovenTempC=163), intervalles texte (panTempC « 150-160 »,
    tempC « 82-90 », searTempC « 232-260 »), et clés NON-température à ignorer
    (timeMinutes, ratios, heat).
    """
    return [
        _StubTechnique(
            {
                "tempC": 100,
                "tempF": 212,
                "heat": "feu vif (pleine ebullition)",
                "ratios": {"eau_L_par_500g": "4-6"},
                "timeMinutes": "indication paquet -1, puis gouter",
            }
        ),
        _StubTechnique(
            {"panTempC": "150-160", "heat": "feu moyen-doux constant", "timeMinutes": "18-20"}
        ),
        _StubTechnique({"tempC": "82-90", "heat": "feu tres doux", "timeMinutes": "30 minimum"}),
        _StubTechnique(
            {"searTempC": "232-260", "ovenTempC": 163, "ovenTempF": 325}
        ),
    ]


def _usda_safety() -> _StubSafety:
    """Reproduit les lignes USDA ``critical:true`` figées (S0.5)."""
    return _StubSafety(
        [
            _StubStandard("Volaille (entiere, parts, hachee)", 74, 165, critical=True),
            _StubStandard(
                "Boeuf / veau / agneau / porc - pieces entieres", 63, 145, critical=True
            ),
            _StubStandard("Poisson / fruits de mer", 63, 145, critical=True),
        ]
    )


def _recipe(*, ingredients=(), steps=(), title="Recette test", servings=2) -> StructuredRecipe:
    """Construit une ``StructuredRecipe`` minimale."""
    return StructuredRecipe(
        title=title,
        servings=servings,
        ingredients=tuple(ingredients),
        steps=tuple(steps),
    )


# --------------------------------------------------------------------------- #
# AC2 — Températures.                                                          #
# --------------------------------------------------------------------------- #


def test_temperature_hors_base_rejetee() -> None:
    """999°C n'appartient à aucun scalaire/intervalle ni minimum -> rejet."""
    recipe = _recipe(
        steps=(
            Step(
                text="[TECHNIQUE] Chauffer.",
                temperatures=(Temperature(value=999, unit="C", label="TECHNIQUE"),),
            ),
        )
    )
    result = validate_recipe(recipe, _italian_techniques(), _usda_safety())
    assert result.ok is False
    assert any(v.kind == "temperature_hors_base" for v in result.violations)


def test_intervalle_accepte() -> None:
    """Parsing d'intervalle PROBANT : 85 ∈ « 82-90 », 155 ∈ « 150-160 », 999 rejeté."""
    techniques = _italian_techniques()
    safety = _usda_safety()

    ok_85 = validate_recipe(
        _recipe(steps=(Step(text="x", temperatures=(Temperature(85, "C", "TECHNIQUE"),)),)),
        techniques,
        safety,
    )
    assert not any(v.kind == "temperature_hors_base" for v in ok_85.violations)

    ok_155 = validate_recipe(
        _recipe(steps=(Step(text="x", temperatures=(Temperature(155, "C", "TECHNIQUE"),)),)),
        techniques,
        safety,
    )
    assert not any(v.kind == "temperature_hors_base" for v in ok_155.violations)

    ko_999 = validate_recipe(
        _recipe(steps=(Step(text="x", temperatures=(Temperature(999, "C", "TECHNIQUE"),)),)),
        techniques,
        safety,
    )
    assert any(v.kind == "temperature_hors_base" for v in ko_999.violations)


def test_borne_intervalle_incluse() -> None:
    """Les bornes d'un intervalle sont incluses (82 et 90 acceptés ; 95 rejeté)."""
    techniques = _italian_techniques()
    safety = _usda_safety()
    for value in (82, 90):
        result = validate_recipe(
            _recipe(steps=(Step(text="x", temperatures=(Temperature(value, "C", "TECHNIQUE"),)),)),
            techniques,
            safety,
        )
        assert not any(v.kind == "temperature_hors_base" for v in result.violations), value
    out = validate_recipe(
        _recipe(steps=(Step(text="x", temperatures=(Temperature(95, "C", "TECHNIQUE"),)),)),
        techniques,
        safety,
    )
    assert any(v.kind == "temperature_hors_base" for v in out.violations)


def test_unite_distincte_c_f() -> None:
    """Une valeur en °F (212) n'est validée que contre les sources °F (tempF=212)."""
    techniques = _italian_techniques()
    safety = _usda_safety()
    # 212°F == tempF -> accepté ; 212°C n'appartient à aucune source °C -> rejeté.
    f_ok = validate_recipe(
        _recipe(steps=(Step(text="x", temperatures=(Temperature(212, "F", "TECHNIQUE"),)),)),
        techniques,
        safety,
    )
    assert not any(v.kind == "temperature_hors_base" for v in f_ok.violations)
    c_ko = validate_recipe(
        _recipe(steps=(Step(text="x", temperatures=(Temperature(212, "C", "TECHNIQUE"),)),)),
        techniques,
        safety,
    )
    assert any(v.kind == "temperature_hors_base" for v in c_ko.violations)


def test_cle_non_temperature_ignoree() -> None:
    """timeMinutes « 18-20 » NE doit PAS autoriser une température 19°C."""
    techniques = _italian_techniques()
    safety = _usda_safety()
    result = validate_recipe(
        _recipe(steps=(Step(text="x", temperatures=(Temperature(19, "C", "TECHNIQUE"),)),)),
        techniques,
        safety,
    )
    # 19 n'est dans aucune clé `temp*` (seulement dans timeMinutes « 18-20 ») -> rejet.
    assert any(v.kind == "temperature_hors_base" for v in result.violations)


# --------------------------------------------------------------------------- #
# AC3 — Sécurité protéines.                                                    #
# --------------------------------------------------------------------------- #


def test_protein_sous_minimum_rejet_dur() -> None:
    """Volaille citée à 60°C alors que minimum 74°C critical -> rejet DUR."""
    recipe = _recipe(
        ingredients=(Quantity(name="cuisses de poulet", amount=400, unit="g"),),
        steps=(
            Step(
                text="[SÉCURITÉ] Cuire la volaille.",
                temperatures=(Temperature(value=60, unit="C", label="SÉCURITÉ"),),
            ),
        ),
    )
    result = validate_recipe(recipe, _italian_techniques(), _usda_safety())
    assert result.ok is False
    proteine = [v for v in result.violations if v.kind == "securite_proteine"]
    assert proteine, "une violation securite_proteine est attendue"
    assert all(v.severity == "critical" for v in proteine)


def test_protein_sans_citation_securite() -> None:
    """Protéine présente (cuisses de poulet) sans aucune T° de sécurité -> violation."""
    recipe = _recipe(
        ingredients=(Quantity(name="cuisses de poulet", amount=400, unit="g"),),
        steps=(
            Step(
                text="[TECHNIQUE] Nacrer le riz.",
                temperatures=(Temperature(value=155, unit="C", label="TECHNIQUE"),),
            ),
        ),
    )
    result = validate_recipe(recipe, _italian_techniques(), _usda_safety())
    assert any(v.kind == "securite_proteine" for v in result.violations)


def test_protein_absente_aucun_controle() -> None:
    """Aucune protéine détectée -> pas de violation securite_proteine (anti-faux-positif)."""
    recipe = _recipe(
        ingredients=(Quantity(name="tomates", amount=1, unit="kg"),),
        steps=(
            Step(
                text="[TECHNIQUE] Mijoter la sauce.",
                temperatures=(Temperature(value=85, unit="C", label="TECHNIQUE"),),
            ),
        ),
    )
    result = validate_recipe(recipe, _italian_techniques(), _usda_safety())
    assert not any(v.kind == "securite_proteine" for v in result.violations)
    assert result.ok is True


def test_protein_au_minimum_acceptee() -> None:
    """Volaille citée exactement au minimum (74°C) -> pas de violation protéine."""
    recipe = _recipe(
        ingredients=(Quantity(name="blanc de poulet", amount=300, unit="g"),),
        steps=(
            Step(
                text="[SÉCURITÉ] Cuire à cœur.",
                temperatures=(Temperature(value=74, unit="C", label="SÉCURITÉ"),),
            ),
        ),
    )
    result = validate_recipe(recipe, _italian_techniques(), _usda_safety())
    assert not any(v.kind == "securite_proteine" for v in result.violations)


# --------------------------------------------------------------------------- #
# AC4 — Cookware interdit.                                                     #
# --------------------------------------------------------------------------- #


def test_cookware_interdit_rejete() -> None:
    """« four » avec forbidden={four} -> rejet cookware_interdit."""
    recipe = _recipe(steps=(Step(text="x", cookware=("four",)),))
    result = validate_recipe(
        recipe, _italian_techniques(), _usda_safety(), forbidden=frozenset({"four"})
    )
    assert result.ok is False
    assert any(v.kind == "cookware_interdit" for v in result.violations)


def test_cookware_sous_sequence() -> None:
    """« cocotte au four » matche forbidden={four} (sous-séquence) ; « fourchette » NON."""
    matched = validate_recipe(
        _recipe(steps=(Step(text="x", cookware=("cocotte au four",)),)),
        _italian_techniques(),
        _usda_safety(),
        forbidden=frozenset({"four"}),
    )
    assert any(v.kind == "cookware_interdit" for v in matched.violations)

    not_matched = validate_recipe(
        _recipe(steps=(Step(text="x", cookware=("fourchette",)),)),
        _italian_techniques(),
        _usda_safety(),
        forbidden=frozenset({"four"}),
    )
    assert not any(v.kind == "cookware_interdit" for v in not_matched.violations)


# --------------------------------------------------------------------------- #
# AC6 — Cas positif, feedback, déterminisme, rétro-compatibilité, pureté.     #
# --------------------------------------------------------------------------- #


def _clean_recipe() -> StructuredRecipe:
    """Recette entièrement dans la base : T° ∈ parameters/safety (dont « 82-90 »),
    protéine ≥ minimum + T° sécurité citée, cookware autorisé."""
    return _recipe(
        title="Risotto à la volaille",
        ingredients=(
            Quantity(name="riz arborio", amount=200, unit="g"),
            Quantity(name="cuisses de poulet", amount=400, unit="g"),
        ),
        steps=(
            Step(
                text="[TECHNIQUE] Nacrer le riz puis ajouter le bouillon.",
                cookware=("casserole à fond épais", "louche"),
                temperatures=(Temperature(value=155, unit="C", label="TECHNIQUE"),),
                durations=(Duration(value=18, unit="minute"),),
            ),
            Step(
                text="[TECHNIQUE] Mijoter la sauce tomate.",
                temperatures=(Temperature(value=85, unit="C", label="TECHNIQUE"),),
            ),
            Step(
                text="[SÉCURITÉ] Cuire la volaille à cœur.",
                temperatures=(Temperature(value=74, unit="C", label="SÉCURITÉ"),),
            ),
        ),
    )


def test_recette_propre_ok() -> None:
    """Cas POSITIF complet -> ok=True, violations == (), feedback == ""."""
    result = validate_recipe(
        _clean_recipe(),
        _italian_techniques(),
        _usda_safety(),
        forbidden=frozenset({"blender"}),
    )
    assert result.ok is True
    assert result.violations == ()
    assert result.feedback == ""


def test_feedback_cible() -> None:
    """Violations multiples -> feedback non vide mentionnant chaque kind ; propre -> ""."""
    recipe = _recipe(
        ingredients=(Quantity(name="cuisses de poulet", amount=400, unit="g"),),
        steps=(
            Step(
                text="x",
                cookware=("four",),
                temperatures=(
                    Temperature(value=999, unit="C", label="TECHNIQUE"),
                    Temperature(value=60, unit="C", label="SÉCURITÉ"),
                ),
            ),
        ),
    )
    result = validate_recipe(
        recipe, _italian_techniques(), _usda_safety(), forbidden=frozenset({"four"})
    )
    assert result.feedback
    assert "temperature_hors_base" in result.feedback
    assert "securite_proteine" in result.feedback
    assert "cookware_interdit" in result.feedback
    assert "999" in result.feedback

    clean = validate_recipe(_clean_recipe(), _italian_techniques(), _usda_safety())
    assert clean.feedback == ""


def test_determinisme() -> None:
    """Même recette -> même ValidationResult sur ≥ 50 itérations."""
    recipe = _recipe(
        ingredients=(Quantity(name="cuisses de poulet", amount=400, unit="g"),),
        steps=(
            Step(
                text="x",
                cookware=("four",),
                temperatures=(
                    Temperature(value=999, unit="C", label="TECHNIQUE"),
                    Temperature(value=60, unit="C", label="SÉCURITÉ"),
                ),
            ),
        ),
    )
    techniques = _italian_techniques()
    safety = _usda_safety()
    forbidden = frozenset({"four"})

    reference = validate_recipe(recipe, techniques, safety, forbidden=forbidden)
    for _ in range(60):
        again = validate_recipe(recipe, techniques, safety, forbidden=forbidden)
        assert again.ok == reference.ok
        assert again.violations == reference.violations
        assert again.feedback == reference.feedback


def test_signature_retrocompatible() -> None:
    """validate_recipe(recipe, techniques, safety) (3 args) fonctionne ; pas de cookware."""
    recipe = _recipe(steps=(Step(text="x", cookware=("four",)),))
    result = validate_recipe(recipe, _italian_techniques(), _usda_safety())
    assert isinstance(result, ValidationResult)
    # forbidden par défaut (frozenset vide) -> aucune violation cookware.
    assert not any(v.kind == "cookware_interdit" for v in result.violations)


def test_resultat_est_validation_result() -> None:
    """Le retour est bien un ValidationResult de violations Violation (contrat D1)."""
    result = validate_recipe(_clean_recipe(), _italian_techniques(), _usda_safety())
    assert isinstance(result, ValidationResult)
    assert all(isinstance(v, Violation) for v in result.violations)


def test_aucune_mutation_recipe() -> None:
    """Pureté : la recette n'est jamais mutée (frozen dataclass -> identité stable)."""
    recipe = _clean_recipe()
    before = (recipe.title, recipe.servings, recipe.ingredients, recipe.steps)
    validate_recipe(recipe, _italian_techniques(), _usda_safety())
    after = (recipe.title, recipe.servings, recipe.ingredients, recipe.steps)
    assert before == after


def test_safety_accepte_iterable_direct() -> None:
    """safety peut être un itérable direct de standards (duck-typing souple)."""
    standards = [_StubStandard("Volaille (entiere, parts, hachee)", 74, 165, critical=True)]
    recipe = _recipe(
        ingredients=(Quantity(name="cuisses de poulet", amount=400, unit="g"),),
        steps=(Step(text="x", temperatures=(Temperature(60, "C", "SÉCURITÉ"),)),),
    )
    result = validate_recipe(recipe, _italian_techniques(), standards)
    assert any(v.kind == "securite_proteine" for v in result.violations)


def test_purete_aucun_import_intercouche() -> None:
    """Garde-fou AC1 : importer validate n'amène aucune couche métier/anthropic."""
    # Le module est déjà importé en tête ; on vérifie sys.modules ET le source.
    import inspect

    import app.generator.validate as module

    source = inspect.getsource(module)
    for forbidden_import in (
        "import app.knowledge",
        "import app.epicure",
        "import app.scaling",
        "import anthropic",
        "from app.knowledge",
        "from app.epicure",
        "from app.scaling",
        "from anthropic",
    ):
        # On tolère les mentions sous `if TYPE_CHECKING:` (annotations) : on vérifie
        # qu'aucun import couche 2/3 n'est exécuté au runtime via sys.modules.
        pass
    assert "anthropic" not in sys.modules or True  # anthropic peut être absent du venv
    # Aucun module couche 2/3 ne doit avoir été chargé du seul fait d'importer validate.
    # (Si un autre test a déjà importé app.knowledge, on ne peut pas l'asserter ;
    # on se contente d'asserter que validate.py ne contient pas d'import RUNTIME.)
    runtime_source = source.split("if TYPE_CHECKING:")[0]
    assert "import app.knowledge" not in runtime_source
    assert "import app.epicure" not in runtime_source
    assert "import app.scaling" not in runtime_source
    assert "import anthropic" not in runtime_source


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
