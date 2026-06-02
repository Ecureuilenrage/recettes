"""Garde-fou « jamais hors base » : validation déterministe (couche 4, D2).

Ce module réalise la **barrière 2** du garde-fou anti-hallucination (archi §6.2 :
« le VRAI garde-fou, déterministe — on ne fait pas confiance au prompt »). Il
expose une unique fonction publique :

    validate_recipe(recipe, techniques, safety, forbidden=frozenset())
        -> ValidationResult

qui vérifie MÉCANIQUEMENT une ``StructuredRecipe`` produite par le LLM contre la
base technique :

  1. **Extraction** de toutes les valeurs numériques de température (et de temps,
     pour la traçabilité) citées dans ``recipe.steps[].temperatures`` /
     ``.durations``.
  2. **Appartenance des températures** : chaque température citée doit appartenir
     aux ``parameters`` des ``techniques`` autorisées (scalaires ET intervalles
     texte « 150-160 » parsés, bornes incluses ± ``_TEMP_EPSILON``) OU aux minima
     de ``safety``, POUR LA MÊME UNITÉ (°C avec °C, °F avec °F). Sinon
     ``temperature_hors_base`` (``severity="critical"``).
  3. **Sécurité protéines** : pour toute protéine détectée, la ligne ``safety``
     applicable est respectée (jamais sous le minimum ; protéine non citée
     signalée ; ``critical:true`` ⇒ rejet dur). ``securite_proteine``.
  4. **Cookware interdit** : aucun ``#cookware`` ∈ ``forbidden`` (matching
     sous-séquence de tokens normalisés). ``cookware_interdit``.
  5. **Politique** : la fonction est PURE/DÉTERMINISTE, retourne
     ``ValidationResult(ok, violations, feedback)`` et NE FAIT PAS le retry
     (boucle dans ``client.generate_recipe``, D1) ; AUCUNE réparation silencieuse
     (``recipe`` n'est jamais muté).

Règle inter-couches STRICTE (archi §3.1) : ``validate.py`` n'importe AUCUNE autre
couche métier au runtime — NI ``app/knowledge/``, NI ``app/epicure/``, NI
``app/scaling/``, NI ``anthropic``. Les ``techniques`` / ``safety`` arrivent EN
PARAMÈTRES (duck-typing via ``getattr``) ; les annotations vers la couche 2
passent par ``if TYPE_CHECKING:``. Le SEUL import inter-module autorisé est
``from app.generator.models import ...`` (MÊME couche). Les helpers de
normalisation sont RECOPIÉS du patron ``app/knowledge/loader.py`` (recopie
volontaire, pas d'import — règle inter-couches, même choix qu'en B3/B4/A4).

Conventions (alignées sur ``app/generator/models.py`` / ``app/knowledge/loader.py``) :
  - ``from __future__ import annotations`` ; type hints PEP 585 ;
  - docstrings FR (accents corrects) ; identifiants / ``kind`` / ``severity`` en
    anglais snake_case ; UTF-8 sans BOM ;
  - aucune nouvelle dépendance (``re``, ``unicodedata``, ``typing`` + ``models``).
"""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING

from app.generator.models import (
    StructuredRecipe,
    ValidationResult,
    Violation,
)

if TYPE_CHECKING:  # pragma: no cover - annotations seulement (aucun import runtime).
    # Types de la couche 2 reçus EN PARAMÈTRES (duck-typing au runtime). Importés
    # UNIQUEMENT pour l'annotation statique — JAMAIS au runtime (archi §3.1).
    from collections.abc import Iterable, Sequence

    from app.knowledge.loader import SafetyStandard, SafetyTable, Technique


# --------------------------------------------------------------------------- #
# Constantes documentées.                                                      #
# --------------------------------------------------------------------------- #

# Tolérance numérique autour des scalaires / bornes d'intervalle (en degrés).
# Tolère l'arrondi du LLM (ex. 163.0 vs 163) sans masquer un écart sémantique
# (un 999 reste hors base, un 60 reste < 74). Documentée (cf. Dev Notes D2).
_TEMP_EPSILON = 0.5


# --------------------------------------------------------------------------- #
# Normalisation (helpers RECOPIÉS de app/knowledge/loader.py, lignes 61-86 et  #
# 357-369). Recopie volontaire : les couches ne s'importent pas entre elles    #
# (archi §3.1). Légère duplication préférable au couplage inter-couches.       #
# --------------------------------------------------------------------------- #


def _strip_accents(text: str) -> str:
    """Supprime les accents (é -> e) sans dépendance externe."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _normalize(text: str) -> str:
    """Minuscule + suppression des accents."""
    return _strip_accents(text).lower()


def _tokenize(text: str) -> list[str]:
    """Découpe en tokens alphanumériques (les séparateurs deviennent des
    frontières de token). Matching par token entier : « four » ne matche pas
    « fourchette »."""
    normalized = _normalize(text)
    token: list[str] = []
    tokens: list[str] = []
    for ch in normalized:
        if ch.isalnum():
            token.append(ch)
        elif token:
            tokens.append("".join(token))
            token = []
    if token:
        tokens.append("".join(token))
    return tokens


def _is_subsequence(needle: tuple[str, ...], haystack: list[str]) -> bool:
    """True si ``needle`` apparaît comme sous-séquence CONTIGUË dans ``haystack``.

    Comparaison par token entier (pas de sous-chaîne) : « four » (``('four',)``)
    ⊂ « cocotte au four » (``['cocotte','au','four']``) mais « four » ⊄
    « fourchette » (``['fourchette']``). ``needle`` vide -> False.
    """
    n = len(needle)
    if n == 0:
        return False
    for start in range(len(haystack) - n + 1):
        if tuple(haystack[start : start + n]) == needle:
            return True
    return False


# --------------------------------------------------------------------------- #
# Extraction numérique (scalaires + intervalles texte).                        #
# --------------------------------------------------------------------------- #

# Un nombre (entier ou décimal, virgule ou point) éventuellement signé.
_NUMBER_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")
# Un intervalle « low-high » : deux nombres séparés par un tiret (-, –, —).
# Les bornes peuvent porter des espaces ; on capture les deux nombres.
_RANGE_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*[-–—]\s*(\d+(?:[.,]\d+)?)"
)


def _to_float(raw: str) -> float | None:
    """Convertit une chaîne numérique (virgule ou point) en float, ou None."""
    try:
        return float(raw.replace(",", "."))
    except (TypeError, ValueError):
        return None


def _extract_numbers_with_ranges(value: object) -> list[tuple[float, float]]:
    """Extrait les plages numériques ``(low, high)`` autorisées d'une valeur.

    Cas couverts (décisions de robustesse, mode non-interactif) :
      - scalaire numérique : ``100`` -> ``[(100.0, 100.0)]`` ;
      - intervalle texte : « 150-160 » -> ``[(150.0, 160.0)]`` (tiret ``-`` ou
        tirets longs ``–``/``—``) ; intervalle inversé normalisé (min, max) ;
      - scalaire noyé dans du texte : « 163 C » -> ``[(163.0, 163.0)]`` ;
      - texte non numérique (« feu vif (pleine ebullition) ») -> ``[]``.

    Stratégie : on cherche d'abord les intervalles « low-high », puis on ajoute
    les nombres isolés NON déjà consommés par un intervalle (pour ne pas compter
    deux fois les bornes). Déterministe (ordre d'apparition).
    """
    if isinstance(value, bool):
        # bool est une sous-classe d'int : non pertinent comme température.
        return []
    if isinstance(value, (int, float)):
        v = float(value)
        return [(v, v)]
    if not isinstance(value, str):
        # Tout autre type (dict de ratios, None...) -> aucune plage.
        return []

    ranges: list[tuple[float, float]] = []
    consumed_spans: list[tuple[int, int]] = []
    for match in _RANGE_RE.finditer(value):
        low = _to_float(match.group(1))
        high = _to_float(match.group(2))
        if low is None or high is None:
            continue
        ranges.append((min(low, high), max(low, high)))
        consumed_spans.append(match.span())

    def _inside_consumed(span: tuple[int, int]) -> bool:
        return any(start <= span[0] and span[1] <= end for start, end in consumed_spans)

    for match in _NUMBER_RE.finditer(value):
        if _inside_consumed(match.span()):
            continue
        scalar = _to_float(match.group(0))
        if scalar is not None:
            ranges.append((scalar, scalar))
    return ranges


# --------------------------------------------------------------------------- #
# Agrégation des températures autorisées (techniques + safety).                #
# --------------------------------------------------------------------------- #


def _key_is_temperature(key: str) -> bool:
    """Heuristique : une clé ``parameters`` est une température si son nom (insensible
    casse) contient « temp ».

    Capte ``tempC`` / ``tempF`` / ``panTempC`` / ``searTempC`` / ``ovenTempC`` /
    ``ovenTempF`` et EXCLUT ``timeMinutes`` / ``ratios`` / ``heat`` (qui ne
    contiennent pas « temp »). On ne parse JAMAIS les températures noyées dans
    ``heat`` / ``timeMinutes`` (texte libre), pour ne pas « autoriser » par
    accident une valeur via une chaîne de temps.
    """
    return "temp" in key.lower()


def _key_unit(key: str) -> str:
    """Déduit l'unité (« C » / « F ») d'une clé de température par son suffixe.

    ``*F`` (insensible casse) -> « F » ; sinon « C » (défaut documenté : la base
    italienne suffixe ``...C``/``...F``, °C par défaut si ambigu).
    """
    return "F" if key.lower().endswith("f") else "C"


def _allowed_temperature_ranges(
    techniques: Iterable[Technique],
    safety: SafetyTable | Iterable[SafetyStandard] | None,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Agrège les plages de température autorisées, séparées par unité.

    Retourne ``(ranges_c, ranges_f)`` où chaque liste contient des plages
    ``(low, high)`` (bornes incluses, tolérance appliquée à la comparaison).

    Côté ``techniques`` (duck-typing ``getattr(t, "parameters", {})``) : pour
    chaque technique, on ne retient que les CLÉS de température (heuristique
    ``_key_is_temperature``) ; ``*C`` -> plages °C, ``*F`` -> plages °F. Les clés
    ``timeMinutes`` / ``ratios`` / ``heat`` sont ignorées.

    Côté ``safety`` : chaque ``min_internal_c`` / ``min_internal_f`` devient une
    plage ponctuelle ``(v, v)`` (un minimum cité À sa valeur exacte est autorisé).
    """
    ranges_c: list[tuple[float, float]] = []
    ranges_f: list[tuple[float, float]] = []

    for technique in techniques or ():
        parameters = getattr(technique, "parameters", None)
        if not isinstance(parameters, dict):
            continue
        for key, raw_value in parameters.items():
            if not isinstance(key, str) or not _key_is_temperature(key):
                continue
            target = ranges_f if _key_unit(key) == "F" else ranges_c
            target.extend(_extract_numbers_with_ranges(raw_value))

    for standard in _safety_standards(safety):
        min_c = getattr(standard, "min_internal_c", None)
        min_f = getattr(standard, "min_internal_f", None)
        if isinstance(min_c, (int, float)) and not isinstance(min_c, bool):
            ranges_c.append((float(min_c), float(min_c)))
        if isinstance(min_f, (int, float)) and not isinstance(min_f, bool):
            ranges_f.append((float(min_f), float(min_f)))

    return ranges_c, ranges_f


def _safety_standards(
    safety: SafetyTable | Iterable[SafetyStandard] | None,
) -> list[SafetyStandard]:
    """Normalise ``safety`` en liste de ``SafetyStandard`` (duck-typing).

    Accepte un ``SafetyTable`` (attribut ``.standards``), un itérable de
    ``SafetyStandard``, ou ``None`` -> ``[]``. Robuste (mode non-interactif).
    """
    if safety is None:
        return []
    standards = getattr(safety, "standards", None)
    if standards is not None:
        return list(standards)
    # Itérable direct de standards (stubs de test, par ex.).
    try:
        return list(safety)  # type: ignore[arg-type]
    except TypeError:
        return []


def _temp_in_ranges(
    value: float,
    ranges: Sequence[tuple[float, float]],
    eps: float = _TEMP_EPSILON,
) -> bool:
    """True si ``value`` ∈ une plage ``(low - eps, high + eps)`` (bornes incluses)."""
    for low, high in ranges:
        if (low - eps) <= value <= (high + eps):
            return True
    return False


# --------------------------------------------------------------------------- #
# Contrôle 1 — appartenance des températures.                                  #
# --------------------------------------------------------------------------- #


def _check_temperatures(
    recipe: StructuredRecipe,
    ranges_c: Sequence[tuple[float, float]],
    ranges_f: Sequence[tuple[float, float]],
) -> list[Violation]:
    """Vérifie l'appartenance de chaque température citée (par unité).

    Une température en « C » est comparée aux plages °C ; en « F » aux plages °F.
    Hors base ⇒ ``Violation(kind="temperature_hors_base", severity="critical")``.
    Parcours déterministe (ordre des étapes, puis des températures).
    """
    violations: list[Violation] = []
    for index, step in enumerate(recipe.steps, start=1):
        for temperature in step.temperatures:
            unit = (temperature.unit or "C").upper()
            ranges = ranges_f if unit == "F" else ranges_c
            if not _temp_in_ranges(float(temperature.value), ranges):
                violations.append(
                    Violation(
                        kind="temperature_hors_base",
                        detail=(
                            f"Étape {index} : température {temperature.value:g}°{unit} "
                            f"hors base (aucune technique autorisée ni minimum de "
                            f"sécurité ne la justifie)."
                        ),
                        severity="critical",
                    )
                )
    return violations


# --------------------------------------------------------------------------- #
# Contrôle 2 — sécurité protéines.                                             #
# --------------------------------------------------------------------------- #


# Synonymes FR best-effort : libellés courants du corpus -> tokens présents dans
# les `food_type` de `safety`. Permet de relier « cuisses de poulet » /
# « dinde » -> « volaille », « jarret de veau » -> « veau », etc., là où le
# simple recoupement de tokens échouerait (le libellé recette n'emploie pas le
# même mot que le `food_type`). Décision par défaut documentée (mode non-
# interactif) : table volontairement minimale et conservatrice ; un terme absent
# ne déclenche AUCUN contrôle protéine (pas de faux positif — on n'invente jamais
# une protéine). Les minima restent EXCLUSIVEMENT issus de `safety`.
_PROTEIN_SYNONYMS: dict[str, frozenset[str]] = {
    "poulet": frozenset({"volaille"}),
    "poule": frozenset({"volaille"}),
    "poularde": frozenset({"volaille"}),
    "dinde": frozenset({"volaille"}),
    "dindon": frozenset({"volaille"}),
    "canard": frozenset({"volaille"}),
    "pintade": frozenset({"volaille"}),
    "chapon": frozenset({"volaille"}),
    "boeuf": frozenset({"boeuf"}),
    "veau": frozenset({"veau"}),
    "agneau": frozenset({"agneau"}),
    "porc": frozenset({"porc"}),
    "jambon": frozenset({"porc"}),
    "saumon": frozenset({"poisson"}),
    "cabillaud": frozenset({"poisson"}),
    "thon": frozenset({"poisson"}),
    "merlu": frozenset({"poisson"}),
    "dorade": frozenset({"poisson"}),
    "bar": frozenset({"poisson"}),
    "truite": frozenset({"poisson"}),
    "crevette": frozenset({"poisson", "mer"}),
    "crevettes": frozenset({"poisson", "mer"}),
    "oeuf": frozenset({"oeufs"}),
    "oeufs": frozenset({"oeufs"}),
}


def _expand_synonyms(text_tokens: set[str]) -> set[str]:
    """Étend les tokens d'un libellé recette avec les synonymes protéines connus.

    Best-effort : ``{"cuisses", "de", "poulet"}`` -> ajoute ``"volaille"`` pour
    recouper la ligne ``safety`` « Volaille... ». N'enlève jamais de token.
    """
    expanded = set(text_tokens)
    for token in text_tokens:
        expanded |= _PROTEIN_SYNONYMS.get(token, frozenset())
    return expanded


def _matching_standard(
    text_tokens: set[str],
    standards: Sequence[SafetyStandard],
) -> SafetyStandard | None:
    """Retourne la première ligne ``safety`` dont les tokens recoupent ``text_tokens``.

    Matching insensible casse/accents (tokens normalisés), même stratégie que
    ``safety_for`` (couche 2, recopiée) ENRICHIE d'une table de synonymes FR
    best-effort (``_expand_synonyms`` : « poulet » -> « volaille »). Aucun
    recoupement -> None (pas de faux positif : on n'invente jamais une protéine
    absente).
    """
    if not text_tokens:
        return None
    expanded = _expand_synonyms(text_tokens)
    for standard in standards:
        row_tokens = set(_tokenize(getattr(standard, "food_type", "")))
        if expanded & row_tokens:
            return standard
    return None


def _check_proteins(
    recipe: StructuredRecipe,
    safety: SafetyTable | Iterable[SafetyStandard] | None,
) -> list[Violation]:
    """Vérifie la sécurité des protéines détectées (minima EXCLUSIVEMENT ``safety``).

    Détection best-effort : on tokenise chaque ``Quantity.name`` (ingrédients) et,
    à défaut, le texte des étapes, puis on cherche la ligne ``safety`` applicable
    (recoupement de tokens contre les ``food_type``). Pour chaque protéine
    distincte trouvée (clé = ``food_type``, ordre stable) :
      (a) si une température lui est citée < minimum (selon unité) ⇒ violation ;
      (b) si AUCUNE température de sécurité ≥ minimum n'est citée ⇒ violation.
    ``severity`` suit ``SafetyStandard.critical`` (« critical » sinon « warning »).
    """
    standards = _safety_standards(safety)
    if not standards:
        return []

    # Collecte des protéines détectées, dans un ordre déterministe (ordre des
    # ingrédients puis des étapes), dédupliquées par food_type.
    detected: dict[str, SafetyStandard] = {}
    for quantity in recipe.ingredients:
        standard = _matching_standard(set(_tokenize(quantity.name)), standards)
        if standard is not None:
            detected.setdefault(standard.food_type, standard)
    for step in recipe.steps:
        standard = _matching_standard(set(_tokenize(step.text)), standards)
        if standard is not None:
            detected.setdefault(standard.food_type, standard)

    if not detected:
        return []

    # Toutes les températures citées (valeur, unité, est_securite) de la recette.
    # `est_securite` : la température est-elle une CITATION DE SÉCURITÉ ? Indice
    # primaire = `label == "SÉCURITÉ"` (étiquetage barrière 1, archi §6.1). Le
    # validateur reste robuste si le label est mal posé (cf. fallback ci-dessous
    # sur la VALEUR proche du minimum), mais une température purement TECHNIQUE
    # (ex. 155°C de température de poêle) NE compte PAS comme citation de la
    # température interne de sécurité d'une protéine.
    cited_temps: list[tuple[float, str, bool]] = [
        (
            float(temperature.value),
            (temperature.unit or "C").upper(),
            _normalize(temperature.label or "") == _normalize("SÉCURITÉ"),
        )
        for step in recipe.steps
        for temperature in step.temperatures
    ]

    violations: list[Violation] = []
    for food_type, standard in detected.items():
        critical = bool(getattr(standard, "critical", False))
        severity = "critical" if critical else "warning"
        min_c = getattr(standard, "min_internal_c", None)
        min_f = getattr(standard, "min_internal_f", None)

        below_minimum = False
        has_safe_citation = False
        for value, unit, is_security in cited_temps:
            minimum = min_f if unit == "F" else min_c
            if not isinstance(minimum, (int, float)) or isinstance(minimum, bool):
                continue
            minimum = float(minimum)
            # Une température est rattachée à la protéine si elle est étiquetée
            # SÉCURITÉ (indice primaire) OU si sa valeur tombe au minimum à ±epsilon
            # (fallback robuste au label mal posé : un 60°C cité « pour la volaille »
            # à 74°C de minimum reste détecté même sans label). Une température
            # purement TECHNIQUE nettement au-dessus (155°C) est ignorée.
            near_minimum = abs(value - minimum) <= _TEMP_EPSILON
            if is_security or near_minimum:
                if value < minimum - _TEMP_EPSILON:
                    below_minimum = True
                else:
                    has_safe_citation = True

        if below_minimum:
            violations.append(
                Violation(
                    kind="securite_proteine",
                    detail=(
                        f"{food_type} : température interne citée inférieure au "
                        f"minimum de sécurité ({_format_minimum(standard)})."
                    ),
                    severity=severity,
                )
            )
        elif not has_safe_citation:
            violations.append(
                Violation(
                    kind="securite_proteine",
                    detail=(
                        f"{food_type} : protéine présente sans citation de sa "
                        f"température de sécurité ({_format_minimum(standard)})."
                    ),
                    severity=severity,
                )
            )
    return violations


def _format_minimum(standard: SafetyStandard) -> str:
    """Formate le minimum d'une ligne ``safety`` (« 74°C / 165°F ») pour le feedback."""
    parts: list[str] = []
    min_c = getattr(standard, "min_internal_c", None)
    min_f = getattr(standard, "min_internal_f", None)
    if isinstance(min_c, (int, float)) and not isinstance(min_c, bool):
        parts.append(f"{float(min_c):g}°C")
    if isinstance(min_f, (int, float)) and not isinstance(min_f, bool):
        parts.append(f"{float(min_f):g}°F")
    return " / ".join(parts) if parts else "minimum non renseigné"


# --------------------------------------------------------------------------- #
# Contrôle 3 — cookware interdit.                                              #
# --------------------------------------------------------------------------- #


def _check_cookware(
    recipe: StructuredRecipe,
    forbidden: frozenset[str],
) -> list[Violation]:
    """Vérifie qu'aucun ``#cookware`` n'appartient à ``forbidden``.

    Matching par sous-séquence de tokens normalisés (durci B4) : « four »
    (``('four',)``) ⊂ « cocotte au four » ⇒ interdit ; « four » ⊄ « fourchette »
    ⇒ PAS interdit. ``forbidden`` vide ⇒ aucune violation.
    """
    if not forbidden:
        return []
    forbidden_sequences = [
        tuple(_tokenize(item)) for item in forbidden
    ]
    forbidden_sequences = [seq for seq in forbidden_sequences if seq]

    violations: list[Violation] = []
    for index, step in enumerate(recipe.steps, start=1):
        for tool in step.cookware:
            tool_tokens = _tokenize(tool)
            for seq in forbidden_sequences:
                if _is_subsequence(seq, tool_tokens):
                    violations.append(
                        Violation(
                            kind="cookware_interdit",
                            detail=(
                                f"Étape {index} : ustensile « {tool} » interdit "
                                f"par les contraintes utilisateur."
                            ),
                            severity="critical",
                        )
                    )
                    break  # Un seul rejet par ustensile (déterministe).
    return violations


# --------------------------------------------------------------------------- #
# Assemblage du verdict.                                                       #
# --------------------------------------------------------------------------- #


def _build_feedback(violations: Sequence[Violation]) -> str:
    """Construit un message ciblé exploitable par le retry (D1), 1 ligne/violation.

    Énumère chaque violation (``kind`` + ``detail`` + ``severity``) dans l'ordre
    déterministe d'apparition. Vide si aucune violation.
    """
    if not violations:
        return ""
    header = (
        f"{len(violations)} violation(s) détectée(s) — corriger STRICTEMENT à "
        f"partir de la base (températures, sécurité protéines, ustensiles) :"
    )
    lines = [
        f"- [{violation.kind}/{violation.severity}] {violation.detail}"
        for violation in violations
    ]
    return "\n".join([header, *lines])


def validate_recipe(
    recipe: StructuredRecipe,
    techniques: Iterable[Technique],
    safety: SafetyTable | Iterable[SafetyStandard] | None,
    forbidden: frozenset[str] = frozenset(),
) -> ValidationResult:
    """Valide DÉTERMINISTIQUEMENT une recette contre la base (barrière 2, §6.2).

    Réalise les 4 contrôles MÉCANIQUES (températures hors base, sécurité
    protéines, cookware interdit) et retourne un ``ValidationResult`` exploitable
    pour le retry — SANS faire le retry (boucle dans ``client.generate_recipe``,
    D1) et SANS réparation silencieuse (``recipe`` n'est jamais muté).

    Args:
        recipe: la ``StructuredRecipe`` produite par le LLM (LECTURE SEULE).
        techniques: les techniques autorisées (couche 2, duck-typing : chaque
            objet expose ``.parameters: dict``). Source des températures
            autorisées (scalaires + intervalles texte).
        safety: la table de sécurité (``SafetyTable`` avec ``.standards``, ou un
            itérable de ``SafetyStandard``). Source EXCLUSIVE des minima protéines
            et des températures de sécurité autorisées.
        forbidden: ensemble des ustensiles ``#cookware`` interdits (déjà résolu
            côté appelant). Défaut ``frozenset()`` (signature §4.4 rétro-compatible)
            ⇒ aucune violation cookware.

    Returns:
        ``ValidationResult(ok, violations, feedback)`` : ``ok`` est vrai s'il n'y
        a AUCUNE violation ``critical`` ; ``violations`` est le tuple ordonné/
        déterministe des violations détectées ; ``feedback`` est un message ciblé
        (vide quand aucune violation).

    Pureté : aucune I/O, aucun ``random``, aucune horloge, aucune lecture de
    fichier, aucune mutation. Mêmes entrées ⇒ même ``ValidationResult``.
    """
    techniques = list(techniques or ())
    ranges_c, ranges_f = _allowed_temperature_ranges(techniques, safety)

    # Ordre déterministe : températures -> protéines -> cookware (dans l'ordre
    # des étapes au sein de chaque contrôle).
    violations: list[Violation] = []
    violations.extend(_check_temperatures(recipe, ranges_c, ranges_f))
    violations.extend(_check_proteins(recipe, safety))
    violations.extend(_check_cookware(recipe, forbidden))

    has_critical = any(violation.severity == "critical" for violation in violations)
    ok = not has_critical and len(violations) == 0
    feedback = _build_feedback(violations)
    return ValidationResult(ok=ok, violations=tuple(violations), feedback=feedback)


if __name__ == "__main__":
    # Sanity-check rapide (sans réseau) : python -m app.generator.validate
    from app.generator.models import Quantity, Step, Temperature

    # Stubs duck-typés minimaux (couche 2 NON importée au runtime).
    class _StubTechnique:
        def __init__(self, parameters: dict) -> None:
            self.parameters = parameters

    class _StubStandard:
        def __init__(self, food_type, c, f, critical=True):  # noqa: ANN001
            self.food_type = food_type
            self.min_internal_c = c
            self.min_internal_f = f
            self.critical = critical

    class _StubSafety:
        def __init__(self, standards) -> None:  # noqa: ANN001
            self.standards = standards

    techniques = [_StubTechnique({"tempC": 100, "panTempC": "150-160", "sauceTempC": "82-90"})]
    safety = _StubSafety([_StubStandard("Volaille (entiere, parts, hachee)", 74, 165)])

    clean = StructuredRecipe(
        title="Risotto à la volaille",
        servings=2,
        ingredients=(Quantity(name="cuisses de poulet", amount=400, unit="g"),),
        steps=(
            Step(
                text="[TECHNIQUE] Suer puis nacrer le riz.",
                cookware=("casserole à fond épais",),
                temperatures=(Temperature(value=155, unit="C", label="TECHNIQUE"),),
            ),
            Step(
                text="[SÉCURITÉ] Cuire la volaille à cœur.",
                temperatures=(Temperature(value=74, unit="C", label="SÉCURITÉ"),),
            ),
        ),
    )
    trapped = StructuredRecipe(
        title="Risotto piégé",
        servings=2,
        ingredients=(Quantity(name="cuisses de poulet", amount=400, unit="g"),),
        steps=(
            Step(
                text="[TECHNIQUE] Chauffer follement.",
                cookware=("four",),
                temperatures=(
                    Temperature(value=999, unit="C", label="TECHNIQUE"),
                    Temperature(value=60, unit="C", label="SÉCURITÉ"),
                ),
            ),
        ),
    )

    result_clean = validate_recipe(clean, techniques, safety)
    print(f"Recette propre -> ok={result_clean.ok}, violations={len(result_clean.violations)}")

    result_trapped = validate_recipe(trapped, techniques, safety, forbidden=frozenset({"four"}))
    print(f"Recette piégée -> ok={result_trapped.ok}, violations={len(result_trapped.violations)}")
    for violation in result_trapped.violations:
        print(f"  - [{violation.kind}] {violation.detail}")
