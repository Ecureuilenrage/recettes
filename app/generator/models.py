"""Contrat de données figé de la couche 4 (générateur LLM) — story D1.

Ce module est la **source de vérité** des types partagés de la couche 4. Il
expose EXACTEMENT les 8 dataclasses stdlib ``frozen`` du contrat (cf.
``docs/stories/D1.md`` — « Contrat de données figé ») ainsi qu'un helper de
parsing tolérant ``parse_structured_recipe(payload) -> StructuredRecipe``.

Une fois figé, D2 (``validate_recipe``), D3 (``to_cooklang``) et D4
(``to_markdown``) importeront ce module en **LECTURE SEULE**
(``from app.generator.models import StructuredRecipe, ...``) sans le redéfinir.

Module PUR (archi §3.1) :
  - n'importe NI ``anthropic`` NI aucune autre couche métier au runtime ;
  - aucune I/O, aucun ``random``, aucun appel horloge.

Conventions (alignées sur ``app/knowledge/loader.py`` / ``app/scaling/table.py``) :
  - ``from __future__ import annotations`` ; type hints PEP 585 ;
  - docstrings FR (accents corrects) ; identifiants/champs en anglais snake_case ;
  - dataclasses stdlib ``@dataclass(frozen=True)`` (PAS de Pydantic — réservé à
    l'API web E1, archi §9.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
# Le CONTRAT figé — 8 dataclasses stdlib `frozen` (VERBATIM, archi §4.4/§6.1). #
# Champs, types PEP 585, valeurs par défaut et `frozen=True` ne doivent PAS    #
# changer : D2/D3/D4 en dépendent en lecture seule.                            #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Quantity:
    """Un ingrédient quantifié de la recette (avant scaling couche 3).

    ``name`` est le libellé FR affichable (ex. « huile d'olive »). ``fixed=True``
    matérialise un verrou ``=`` Cooklang (quantité/température non scalée, archi
    §8.4) — consommé par D3.
    """

    name: str            # nom FR affichable, ex. "huile d'olive"
    amount: float
    unit: str
    fixed: bool = False  # True => verrou '=' (quantité/température fixe)


@dataclass(frozen=True)
class Temperature:
    """Une température citée dans une étape, étiquetée par sa nature.

    ``label`` ∈ {« SÉCURITÉ », « TECHNIQUE », « PRÉFÉRENCE »} (étiquetage de la
    barrière 1, archi §6.1). ``unit`` ∈ {« C », « F »}.
    """

    value: float
    unit: str            # "C" | "F"
    label: str           # "SÉCURITÉ" | "TECHNIQUE" | "PRÉFÉRENCE"


@dataclass(frozen=True)
class Duration:
    """Une durée citée dans une étape.

    ``unit`` privilégie « minute » pour rester compatible avec le scaling
    géométrique du temps (couche 3).
    """

    value: float
    unit: str            # "minute" | "heure" (minutes pour le scaling couche 3)


@dataclass(frozen=True)
class Step:
    """Une étape rédigée de la recette (consigne étiquetée).

    ``cookware``/``temperatures``/``durations`` sont des tuples (immuables,
    hashables) ; ``technique_id`` relie l'étape à une technique de la base
    (couche 2) lorsque pertinent.
    """

    text: str                                  # consigne rédigée, étiquetée
    cookware: tuple[str, ...] = ()
    temperatures: tuple[Temperature, ...] = ()
    durations: tuple[Duration, ...] = ()
    technique_id: str | None = None


@dataclass(frozen=True)
class StructuredRecipe:
    """Recette structurée produite par le LLM (sortie JSON parsée, D10).

    ``servings`` = portions de **BASE** (le scaling de la couche 3 s'applique
    APRÈS la rédaction, archi §7). ``ingredients``/``steps`` sont des tuples.
    """

    title: str
    servings: int                              # portions de BASE (scaling appliqué après, archi §7)
    ingredients: tuple[Quantity, ...]
    steps: tuple[Step, ...]
    techniques: tuple[str, ...] = ()           # ids de techniques utilisées
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConstrainedPrompt:
    """Prompt contraint assemblé par ``build_prompt`` (barrière 1, archi §6.1).

    ``system``/``user`` sont les deux messages du prompt. Les trois frozensets
    servent la traçabilité et la validation aval (D2) : valeurs de température
    autorisées (extraites de la base), ustensiles requis autorisés, et ustensiles
    interdits par les contraintes utilisateur.
    """

    system: str
    user: str
    allowed_temperatures: frozenset[float] = frozenset()   # valeurs autorisées (traçabilité/validation)
    allowed_cookware: frozenset[str] = frozenset()
    forbidden_cookware: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Violation:
    """Une violation détectée par la validation déterministe (D2, archi §6.2).

    ``kind`` est une clé stable (ex. « temperature_hors_base »,
    « securite_proteine », « cookware_interdit ») ; ``severity`` ∈
    {« critical », « warning »}.
    """

    kind: str            # "temperature_hors_base" | "securite_proteine" | "cookware_interdit"
    detail: str
    severity: str        # "critical" | "warning"


@dataclass(frozen=True)
class ValidationResult:
    """Résultat de la validation déterministe d'une recette (D2, archi §6.2).

    ``ok=False`` déclenche la boucle rejet→retry de ``generate_recipe`` (1 max) ;
    ``feedback`` porte le message ciblé réinjecté au LLM lors du retry.
    """

    ok: bool
    violations: tuple[Violation, ...] = ()
    feedback: str = ""   # feedback ciblé pour le retry (consommé par client.generate_recipe)


# --------------------------------------------------------------------------- #
# Helper de parsing JSON -> StructuredRecipe (décision D1 : fonction de        #
# module ici, près du contrat, plutôt que `@staticmethod` de ValidationResult  #
# — le parsing n'a pas de rapport sémantique avec la validation).              #
# PUR et tolérant (clés manquantes -> défauts sûrs) ; sans dépendance externe. #
# --------------------------------------------------------------------------- #


def _coerce_float(value: object, default: float = 0.0) -> float:
    """Convertit ``value`` en ``float`` de façon tolérante (défaut sûr sinon)."""
    if isinstance(value, bool):
        # bool est une sous-classe d'int : on l'écarte explicitement.
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default


def _coerce_int(value: object, default: int = 0) -> int:
    """Convertit ``value`` en ``int`` de façon tolérante (défaut sûr sinon)."""
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip()))
        except ValueError:
            return default
    return default


def _coerce_str_tuple(value: object) -> tuple[str, ...]:
    """Convertit une liste/valeur en tuple de chaînes (tolérant)."""
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return ()


def _parse_quantity(payload: object) -> Quantity:
    """Construit une ``Quantity`` à partir d'un dict tolérant."""
    data = payload if isinstance(payload, dict) else {}
    return Quantity(
        name=str(data.get("name", "")),
        amount=_coerce_float(data.get("amount")),
        unit=str(data.get("unit", "")),
        fixed=bool(data.get("fixed", False)),
    )


def _parse_temperature(payload: object) -> Temperature:
    """Construit une ``Temperature`` à partir d'un dict tolérant."""
    data = payload if isinstance(payload, dict) else {}
    return Temperature(
        value=_coerce_float(data.get("value")),
        unit=str(data.get("unit", "C")),
        label=str(data.get("label", "TECHNIQUE")),
    )


def _parse_duration(payload: object) -> Duration:
    """Construit une ``Duration`` à partir d'un dict tolérant."""
    data = payload if isinstance(payload, dict) else {}
    return Duration(
        value=_coerce_float(data.get("value")),
        unit=str(data.get("unit", "minute")),
    )


def _parse_step(payload: object) -> Step:
    """Construit une ``Step`` (avec ses tuples imbriqués) à partir d'un dict."""
    data = payload if isinstance(payload, dict) else {}
    temperatures = data.get("temperatures", [])
    durations = data.get("durations", [])
    technique_id = data.get("technique_id")
    return Step(
        text=str(data.get("text", "")),
        cookware=_coerce_str_tuple(data.get("cookware", [])),
        temperatures=tuple(
            _parse_temperature(t) for t in (temperatures if isinstance(temperatures, list) else [])
        ),
        durations=tuple(
            _parse_duration(d) for d in (durations if isinstance(durations, list) else [])
        ),
        technique_id=str(technique_id) if technique_id is not None else None,
    )


def parse_structured_recipe(payload: dict) -> StructuredRecipe:
    """Parse un dict (sortie LLM JSON, D10) en ``StructuredRecipe``.

    Tolérant aux clés manquantes (défauts sûrs) et pur (aucune I/O, aucune
    dépendance externe). Construit récursivement les tuples imbriqués
    (``Quantity``, ``Step`` -> ``Temperature``/``Duration``). Une entrée non-dict
    produit une recette vide cohérente plutôt qu'une exception, afin que le
    contrôle de validité incombe à la barrière 2 (``validate_recipe``, D2).

    Args:
        payload: dictionnaire issu du JSON structuré renvoyé par le LLM.

    Returns:
        Une ``StructuredRecipe`` (immuable) reflétant ``payload``.
    """
    data = payload if isinstance(payload, dict) else {}
    ingredients = data.get("ingredients", [])
    steps = data.get("steps", [])
    return StructuredRecipe(
        title=str(data.get("title", "")),
        servings=_coerce_int(data.get("servings"), default=1),
        ingredients=tuple(
            _parse_quantity(q) for q in (ingredients if isinstance(ingredients, list) else [])
        ),
        steps=tuple(_parse_step(s) for s in (steps if isinstance(steps, list) else [])),
        techniques=_coerce_str_tuple(data.get("techniques", [])),
        notes=_coerce_str_tuple(data.get("notes", [])),
    )


if __name__ == "__main__":
    # Sanity-check rapide : python -m app.generator.models
    recipe = parse_structured_recipe(
        {
            "title": "Spaghetti al pomodoro",
            "servings": 2,
            "ingredients": [{"name": "spaghetti", "amount": 200, "unit": "g"}],
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
        }
    )
    print(f"Recette : {recipe.title!r} ({recipe.servings} portions)")
    print(f"  ingrédients : {[q.name for q in recipe.ingredients]}")
    print(f"  étapes : {len(recipe.steps)} ; techniques : {recipe.techniques}")
