"""Intégration Claude API + boucle rejet→retry — SEUL point non-déterministe (D1).

``generate_recipe(prompt, complete=None, validate=None, max_retries=1) ->
StructuredRecipe`` : appelle le LLM (via la couture injectable ``complete``),
parse la sortie JSON en ``StructuredRecipe`` (helper ``parse_structured_recipe``
de ``models.py``) et — si un ``validate`` est fourni — applique la politique de
violation « rejet + 1 retry » (D9, archi §6.2) avant un échec propre.

C'est le **SEUL** module de la couche 4 qui importe ``anthropic`` (de façon
GARDÉE, patron ``app/main.py:11-14``). ``models.py``/``prompt.py`` restent purs.

Couture injectable (testabilité, archi §6.3 — R7 : aucun appel LLM en test) :
  - ``complete`` : callable ``(ConstrainedPrompt, feedback: str | None) ->
    dict | StructuredRecipe``. En test on injecte un FAUX ``complete`` (aucun
    réseau, aucune clé). Si ``complete is None``, le défaut ``_default_complete``
    appelle l'API Anthropic réelle (clé via ``ANTHROPIC_API_KEY``).
  - ``validate`` : callable optionnel ``(StructuredRecipe) -> ValidationResult``.
    INJECTÉ (pas importé) : D1 ne connaît PAS ``validate_recipe`` (D2). Le
    câblage réel ``validate=validate_recipe`` se fera côté E1/orchestrateur.

Politique de violation (D9, archi §6.2 point 5) : si ``validate`` renvoie
``ok=False``, on relance ``complete`` UNE fois (``max_retries=1`` par défaut) en
réinjectant le ``feedback`` ciblé ; si la 2ᵉ tentative viole encore -> exception
claire (``RecipeValidationError``). PAS de réparation silencieuse.

Règle inter-couches (archi §3.1) : aucun import runtime de ``app/epicure/``,
``app/knowledge/``, ``app/scaling/``. Seul ``app.generator.models`` (même couche)
est importé.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Callable

from app.generator.models import StructuredRecipe, parse_structured_recipe

# Import GARDÉ d'`anthropic` (patron app/main.py:11-14) — SEUL fichier de la
# couche 4 qui importe anthropic. Absence tolérée à l'import : seul l'appel réel
# (`_default_complete`) lèvera une erreur claire, jamais déclenchée en test.
try:
    import anthropic
except ImportError:  # dépendance non installée
    anthropic = None

if TYPE_CHECKING:  # annotations seulement
    from app.generator.models import ConstrainedPrompt, ValidationResult

# Modèle Anthropic par défaut (documenté ; surchargeable via ``req.model`` côté
# orchestrateur en passant un ``complete`` dédié). Modèle récent Claude.
DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_MAX_TOKENS = 4096

# Type de la couture LLM (sortie : dict JSON ou directement un StructuredRecipe).
CompleteFn = Callable[["ConstrainedPrompt", "str | None"], "dict | StructuredRecipe"]
ValidateFn = Callable[[StructuredRecipe], "ValidationResult"]


class RecipeGenerationError(RuntimeError):
    """Échec de génération LLM (dépendance/clé absente, appel API en échec).

    Traduite en 502/500 par l'API web (archi §9.1) côté E1.
    """


class RecipeValidationError(RuntimeError):
    """La recette viole encore les contraintes après le dernier retour autorisé.

    Levée après épuisement des retries (archi §6.2 : échec propre, pas de
    réparation silencieuse). Porte les ``violations``/``feedback`` du dernier
    ``ValidationResult`` pour traçabilité (502/500 côté API web).
    """

    def __init__(self, result: ValidationResult) -> None:
        self.result = result
        violations = "; ".join(
            f"{v.kind} ({v.severity}) : {v.detail}" for v in result.violations
        )
        message = (
            "La recette générée viole encore les contraintes après le retry "
            f"autorisé. Feedback : {result.feedback!r}."
        )
        if violations:
            message += f" Violations : {violations}."
        super().__init__(message)


def _default_complete(prompt: ConstrainedPrompt, feedback: str | None = None) -> dict:
    """Couture LLM par défaut : appel RÉEL à l'API Anthropic (jamais en test).

    Lève une ``RecipeGenerationError`` claire (FR) si la dépendance ``anthropic``
    est absente ou si ``ANTHROPIC_API_KEY`` n'est pas définie. Réinjecte le
    ``feedback`` ciblé (retry) en complément du prompt utilisateur, SANS muter le
    ``ConstrainedPrompt`` figé.

    Retourne le payload JSON (``dict``) parsé depuis la réponse du modèle.
    """
    if anthropic is None:
        raise RecipeGenerationError(
            "Dépendance `anthropic` absente : installez-la pour générer une "
            "recette (ou injectez un `complete` de test)."
        )
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RecipeGenerationError(
            "Variable d'environnement `ANTHROPIC_API_KEY` non définie : "
            "impossible d'appeler l'API Anthropic."
        )

    user_content = prompt.user
    if feedback:
        user_content = (
            f"{prompt.user}\n\n"
            f"CORRECTION DEMANDÉE (la tentative précédente a été rejetée) :\n{feedback}"
        )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=DEFAULT_MAX_TOKENS,
        system=prompt.system,
        messages=[{"role": "user", "content": user_content}],
    )
    text = "".join(
        getattr(block, "text", "") for block in response.content
    ).strip()
    try:
        return json.loads(text)
    except (ValueError, TypeError) as exc:
        raise RecipeGenerationError(
            "Réponse du modèle non parsable en JSON structuré."
        ) from exc


def _to_recipe(payload: dict | StructuredRecipe) -> StructuredRecipe:
    """Normalise la sortie de ``complete`` en ``StructuredRecipe``.

    Accepte directement un ``StructuredRecipe`` (faux ``complete`` typé) ou un
    ``dict`` JSON (cas réel / faux ``complete`` renvoyant du JSON), parsé via
    ``parse_structured_recipe``.
    """
    if isinstance(payload, StructuredRecipe):
        return payload
    return parse_structured_recipe(payload)


def generate_recipe(
    prompt: ConstrainedPrompt,
    complete: CompleteFn | None = None,
    validate: ValidateFn | None = None,
    max_retries: int = 1,
) -> StructuredRecipe:
    """Génère une recette structurée sous contraintes, avec retry borné.

    Flux : (1) ``complete(prompt, None)`` -> payload -> ``StructuredRecipe`` ;
    (2) si ``validate`` est ``None`` -> renvoyer la recette (une seule
    génération) ; (3) sinon ``validate(recipe)`` : si ``ok`` -> renvoyer ; sinon,
    tant que ``retries < max_retries``, relancer ``complete(prompt, feedback)``
    avec le ``feedback`` ciblé (SANS muter ``prompt``), reparser, revalider ;
    (4) épuisement -> ``RecipeValidationError`` (échec propre, archi §6.2).

    Args:
        prompt: le ``ConstrainedPrompt`` figé (produit par ``build_prompt``).
        complete: couture LLM injectable ``(prompt, feedback) -> dict |
            StructuredRecipe``. ``None`` -> appel Anthropic réel
            (``_default_complete``), JAMAIS déclenché en test.
        validate: callable ``(StructuredRecipe) -> ValidationResult`` injecté.
            ``None`` (défaut) -> aucune validation, une seule génération
            (découple D1 de D2).
        max_retries: nombre maximal de relances après rejet (défaut 1, R7).

    Returns:
        La ``StructuredRecipe`` validée (ou la première si ``validate is None``).

    Raises:
        RecipeGenerationError: dépendance/clé absente ou appel API en échec
            (uniquement via le ``complete`` par défaut).
        RecipeValidationError: violations persistantes après les retries.
    """
    fn = complete if complete is not None else _default_complete

    recipe = _to_recipe(fn(prompt, None))
    if validate is None:
        return recipe

    result = validate(recipe)
    if result.ok:
        return recipe

    retries = 0
    while retries < max_retries:
        retries += 1
        recipe = _to_recipe(fn(prompt, result.feedback))
        result = validate(recipe)
        if result.ok:
            return recipe

    # Échec propre : violations persistantes après le dernier retry autorisé.
    raise RecipeValidationError(result)


if __name__ == "__main__":
    # Sanity-check (FAUX `complete`, AUCUN réseau) : python -m app.generator.client
    from app.generator.models import ConstrainedPrompt as _CP

    def _fake_complete(_prompt: _CP, _feedback: str | None = None) -> dict:
        return {
            "title": "Spaghetti al pomodoro",
            "servings": 2,
            "ingredients": [{"name": "spaghetti", "amount": 200, "unit": "g"}],
            "steps": [{"text": "[TECHNIQUE] Cuire al dente.", "technique_id": "pasta_al_dente"}],
            "techniques": ["pasta_al_dente"],
        }

    demo_prompt = _CP(system="(système)", user="(utilisateur)")
    recipe = generate_recipe(demo_prompt, complete=_fake_complete)
    print(f"Recette (sans réseau) : {recipe.title!r} ({recipe.servings} portions)")
    print(f"  étapes : {[s.text for s in recipe.steps]}")
