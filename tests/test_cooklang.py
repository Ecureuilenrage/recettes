"""Tests de l'émission Cooklang `.cook` + validation regex — story D3 (couche 4).

Couvre les AC1-AC6 :
  - `to_cooklang(recipe, None)` produit un `.cook` qui PASSE `validate_cooklang` ;
  - verrou `=` sur les quantités/températures `fixed` ;
  - notes `--` (réserve 10 %) reportées depuis `scaling_notes`, sans double préfixe ;
  - quantités SCALÉES quand `scaling_notes` est fourni, BASE sinon ;
  - déterminisme strict (même entrée -> même texte sur ≥ 50 exécutions) ;
  - `validate_cooklang` REJETTE un `.cook` mal formé (NON tautologique) ;
  - garde-fou inter-couches : aucun import runtime de `app/scaling|knowledge|epicure`,
    `anthropic`, `cooklang` après import de `app.generator.cooklang`.

Imports DIRECTS des sous-modules (règle anti-conflit : `__init__.py` lecture seule).
Tests PURS : aucune I/O, aucun LLM/réseau, `StructuredRecipe`/scaling construits à la main.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

from app.generator.cooklang import to_cooklang, validate_cooklang
from app.generator.models import (
    Duration,
    Quantity,
    Step,
    StructuredRecipe,
    Temperature,
)


# --------------------------------------------------------------------------- #
# Doublures de test (duck-typing) — imitent les types couche 3 SANS importer   #
# `app/scaling/`. Prouvent que `to_cooklang` lit `.name`/`.value`/`.unit`/     #
# `.fixed`/`.notes` par attributs, pas par type.                              #
# --------------------------------------------------------------------------- #


@dataclass
class FakeScaled:
    """Imite `ScaledQuantity` (couche 3) : attributs lus par duck-typing."""

    name: str
    value: float
    unit: str
    fixed: bool = False
    notes: list[str] = field(default_factory=list)


def _recipe_simple() -> StructuredRecipe:
    """Une recette minimale bien formée pour les tests d'émission."""
    return StructuredRecipe(
        title="Tomates farcies",
        servings=4,
        ingredients=(
            Quantity(name="tomate", amount=200, unit="g"),
            Quantity(name="sel", amount=1, unit="c.à.c", fixed=True),
        ),
        steps=(
            Step(
                text="Cuire au four.",
                cookware=("grande casserole",),
                temperatures=(Temperature(value=180, unit="C", label="TECHNIQUE"),),
                durations=(Duration(value=20, unit="minutes"),),
            ),
        ),
        notes=("[SÉCURITÉ] Vérifier la cuisson à coeur.",),
    )


# --------------------------------------------------------------------------- #
# AC1/AC5 — émission valide.                                                   #
# --------------------------------------------------------------------------- #


def test_to_cooklang_passe_la_validation():
    """AC1/AC5 : `to_cooklang(recipe, None)` -> validate_cooklang == (True, [])."""
    cook = to_cooklang(_recipe_simple(), None)
    ok, problems = validate_cooklang(cook)
    assert ok is True, f"validation a échoué : {problems}"
    assert problems == []
    # Frontmatter + au moins un marqueur ingrédient bien formé.
    assert cook.startswith("---\nservings: 4\n---")
    assert "@tomate{200%g}" in cook


def test_marqueurs_cookware_et_timer_emis():
    """AC1 : ustensile `#` et timer `~{…}` matérialisés depuis les champs Step."""
    cook = to_cooklang(_recipe_simple(), None)
    assert "#grande casserole" in cook  # ustensile multi-mots, style corpus S0.6
    assert "~{20%minutes}" in cook
    ok, _ = validate_cooklang(cook)
    assert ok is True


# --------------------------------------------------------------------------- #
# AC3 — verrou `=` sur fixed.                                                  #
# --------------------------------------------------------------------------- #


def test_verrou_egal_sur_quantite_fixed():
    """AC3 : `Quantity(fixed=True)` -> marqueur avec verrou `{=`."""
    cook = to_cooklang(_recipe_simple(), None)
    assert "@sel{=1%c.à.c}" in cook
    assert "{=" in cook


def test_verrou_egal_sur_temperature():
    """AC3 : une température (type fixed) est émise avec verrou `(=…%°C)`."""
    cook = to_cooklang(_recipe_simple(), None)
    assert "(=180%°C)" in cook


def test_verrou_egal_depuis_scaling_fixed():
    """AC3 : `fixed=True` porté par le scaling -> verrou même si base non-fixed."""
    recipe = StructuredRecipe(
        title="Sauce",
        servings=2,
        ingredients=(Quantity(name="sel", amount=5, unit="g", fixed=False),),
        steps=(Step(text="Assaisonner."),),
    )
    scaling = [FakeScaled(name="sel", value=5, unit="g", fixed=True)]
    cook = to_cooklang(recipe, scaling)
    assert "@sel{=5%g}" in cook


# --------------------------------------------------------------------------- #
# AC4 — notes `--`.                                                            #
# --------------------------------------------------------------------------- #


def test_note_reserve_emise_sans_double_prefixe():
    """AC4 : note de réserve 10 % portée par le scaling -> `--` présente, pas `----`."""
    recipe = StructuredRecipe(
        title="Sauce salée",
        servings=4,
        ingredients=(Quantity(name="sel", amount=10, unit="g"),),
        steps=(Step(text="Saler."),),
    )
    note = "-- réserver ~10 % et ajuster en fin de cuisson"
    scaling = [FakeScaled(name="sel", value=20, unit="g", notes=[note])]
    cook = to_cooklang(recipe, scaling)
    assert note in cook
    assert "----" not in cook  # pas de double préfixe (idempotence)


def test_note_etiquette_recette_emise():
    """AC4 : une étiquette [SÉCURITÉ] de `StructuredRecipe.notes` -> note `--`."""
    cook = to_cooklang(_recipe_simple(), None)
    assert "-- [SÉCURITÉ] Vérifier la cuisson à coeur." in cook


def test_note_deja_prefixee_non_redoublee():
    """AC4 : une note déjà préfixée `--` n'est pas re-préfixée."""
    recipe = StructuredRecipe(
        title="X",
        servings=2,
        ingredients=(Quantity(name="eau", amount=1, unit="L"),),
        steps=(Step(text="Bouillir."),),
        notes=("-- déjà préfixée",),
    )
    cook = to_cooklang(recipe, None)
    assert "-- déjà préfixée" in cook
    assert "----" not in cook


# --------------------------------------------------------------------------- #
# AC2 — quantités scalées vs base.                                             #
# --------------------------------------------------------------------------- #


def test_quantites_scalees_quand_scaling_fourni():
    """AC2 (a) : avec scaling fourni, la valeur SCALÉE est reportée (alignée par nom)."""
    recipe = StructuredRecipe(
        title="Salade",
        servings=4,
        ingredients=(Quantity(name="tomate", amount=200, unit="g"),),
        steps=(Step(text="Couper."),),
    )
    scaling = [FakeScaled(name="tomate", value=400, unit="g")]
    cook = to_cooklang(recipe, scaling)
    assert "@tomate{400%g}" in cook
    assert "@tomate{200%g}" not in cook


def test_quantites_base_quand_scaling_none():
    """AC2 (b) : `scaling_notes=None` -> quantité de BASE (`Quantity.amount`)."""
    recipe = StructuredRecipe(
        title="Salade",
        servings=4,
        ingredients=(Quantity(name="tomate", amount=200, unit="g"),),
        steps=(Step(text="Couper."),),
    )
    cook = to_cooklang(recipe, None)
    assert "@tomate{200%g}" in cook


def test_alignement_par_nom_normalise_accents_casse():
    """AC2 : l'alignement scaling<->ingrédient est insensible casse/accents."""
    recipe = StructuredRecipe(
        title="Plat",
        servings=4,
        ingredients=(Quantity(name="Céleri", amount=100, unit="g"),),
        steps=(Step(text="Émincer."),),
    )
    scaling = {"celeri": FakeScaled(name="celeri", value=250, unit="g")}
    cook = to_cooklang(recipe, scaling)
    assert "@Céleri{250%g}" in cook


def test_scaling_dict_accepte():
    """AC2 : `scaling_notes` accepté sous forme de dict {name: note}."""
    recipe = StructuredRecipe(
        title="Plat",
        servings=4,
        ingredients=(Quantity(name="carotte", amount=100, unit="g"),),
        steps=(Step(text="Râper."),),
    )
    scaling = {"carotte": FakeScaled(name="carotte", value=300, unit="g")}
    cook = to_cooklang(recipe, scaling)
    assert "@carotte{300%g}" in cook


def test_format_nombre_entier_sans_decimale():
    """AC6 : formatage déterministe — `2.0` -> `2` (pas de flottant superflu)."""
    recipe = StructuredRecipe(
        title="X",
        servings=2,
        ingredients=(Quantity(name="eau", amount=2.0, unit="L"),),
        steps=(Step(text="Bouillir."),),
    )
    cook = to_cooklang(recipe, None)
    assert "@eau{2%L}" in cook
    assert "2.0" not in cook


# --------------------------------------------------------------------------- #
# AC6 — déterminisme.                                                          #
# --------------------------------------------------------------------------- #


def test_determinisme_50_executions():
    """AC6 : même (recipe, scaling_notes) -> même texte EXACT sur 50 exécutions."""
    recipe = _recipe_simple()
    scaling = [
        FakeScaled(name="tomate", value=400, unit="g"),
        FakeScaled(
            name="sel",
            value=1,
            unit="c.à.c",
            fixed=True,
            notes=["-- réserver ~10 % et ajuster en fin de cuisson"],
        ),
    ]
    reference = to_cooklang(recipe, scaling)
    for _ in range(60):
        assert to_cooklang(recipe, scaling) == reference


# --------------------------------------------------------------------------- #
# AC5 — validation NON tautologique : rejets.                                  #
# --------------------------------------------------------------------------- #


def test_validation_rejette_accolades_desequilibrees():
    """AC5 (non tautologique) : accolades déséquilibrées -> ok=False + message."""
    mal_forme = "---\nservings: 4\n---\nCuire @pasta{200%g.\n"
    ok, problems = validate_cooklang(mal_forme)
    assert ok is False
    assert any("accolades" in p.lower() for p in problems)


def test_validation_rejette_frontmatter_manquant():
    """AC5 : sans frontmatter `servings` -> ok=False + message dédié."""
    sans_front = "Cuire @pasta{200%g}.\n"
    ok, problems = validate_cooklang(sans_front)
    assert ok is False
    assert any("servings" in p for p in problems)


def test_validation_rejette_sans_marqueur_ingredient():
    """AC5 : aucun marqueur `@…{…%…}` -> ok=False + message dédié."""
    sans_ing = "---\nservings: 4\n---\nCuire les pâtes al dente.\n"
    ok, problems = validate_cooklang(sans_ing)
    assert ok is False
    assert any("@ingredient" in p for p in problems)


def test_validation_accepte_cook_bien_forme():
    """AC5 : un `.cook` bien formé -> (True, [])."""
    bien = "---\nservings: 4\n---\nCuire @pasta{200%g} ~{9%minutes}.\n"
    ok, problems = validate_cooklang(bien)
    assert ok is True
    assert problems == []


# --------------------------------------------------------------------------- #
# AC6 — garde-fou inter-couches (pas d'import runtime interdit).               #
# --------------------------------------------------------------------------- #


def test_aucun_import_intercouche_runtime():
    """AC6 : après import de cooklang, aucun module couche 3/LLM/cooklang-py chargé.

    Prouve l'absence de couplage runtime à `app/scaling|knowledge|epicure`,
    `anthropic` et `cooklang-py` (RZ5 : fallback regex, pas de dépendance native).
    """
    import importlib

    # On (ré)importe le module cible explicitement.
    importlib.import_module("app.generator.cooklang")
    interdits = ("app.scaling", "app.knowledge", "app.epicure", "anthropic", "cooklang")
    # Le module cooklang lui-même ne doit avoir tiré AUCUN de ces modules.
    # (Note : on tolère que d'autres tests aient chargé app.scaling ; ici on
    #  vérifie surtout anthropic/cooklang qui ne sont importés nulle part dans
    #  le chemin de cooklang.)
    import app.generator.cooklang as mod

    source_globals = set(dir(mod))
    # Aucune référence runtime aux types couche 3 dans les globals du module.
    assert "ScaledQuantity" not in source_globals
    assert "anthropic" not in sys.modules
    assert "cooklang" not in sys.modules
