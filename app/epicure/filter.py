"""Filtrage des voisins Epicure par cuisine / contraintes (couche 1, story A3).

À partir des voisins bruts produits par `EpicureIndex.neighbors(...)` (A1), cette
fonction pure applique un filtrage à DEUX régimes, conforme à la signature
prescrite (architecture §4.1) et à la décision D14 :

  1. Filtrage cuisine SOUPLE : n'écarte JAMAIS un voisin ; il l'ANNOTE de son
     contexte cuisine (macro-région résolue via `docs/epicure/cuisine_macroregions.json`).
     L'annotation sert l'explicabilité (FR7), pas la sélection. Dégradation
     gracieuse : si les données cuisine sont absentes / non résolubles,
     l'annotation devient neutre (`"unknown"`), aucune exception n'est levée.
  2. Rejet DUR par régime alimentaire : seul mécanisme qui SUPPRIME un voisin.
     Piloté par la table de données versionnée `app/epicure/diet_exclusions.json`
     (régime -> clés Epicure exclues). Chaque rejet porte sa raison explicite en
     français. Modulaire (OA3) : ajouter un régime = éditer le JSON, pas le code.

La sortie `FilteredNeighbors` expose `kept` (voisins retenus annotés) et
`rejected` (tuples `(name, score, reason)`), directement sérialisables pour
`DebugInfo.epicure` (FR7).

Module PUR / déterministe (archi §5.1) : mêmes entrées -> même sortie, ordre des
`candidates` préservé, score cosinus d'origine conservé. Lecture seule des JSON
(via `functools.lru_cache`), aucune I/O réseau, aucun LLM, aucun état mutable
global. Aucune nouvelle dépendance (json, unicodedata, pathlib, dataclasses,
functools suffisent).

Périmètre (Dev Notes A3) :
  - A3 reçoit des clés Epicure DÉJÀ RÉSOLUES (snake_case EN) : aucune traduction
    FR->EN ici (relève d'A4 / RZ3).
  - `no_cookware` est conservé dans `Constraints` pour l'alignement de schéma
    (archi §9.1) mais n'est PAS utilisé pour filtrer des voisins (un ustensile
    n'est pas un ingrédient ; le cookware est couvert par la couche 2 / B4).
  - Découplage inter-couches (archi §3.1) : `app/epicure/` n'importe NI
    `app/knowledge/` NI `app/scaling/`. Le patron de normalisation
    `_strip_accents`/`_normalize` est RECOPIÉ ici (et non importé), comme déjà
    fait en couche 2 (`app/knowledge/loader.py:61-86`, recopie de
    `app/scaling/table.py:52-77`). Cette légère duplication est volontaire.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# Chemins relatifs au repo (cf. patron app/epicure/loader.py#21). Depuis
# app/epicure/, la racine du dépôt est à parents[2].
_MACROREGIONS_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "epicure" / "cuisine_macroregions.json"
)
# La table de régime est versionnée À CÔTÉ du module (app/epicure/).
_DIET_EXCLUSIONS_PATH = Path(__file__).with_name("diet_exclusions.json")

# Annotation cuisine neutre lorsqu'aucune macro-région n'est résoluble
# (cuisine inconnue, ou données cuisine absentes -> dégradation gracieuse).
_UNKNOWN_CUISINE = "unknown"


# --------------------------------------------------------------------------- #
# Normalisation (mêmes helpers que app/scaling/table.py:52-60).                #
# Les couches ne se connaissent pas entre elles (archi §3.1) : on RECOPIE les  #
# helpers plutôt que d'importer app.scaling (couche 3) ou app.knowledge        #
# (couche 2) depuis la couche 1. Duplication volontaire (testabilité).         #
# --------------------------------------------------------------------------- #


def _strip_accents(text: str) -> str:
    """Supprime les accents (é -> e) sans dépendance externe."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _normalize(text: str) -> str:
    """Minuscule + suppression des accents (« VÉGÉTARIEN » -> « vegetarien »)."""
    return _strip_accents(text).strip().lower()


# --------------------------------------------------------------------------- #
# Type Constraints LOCAL minimal (couche 1).                                   #
# Décision figée (Dev Notes A3, §5) : A3 NE réimporte PAS le Constraints de    #
# app/knowledge ; on définit un Constraints local minimal aligné sur le schéma #
# archi §9.1, sans coupler les couches. La conversion depuis le Constraints    #
# Pydantic se fera à la frontière web (E1), pas ici.                           #
# --------------------------------------------------------------------------- #


@dataclass
class Constraints:
    """Contraintes utilisateur minimales pour le filtrage couche 1.

    Aligné sur le schéma archi §9.1. `no_cookware` est conservé pour
    l'alignement de schéma mais n'est PAS utilisé par `filter_neighbors` (le
    cookware est une affaire de couche 2 / B4, pas d'un voisin d'ingrédient).
    """

    diet: list[str] = field(default_factory=list)
    no_cookware: list[str] = field(default_factory=list)
    highlight: str | None = None


# --------------------------------------------------------------------------- #
# Dataclasses de sortie (stdlib, sérialisables pour FR7 / DebugInfo.epicure).  #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class KeptNeighbor:
    """Voisin retenu, annoté de son contexte cuisine (macro-région ou unknown).

    `score` est le score cosinus d'origine reçu en entrée (préservé, non
    recalculé). `cuisine_context` sert l'explicabilité (FR7), jamais la
    sélection (filtrage cuisine SOUPLE, D14).
    """

    name: str
    score: float
    cuisine_context: str


@dataclass(frozen=True)
class FilteredNeighbors:
    """Résultat du filtrage : retenus (annotés) + rejetés (avec raison).

    Exposé tel quel à la couche 4 (associations validées = `kept`) et au panneau
    debug FR7 (`DebugInfo.epicure` = retenus/rejetés + raisons). `rejected` est
    une liste de tuples `(name, score, reason)` directement sérialisables.
    """

    kept: list[KeptNeighbor] = field(default_factory=list)
    rejected: list[tuple[str, float, str]] = field(default_factory=list)

    def to_debug(self) -> dict[str, list[dict[str, object]]]:
        """Représentation sérialisable (JSON-friendly) pour `DebugInfo.epicure`."""
        return {
            "kept": [
                {"name": n.name, "score": n.score, "cuisine_context": n.cuisine_context}
                for n in self.kept
            ],
            "rejected": [
                {"name": name, "score": score, "reason": reason}
                for (name, score, reason) in self.rejected
            ],
        }


# --------------------------------------------------------------------------- #
# Chargement des données (lecture seule, mises en cache une seule fois).       #
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=1)
def _load_macroregions() -> dict[str, list[str]]:
    """Charge `cuisine_macroregions.json` -> { macro_region: [traditions...] }.

    Dégradation gracieuse : si le fichier est absent ou illisible, retourne un
    mapping VIDE (jamais d'exception). NOTE (Dev Notes A3) : les fichiers par
    modèle `cuisine_pole_provenance.json` / `modes.json` (archi §4.1)
    N'EXISTENT PAS dans le repo (`data/epicure/` gitignoré) ; seule
    `cuisine_macroregions.json` est consommée, et son absence est tolérée.
    """
    try:
        raw = json.loads(_MACROREGIONS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    result: dict[str, list[str]] = {}
    for macro_region, payload in raw.items():
        if isinstance(payload, dict):
            traditions = payload.get("traditions", [])
            if isinstance(traditions, list):
                result[macro_region] = [str(t) for t in traditions]
    return result


@lru_cache(maxsize=1)
def _load_diet_exclusions() -> dict[str, frozenset[str]]:
    """Charge `diet_exclusions.json` -> { regime_normalisé: frozenset(clés exclues) }.

    Les clés de régime sont normalisées (casse/accents) pour un appariement
    robuste. Dégradation gracieuse : fichier absent/illisible -> mapping vide.
    """
    try:
        raw = json.loads(_DIET_EXCLUSIONS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    result: dict[str, frozenset[str]] = {}
    for diet_key, excluded in raw.items():
        # Les clés de commentaire (préfixe « _ ») et entrées non-listes sont ignorées.
        if diet_key.startswith("_") or not isinstance(excluded, list):
            continue
        result[_normalize(diet_key)] = frozenset(str(k) for k in excluded)
    return result


# --------------------------------------------------------------------------- #
# Résolution cuisine SOUPLE -> macro-région (annotation, jamais sélection).    #
# --------------------------------------------------------------------------- #


def _resolve_cuisine_context(cuisine: str) -> str:
    """Résout `cuisine` -> macro-région (annotation), ou `"unknown"`.

    Heuristique v1 (documentée) : on normalise `cuisine` (ex. `italian_savory_v1`
    -> `italian savory v1`) puis on cherche une tradition de
    `cuisine_macroregions.json` dont le radical normalisé est contenu dans la
    cuisine normalisée (ex. radical `ital` de `Italian` ⊂ `italian...` ->
    macro-région `Mediterranean`). Aucune correspondance ou données absentes ->
    `"unknown"` (dégradation gracieuse, aucune exception, aucun rejet).
    """
    normalized_cuisine = _normalize(cuisine)
    if not normalized_cuisine:
        return _UNKNOWN_CUISINE
    macroregions = _load_macroregions()
    for macro_region, traditions in macroregions.items():
        for tradition in traditions:
            # On compare sur le radical : « Italian » -> radical « ital » suffit à
            # matcher « italian_savory_v1 » sans dépendre de la casse/des accents.
            radical = _normalize(tradition)[:4]
            if radical and radical in normalized_cuisine:
                return macro_region
    return _UNKNOWN_CUISINE


# --------------------------------------------------------------------------- #
# Fonction principale (signature PRESCRITE, archi §4.1).                       #
# --------------------------------------------------------------------------- #


def filter_neighbors(
    candidates: list[tuple[str, float]],
    cuisine: str,
    constraints: Constraints,
) -> FilteredNeighbors:  # retenus + rejetés (avec raison) pour le panneau debug
    """Filtre les voisins bruts par cuisine (souple) et régime (rejet dur).

    Args:
        candidates: voisins déjà résolus `[(clé_snake_case_EN, score_cosinus), ...]`
            tels que produits par `EpicureIndex.neighbors(...)`. A3 ne traduit pas.
        cuisine: identifiant de cuisine (ex. `"italian_savory_v1"`), utilisé pour
            ANNOTER (jamais filtrer) chaque voisin retenu.
        constraints: contraintes utilisateur ; seul `constraints.diet` peut
            provoquer un rejet DUR (via `diet_exclusions.json`).

    Returns:
        `FilteredNeighbors(kept, rejected)`. Invariant garanti :
        `len(kept) + len(rejected) == len(candidates)`. Ordre d'entrée préservé,
        score d'origine préservé. `candidates` vide -> tout vide (aucune erreur).
    """
    # Union des clés exclues par l'ensemble des régimes demandés. Un régime
    # inconnu de la table contribue l'ensemble vide (no-op, pas d'erreur).
    exclusions = _load_diet_exclusions()
    excluded_keys: set[str] = set()
    for diet in constraints.diet:
        excluded_keys |= exclusions.get(_normalize(diet), frozenset())

    # Annotation cuisine commune (souple) : résolue une fois, identique pour tous.
    cuisine_context = _resolve_cuisine_context(cuisine)

    kept: list[KeptNeighbor] = []
    rejected: list[tuple[str, float, str]] = []

    for name, score in candidates:
        if name in excluded_keys:
            # Rejet DUR par régime : raison explicite en français.
            reason = f"régime {', '.join(constraints.diet)} : ingrédient exclu ({name})"
            rejected.append((name, score, reason))
        else:
            kept.append(KeptNeighbor(name=name, score=score, cuisine_context=cuisine_context))

    return FilteredNeighbors(kept=kept, rejected=rejected)
