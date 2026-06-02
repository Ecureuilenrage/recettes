"""Tests de `to_markdown` (story D4, couche 4) — rendu Markdown lisible.

Imports DIRECTS (règle anti-conflit : `app/generator/__init__.py` lecture seule,
export fusionné par l'orchestrateur APRÈS le dev) :
    from app.generator.markdown import to_markdown
    from app.generator.models import StructuredRecipe, Quantity, Step, ...

Tests DÉTERMINISTES, SANS I/O, SANS appel LLM/réseau (R7) : on construit les
``StructuredRecipe`` À LA MAIN, en mémoire.
"""

from __future__ import annotations

import inspect

from app.generator.markdown import to_markdown
from app.generator.models import (
    Duration,
    Quantity,
    Step,
    StructuredRecipe,
    Temperature,
)


def _recette_complete() -> StructuredRecipe:
    """Construit une recette représentative (ingrédients, étapes, étiquettes)."""
    return StructuredRecipe(
        title="Poulet rôti aux herbes",
        servings=4,
        ingredients=(
            Quantity(name="huile d'olive", amount=2.0, unit="c.à.s"),
            Quantity(name="œufs", amount=3, unit=""),
            Quantity(name="gros sel", amount=10, unit="g", fixed=True),
        ),
        steps=(
            Step(
                text="Saisir le poulet sur toutes ses faces.",
                cookware=("grande poêle",),
                temperatures=(Temperature(value=180, unit="C", label="TECHNIQUE"),),
                durations=(Duration(value=5, unit="minutes"),),
                technique_id="searing",
            ),
            Step(
                text="Cuire au four jusqu'à cœur.",
                temperatures=(Temperature(value=74, unit="C", label="SÉCURITÉ"),),
                durations=(Duration(value=45, unit="minutes"),),
            ),
        ),
        techniques=("searing",),
        notes=("Laisser reposer 10 minutes avant de découper.",),
    )


def test_markdown_contient_titre_portions_ingredients_etapes() -> None:
    """AC1 — titre, portions, en-têtes de sections et listes attendus."""
    md = to_markdown(_recette_complete())

    # (a) titre
    assert "# Poulet rôti aux herbes" in md
    # (b) ligne de portions mentionnant servings
    assert "Portions : 4" in md
    # (c) section Ingrédients + puce « quantité + unité + nom »
    assert "## Ingrédients" in md
    assert "- 2 c.à.s huile d'olive" in md
    # (d) section Préparation + étapes numérotées
    assert "## Préparation" in md
    assert "1. Saisir le poulet sur toutes ses faces." in md
    assert "2. Cuire au four jusqu'à cœur." in md


def test_etiquettes_securite_visibles() -> None:
    """AC3/§9.2 — températures + étiquettes SÉCURITÉ/TECHNIQUE/PRÉFÉRENCE visibles."""
    recipe = StructuredRecipe(
        title="Test étiquettes",
        servings=2,
        ingredients=(Quantity(name="poulet", amount=500, unit="g"),),
        steps=(
            Step(
                text="Cuire la protéine.",
                temperatures=(
                    Temperature(value=74, unit="C", label="SÉCURITÉ"),
                    Temperature(value=180, unit="C", label="TECHNIQUE"),
                    Temperature(value=63, unit="C", label="PRÉFÉRENCE"),
                ),
            ),
        ),
    )
    md = to_markdown(recipe)

    # Température de sécurité protéine clairement restituée.
    assert "74" in md
    assert "°C" in md
    assert "[SÉCURITÉ]" in md
    # Les trois étiquettes apparaissent avec leur valeur.
    assert "[TECHNIQUE]" in md
    assert "[PRÉFÉRENCE]" in md
    assert "180" in md
    assert "63" in md
    # Rendu non ambigu pour la sécurité (libellé dédié).
    assert "Température de sécurité : 74 °C [SÉCURITÉ]" in md


def test_durees_et_cookware_restitues() -> None:
    """AC3 — durées et cookware restitués quand présents."""
    md = to_markdown(_recette_complete())
    assert "5 minutes" in md
    assert "45 minutes" in md
    assert "grande poêle" in md


def test_determinisme() -> None:
    """AC2 — même recette -> exactement le même Markdown sur 50+ exécutions."""
    recipe = _recette_complete()
    reference = to_markdown(recipe)
    for _ in range(60):
        assert to_markdown(recipe) == reference


def test_formatage_nombre_deterministe() -> None:
    """AC2 — 2.0 -> « 2 » (pas « 2.0 ») ; 2.5 reste « 2.5 »."""
    recipe = StructuredRecipe(
        title="Test nombres",
        servings=1,
        ingredients=(
            Quantity(name="farine", amount=2.0, unit="tasse"),
            Quantity(name="lait", amount=2.5, unit="dl"),
        ),
        steps=(),
    )
    md = to_markdown(recipe)
    assert "- 2 tasse farine" in md
    assert "2.0 tasse" not in md
    assert "- 2.5 dl lait" in md


def test_recette_minimale_valide() -> None:
    """AC4 — recette minimale -> Markdown valide, pas de section vide cassée."""
    recipe = StructuredRecipe(title="Recette vide", servings=2, ingredients=(), steps=())
    md = to_markdown(recipe)

    # Titre + portions toujours émis.
    assert "# Recette vide" in md
    assert "Portions : 2" in md
    # Sections structurantes présentes avec libellé sobre (pas d'en-tête orphelin).
    assert "## Ingrédients" in md
    assert "_(aucun ingrédient)_" in md
    assert "## Préparation" in md
    assert "_(aucune étape)_" in md
    # Sections optionnelles ABSENTES (pas de section vide cassée).
    assert "## Techniques" not in md
    assert "## Notes" not in md


def test_sections_optionnelles_absentes_si_vides() -> None:
    """AC4 — avec ingrédients/étapes mais sans techniques/notes -> sections absentes."""
    recipe = StructuredRecipe(
        title="Sans techniques ni notes",
        servings=3,
        ingredients=(Quantity(name="riz", amount=200, unit="g"),),
        steps=(Step(text="Cuire le riz."),),
    )
    md = to_markdown(recipe)
    assert "## Ingrédients" in md
    assert "## Préparation" in md
    assert "## Techniques" not in md
    assert "## Notes" not in md


def test_sections_optionnelles_presentes_si_non_vides() -> None:
    """AC1/AC4 — Techniques et Notes émises quand non vides."""
    md = to_markdown(_recette_complete())
    assert "## Techniques" in md
    assert "- searing" in md
    assert "## Notes" in md
    assert "- Laisser reposer 10 minutes avant de découper." in md


def test_signature_un_seul_parametre() -> None:
    """AC5 — exactement 1 paramètre (recipe), pas de scaling_notes."""
    params = list(inspect.signature(to_markdown).parameters)
    assert params == ["recipe"]
    assert "scaling_notes" not in params


def test_termine_par_newline_stable() -> None:
    """AC2 — le document se termine par un « \\n » final stable."""
    md = to_markdown(_recette_complete())
    assert md.endswith("\n")


def test_aucun_import_intercouche_runtime() -> None:
    """Garde-fou AC6 — pas d'import runtime d'une autre couche/anthropic.

    On vérifie le source du module `app.generator.markdown` (le seul `import`
    métier autorisé est `app.generator.models`) : aucune référence à
    `anthropic`, à `app/scaling|knowledge|epicure`, ni aux autres modules de la
    couche (`cooklang`/`validate`/`prompt`/`client`). On inspecte le source
    plutôt que `sys.modules` global, car la suite complète (un seul process
    pytest) charge ces modules via d'AUTRES tests — ce qui ne dit rien de
    l'import de markdown.
    """
    import ast

    import app.generator.markdown as md_module

    source = inspect.getsource(md_module)
    # On analyse les INSTRUCTIONS d'import réelles (AST) — pas le texte brut, qui
    # mentionne légitimement « anthropic » dans la docstring (explication de ce
    # que le module N'importe PAS).
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")

    # Seul import métier autorisé : le contrat de données (même couche 4).
    assert "app.generator.models" in imported

    forbidden_prefixes = (
        "anthropic",
        "app.scaling",
        "app.knowledge",
        "app.epicure",
        # Autres modules de la couche 4 (le helper de formatage est RECOPIÉ).
        "app.generator.cooklang",
        "app.generator.validate",
        "app.generator.prompt",
        "app.generator.client",
    )
    for name in imported:
        for forbidden in forbidden_prefixes:
            assert name != forbidden and not name.startswith(
                forbidden + "."
            ), f"import interdit détecté : {name}"
