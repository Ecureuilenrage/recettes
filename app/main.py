"""Backend FastAPI + pipeline d'assemblage — story E1 (couche web, archi §9).

``app/main.py`` est l'ASSEMBLEUR : le SEUL module autorisé à importer les quatre
couches métier (archi §3.1, règle ``main → {1, 2, 3, 4}``). Il ne contient
**aucune logique métier** : il ORCHESTRE (câble le pipeline bout-en-bout, archi
§7) et TRADUIT les erreurs des couches en codes HTTP (archi §9.1). Toute la
matière (associations, techniques, sécurité, scaling, rédaction LLM) provient des
couches appelées ; E1 se contente de la glu d'orchestration (autorisée ici).

Le cœur TESTABLE est ``run_pipeline(request, *, complete=None, index=None)`` :
une fonction pure d'orchestration appelable SANS HTTP, SANS appel LLM réel et
SANS clé/fichier de données (R7), grâce aux coutures injectables ``complete``
(couche 4) et ``index`` (couche 1). L'endpoint ``POST /generate`` n'est qu'une
enveloppe MINCE par-dessus ``run_pipeline`` qui mappe ses exceptions en
``HTTPException`` (422 / 502 / 500). ``GET /health`` est conservé.

Imports GARDÉS (patron historique du squelette) : ``fastapi`` et ``pydantic``
sont importés de façon tolérante (``try/except ImportError``). Si ``pydantic`` est
absent, un fallback en dataclasses stdlib préserve la testabilité de
``run_pipeline`` ; si ``fastapi`` est absent, seuls les endpoints HTTP sont
désactivés (``run_pipeline`` reste appelable).

Conventions : ``from __future__ import annotations`` ; type hints PEP 585 ;
docstrings/commentaires FR (accents corrects) ; identifiants/clés en anglais
snake_case ; UTF-8 sans BOM ; fins de ligne LF.

Lancement (une fois ``fastapi``/``uvicorn`` installés) :
    uvicorn app.main:app --reload
"""

from __future__ import annotations

import dataclasses
from typing import Any, Callable

# --------------------------------------------------------------------------- #
# Les quatre couches métier (archi §3.1 : E1 = SEUL module qui les importe).   #
# Les couches ne s'importent JAMAIS entre elles ; ici, on les assemble.        #
# --------------------------------------------------------------------------- #
from app.epicure import (
    Constraints as EpicureConstraints,
    EpicureIndex,
    filter_neighbors,
    translate,
)
from app.generator import (
    RecipeGenerationError,
    RecipeValidationError,
    StructuredRecipe,
    build_prompt,
    generate_recipe,
    to_cooklang,
    to_markdown,
    validate_recipe,
)
from app.knowledge import (
    Constraints as KnowledgeConstraints,
    excluded_techniques,
    forbidden_cookware,
    load_cuisines,
    load_safety,
    safety_for,
    techniques_for,
)
from app.scaling import ScaledQuantity, scale, scale_eggs

# --------------------------------------------------------------------------- #
# Import GARDÉ de pydantic (patron du squelette historique). Absence tolérée : #
# `run_pipeline` reste testable sans pydantic (fallback dataclasses stdlib).   #
# --------------------------------------------------------------------------- #
try:
    from pydantic import BaseModel, Field
except ImportError:  # pydantic non installé -> dégradation propre
    BaseModel = None
    Field = None

# --------------------------------------------------------------------------- #
# Import GARDÉ de fastapi (patron `app/main.py:11-14` d'origine). Absence       #
# tolérée : seuls les endpoints HTTP sont désactivés (run_pipeline reste OK).  #
# --------------------------------------------------------------------------- #
try:
    from fastapi import Depends, FastAPI, Form, HTTPException, Request
    from fastapi.responses import HTMLResponse
except ImportError:  # dépendances web non encore installées
    Depends = None
    FastAPI = None
    Form = None
    HTTPException = None
    Request = None
    HTMLResponse = None

# --------------------------------------------------------------------------- #
# Import GARDÉ de jinja2 via `fastapi.templating` (UI E2, archi §9.2). Absence  #
# tolérée : seules les pages HTML sont désactivées (l'API JSON E1 et le helper  #
# pur `build_view_context` restent disponibles/testables sans jinja2).         #
# --------------------------------------------------------------------------- #
try:
    from fastapi.templating import Jinja2Templates
except ImportError:  # jinja2 non installé -> UI HTML désactivée, reste OK
    Jinja2Templates = None


# --------------------------------------------------------------------------- #
# Schémas (archi §9.1). Sous pydantic si disponible ; sinon dataclasses        #
# stdlib équivalentes (mêmes champs/défauts) pour que run_pipeline reste       #
# testable hors API. Les deux variantes exposent les mêmes attributs.          #
# --------------------------------------------------------------------------- #

DEFAULT_CUISINE = "italian_savory_v1"
DEFAULT_MODEL = "cooc"
# Nombre de voisins demandés à l'index Epicure (archi §7 : `neighbors(hero, k)`).
NEIGHBORS_K = 6


if BaseModel is not None:  # ---- Variante Pydantic (API web, archi §9.1) ----

    class Constraints(BaseModel):
        """Contraintes utilisateur (archi §9.1)."""

        diet: list[str] = Field(default_factory=list)
        no_cookware: list[str] = Field(default_factory=list)
        highlight: str | None = None

    class GenerationRequest(BaseModel):
        """Requête de génération (archi §9.1 ``POST /generate``)."""

        hero: str
        cuisine: str = DEFAULT_CUISINE
        constraints: Constraints = Field(default_factory=lambda: Constraints())
        servings: int
        model: str = DEFAULT_MODEL

    class DebugInfo(BaseModel):
        """Panneau debug (FR7) : les 4 sections de l'explicabilité (archi §9.1)."""

        epicure: dict
        scaling: list[dict]
        techniques: list[dict] | dict
        validation: dict

    class GenerationResponse(BaseModel):
        """Réponse de génération (archi §9.1) : ``.cook`` + Markdown + debug."""

        cooklang: str
        markdown: str
        debug: DebugInfo

else:  # ---- Fallback dataclasses stdlib (pydantic absent) ----

    @dataclasses.dataclass
    class Constraints:  # type: ignore[no-redef]
        """Contraintes utilisateur (fallback dataclass, mêmes champs §9.1)."""

        diet: list[str] = dataclasses.field(default_factory=list)
        no_cookware: list[str] = dataclasses.field(default_factory=list)
        highlight: str | None = None

    @dataclasses.dataclass
    class GenerationRequest:  # type: ignore[no-redef]
        """Requête de génération (fallback dataclass, mêmes champs §9.1)."""

        hero: str
        servings: int
        cuisine: str = DEFAULT_CUISINE
        constraints: "Constraints" = dataclasses.field(default_factory=lambda: Constraints())
        model: str = DEFAULT_MODEL

    @dataclasses.dataclass
    class DebugInfo:  # type: ignore[no-redef]
        """Panneau debug (fallback dataclass, mêmes champs §9.1)."""

        epicure: dict
        scaling: list[dict]
        techniques: "list[dict] | dict"
        validation: dict

    @dataclasses.dataclass
    class GenerationResponse:  # type: ignore[no-redef]
        """Réponse de génération (fallback dataclass, mêmes champs §9.1)."""

        cooklang: str
        markdown: str
        debug: "DebugInfo"


# --------------------------------------------------------------------------- #
# Hiérarchie d'exceptions d'orchestration (PAS de dépendance fastapi ici).     #
# `run_pipeline` lève ces exceptions ; l'enveloppe HTTP les mappe en codes.    #
# --------------------------------------------------------------------------- #


class PipelineError(Exception):
    """Erreur d'orchestration du pipeline (classe de base)."""


class PipelineInputError(PipelineError):
    """Entrée invalide -> 422 (héros hors vocab, cuisine inconnue, archi §9.1)."""


class PipelineGenerationError(PipelineError):
    """Échec LLM / violation persistante après retry -> 502 (archi §6.2/§9.1)."""


# --------------------------------------------------------------------------- #
# Helpers d'orchestration (glu E1 : lecture souple de la requête, conversion   #
# des `Constraints` web vers les `Constraints` propres aux couches 1 et 2).    #
# AUCUNE logique métier : uniquement de l'adaptation entre types.              #
# --------------------------------------------------------------------------- #


def _req_get(request: object, key: str, default: object = None) -> Any:
    """Lit ``key`` sur ``request`` qu'il soit un dict ou un objet (duck-typing)."""
    if isinstance(request, dict):
        return request.get(key, default)
    return getattr(request, key, default)


def _read_constraints(request: object) -> tuple[list[str], list[str], str | None]:
    """Extrait ``(diet, no_cookware, highlight)`` de la requête (souple)."""
    raw = _req_get(request, "constraints", None)
    if raw is None:
        return [], [], None
    diet = list(_req_get(raw, "diet", []) or [])
    no_cookware = list(_req_get(raw, "no_cookware", []) or [])
    highlight = _req_get(raw, "highlight", None)
    return diet, no_cookware, highlight


def _is_egg(name: str) -> bool:
    """True si l'ingrédient est un œuf (nom contenant « oeuf »/« œuf »).

    Insensible à la casse et à la graphie « œ »/« oe » (décision documentée :
    le scaling discret des œufs, couche 3, ne s'applique qu'aux œufs).
    """
    lowered = name.lower().replace("œ", "oe")
    return "oeuf" in lowered


# --------------------------------------------------------------------------- #
# Le CŒUR testable : run_pipeline (câble les couches dans l'ordre archi §7).   #
# --------------------------------------------------------------------------- #


def run_pipeline(
    request: object,
    *,
    complete: Callable | None = None,
    index: object | None = None,
) -> "GenerationResponse":
    """Assemble le pipeline complet de génération (archi §7), sans HTTP ni clé.

    Câble les quatre couches dans l'ordre du flux bout-en-bout (archi §7) ;
    n'effectue AUCUN calcul métier lui-même (il appelle les fonctions des
    couches). Testable HORS HTTP et HORS API : injecter ``complete`` (faux
    rédacteur LLM) et ``index`` (faux index Epicure) suffit — aucun appel réseau,
    aucune clé, aucun fichier de données requis (R7).

    Étapes (archi §7) :
      (a) ``translate(hero)`` -> clé Epicure (``KeyError`` -> 422) ;
      (b) cuisine ∈ ``load_cuisines()`` (sinon -> 422 « cuisine inconnue ») ;
      (c) ``index.neighbors(clé, k)`` -> voisins bruts (``KeyError`` -> 422 ;
          ``index`` paresseux ``EpicureIndex(model)`` si non injecté) ;
      (d) ``filter_neighbors(...)`` -> ``FilteredNeighbors`` (couche 1) ;
      (e) couche 2 : ``techniques_for`` / ``forbidden_cookware`` / sécurité ;
      (f) ``build_prompt(...)`` -> prompt contraint (couche 4) ;
      (g) ``generate_recipe(prompt, complete=..., validate=...)`` -> recette
          (``RecipeGenerationError``/``RecipeValidationError`` -> 502) ;
      (h) scaling APRÈS rédaction : ``k = servings / recipe.servings`` ; pour
          chaque ingrédient, ``scale_eggs`` (œuf) ou ``scale(...)`` (couche 3) ;
          construction d'UNE recette scalée canonique (``servings`` CIBLE + TOUS
          les ingrédients scalés, œufs inclus) ;
      (i) ``to_cooklang(recette_canonique, scaling_notes=...)`` +
          ``to_markdown(recette_canonique)`` — MÊME recette pour les deux ;
      (j) ``DebugInfo`` (epicure / scaling / techniques / validation).

    Cohérence des deux artefacts (corrige les 2 majeurs de la revue E1) :
    ``.cook`` et Markdown sont émis depuis la MÊME recette scalée canonique. Cette
    recette porte ``servings = request.servings`` (portions CIBLE) et des
    ingrédients DÉJÀ scalés (œufs compris, valeur entière issue de ``scale_eggs``).
    Les ``scaling_notes`` passées à ``to_cooklang`` couvrent TOUS les ingrédients
    (un ``ScaledQuantity`` est synthétisé pour l'œuf à partir de la valeur entière
    scalée + la note de reliquat RZ1) : chaque ``ScaledQuantity.value`` est aligné
    sur l'``amount`` de l'ingrédient canonique correspondant, donc AUCUN double
    scaling — les notes ``--`` (réserve 10 %, contenant, reliquat œufs) et les
    unités/verrous sont portés par ``scaling_notes`` sans rejouer le calcul.

    Args:
        request: requête de génération (objet Pydantic/dataclass ou dict)
            exposant ``hero``/``cuisine``/``constraints``/``servings``/``model``.
        complete: couture LLM injectable (couche 4) ``(prompt, feedback) ->
            dict | StructuredRecipe``. ``None`` -> appel Anthropic réel (jamais
            en test). Permet un faux rédacteur déterministe et offline.
        index: objet exposant ``.neighbors(name, k) -> list[tuple[str, float]]``.
            ``None`` -> instanciation paresseuse de ``EpicureIndex(model)``.

    Returns:
        Une ``GenerationResponse`` (``cooklang`` + ``markdown`` + ``debug``).

    Raises:
        PipelineInputError: entrée invalide (héros hors vocab, cuisine inconnue,
            héros absent de l'index Epicure).
        PipelineGenerationError: échec LLM ou violations persistantes (retry).
    """
    hero = str(_req_get(request, "hero", ""))
    cuisine = str(_req_get(request, "cuisine", DEFAULT_CUISINE))
    servings = int(_req_get(request, "servings", 1))
    model = str(_req_get(request, "model", DEFAULT_MODEL))
    diet, no_cookware, highlight = _read_constraints(request)

    # (a) Traduction FR -> clé Epicure (couche 1). Terme hors vocab -> 422.
    try:
        hero_key = translate(hero)
    except KeyError as exc:
        raise PipelineInputError(
            f"Héros « {hero} » inconnu du vocabulaire FR→Epicure : {exc}"
        ) from exc

    # (b) Vérifier que la cuisine existe (couche 2). Inconnue -> 422.
    cuisines = load_cuisines()
    if cuisine not in cuisines:
        raise PipelineInputError(
            f"Cuisine inconnue : « {cuisine} » (cuisines disponibles : "
            f"{sorted(cuisines)})."
        )

    # (c) Voisins bruts via l'index Epicure (couche 1). Index paresseux si non
    # injecté (en test on injecte un faux index : aucun fichier requis).
    if index is None:
        index = EpicureIndex(model)
    try:
        raw_neighbors = index.neighbors(hero_key, NEIGHBORS_K)
    except KeyError as exc:
        raise PipelineInputError(
            f"Héros « {hero} » (clé {hero_key!r}) absent du vocabulaire Epicure : {exc}"
        ) from exc

    # (d) Filtrage cuisine (souple) + régime (rejet dur) -> FilteredNeighbors.
    epicure_constraints = EpicureConstraints(
        diet=diet, no_cookware=no_cookware, highlight=highlight
    )
    filtered = filter_neighbors(list(raw_neighbors), cuisine, epicure_constraints)

    # (e) Couche 2 : techniques autorisées, cookware interdit, sécurité.
    knowledge_constraints = KnowledgeConstraints(
        diet=diet, no_cookware=no_cookware, highlight=highlight
    )
    techniques = techniques_for(cuisine, hero, knowledge_constraints)
    forbidden = forbidden_cookware(cuisine, knowledge_constraints)
    # Sécurité : ligne applicable au héros si protéine, sinon table complète
    # (le générateur cite la (les) ligne(s) pertinente(s) ; le validateur s'appuie
    # sur la table pour autoriser les minima de sécurité).
    safety = load_safety()

    # (f) Prompt contraint (couche 4, barrière 1). On enrichit la requête avec la
    # clé Epicure traduite, sans muter l'objet d'origine.
    prompt_req = {
        "hero": hero,
        "cuisine": cuisine,
        "servings": servings,
        "highlight": highlight,
    }
    prompt = build_prompt(
        prompt_req,
        neighbors=filtered.kept,
        techniques=techniques,
        safety=safety,
        forbidden=forbidden,
    )

    # (g) Rédaction LLM + validation déterministe (barrière 2) avec retry borné.
    forbidden_frozen = frozenset(forbidden)

    def _validate(recipe: StructuredRecipe):
        return validate_recipe(recipe, techniques, safety, forbidden_frozen)

    try:
        recipe = generate_recipe(
            prompt,
            complete=complete,
            validate=_validate,
            max_retries=1,
        )
    except (RecipeValidationError, RecipeGenerationError) as exc:
        raise PipelineGenerationError(
            f"Échec de génération de la recette (LLM ou validation) : {exc}"
        ) from exc

    # (h) Scaling APRÈS rédaction (couche 3) : k = portions cible / portions base.
    base_servings = recipe.servings if recipe.servings else 1
    k = servings / base_servings

    # `scaled_quantities` couvre TOUS les ingrédients (œufs inclus) : c'est la
    # liste `scaling_notes` passée à `to_cooklang`. Chaque `ScaledQuantity.value`
    # est aligné sur l'`amount` de l'ingrédient canonique correspondant (mêmes
    # valeurs scalées) -> aucun double scaling.
    scaled_quantities: list[object] = []
    scaling_debug: list[dict] = []
    scaled_ingredients: list[object] = []

    for qty in recipe.ingredients:
        if _is_egg(qty.name):
            # Œuf : scaling discret (unité non sécable + reste, RZ1). La valeur
            # ENTIÈRE scalée devient l'`amount` de l'ingrédient canonique ET la
            # `value` d'un `ScaledQuantity` synthétisé (même valeur, aucun double
            # scaling) afin que le .cook reflète EXACTEMENT le Markdown. La note de
            # reliquat RZ1 est portée par les `notes` (émise en `--` dans le .cook)
            # et conservée dans le debug.
            eggs = scale_eggs(qty.amount, k)
            scaled_value = float(eggs.whole_eggs)
            scaled_quantities.append(
                ScaledQuantity(
                    name=qty.name,
                    value=scaled_value,
                    unit=qty.unit,
                    type=eggs.type,
                    fixed=bool(qty.fixed),
                    notes=[eggs.note] if eggs.note else [],
                    debug=dict(eggs.debug or {}),
                )
            )
            scaling_debug.append(
                {
                    "name": qty.name,
                    "type": eggs.type,
                    "coeff": None,
                    "formula": "discrete (round down, RZ1)",
                    "reasoning": eggs.note,
                    "value": scaled_value,
                }
            )
            scaled_ingredients.append(
                dataclasses.replace(qty, amount=scaled_value)
            )
        else:
            scaled = scale(qty.name, qty.amount, qty.unit, k)
            scaled_quantities.append(scaled)
            debug = scaled.debug or {}
            scaling_debug.append(
                {
                    "name": scaled.name,
                    "type": scaled.type,
                    "coeff": debug.get("coeff"),
                    "formula": debug.get("formula"),
                    "reasoning": debug.get("reasoning"),
                    "value": scaled.value,
                }
            )
            scaled_ingredients.append(
                dataclasses.replace(qty, amount=scaled.value, unit=scaled.unit)
            )

    # Recette scalée CANONIQUE (source de vérité UNIQUE pour les DEUX émetteurs) :
    # `servings` = portions CIBLE (request.servings) + TOUS les ingrédients scalés
    # (œufs inclus). Corrige les 2 majeurs de la revue : portions cohérentes
    # (frontmatter .cook == ligne « Portions » Markdown) et œufs cohérents
    # (.cook == Markdown). Le reste (étapes, techniques, notes) est inchangé.
    canonical_recipe = dataclasses.replace(
        recipe, servings=servings, ingredients=tuple(scaled_ingredients)
    )

    # (i) Émissions depuis la MÊME recette canonique : .cook (avec les notes de
    # scaling de TOUS les ingrédients) + Markdown. Les `scaling_notes` portent les
    # mêmes valeurs scalées que les ingrédients canoniques (aucun double scaling) ;
    # elles ajoutent les notes `--` (réserve, contenant, reliquat œufs) et les
    # unités/verrous au .cook.
    cooklang = to_cooklang(canonical_recipe, scaling_notes=scaled_quantities)
    markdown = to_markdown(canonical_recipe)

    # (j) DebugInfo : les 4 sections du panneau (FR7).
    kept_ids = [getattr(t, "id", "") for t in techniques]
    exclusions = excluded_techniques(cuisine, hero, knowledge_constraints)
    techniques_debug = {
        "kept": kept_ids,
        "excluded": [
            {
                "technique_id": ex.technique_id,
                "forbidden_tool": ex.forbidden_tool,
                "via_constraint": ex.via_constraint,
            }
            for ex in exclusions
        ],
    }

    # Validation déterministe rejouée pour le panneau (sérialisable).
    validation_result = _validate(recipe)
    validation_debug = {
        "ok": validation_result.ok,
        "violations": [
            {
                "kind": v.kind,
                "detail": v.detail,
                "severity": v.severity,
            }
            for v in validation_result.violations
        ],
        "feedback": validation_result.feedback,
    }

    debug = DebugInfo(
        epicure=filtered.to_debug(),
        scaling=scaling_debug,
        techniques=techniques_debug,
        validation=validation_debug,
    )
    return GenerationResponse(cooklang=cooklang, markdown=markdown, debug=debug)


# --------------------------------------------------------------------------- #
# Enveloppe FastAPI MINCE (sous garde `if FastAPI is not None`). Aucune logique #
# métier : appelle run_pipeline et traduit ses exceptions en HTTPException.    #
# Coutures d'injection surchargeables via `app.dependency_overrides` (tests).  #
# --------------------------------------------------------------------------- #

# Valeurs par défaut des coutures (None -> run_pipeline instancie/appelle réel).
_DEFAULT_INDEX: object | None = None
_DEFAULT_COMPLETE: Callable | None = None


def get_index() -> object | None:
    """Couture d'injection de l'index Epicure (surchargeable en test).

    Retourne ``None`` par défaut (``run_pipeline`` instancie alors paresseusement
    ``EpicureIndex``). Les tests TestClient surchargent cette dépendance via
    ``app.dependency_overrides[get_index]`` pour injecter un faux index (aucun
    fichier de données requis).
    """
    return _DEFAULT_INDEX


def get_complete() -> Callable | None:
    """Couture d'injection du rédacteur LLM (surchargeable en test).

    Retourne ``None`` par défaut (appel Anthropic réel via ``generate_recipe``).
    Les tests surchargent ``app.dependency_overrides[get_complete]`` pour injecter
    un faux ``complete`` déterministe (aucun réseau, aucune clé — R7).
    """
    return _DEFAULT_COMPLETE


# --------------------------------------------------------------------------- #
# UI minimale (story E2, archi §9.2). Helper PUR `build_view_context` testable  #
# SANS jinja2/fastapi : transforme une `GenerationResponse` (ou un message      #
# d'erreur) en dict de contexte pour le template. Aucune logique métier ici :   #
# uniquement de l'APLATISSEMENT/présentation des données déjà produites par     #
# `run_pipeline` (E1, LECTURE SEULE). Les templates ne portent QUE de la        #
# présentation. Le panneau debug expose les 4 sections de `DebugInfo` (FR7) :   #
# c'est la VITRINE portfolio de l'explicabilité (§9.2).                         #
# --------------------------------------------------------------------------- #

# Valeurs par défaut du formulaire (réutilisées par la vue et les templates).
DEFAULT_FORM = {
    "hero": "",
    "cuisine": DEFAULT_CUISINE,
    "diet": "",
    "no_cookware": "",
    "highlight": "",
    "servings": 4,
    "model": DEFAULT_MODEL,
}

# Libellés FR des 4 sections du panneau debug (présentation §9.2). Les clés
# anglaises (`epicure`/`scaling`/`techniques`/`validation`) restent les
# identifiants stables consommés par le template ; ces libellés sont l'habillage.
DEBUG_SECTION_LABELS = {
    "epicure": "Épicure — voisins retenus / rejetés",
    "scaling": "Scaling — par ingrédient (type, coefficient, raisonnement)",
    "techniques": "Techniques — retenues / exclues",
    "validation": "Validation — garde-fou déterministe (sécurité)",
}


def _debug_to_dict(debug: object) -> dict:
    """Normalise un ``DebugInfo`` (pydantic ou dataclass) en dict aplati.

    Lecture souple (duck-typing) : qu'il s'agisse du modèle Pydantic ou du
    fallback dataclass, on récupère les 4 sections sous forme de structures
    Python natives (sérialisables) pour le template. AUCUN recalcul : on relit
    ce que ``run_pipeline`` a déjà produit.
    """
    return {
        "epicure": _req_get(debug, "epicure", {}) or {},
        "scaling": list(_req_get(debug, "scaling", []) or []),
        "techniques": _req_get(debug, "techniques", {}) or {},
        "validation": _req_get(debug, "validation", {}) or {},
    }


def build_view_context(
    result: object,
    *,
    form: dict | None = None,
    error: str | None = None,
) -> dict:
    """Prépare le dict de contexte de la page résultat (UI E2), SANS jinja2/HTTP.

    Fonction PURE et testable hors API : elle transforme une
    ``GenerationResponse`` (le ``result`` produit par ``run_pipeline``) — ou un
    message d'erreur lisible — en un dictionnaire de présentation consommé tel
    quel par ``templates/result.html``. AUCUNE logique métier : on relit/aplatit
    les champs déjà calculés (cooklang, markdown, et les 4 sections de
    ``DebugInfo``). Le panneau debug est la vitrine d'explicabilité (§9.2/FR7).

    Args:
        result: une ``GenerationResponse`` (``cooklang``/``markdown``/``debug``)
            ou ``None`` en cas d'erreur (alors ``error`` porte le message).
        form: les valeurs du formulaire à ré-afficher (saisie utilisateur). Si
            ``None``, on utilise les valeurs par défaut (``DEFAULT_FORM``).
        error: message d'erreur lisible (entrée invalide 422 / échec LLM 502) à
            présenter dans la page SANS la faire planter. ``None`` si succès.

    Returns:
        Un ``dict`` de contexte : ``ok`` (bool), ``error`` (str | None),
        ``form`` (dict), et — en cas de succès — ``cooklang`` (str),
        ``markdown`` (str), ``debug`` (dict aplati à 4 sections) +
        ``debug_labels`` (libellés FR des sections).
    """
    context: dict = {
        "form": dict(form) if form else dict(DEFAULT_FORM),
        "ok": error is None and result is not None,
        "error": error,
        "debug_labels": dict(DEBUG_SECTION_LABELS),
    }

    if context["ok"]:
        context["cooklang"] = str(_req_get(result, "cooklang", "") or "")
        context["markdown"] = str(_req_get(result, "markdown", "") or "")
        context["debug"] = _debug_to_dict(_req_get(result, "debug", None))
    else:
        # Page d'erreur : pas de recette, mais on conserve la saisie + le message.
        context["cooklang"] = ""
        context["markdown"] = ""
        context["debug"] = {
            "epicure": {},
            "scaling": [],
            "techniques": {},
            "validation": {},
        }

    return context


def _request_from_form(
    *,
    hero: str,
    cuisine: str,
    diet: str,
    no_cookware: str,
    highlight: str,
    servings: int,
    model: str,
) -> "GenerationRequest":
    """Construit un ``GenerationRequest`` depuis les champs bruts du formulaire.

    Glu de présentation UNIQUEMENT (pas de logique métier) : découpe les champs
    « liste » saisis en texte (``diet``/``no_cookware`` séparés par virgule ou
    saut de ligne) en listes, normalise ``highlight`` vide -> ``None``, et délègue
    toute la VALIDATION à ``run_pipeline`` (héros hors vocab, cuisine inconnue…).
    """
    diet_list = [item.strip() for item in diet.replace("\n", ",").split(",") if item.strip()]
    cookware_list = [
        item.strip() for item in no_cookware.replace("\n", ",").split(",") if item.strip()
    ]
    highlight_value = highlight.strip() or None
    constraints = Constraints(
        diet=diet_list, no_cookware=cookware_list, highlight=highlight_value
    )
    return GenerationRequest(
        hero=hero.strip(),
        cuisine=cuisine.strip() or DEFAULT_CUISINE,
        constraints=constraints,
        servings=servings,
        model=model.strip() or DEFAULT_MODEL,
    )


if FastAPI is not None:
    app = FastAPI(title="recettes - scaler Epicure", version="0.1.0")

    @app.get("/health")
    def health() -> dict:
        """Sonde de vivacité (conservée depuis le squelette d'origine)."""
        return {"status": "ok", "stage": "pipeline"}

    @app.post("/generate", response_model=GenerationResponse)
    def generate(
        request: GenerationRequest,
        index: object | None = Depends(get_index),
        complete: Callable | None = Depends(get_complete),
    ) -> "GenerationResponse":
        """Génère une recette (enveloppe MINCE : appelle ``run_pipeline``).

        Aucune logique métier ici : on délègue à ``run_pipeline`` et on TRADUIT
        ses exceptions d'orchestration en codes HTTP (archi §9.1) :
          - ``PipelineInputError`` -> 422 (entrée invalide) ;
          - ``PipelineGenerationError`` -> 502 (échec LLM / violation persistante) ;
          - toute autre exception -> 500 (erreur inattendue).
        """
        try:
            return run_pipeline(request, complete=complete, index=index)
        except PipelineInputError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except PipelineGenerationError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:  # garde-fou : erreur inattendue -> 500
            raise HTTPException(
                status_code=500, detail=f"Erreur inattendue : {exc}"
            ) from exc

    # ----------------------------------------------------------------------- #
    # UI minimale Jinja2 (E2, archi §9.2). Montée SEULEMENT si jinja2 présent  #
    # (sinon l'API JSON E1 reste pleinement fonctionnelle ; les pages HTML     #
    # sont simplement absentes). Chemin des templates ROBUSTE : relatif au     #
    # module `app/main.py` -> `<repo>/templates`, indépendant du cwd.          #
    # ----------------------------------------------------------------------- #
    if Jinja2Templates is not None:
        import os

        _TEMPLATES_DIR = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates"
        )
        templates = Jinja2Templates(directory=_TEMPLATES_DIR)

        @app.get("/", response_class=HTMLResponse)
        def ui_form(request: Request) -> "HTMLResponse":
            """Page formulaire (GET ``/``) : héros/cuisine/contraintes/portions.

            Rend ``templates/index.html`` avec les valeurs par défaut. Aucune
            logique métier : simple présentation du formulaire (méthode POST vers
            ``/generate-ui``).
            """
            return templates.TemplateResponse(
                request, "index.html", {"form": dict(DEFAULT_FORM)}
            )

        @app.post("/generate-ui", response_class=HTMLResponse)
        def ui_generate(
            request: Request,
            hero: str = Form(""),
            cuisine: str = Form(DEFAULT_CUISINE),
            diet: str = Form(""),
            no_cookware: str = Form(""),
            highlight: str = Form(""),
            servings: int = Form(4),
            model: str = Form(DEFAULT_MODEL),
            index: object | None = Depends(get_index),
            complete: Callable | None = Depends(get_complete),
        ) -> "HTMLResponse":
            """Soumission du formulaire (POST ``/generate-ui``) -> page résultat.

            Enveloppe MINCE : construit un ``GenerationRequest`` depuis le form,
            appelle ``run_pipeline`` (RÉUTILISE les coutures d'injection E1
            ``get_index``/``get_complete`` pour rester testable offline), puis rend
            ``templates/result.html`` via le helper PUR ``build_view_context``. En
            cas d'erreur pipeline, AFFICHE un message lisible dans la page (la page
            ne plante pas) : 422 (entrée invalide) ou 502 (échec LLM).
            """
            form_echo = {
                "hero": hero,
                "cuisine": cuisine,
                "diet": diet,
                "no_cookware": no_cookware,
                "highlight": highlight,
                "servings": servings,
                "model": model,
            }
            try:
                gen_request = _request_from_form(
                    hero=hero,
                    cuisine=cuisine,
                    diet=diet,
                    no_cookware=no_cookware,
                    highlight=highlight,
                    servings=servings,
                    model=model,
                )
                response = run_pipeline(
                    gen_request, complete=complete, index=index
                )
                context = build_view_context(response, form=form_echo)
            except PipelineInputError as exc:
                context = build_view_context(
                    None,
                    form=form_echo,
                    error=f"Entrée invalide (422) : {exc}",
                )
            except PipelineGenerationError as exc:
                context = build_view_context(
                    None,
                    form=form_echo,
                    error=f"Échec de génération (502) : {exc}",
                )
            except Exception as exc:  # garde-fou : ne pas crasher la page
                context = build_view_context(
                    None,
                    form=form_echo,
                    error=f"Erreur inattendue : {exc}",
                )

            return templates.TemplateResponse(request, "result.html", context)


if __name__ == "__main__":  # pragma: no cover - sanity-check manuel (sans réseau)
    # Démonstration HORS RÉSEAU : faux index + faux complete -> pipeline complet.
    from app.generator import Quantity, Step, Temperature, Duration

    def _fake_index(_model: str = "cooc"):
        class _Idx:
            def neighbors(self, name: str, k: int = 6):
                return [("basil", 0.91), ("garlic", 0.88)][:k]

        return _Idx()

    def _fake_complete(_prompt, _feedback=None) -> StructuredRecipe:
        return StructuredRecipe(
            title="Spaghetti à la tomate",
            servings=2,
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

    demo = GenerationRequest(hero="basilic", servings=4)
    response = run_pipeline(demo, complete=_fake_complete, index=_fake_index())
    print(response.markdown)
    print("--- cooklang ---")
    print(response.cooklang)
    print("--- debug.scaling ---")
    for row in response.debug.scaling:
        print(row)
