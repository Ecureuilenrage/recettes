"""Tests de l'UI minimale (story E2 : app/main.py + templates/) — déterministes.

L'UI E2 ÉTEND ``app/main.py`` (zone partagée mono-fichier, APRÈS E1) : routes
HTML Jinja2 (``GET /`` formulaire, ``POST /generate-ui`` rendu) + helper PUR de
contexte de vue ``build_view_context``. E2 est en LECTURE SEULE sur la logique
E1 (``run_pipeline`` inchangé) et n'ajoute AUCUNE logique métier.

Deux familles de tests :
  - le helper PUR ``build_view_context`` tourne SANS fastapi/jinja2 (offline, avec
    une ``GenerationResponse``/un debug fabriqués À LA MAIN) ;
  - les tests HTTP (TestClient) sont GARDÉS par ``pytest.importorskip("fastapi")``
    (et jinja2) -> skip propre si les dépendances web ne sont pas installées.

Aucun appel LLM/réseau/clé (R7) : les tests HTTP injectent un FAUX ``complete`` +
un FAUX ``index`` via ``app.dependency_overrides`` (patron de ``test_main.py``).
"""

from __future__ import annotations

import pytest

from app.generator import (
    Duration,
    Quantity,
    Step,
    StructuredRecipe,
    Temperature,
)
from app.main import (
    DEFAULT_CUISINE,
    DebugInfo,
    GenerationResponse,
    build_view_context,
)


# --------------------------------------------------------------------------- #
# Doubles de test : faux index Epicure + faux rédacteur LLM (réutilisés des     #
# tests E1 — patron déterministe, offline).                                     #
# --------------------------------------------------------------------------- #


class FakeIndex:
    """Faux ``EpicureIndex`` : ``.neighbors(name, k)`` -> voisins déterministes."""

    def __init__(self, neighbors=None) -> None:
        self._neighbors = neighbors if neighbors is not None else [
            ("basil", 0.91),
            ("garlic", 0.88),
            ("olive_oil", 0.85),
        ]

    def neighbors(self, name: str, k: int = 6):
        return list(self._neighbors)[:k]


def _recipe_valide(servings: int = 2) -> StructuredRecipe:
    """Recette italienne COHÉRENTE (passe ``validate_recipe``)."""
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


def _debug_fabrique() -> DebugInfo:
    """Construit À LA MAIN un ``DebugInfo`` aux 4 sections renseignées."""
    return DebugInfo(
        epicure={
            "kept": [{"name": "basil", "score": 0.91, "cuisine_context": "italian"}],
            "rejected": [{"name": "wasabi", "score": 0.40, "reason": "hors cuisine"}],
        },
        scaling=[
            {
                "name": "spaghetti",
                "type": "linear",
                "coeff": 1.0,
                "formula": "amount * k",
                "reasoning": "ingrédient linéaire",
                "value": 400.0,
            }
        ],
        techniques={
            "kept": ["pasta_al_dente"],
            "excluded": [
                {
                    "technique_id": "rotir_four",
                    "forbidden_tool": "four",
                    "via_constraint": "pas_de_four",
                }
            ],
        },
        validation={"ok": True, "violations": [], "feedback": ""},
    )


def _response_fabrique() -> GenerationResponse:
    """Construit À LA MAIN une ``GenerationResponse`` complète (offline)."""
    return GenerationResponse(
        cooklang=">> servings: 4\n@spaghetti{400%g}\n",
        markdown="# Spaghetti à la tomate\n\n**Portions : 4**\n",
        debug=_debug_fabrique(),
    )


# --------------------------------------------------------------------------- #
# Tests du helper PUR build_view_context (SANS fastapi/jinja2 — offline).       #
# --------------------------------------------------------------------------- #


def test_build_view_context_4_sections_debug():
    """Le contexte de vue contient cooklang/markdown + les 4 sections de debug
    (epicure/scaling/techniques/validation) — vitrine d'explicabilité §9.2."""
    response = _response_fabrique()
    context = build_view_context(response)

    assert context["ok"] is True
    assert context["error"] is None
    # cooklang + markdown présents (présentation du rendu).
    assert "@spaghetti{400%g}" in context["cooklang"]
    assert "Spaghetti à la tomate" in context["markdown"]
    # Les 4 sections du panneau debug sont aplaties et présentes.
    debug = context["debug"]
    assert set(debug) >= {"epicure", "scaling", "techniques", "validation"}
    assert debug["epicure"]["kept"][0]["name"] == "basil"
    assert debug["epicure"]["rejected"][0]["reason"] == "hors cuisine"
    assert debug["scaling"][0]["type"] == "linear"
    assert debug["techniques"]["kept"] == ["pasta_al_dente"]
    assert debug["techniques"]["excluded"][0]["forbidden_tool"] == "four"
    assert debug["validation"]["ok"] is True
    # Libellés FR des 4 sections fournis au template (présentation).
    assert set(context["debug_labels"]) == {
        "epicure",
        "scaling",
        "techniques",
        "validation",
    }


def test_build_view_context_erreur_sans_crash():
    """En cas d'erreur (result=None + message), le contexte est cohérent : ok=False,
    message conservé, sections debug vides — la page peut s'afficher sans planter."""
    context = build_view_context(
        None,
        form={"hero": "xyz", "cuisine": DEFAULT_CUISINE, "servings": 4},
        error="Entrée invalide (422) : héros inconnu",
    )
    assert context["ok"] is False
    assert "422" in context["error"]
    # La saisie est conservée pour ré-affichage.
    assert context["form"]["hero"] == "xyz"
    # Sections debug présentes mais vides (pas de KeyError côté template).
    assert context["debug"]["epicure"] == {}
    assert context["debug"]["scaling"] == []


def test_build_view_context_form_par_defaut():
    """Sans form fourni, le contexte porte les valeurs par défaut du formulaire."""
    context = build_view_context(_response_fabrique())
    assert context["form"]["cuisine"] == DEFAULT_CUISINE


# --------------------------------------------------------------------------- #
# Tests HTTP (gardés : skip propre si fastapi/jinja2 absents).                  #
# --------------------------------------------------------------------------- #


def test_get_form():
    """GET / -> 200 et la page contient le formulaire (champs héros/portions)."""
    pytest.importorskip("fastapi")
    pytest.importorskip("jinja2")
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200, response.text
    body = response.text
    assert "<form" in body
    assert 'name="hero"' in body
    assert 'name="servings"' in body
    assert 'name="cuisine"' in body


def test_post_form_rend_recette_et_debug():
    """POST /generate-ui (faux deps injectés) -> 200 ; la page contient le .cook,
    le Markdown et les libellés des 4 sections debug (vitrine §9.2)."""
    pytest.importorskip("fastapi")
    pytest.importorskip("jinja2")
    from fastapi.testclient import TestClient

    from app.main import app, get_complete, get_index

    app.dependency_overrides[get_index] = lambda: FakeIndex()
    app.dependency_overrides[get_complete] = lambda: fake_complete_valide
    try:
        client = TestClient(app)
        response = client.post(
            "/generate-ui",
            data={"hero": "basilic", "servings": 4},
        )
        assert response.status_code == 200, response.text
        body = response.text
        # Le titre de la recette (Markdown) est rendu.
        assert "Spaghetti à la tomate" in body
        # La valeur scalée (400) apparaît dans le .cook et/ou le Markdown rendus.
        assert "400" in body
        # Les 4 sections du panneau debug sont étiquetées dans la page.
        assert "Épicure" in body
        assert "Scaling" in body
        assert "Techniques" in body
        assert "Validation" in body
    finally:
        app.dependency_overrides.clear()


def test_erreur_entree_affichee():
    """POST /generate-ui avec un héros invalide -> 200 (page d'erreur lisible, PAS
    un crash) : le message d'erreur est affiché dans la page."""
    pytest.importorskip("fastapi")
    pytest.importorskip("jinja2")
    from fastapi.testclient import TestClient

    from app.main import app, get_complete, get_index

    app.dependency_overrides[get_index] = lambda: FakeIndex()
    app.dependency_overrides[get_complete] = lambda: fake_complete_valide
    try:
        client = TestClient(app)
        response = client.post(
            "/generate-ui",
            data={"hero": "ingredient_inexistant_xyz", "servings": 4},
        )
        # La page ne plante pas : 200 avec un message d'erreur lisible.
        assert response.status_code == 200, response.text
        assert "422" in response.text or "invalide" in response.text.lower()
    finally:
        app.dependency_overrides.clear()


def test_health_et_generate_intacts():
    """Non-régression E1 : GET /health -> 200 et POST /generate (JSON) reste OK
    (faux deps injectés). E2 n'a pas cassé les endpoints E1."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from app.main import app, get_complete, get_index

    # /health reste fonctionnel.
    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    # POST /generate (JSON E1) reste fonctionnel.
    app.dependency_overrides[get_index] = lambda: FakeIndex()
    app.dependency_overrides[get_complete] = lambda: fake_complete_valide
    try:
        response = client.post("/generate", json={"hero": "basilic", "servings": 2})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["cooklang"].strip()
        assert body["markdown"].strip()
        assert set(body["debug"]) >= {
            "epicure",
            "scaling",
            "techniques",
            "validation",
        }
    finally:
        app.dependency_overrides.clear()
