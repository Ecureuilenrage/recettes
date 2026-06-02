"""Tests de l'assembleur E1 (app/main.py) : pipeline + endpoints — déterministes.

Tous les tests sont OFFLINE (R7) : aucun appel LLM/réseau, aucune clé, aucun
fichier de données Epicure requis. Le cœur ``run_pipeline`` est exercé avec un
FAUX ``complete`` (rédacteur LLM injecté qui renvoie une ``StructuredRecipe``
fabriquée) et un FAUX ``index`` (objet exposant ``.neighbors(name, k)``). Les
tests HTTP (TestClient) sont gardés par ``pytest.importorskip("fastapi")`` et
restent skippés proprement si ``fastapi`` n'est pas installé.

Conventions : imports DIRECTS depuis ``app.main`` ; construction des recettes À
LA MAIN ; docstrings/commentaires FR (accents corrects).
"""

from __future__ import annotations

import sys

import pytest

from app.generator import (
    Duration,
    Quantity,
    Step,
    StructuredRecipe,
    Temperature,
)
from app.main import (
    GenerationRequest,
    GenerationResponse,
    PipelineGenerationError,
    PipelineInputError,
    run_pipeline,
)


# --------------------------------------------------------------------------- #
# Doubles de test : faux index Epicure + faux rédacteur LLM (complete).        #
# --------------------------------------------------------------------------- #


class FakeIndex:
    """Faux ``EpicureIndex`` : ``.neighbors(name, k)`` -> voisins déterministes.

    ``raise_on`` permet de simuler un héros absent du vocab Epicure (``KeyError``,
    comportement réel de ``EpicureIndex.neighbors``).
    """

    def __init__(self, neighbors=None, raise_on: set[str] | None = None) -> None:
        self._neighbors = neighbors if neighbors is not None else [
            ("basil", 0.91),
            ("garlic", 0.88),
            ("olive_oil", 0.85),
        ]
        self._raise_on = raise_on or set()

    def neighbors(self, name: str, k: int = 6):
        if name in self._raise_on:
            raise KeyError(name)
        return list(self._neighbors)[:k]


def _recipe_valide(servings: int = 2) -> StructuredRecipe:
    """Recette italienne COHÉRENTE (passe ``validate_recipe`` : temp. 100 °C de la
    base ``pasta_al_dente``, aucune protéine non citée)."""
    return StructuredRecipe(
        title="Spaghetti à la tomate",
        servings=servings,
        ingredients=(
            Quantity(name="spaghetti", amount=200, unit="g"),
            Quantity(name="sel", amount=10, unit="g"),
        ),
        steps=(
            Step(
                text="[TECHNIQUE] Cuire les pâtes al dente.",
                cookware=("grande casserole",),
                temperatures=(Temperature(value=100, unit="C", label="TECHNIQUE"),),
                durations=(Duration(value=9, unit="minute"),),
                technique_id="pasta_al_dente",
            ),
        ),
        techniques=("pasta_al_dente",),
    )


def fake_complete_valide(_prompt, _feedback=None) -> StructuredRecipe:
    """Faux ``complete`` déterministe renvoyant une recette valide (offline)."""
    return _recipe_valide()


def fake_complete_violation(_prompt, _feedback=None) -> StructuredRecipe:
    """Faux ``complete`` renvoyant une recette qui VIOLE la base (999 °C) à CHAQUE
    appel (y compris au retry) -> ``RecipeValidationError`` attendue."""
    return StructuredRecipe(
        title="Recette piégée",
        servings=2,
        ingredients=(Quantity(name="spaghetti", amount=200, unit="g"),),
        steps=(
            Step(
                text="[TECHNIQUE] Chauffer follement.",
                temperatures=(Temperature(value=999, unit="C", label="TECHNIQUE"),),
            ),
        ),
    )


# --------------------------------------------------------------------------- #
# Tests du cœur : run_pipeline (sans HTTP).                                     #
# --------------------------------------------------------------------------- #


def test_run_pipeline_succes():
    """run_pipeline avec faux complete+index -> GenerationResponse non vide avec
    les 4 sections de debug."""
    request = GenerationRequest(hero="basilic", servings=2)
    response = run_pipeline(
        request, complete=fake_complete_valide, index=FakeIndex()
    )

    assert isinstance(response, GenerationResponse)
    assert response.cooklang.strip()
    assert response.markdown.strip()
    # Le markdown contient le titre de la recette.
    assert "Spaghetti à la tomate" in response.markdown
    # Les 4 sections du panneau debug (FR7) sont présentes.
    debug = response.debug
    assert "kept" in debug.epicure and "rejected" in debug.epicure
    assert isinstance(debug.scaling, list) and debug.scaling
    assert "kept" in debug.techniques and "excluded" in debug.techniques
    assert "ok" in debug.validation and "violations" in debug.validation
    # La recette de base est valide -> validation ok.
    assert debug.validation["ok"] is True


def test_hero_absent_vocab_422():
    """Un héros hors vocabulaire FR→Epicure (``translate`` lève KeyError) ->
    PipelineInputError (mappée en 422)."""
    request = GenerationRequest(hero="ingredient_inexistant_xyz", servings=2)
    with pytest.raises(PipelineInputError):
        run_pipeline(request, complete=fake_complete_valide, index=FakeIndex())


def test_hero_absent_index_422():
    """Un héros traduit mais absent de l'index Epicure (``neighbors`` lève
    KeyError) -> PipelineInputError (mappée en 422)."""
    request = GenerationRequest(hero="basilic", servings=2)
    index = FakeIndex(raise_on={"basil"})  # 'basilic' -> 'basil'
    with pytest.raises(PipelineInputError):
        run_pipeline(request, complete=fake_complete_valide, index=index)


def test_cuisine_inconnue_422():
    """Une cuisine inconnue de ``load_cuisines()`` -> PipelineInputError (422)."""
    request = GenerationRequest(
        hero="basilic", servings=2, cuisine="cuisine_bidon_v0"
    )
    with pytest.raises(PipelineInputError):
        run_pipeline(request, complete=fake_complete_valide, index=FakeIndex())


def test_violation_persistante_502():
    """Un faux complete renvoyant une recette qui viole la base (999 °C) à chaque
    appel -> RecipeValidationError -> PipelineGenerationError (mappée en 502)."""
    request = GenerationRequest(hero="basilic", servings=2)
    with pytest.raises(PipelineGenerationError):
        run_pipeline(
            request, complete=fake_complete_violation, index=FakeIndex()
        )


def test_scaling_applique():
    """servings cible (4) ≠ base (2) -> k = 2 : spaghetti (linéaire) double,
    sel (sous-linéaire) augmente MOINS que le double. Reflété dans debug.scaling
    et le cooklang/markdown."""
    request = GenerationRequest(hero="basilic", servings=4)
    response = run_pipeline(
        request, complete=fake_complete_valide, index=FakeIndex()
    )

    by_name = {row["name"]: row for row in response.debug.scaling}
    assert "spaghetti" in by_name and "sel" in by_name
    # Linéaire : 200 * 2 = 400.
    assert by_name["spaghetti"]["type"] == "linear"
    assert abs(by_name["spaghetti"]["value"] - 400.0) < 1e-6
    # Sous-linéaire : 10 * 2^0.75 ≈ 16.8, strictement entre la base (10) et le
    # double naïf (20).
    sel_value = by_name["sel"]["value"]
    assert by_name["sel"]["type"] == "sublinear"
    assert 10.0 < sel_value < 20.0
    # La valeur scalée du spaghetti apparaît dans le cooklang et le markdown.
    assert "400" in response.cooklang
    assert "400" in response.markdown


def test_scaling_oeufs_discrets():
    """Un ingrédient « œufs » -> scaling discret (``scale_eggs``) : 2 œufs ×2 -> 3
    entiers (borne basse RZ1), reflété dans debug.scaling (type ``discrete``)."""
    recipe = StructuredRecipe(
        title="Pâtes aux œufs",
        servings=2,
        ingredients=(
            Quantity(name="spaghetti", amount=200, unit="g"),
            Quantity(name="oeufs", amount=2, unit=""),
        ),
        steps=(
            Step(
                text="[TECHNIQUE] Cuire al dente.",
                temperatures=(Temperature(value=100, unit="C", label="TECHNIQUE"),),
                technique_id="pasta_al_dente",
            ),
            # Cite la température de sécurité des œufs (71 °C) pour passer la
            # validation protéines.
            Step(
                text="[SÉCURITÉ] Cuire l'œuf à cœur.",
                temperatures=(Temperature(value=71, unit="C", label="SÉCURITÉ"),),
            ),
        ),
    )

    def _complete(_prompt, _feedback=None):
        return recipe

    request = GenerationRequest(hero="basilic", servings=4)
    response = run_pipeline(request, complete=_complete, index=FakeIndex())
    by_name = {row["name"]: row for row in response.debug.scaling}
    assert by_name["oeufs"]["type"] == "discrete"
    # 2 œufs ×2 -> 3 entiers (RZ1 : on borne par le bas).
    assert by_name["oeufs"]["value"] == 3.0


def test_portions_emises_sont_la_cible():
    """Portions CIBLE cohérentes dans les DEUX artefacts (corrige Majeur 1).

    Pour ``servings`` cible (4) ≠ base (2), le ``.cook`` doit porter
    ``servings: 4`` (frontmatter) ET le Markdown ``Portions : 4`` — JAMAIS la
    valeur de base (2). Échouerait sur l'ancien comportement (base émise des deux
    côtés)."""
    request = GenerationRequest(hero="basilic", servings=4)
    response = run_pipeline(
        request, complete=fake_complete_valide, index=FakeIndex()
    )
    # La recette de base a servings=2 ; la cible est 4.
    assert "servings: 4" in response.cooklang
    assert "servings: 2" not in response.cooklang
    assert "**Portions : 4**" in response.markdown
    assert "**Portions : 2**" not in response.markdown


def test_coherence_oeufs_cook_markdown():
    """Œufs IDENTIQUES entre ``.cook`` et Markdown, reflétant le scaling discret
    RZ1 (corrige Majeur 2).

    3 œufs base ×2 -> 5 entiers (RZ1 borne basse : 6 théoriques - 1 œuf liant), et
    la MÊME valeur (5) apparaît dans le ``.cook`` (``@oeufs{5%}``) ET le Markdown
    (``- 5 oeufs``). Échouerait sur l'ancien comportement (.cook = base, Markdown =
    scalé)."""
    recipe = StructuredRecipe(
        title="Pâtes aux œufs",
        servings=2,
        ingredients=(
            Quantity(name="spaghetti", amount=200, unit="g"),
            Quantity(name="oeufs", amount=3, unit=""),
        ),
        steps=(
            Step(
                text="[TECHNIQUE] Cuire al dente.",
                temperatures=(Temperature(value=100, unit="C", label="TECHNIQUE"),),
                technique_id="pasta_al_dente",
            ),
            Step(
                text="[SÉCURITÉ] Cuire l'œuf à cœur.",
                temperatures=(Temperature(value=71, unit="C", label="SÉCURITÉ"),),
            ),
        ),
    )

    def _complete(_prompt, _feedback=None):
        return recipe

    request = GenerationRequest(hero="basilic", servings=4)
    response = run_pipeline(request, complete=_complete, index=FakeIndex())

    # RZ1 : 3 œufs ×2 -> 5 entiers (6 théoriques - 1 œuf liant).
    by_name = {row["name"]: row for row in response.debug.scaling}
    assert by_name["oeufs"]["value"] == 5.0
    # MÊME quantité (5) dans les deux artefacts.
    assert "@oeufs{5%}" in response.cooklang
    assert "- 5 oeufs" in response.markdown
    # La valeur de base (3) ne subsiste dans aucun des deux émetteurs.
    assert "@oeufs{3%}" not in response.cooklang
    assert "- 3 oeufs" not in response.markdown


def test_coherence_quantites_cook_markdown():
    """Renforcement : pour un ingrédient linéaire, la quantité scalée affichée
    dans le ``.cook`` et le Markdown coïncide (et = base × k)."""
    request = GenerationRequest(hero="basilic", servings=4)
    response = run_pipeline(
        request, complete=fake_complete_valide, index=FakeIndex()
    )
    # Spaghetti linéaire : 200 × 2 = 400, présent dans les deux artefacts.
    assert "@spaghetti{400%g}" in response.cooklang
    assert "- 400 g spaghetti" in response.markdown


def test_aucune_logique_metier_ni_appel_reel():
    """Garde-fou R7 : run_pipeline avec faux complete N'effectue AUCUN appel réel
    (le faux complete EST appelé) et ``anthropic`` n'est pas requis."""
    appels = {"complete": 0}

    def _complete(_prompt, _feedback=None):
        appels["complete"] += 1
        return _recipe_valide()

    request = GenerationRequest(hero="basilic", servings=2)
    run_pipeline(request, complete=_complete, index=FakeIndex())
    # Le faux complete a été appelé (aucun chemin réseau emprunté).
    assert appels["complete"] >= 1
    # `anthropic` n'a pas été importé du seul fait d'exécuter le pipeline.
    assert "anthropic" not in sys.modules


# --------------------------------------------------------------------------- #
# Tests HTTP (gardés : skip propre si fastapi absent).                          #
# --------------------------------------------------------------------------- #


def test_health():
    """GET /health -> 200 {status, stage} (endpoint conservé)."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "stage" in body


def test_generate_endpoint():
    """POST /generate -> 200 avec cooklang/markdown/debug (faux index+complete
    injectés via ``app.dependency_overrides``) ; et un cas entrée invalide -> 422."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from app.main import app, get_complete, get_index

    app.dependency_overrides[get_index] = lambda: FakeIndex()
    app.dependency_overrides[get_complete] = lambda: fake_complete_valide
    try:
        client = TestClient(app)
        # Cas succès.
        response = client.post(
            "/generate", json={"hero": "basilic", "servings": 2}
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["cooklang"].strip()
        assert body["markdown"].strip()
        assert set(body["debug"]) >= {"epicure", "scaling", "techniques", "validation"}

        # Cas entrée invalide (héros hors vocab) -> 422.
        bad = client.post(
            "/generate", json={"hero": "ingredient_inexistant_xyz", "servings": 2}
        )
        assert bad.status_code == 422, bad.text
    finally:
        app.dependency_overrides.clear()
