"""Émission Cooklang `.cook` + validation regex — story D3 (couche 4).

Ce module expose deux fonctions PURES et DÉTERMINISTES de la couche 4
(``app/generator/``) :

  - ``to_cooklang(recipe, scaling_notes) -> str`` : émet un document Cooklang
    ``.cook`` complet à partir d'un ``StructuredRecipe`` (contrat figé D1,
    consommé en LECTURE SEULE) et des sorties de scaling de la couche 3
    (``ScaledQuantity``/``ScaledEggs``/``ScaledTime`` + notes) reçues EN
    PARAMÈTRE (duck-typing). Pose le frontmatter ``servings``, les marqueurs
    ``@ingrédient{quantité%unité}`` / ``#ustensile`` / ``~{durée}``, les verrous
    ``=`` sur les quantités/températures ``fixed`` et les notes ``--`` (réserve
    10 %, changement de contenant, étiquettes ``[SÉCURITÉ]/[TECHNIQUE]/
    [PRÉFÉRENCE]``).
  - ``validate_cooklang(text) -> tuple[bool, list[str]]`` : validation regex
    légère (RZ5 — fallback regex ACTÉ, décision D5/archi §8.4/§12) réutilisant le
    patron de ``recipes/_check_cook.py`` (regex RECOPIÉES, PAS importées).

Réserve RZ5 résolue : émission ``.cook`` par **templating maison + validation
regex**, **AUCUNE dépendance ``cooklang-py``** ni binding natif. ``re`` et
``unicodedata`` (stdlib) suffisent.

Règle inter-couches STRICTE (archi §3.1) : ce module importe UNIQUEMENT
``app.generator.models`` (même couche 4, LECTURE SEULE). Il N'IMPORTE NI
``app/scaling/``, NI ``app/knowledge/``, NI ``app/epicure/`` au runtime, NI
``anthropic``, NI ``cooklang-py`` ; ``scaling_notes`` arrive EN PARAMÈTRE
(duck-typing via ``getattr``) ; les annotations vers la couche 3 passent par
``if TYPE_CHECKING:`` uniquement.

Conventions : ``from __future__ import annotations`` ; type hints PEP 585 ;
docstrings FR (accents corrects) ; identifiants/clés en anglais snake_case ;
module pur (aucune I/O, aucun ``random``, aucune horloge, aucun LLM/réseau).
"""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING

from app.generator.models import (
    Duration,
    Quantity,
    Step,
    StructuredRecipe,
    Temperature,
)

if TYPE_CHECKING:  # pragma: no cover - annotations seulement, jamais d'import runtime
    # Types de la couche 3 (app/scaling/engine.py) reçus EN PARAMÈTRE. Référencés
    # uniquement pour la documentation/typage ; JAMAIS importés au runtime
    # (règle inter-couches archi §3.1). On lit leurs attributs par duck-typing.
    from collections.abc import Mapping, Sequence
    from typing import Any


# --------------------------------------------------------------------------- #
# Regex RECOPIÉES de `recipes/_check_cook.py` (S0.4) — PAS importées.          #
# `recipes/` n'est pas un package importable ; on recopie le patron éprouvé    #
# pour `validate_cooklang` (fallback regex RZ5, décision D5/archi §8.4/§12).    #
# --------------------------------------------------------------------------- #

RE_SERVINGS = re.compile(r"^---\s*\nservings:\s*\d+", re.MULTILINE)
RE_INGREDIENT = re.compile(r"@[^@#~\n]+?\{[^}]*?%[^}]*?\}")
RE_TIMER = re.compile(r"~\{[^}]*?\}")
RE_COOKWARE = re.compile(r"#[^\s#@~{]+")


# --------------------------------------------------------------------------- #
# Helpers de normalisation (RECOPIÉS de `app/scaling/table.py`, ≈ stdlib       #
# `unicodedata`) — PAS importés d'une autre couche. Servent à aligner les      #
# `scaling_notes` (couche 3) sur `recipe.ingredients` par nom normalisé.       #
# --------------------------------------------------------------------------- #


def _strip_accents(text: str) -> str:
    """Supprime les accents (« é » -> « e ») sans dépendance externe."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _normalize(text: str) -> str:
    """Minuscule + suppression des accents + espaces de bord — clé d'alignement."""
    return _strip_accents(text).strip().lower()


def _format_number(value: float) -> str:
    """Formate un nombre de façon DÉTERMINISTE (entiers sans décimale superflue).

    ``2.0`` -> ``"2"`` ; ``2.5`` -> ``"2.5"`` ; ``0`` -> ``"0"``. On évite toute
    instabilité de représentation flottante cross-plateforme via ``format(.., "g")``
    qui supprime les zéros non significatifs et l'exposant inutile.
    """
    if isinstance(value, bool):
        # bool est une sous-classe d'int : on le rend en entier 0/1.
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    # float : "g" supprime les zéros superflus ("2.0" -> "2") de façon stable.
    text = format(float(value), "g")
    # `format(.., "g")` peut produire un exposant ("1e-05") pour des valeurs
    # extrêmes ; on retombe alors sur une représentation décimale lisible.
    if "e" in text or "E" in text:
        text = (f"{float(value):.6f}").rstrip("0").rstrip(".")
    return text


# --------------------------------------------------------------------------- #
# Indexation SOUPLE des `scaling_notes` (duck-typing) — aucune dépendance      #
# couche 3. Accepte None / Mapping {name: note} / séquence d'objets `.name`.   #
# --------------------------------------------------------------------------- #


def _index_scaling(scaling_notes: object) -> dict[str, object]:
    """Indexe ``scaling_notes`` par nom d'ingrédient NORMALISÉ (duck-typing).

    Accepte de façon SOUPLE (archi §3.1, aucune import de ``app/scaling/``) :

      - ``None`` -> ``{}`` (l'émission utilisera les quantités de base) ;
      - un *mapping* ``{name: note}`` (clés re-normalisées) ;
      - une *séquence* d'objets exposant un attribut ``.name`` (ex.
        ``ScaledQuantity``).

    Robuste aux objets sans l'attribut attendu (``getattr(..., None)``). En cas
    de doublon de nom normalisé, la PREMIÈRE occurrence prime (déterminisme,
    ordre d'entrée préservé).
    """
    index: dict[str, object] = {}
    if scaling_notes is None:
        return index

    # Mapping {name: note} : on re-normalise la clé. On exclut volontairement les
    # str/bytes (qui exposent des méthodes de mapping-like via .get sur certains
    # types) en testant la présence de `.items`.
    items = getattr(scaling_notes, "items", None)
    if callable(items) and not isinstance(scaling_notes, (str, bytes)):
        for key, note in items():
            norm = _normalize(str(key))
            if norm and norm not in index:
                index[norm] = note
        return index

    # Séquence d'objets `.name` (liste/tuple/itérable). On ignore str/bytes.
    if isinstance(scaling_notes, (str, bytes)):
        return index
    try:
        iterator = iter(scaling_notes)  # type: ignore[arg-type]
    except TypeError:
        return index
    for note in iterator:
        name = getattr(note, "name", None)
        if name is None:
            continue
        norm = _normalize(str(name))
        if norm and norm not in index:
            index[norm] = note
    return index


def _scaled_value_unit(
    qty: Quantity, scaled: object | None
) -> tuple[float, str, bool, list[str]]:
    """Résout (valeur, unité, verrou, notes) d'un ingrédient (base ou scalé).

    Si ``scaled`` correspond (objet couche 3 aligné par nom), on lit ``.value``/
    ``.unit``/``.fixed``/``.notes`` par duck-typing (``getattr`` avec défauts) ;
    sinon on retombe sur la quantité de BASE (``qty.amount``/``qty.unit``/
    ``qty.fixed``). Le verrou ``=`` est posé si ``qty.fixed`` OU
    ``scaled.fixed`` (priorité au scaling s'il correspond, archi §8.4/AC3).
    """
    notes: list[str] = []
    if scaled is None:
        return qty.amount, qty.unit, bool(qty.fixed), notes

    value = getattr(scaled, "value", None)
    if value is None:
        value = qty.amount
    unit = getattr(scaled, "unit", None)
    if unit is None:
        unit = qty.unit
    fixed = bool(getattr(scaled, "fixed", False)) or bool(qty.fixed)

    raw_notes = getattr(scaled, "notes", None)
    if isinstance(raw_notes, (list, tuple)):
        notes = [str(n) for n in raw_notes if n]
    elif raw_notes:
        notes = [str(raw_notes)]
    # `ScaledTime` expose `.note` (property scalaire) ; on l'accepte aussi.
    single = getattr(scaled, "note", None)
    if single and str(single) not in notes:
        notes.append(str(single))

    return float(value), str(unit), fixed, notes


# --------------------------------------------------------------------------- #
# Helpers d'émission des marqueurs Cooklang.                                   #
# --------------------------------------------------------------------------- #


def _emit_ingredient(name: str, value: float, unit: str, locked: bool) -> str:
    """Compose un marqueur ingrédient ``@nom{[=]valeur%unité}`` (archi §8.4).

    Le verrou ``=`` (quantité figée) précède la valeur dans les accolades, format
    ``@sel{=1%c.à.c}``. L'unité peut être vide (``@oeufs{3%}``), tolérée par la
    regex d'ingrédient.
    """
    lock = "=" if locked else ""
    return f"@{name}{{{lock}{_format_number(value)}%{unit}}}"


def _emit_temperature(temp: Temperature) -> str:
    """Compose un marqueur température figée ``(=valeur%°C)`` (archi §5.4/§8.4).

    La température est de type ``fixed`` côté scaling : elle reçoit TOUJOURS le
    verrou ``=`` à l'émission. L'unité « C »/« F » du contrat est rendue
    ``°C``/``°F`` (style corpus S0.6).
    """
    unit = str(temp.unit).strip().upper()
    symbol = "°F" if unit in {"F", "°F"} else "°C"
    return f"(={_format_number(temp.value)}%{symbol})"


def _emit_timer(duration: Duration) -> str:
    """Compose un marqueur timer ``~{valeur%unité}`` (archi §8.4)."""
    return f"~{{{_format_number(duration.value)}%{duration.unit}}}"


def _emit_cookware(item: str) -> str:
    """Compose un marqueur ustensile ``#token`` bien formé (regex ``#[^\\s#@~{]+``).

    Décision par défaut DOCUMENTÉE : un ustensile multi-mots (« grande casserole »)
    ne peut pas former un marqueur ``#`` mono-token (la regex Cooklang s'arrête au
    premier espace). On émet donc ``#`` + PREMIER token + le reste du libellé en
    texte (ex. ``#grande casserole`` -> ``#grande casserole`` reste lisible, le
    marqueur reconnu par la regex étant ``#grande``). Cela respecte exactement le
    style du corpus S0.6 (``#grande casserole`` y figure verbatim) tout en
    garantissant un marqueur ``#`` valide.
    """
    item = item.strip()
    if not item:
        return ""
    parts = item.split(" ", 1)
    head = parts[0]
    tail = f" {parts[1]}" if len(parts) > 1 else ""
    return f"#{head}{tail}"


def _emit_note(text: str) -> str:
    """Préfixe ``-- `` une note, SAUF si elle commence déjà par ``--`` (idempotence).

    Évite tout double préfixe ``----`` (AC4). Le texte est rstrip-é (pas de
    retour à la ligne parasite qui casserait le marqueur).
    """
    text = text.strip()
    if not text:
        return ""
    if text.startswith("--"):
        return text
    return f"-- {text}"


# --------------------------------------------------------------------------- #
# Fonction publique : émission `.cook`.                                        #
# --------------------------------------------------------------------------- #


def to_cooklang(recipe: StructuredRecipe, scaling_notes: object = None) -> str:
    """Émet un document Cooklang ``.cook`` depuis un ``StructuredRecipe`` + scaling.

    Composition DÉTERMINISTE (archi §7, §8.4) :

      1. **Frontmatter** ``---\\nservings: N\\n---`` (``N = recipe.servings``,
         portions de BASE).
      2. **Notes de recette** (``StructuredRecipe.notes``) émises en ``--``.
      3. **Étapes** : pour chaque ``Step``, on émet le texte de l'étape suivi des
         marqueurs structurés bien formés :
         - ``@ingrédient{[=]valeur%unité}`` (ingrédients de la recette,
           réconciliés par nom NORMALISÉ avec ``scaling_notes`` — valeur SCALÉE si
           disponible, sinon valeur de BASE ; verrou ``=`` si ``fixed``) ;
         - ``(=valeur%°C)`` (températures figées de l'étape, verrou ``=``) ;
         - ``#ustensile`` (``Step.cookware``) ; ``~{valeur%unité}``
           (``Step.durations``) ;
         - les notes ``--`` portées par les ``scaling_notes`` correspondants
           (réserve 10 %, changement de contenant) sont émises une seule fois,
           dédupliquées, en fin de document.

    Le paramètre ``scaling_notes`` est accepté SOUPLEMENT (duck-typing, archi
    §3.1) : ``None`` (quantités de base), un mapping ``{name: note}``, ou une
    séquence d'objets exposant ``.name``/``.value``/``.unit``/``.fixed``/
    ``.notes``. Aucun import de ``app/scaling/``.

    Args:
        recipe: la recette structurée (contrat figé D1, LECTURE SEULE).
        scaling_notes: sorties de la couche 3 (duck-typing) ou ``None``.

    Returns:
        Le document Cooklang ``.cook`` (str, UTF-8). Passe ``validate_cooklang``.
    """
    index = _index_scaling(scaling_notes)

    lines: list[str] = []
    # --- 1. Frontmatter --------------------------------------------------------
    lines.append("---")
    lines.append(f"servings: {recipe.servings}")
    lines.append("---")

    # --- 2. Notes de recette (étiquettes [SÉCURITÉ]/[TECHNIQUE]/[PRÉFÉRENCE]) ---
    for note in recipe.notes:
        emitted = _emit_note(str(note))
        if emitted:
            lines.append(emitted)

    # Notes de scaling à émettre une seule fois (réserve 10 %, contenant), dans
    # l'ordre d'apparition des ingrédients (déterministe). Dédupliquées.
    scaling_note_lines: list[str] = []
    seen_notes: set[str] = set()

    # --- 3. Étapes -------------------------------------------------------------
    for step in recipe.steps:
        segments: list[str] = []
        text = step.text.strip()
        if text:
            segments.append(text)

        # Ingrédients de la recette réconciliés avec le scaling, par nom
        # normalisé. On n'émet un @marqueur QUE si le texte de l'étape ne le porte
        # pas déjà (évite le doublon — décision §8.4 « ne pas dupliquer »).
        for qty in recipe.ingredients:
            scaled = index.get(_normalize(qty.name))
            value, unit, locked, notes = _scaled_value_unit(qty, scaled)
            marker = _emit_ingredient(qty.name, value, unit, locked)
            already = f"@{qty.name}{{" in text
            if not already:
                segments.append(marker)
            # Notes de scaling (réserve/contenant) : collectées même si le
            # marqueur est déjà présent dans le texte.
            for note in notes:
                emitted = _emit_note(note)
                if emitted and emitted not in seen_notes:
                    seen_notes.add(emitted)
                    scaling_note_lines.append(emitted)

        # Températures figées (verrou =).
        for temp in step.temperatures:
            marker = _emit_temperature(temp)
            if marker not in text:
                segments.append(marker)

        # Ustensiles.
        for item in step.cookware:
            marker = _emit_cookware(item)
            if marker and f"#{item}" not in text and marker not in text:
                segments.append(marker)

        # Timers.
        for duration in step.durations:
            marker = _emit_timer(duration)
            if marker not in text:
                segments.append(marker)

        line = " ".join(seg for seg in segments if seg).strip()
        if line:
            lines.append(line)

    # --- 4. Notes de scaling (réserve 10 %, contenant) en fin de document ------
    lines.extend(scaling_note_lines)

    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Fonction publique : validation regex (RZ5 — fallback ACTÉ, pas de            #
# `cooklang-py`). Patron RECOPIÉ de `recipes/_check_cook.py`.                  #
# --------------------------------------------------------------------------- #


def validate_cooklang(text: str) -> tuple[bool, list[str]]:
    """Valide la bonne formation d'un texte Cooklang ``.cook`` (regex légère).

    **Fallback regex RZ5** (décision D5/archi §8.4/§12) : AUCUNE dépendance
    ``cooklang-py``. Réutilise le patron éprouvé de ``recipes/_check_cook.py``
    (regex RECOPIÉES, pas importées). Contrôles :

      1. **frontmatter ``servings``** présent (``RE_SERVINGS``) ;
      2. **≥ 1 marqueur ingrédient** ``@…{…%…}`` (``RE_INGREDIENT``) ;
      3. **accolades ``{}`` équilibrées** (``text.count("{") == text.count("}")``).

    Args:
        text: le contenu ``.cook`` à valider.

    Returns:
        ``(ok, problems)`` où ``ok == (problems == [])``. Messages en français.
    """
    problems: list[str] = []
    if not RE_SERVINGS.search(text):
        problems.append("frontmatter 'servings' manquant")
    if not RE_INGREDIENT.search(text):
        problems.append("aucun marqueur @ingredient{qty%unit}")
    open_braces = text.count("{")
    close_braces = text.count("}")
    if open_braces != close_braces:
        problems.append(
            f"accolades déséquilibrées ({open_braces} '{{' vs {close_braces} '}}')"
        )
    return (not problems), problems


if __name__ == "__main__":  # pragma: no cover - sanity-check manuel
    # Sanity-check : construire un StructuredRecipe minimal, émettre, valider.
    demo = StructuredRecipe(
        title="Spaghetti al pomodoro",
        servings=4,
        ingredients=(
            Quantity(name="spaghetti", amount=400, unit="g"),
            Quantity(name="gros sel", amount=30, unit="g", fixed=True),
            Quantity(name="oeufs", amount=3, unit=""),
        ),
        steps=(
            Step(
                text="Porter l'eau à ébullition puis cuire les pâtes.",
                cookware=("grande casserole",),
                temperatures=(Temperature(value=100, unit="C", label="TECHNIQUE"),),
                durations=(Duration(value=9, unit="minutes"),),
                technique_id="pasta_al_dente",
            ),
        ),
        notes=("[TECHNIQUE] Liaison aux œufs hors feu.",),
    )
    cook = to_cooklang(demo, None)
    print(cook)
    ok, problems = validate_cooklang(cook)
    print(f"validate_cooklang -> ok={ok} ; problems={problems}")
