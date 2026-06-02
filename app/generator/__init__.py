"""Couche 4 — Generateur LLM sous contraintes + sortie Cooklang.

Cette couche orchestre le LLM (Claude API) en REDACTEUR sous contraintes : il
CHOISIT dans la base (associations couche 1, techniques/temperatures couche 2,
securite) et n'invente jamais une temperature ni une technique (FR3, OA2). La
sortie est ensuite VALIDEE (garde-fou deterministe, D2) puis emise en `.cook`
(D3) et en Markdown lisible (D4).

Regle inter-couches STRICTE (archi 3.1) : `app/generator/` N'IMPORTE NI
`app/epicure/`, NI `app/knowledge/`, NI `app/scaling/` au runtime. Les sorties
des couches 1/2/3 arrivent EN PARAMETRES (neighbors, techniques, safety,
forbidden, scaling_notes). Les annotations de type vers ces couches passent par
`if TYPE_CHECKING:` uniquement. `anthropic` est la SEULE dependance nouvelle,
importee de facon GARDEE et UNIQUEMENT dans `client.py`.

API publique (assemblee ici par l'orchestrateur apres livraison des stories) :
  - Contrat de donnees partage (D1, `models.py`) : `Quantity`, `Temperature`,
    `Duration`, `Step`, `StructuredRecipe`, `ConstrainedPrompt`, `Violation`,
    `ValidationResult` (dataclasses stdlib `frozen`) + `parse_structured_recipe`.
  - `build_prompt(req, neighbors, techniques, safety, forbidden)` (D1,
    `prompt.py`) -> `ConstrainedPrompt`. PUR/deterministe (barriere 1, archi 6.1).
  - `generate_recipe(prompt, complete=..., validate=..., max_retries=1)` (D1,
    `client.py`) -> `StructuredRecipe`. SEUL point non-deterministe ; couture
    `complete` injectable (tests sans reseau ni cle) ; boucle rejet->retry
    (1 max) + echec propre (`RecipeValidationError`, D9/archi 6.2).
  - `validate_recipe(recipe, techniques, safety, forbidden=...)` (D2,
    `validate.py`) -> `ValidationResult`. Garde-fou DETERMINISTE (barriere 2,
    archi 6.2) : aucune temperature/technique hors base, securite proteines
    (minima USDA `critical:true`), `#cookware` interdit. PUR (pas de retry, pas
    de reparation silencieuse) ; n'importe AUCUNE autre couche au runtime.
  - `to_cooklang(recipe, scaling_notes)` (D3, `cooklang.py`) -> str : emission
    `.cook` par templating maison (marqueurs `@`/`#`/`~`, verrou `=`, notes `--`)
    apres scaling (archi 7/8.4). `validate_cooklang(text)` : validation regex
    (fallback RZ5, AUCUNE dependance cooklang-py ; D5/archi 8.4/12).
  - `to_markdown(recipe)` (D4, `markdown.py`) -> str : rendu Markdown LISIBLE
    (titre, portions, ingredients, etapes numerotees) avec etiquettes
    [SECURITE]/[TECHNIQUE]/[PREFERENCE] et temperatures de securite VISIBLES
    (vitrine d'explicabilite, archi 9.2). PUR/deterministe, 1 parametre (4.4).
"""

from __future__ import annotations

from app.generator.client import (
    RecipeGenerationError,
    RecipeValidationError,
    generate_recipe,
)
from app.generator.cooklang import to_cooklang, validate_cooklang
from app.generator.markdown import to_markdown
from app.generator.models import (
    ConstrainedPrompt,
    Duration,
    Quantity,
    Step,
    StructuredRecipe,
    Temperature,
    ValidationResult,
    Violation,
    parse_structured_recipe,
)
from app.generator.prompt import LLM_CONSTRAINTS, build_prompt
from app.generator.validate import validate_recipe

__all__ = [
    "ConstrainedPrompt",
    "Duration",
    "LLM_CONSTRAINTS",
    "Quantity",
    "RecipeGenerationError",
    "RecipeValidationError",
    "Step",
    "StructuredRecipe",
    "Temperature",
    "ValidationResult",
    "Violation",
    "build_prompt",
    "generate_recipe",
    "parse_structured_recipe",
    "to_cooklang",
    "to_markdown",
    "validate_cooklang",
    "validate_recipe",
]
