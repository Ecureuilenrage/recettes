"""Construction du prompt contraint — barrière 1 anti-hallucination (story D1).

``build_prompt(req, neighbors, techniques, safety, forbidden) -> ConstrainedPrompt``
assemble le prompt système + utilisateur que le LLM (couche 4) recevra. Il
réalise la **Barrière 1** (archi §6.1) : injecter UNIQUEMENT les 4 blocs
autorisés et reprendre VERBATIM les ``llmConstraints`` de la cuisine, pour que
le LLM CHOISISSE dans la base sans rien inventer (FR3).

Module **PUR et déterministe** (archi §3.1, §5.1) :
  - aucune I/O réseau, aucun appel LLM, aucun ``random``, aucun appel horloge ;
  - mêmes entrées -> même ``ConstrainedPrompt`` (ordre des blocs = ordre d'entrée) ;
  - n'importe AUCUNE autre couche métier au runtime : les sorties des couches
    1/2 arrivent EN PARAMÈTRES (duck-typing). Les annotations vers ces types
    passent par ``if TYPE_CHECKING:`` uniquement ; les helpers de normalisation
    sont RECOPIÉS (et non importés), comme en couches 1/2.

Contrat d'entrée (souple, pour ne pas coupler à la couche web) :
  - ``req``      : objet ou dict exposant ``hero``/``cuisine``/``servings``
    (et éventuellement ``constraints``) — lu par ``getattr``/``dict.get``.
  - ``neighbors``: un ``FilteredNeighbors`` (attribut ``.kept``), une séquence
    de ``KeptNeighbor`` (attributs ``.name``/``.score``), ou de tuples
    ``(name, score)``.
  - ``techniques``: séquence de ``Technique`` (attributs ``.id``/``.name``/
    ``.category``/``.parameters``/``.required_tools``).
  - ``safety``   : séquence de ``SafetyStandard`` (attributs ``.food_type``/
    ``.min_internal_c``/``.min_internal_f``/``.rest_minutes``/``.critical``),
    ou un ``SafetyTable`` (attribut ``.standards``).
  - ``forbidden``: itérable d'ustensiles interdits (déjà normalisés, B4).

Décision D1 (mode non-interactif) : ``LLM_CONSTRAINTS`` est figée EN DUR ici
(verbatim du JSON ``cuisine-italienne.json``), D1 ne lisant aucun JSON (tout
arrive en paramètres ; la cuisine italienne est l'unique cuisine v1). Si ``req``
fournit des ``llm_constraints`` non vides, ``build_prompt`` les préfère.
"""

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING

from app.generator.models import ConstrainedPrompt  # même couche : import autorisé

if TYPE_CHECKING:  # annotations seulement — JAMAIS d'import runtime inter-couches
    from collections.abc import Iterable, Sequence


# --------------------------------------------------------------------------- #
# Les `llmConstraints` reprises VERBATIM de docs/base-technique/              #
# cuisine-italienne.json (lignes 122-128).                                    #
#                                                                            #
# NOTE ENCODAGE (importante) : le JSON source porte ces lignes SANS accents   #
# (« temperature », « securite »…). « Verbatim » signifie reproduire le       #
# contenu de la base TEL QUEL : on NE réécrit PAS ces 5 lignes. En revanche,  #
# la prose/les docstrings du code FR portent les accents corrects (convention #
# projet), et l'étiquetage côté CONTRAT (`Temperature.label`) utilise la      #
# forme accentuée « SÉCURITÉ »/« TECHNIQUE »/« PRÉFÉRENCE » (archi §6.1).      #
# --------------------------------------------------------------------------- #
LLM_CONSTRAINTS: tuple[str, ...] = (
    "NE JAMAIS inventer une temperature ou un temps : choisir dans parameters ou safety-temperatures.json.",
    "Etiqueter chaque consigne : [SECURITE] / [TECHNIQUE] / [PREFERENCE].",
    "Pour toute proteine, citer la temperature de securite et le temps de repos.",
    "Ne pas utiliser un ustensile present dans les #cookware interdits par les contraintes utilisateur.",
    "Si une technique requise utilise un ustensile interdit (ex. four), la remplacer ou refuser proprement.",
)

# Consigne d'étiquetage imposée au LLM (archi §6.1) — forme accentuée (prose FR).
LABELING_INSTRUCTION: str = (
    "Étiquette CHAQUE consigne par sa nature : [SÉCURITÉ] / [TECHNIQUE] / [PRÉFÉRENCE]."
)


# --------------------------------------------------------------------------- #
# Normalisation (mêmes helpers que app/scaling/table.py:52-60). RECOPIÉS (et   #
# non importés) : la couche 4 n'importe aucune autre couche métier (archi      #
# §3.1). Duplication volontaire (≈ 8 lignes stdlib), comme en couches 1/2.     #
# --------------------------------------------------------------------------- #


def _strip_accents(text: str) -> str:
    """Supprime les accents (é -> e) sans dépendance externe."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _normalize(text: str) -> str:
    """Minuscule + suppression des accents + ``strip`` (ustensile normalisé)."""
    return _strip_accents(text).strip().lower()


# --------------------------------------------------------------------------- #
# Lecture souple de `req` (objet/dataclass ou dict) — duck-typing.            #
# --------------------------------------------------------------------------- #


def _req_get(req: object, key: str, default: object = None) -> object:
    """Lit ``key`` sur ``req`` qu'il soit un dict ou un objet (``getattr``)."""
    if isinstance(req, dict):
        return req.get(key, default)
    return getattr(req, key, default)


# --------------------------------------------------------------------------- #
# Adaptation souple des voisins (FilteredNeighbors / KeptNeighbor / tuples).   #
# --------------------------------------------------------------------------- #


def _iter_neighbors(neighbors: object) -> list[tuple[str, float]]:
    """Normalise ``neighbors`` en liste ``[(name, score), ...]`` (ordre préservé).

    Accepte un ``FilteredNeighbors`` (attribut ``.kept``), une séquence de
    ``KeptNeighbor`` (attributs ``.name``/``.score``) ou de tuples
    ``(name, score)``. Toute forme inconnue -> liste vide (dégradation gracieuse).
    """
    items = getattr(neighbors, "kept", neighbors)
    result: list[tuple[str, float]] = []
    if items is None:
        return result
    for item in items:
        name = getattr(item, "name", None)
        score = getattr(item, "score", None)
        if name is None and isinstance(item, (tuple, list)) and item:
            name = item[0]
            score = item[1] if len(item) > 1 else 0.0
        if name is None:
            continue
        result.append((str(name), float(score) if score is not None else 0.0))
    return result


# --------------------------------------------------------------------------- #
# Adaptation souple de `safety` (SafetyTable / séquence de SafetyStandard).    #
# --------------------------------------------------------------------------- #


def _iter_safety(safety: object) -> list[object]:
    """Normalise ``safety`` en liste de ``SafetyStandard`` (ordre préservé)."""
    standards = getattr(safety, "standards", safety)
    if standards is None:
        return []
    return list(standards)


# --------------------------------------------------------------------------- #
# Extraction des températures numériques d'un dict `parameters` (couche 2).    #
# Les valeurs peuvent être int/float OU des chaînes (« 150-160 », « 82-90 »).  #
# --------------------------------------------------------------------------- #


def _extract_temperatures(parameters: object) -> list[float]:
    """Extrait toutes les valeurs numériques de température d'un ``parameters``.

    Parcourt les clés contenant « temp » (insensible casse) — ``tempC``,
    ``tempF``, ``panTempC``, ``ovenTempC``, ``searTempC``… — et en extrait tous
    les nombres (un intervalle « 150-160 » donne 150 et 160). Pur et tolérant.
    """
    values: list[float] = []
    if not isinstance(parameters, dict):
        return values
    for key, raw in parameters.items():
        if "temp" not in str(key).lower():
            continue
        values.extend(_numbers_in(raw))
    return values


def _numbers_in(raw: object) -> list[float]:
    """Retourne tous les nombres présents dans ``raw`` (int/float ou chaîne)."""
    if isinstance(raw, bool):
        return []
    if isinstance(raw, (int, float)):
        return [float(raw)]
    if isinstance(raw, str):
        numbers: list[float] = []
        token: list[str] = []
        for ch in raw:
            if ch.isdigit() or (ch == "." and token):
                token.append(ch)
            elif token:
                numbers.append(float("".join(token)))
                token = []
        if token:
            numbers.append(float("".join(token)))
        return numbers
    return []


# --------------------------------------------------------------------------- #
# Fonction principale (signature PRESCRITE, archi §4.4).                       #
# --------------------------------------------------------------------------- #


def build_prompt(
    req: object,
    neighbors: object,
    techniques: object,
    safety: object,
    forbidden: object,
) -> ConstrainedPrompt:
    """Assemble le prompt contraint (barrière 1) à partir des sorties amont.

    PURE et déterministe : mêmes entrées -> même ``ConstrainedPrompt`` (mêmes
    ``system``/``user`` et frozensets), aucun ``random``, aucune I/O.

    Le prompt **système** définit le rôle (« rédacteur sous contraintes », D8),
    reprend VERBATIM les ``LLM_CONSTRAINTS`` (couche 2), impose l'étiquetage
    ``[SÉCURITÉ]/[TECHNIQUE]/[PRÉFÉRENCE]`` et demande une SORTIE JSON STRUCTURÉE
    conforme au schéma ``StructuredRecipe`` (D10). Le prompt **utilisateur**
    injecte les 4 blocs autorisés (archi §6.1) : (1) associations validées
    (``neighbors``), (2) techniques + ``parameters`` (``techniques``), (3) lignes
    de sécurité (``safety``), (4) ``#cookware`` interdits (``forbidden``).

    Args:
        req: requête de génération (objet ou dict exposant ``hero``/``cuisine``/
            ``servings`` ; ``llm_constraints`` optionnel pour override).
        neighbors: ``FilteredNeighbors`` / séquence de ``KeptNeighbor`` / tuples.
        techniques: séquence de ``Technique`` (sortie ``techniques_for``).
        safety: ``SafetyTable`` ou séquence de ``SafetyStandard``.
        forbidden: itérable d'ustensiles interdits (déjà normalisés, B4).

    Returns:
        Un ``ConstrainedPrompt`` figé (``system``/``user`` + les 3 frozensets de
        traçabilité ``allowed_temperatures``/``allowed_cookware``/
        ``forbidden_cookware``).
    """
    hero = _req_get(req, "hero", "")
    cuisine = _req_get(req, "cuisine", "")
    servings = _req_get(req, "servings", 4)
    override = _req_get(req, "llm_constraints", None)
    constraints_used = tuple(override) if override else LLM_CONSTRAINTS

    kept = _iter_neighbors(neighbors)
    technique_list = list(techniques) if techniques is not None else []
    standards = _iter_safety(safety)
    forbidden_list = sorted({_normalize(str(t)) for t in (forbidden or []) if str(t).strip()})

    # ----- Frozensets de traçabilité (pour D2) ----------------------------- #
    allowed_temperatures: set[float] = set()
    allowed_cookware: set[str] = set()
    for tech in technique_list:
        allowed_temperatures.update(_extract_temperatures(getattr(tech, "parameters", {})))
        for tool in getattr(tech, "required_tools", ()) or ():
            normalized = _normalize(str(tool))
            if normalized:
                allowed_cookware.add(normalized)
    for std in standards:
        for value in (getattr(std, "min_internal_c", None), getattr(std, "min_internal_f", None)):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                allowed_temperatures.add(float(value))

    # ----- Prompt système -------------------------------------------------- #
    system_lines: list[str] = [
        "Tu es un rédacteur de recettes SOUS CONTRAINTES STRICTES.",
        "Tu ne CHOISIS que dans la base fournie ci-dessous : tu n'inventes jamais "
        "une température, un temps, une technique ni un ustensile.",
        "",
        "Contraintes impératives (reprises verbatim de la base technique) :",
    ]
    system_lines.extend(f"  {i}. {line}" for i, line in enumerate(constraints_used, start=1))
    system_lines.extend(
        [
            "",
            LABELING_INSTRUCTION,
            "",
            "SORTIE ATTENDUE : un objet JSON STRUCTURÉ conforme au schéma "
            "StructuredRecipe, avec les clés :",
            '  {"title": str, "servings": int, '
            '"ingredients": [{"name": str, "amount": number, "unit": str, "fixed": bool}], '
            '"steps": [{"text": str, "cookware": [str], '
            '"temperatures": [{"value": number, "unit": "C"|"F", '
            '"label": "SÉCURITÉ"|"TECHNIQUE"|"PRÉFÉRENCE"}], '
            '"durations": [{"value": number, "unit": "minute"|"heure"}], '
            '"technique_id": str|null}], '
            '"techniques": [str], "notes": [str]}',
            "Ne renvoie QUE ce JSON, sans texte autour.",
        ]
    )
    system = "\n".join(system_lines)

    # ----- Prompt utilisateur (les 4 blocs autorisés) ---------------------- #
    user_lines: list[str] = [
        f"Héros : {hero}",
        f"Cuisine : {cuisine}",
        f"Portions de base : {servings}",
        "",
        "Bloc 1 — Associations validées (choisis tes ingrédients PARMI celles-ci) :",
    ]
    if kept:
        user_lines.extend(f"  - {name} (score {score:.4f})" for name, score in kept)
    else:
        user_lines.append("  (aucune association validée)")

    user_lines.extend(["", "Bloc 2 — Techniques autorisées + paramètres (choisis temps/températures ICI) :"])
    if technique_list:
        for tech in technique_list:
            tid = getattr(tech, "id", "")
            name = getattr(tech, "name", "")
            category = getattr(tech, "category", "")
            params = getattr(tech, "parameters", {})
            user_lines.append(f"  - [{tid}] {name} — {category}")
            user_lines.append(f"      parameters : {_render_parameters(params)}")
    else:
        user_lines.append("  (aucune technique autorisée)")

    user_lines.extend(["", "Bloc 3 — Lignes de sécurité applicables (à citer pour toute protéine) :"])
    if standards:
        for std in standards:
            user_lines.append(f"  - {_render_safety(std)}")
    else:
        user_lines.append("  (aucune ligne de sécurité applicable)")

    user_lines.extend(["", "Bloc 4 — Ustensiles #cookware INTERDITS (ne jamais les utiliser) :"])
    if forbidden_list:
        user_lines.extend(f"  - {tool}" for tool in forbidden_list)
    else:
        user_lines.append("  (aucun ustensile interdit)")

    user = "\n".join(user_lines)

    return ConstrainedPrompt(
        system=system,
        user=user,
        allowed_temperatures=frozenset(allowed_temperatures),
        allowed_cookware=frozenset(allowed_cookware),
        forbidden_cookware=frozenset(forbidden_list),
    )


def _render_parameters(params: object) -> str:
    """Rendu déterministe et lisible d'un dict ``parameters`` (clés triées)."""
    if not isinstance(params, dict):
        return "{}"
    parts = [f"{key}={params[key]}" for key in sorted(params, key=str)]
    return ", ".join(parts) if parts else "{}"


def _render_safety(std: object) -> str:
    """Rendu d'une ligne de sécurité (protéine + min °C/°F + repos + critical)."""
    food = getattr(std, "food_type", "")
    cmin = getattr(std, "min_internal_c", None)
    fmin = getattr(std, "min_internal_f", None)
    rest = getattr(std, "rest_minutes", None)
    critical = getattr(std, "critical", False)
    flag = " [CRITIQUE]" if critical else ""
    return (
        f"{food} : min interne {cmin} °C / {fmin} °F ; repos {rest} min{flag}"
    )


if __name__ == "__main__":
    # Sanity-check rapide (PUR, sans réseau ni LLM) : python -m app.generator.prompt
    class _FakeTech:
        def __init__(self):
            self.id = "pasta_al_dente"
            self.name = "Pâtes al dente"
            self.category = "Ébullition"
            self.parameters = {"tempC": 100, "tempF": 212, "timeMinutes": "8-10"}
            self.required_tools = ("grande casserole", "passoire")

    class _FakeStd:
        food_type = "Volaille"
        min_internal_c = 74
        min_internal_f = 165
        rest_minutes = 0
        critical = True

    prompt = build_prompt(
        req={"hero": "tomate", "cuisine": "italian_savory_v1", "servings": 4},
        neighbors=[("basilic", 0.91), ("ail", 0.88)],
        techniques=[_FakeTech()],
        safety=[_FakeStd()],
        forbidden=["four", "blender"],
    )
    print("=== SYSTEM ===")
    print(prompt.system)
    print("\n=== USER ===")
    print(prompt.user)
    print("\nallowed_temperatures :", sorted(prompt.allowed_temperatures))
    print("allowed_cookware     :", sorted(prompt.allowed_cookware))
    print("forbidden_cookware   :", sorted(prompt.forbidden_cookware))
