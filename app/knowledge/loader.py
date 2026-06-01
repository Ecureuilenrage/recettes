"""Loader de la base technique : securite + cuisines modulaires (couche 2, B3).

Sources de verite (lues UNE SEULE fois, en lecture seule) :
  - docs/base-technique/safety-temperatures.json  (autoritatif, transverse)
  - docs/base-technique/cuisine-*.json            (decouverte modulaire, OA3)

Expose (signatures prescrites archi 4.2) :
  - load_safety() -> SafetyTable          : table de securite typee.
  - load_cuisines() -> dict[str, Cuisine] : cuisines indexees par meta.id.
  - safety_for(food_type) -> SafetyStandard | None : ligne de securite d'une
    proteine (matching insensible casse/accents).
  - techniques_for(cuisine, ingredient, constraints) -> list[Technique] :
    techniques applicables, EXCLUT celles dont un ustensile requis est interdit.
  - forbidden_cookware(cuisine, constraints) -> set[str] : API publique (B4)
    de l'ensemble normalise des ustensiles #cookware interdits par les
    contraintes utilisateur (FR4).
  - excluded_techniques(cuisine, ingredient, constraints) -> list[Exclusion] :
    raisons d'exclusion (technique + ustensile interdit + contrainte) pour le
    panneau debug FR7 et la barriere LLM (archi 6.1).

Le LLM (couche 4) CHOISIT dans cette base ; il n'invente jamais une temperature
ni une technique. Module PUR / DETERMINISTE (archi 3.1) : meme appel -> meme
resultat ; aucune nouvelle dependance (dataclasses stdlib, pas de Pydantic).

Decisions par defaut (cf. docs/stories/B3.md, B4.md) :
  - Filtrage par `ingredient` SOUPLE (D14) : on n'ecarte pas une technique si
    l'ingredient ne matche pas ; le rejet DUR est reserve au cookware interdit.
  - Cuisine inconnue -> liste vide (pas d'exception).
  - B4 promeut le helper interne B3 en API publique `forbidden_cookware` et
    DURCIT le matching : un ustensile interdit (mono- ou multi-mots) est
    compare en SOUS-SEQUENCE de tokens (« four » incluse dans « cocotte au
    four », « robot culinaire » incluse dans un requiredTools la contenant),
    insensible a la casse/aux accents, sans faux positif de sous-chaine
    (« four » ne matche pas « fourchette »).
  - HORS perimetre B4 (differe couche 4 / D1) : la SUGGESTION d'une technique
    alternative (« remplacer ») relevent du generateur LLM ; B4 se limite a
    exclure proprement et a exposer la raison d'exclusion (FR7).
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# Chemin relatif au repo (cf. patron app/scaling/table.py et app/epicure/loader.py) :
# depuis app/knowledge/, la racine du depot est a parents[2].
BASE_TECHNIQUE_DIR = Path(__file__).resolve().parents[2] / "docs" / "base-technique"
SAFETY_PATH = BASE_TECHNIQUE_DIR / "safety-temperatures.json"


# --------------------------------------------------------------------------- #
# Normalisation (memes helpers que app/scaling/table.py).                      #
# Les couches ne se connaissent pas entre elles (archi 3.1) : on recopie les   #
# helpers plutot que d'importer app.scaling (couche 3) depuis la couche 2.     #
# --------------------------------------------------------------------------- #


def _strip_accents(text: str) -> str:
    """Supprime les accents (e -> e) sans dependance externe."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _normalize(text: str) -> str:
    """Minuscule + suppression des accents."""
    return _strip_accents(text).lower()


def _tokenize(text: str) -> list[str]:
    """Decoupe en tokens alphanumeriques (les separateurs deviennent des
    frontieres de token). Matching par token entier : « ail » ne matche pas
    « vol-au-vent »."""
    normalized = _normalize(text)
    token, tokens = [], []
    for ch in normalized:
        if ch.isalnum():
            token.append(ch)
        elif token:
            tokens.append("".join(token))
            token = []
    if token:
        tokens.append("".join(token))
    return tokens


# --------------------------------------------------------------------------- #
# Dataclasses de sortie (stdlib, alignees archi 9.1).                          #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SafetyStandard:
    """Une ligne de la table de securite alimentaire (autoritatif).

    Mappe une entree de `standards[]` (cles JSON : foodType, minInternalC,
    minInternalF, restMinutes, critical, source, note). Le WORDING des valeurs
    n'est pas fige (le fichier est edite en parallele) ; seul le schema de cles
    est stable.
    """

    food_type: str
    min_internal_c: float | None
    min_internal_f: float | None
    rest_minutes: float | None
    critical: bool
    source: str
    note: str


@dataclass(frozen=True)
class SafetyTable:
    """Table de securite : liste de `SafetyStandard` (+ meta brute).

    `meta` conserve l'en-tete du fichier (authority, sources, disclaimer...)
    pour tracabilite ; jamais mute.
    """

    standards: tuple[SafetyStandard, ...]
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Technique:
    """Une technique culinaire d'une cuisine (niveau TECHNIQUE / PREFERENCE).

    `raw` conserve l'objet JSON complet (criticalPoints, donenessIndicators,
    sources...) pour que la couche 4 le consomme sans remapping exhaustif.
    """

    id: str
    name: str
    category: str
    parameters: dict
    required_tools: tuple[str, ...]
    forbidden_if: dict
    raw: dict


@dataclass(frozen=True)
class Cuisine:
    """Un module cuisine decouvert (cle = meta.id, ex. italian_savory_v1).

    `cookware_constraints` mappe une contrainte utilisateur (ex. "pas_de_four")
    a la liste des ustensiles (#cookware) interdits. `raw` conserve le JSON
    complet (meta, llmConstraints...).
    """

    id: str
    name: str
    techniques: tuple[Technique, ...]
    cookware_constraints: dict[str, list[str]]
    llm_constraints: tuple[str, ...]
    raw: dict


@dataclass
class Constraints:
    """Contraintes utilisateur (alignees sur archi 9.1 / GenerationRequest).

    Dataclass MUTABLE (listes par defaut via field) : seul conteneur de cette
    couche destine a etre instancie cote appelant.
    """

    diet: list[str] = field(default_factory=list)
    no_cookware: list[str] = field(default_factory=list)
    highlight: str | None = None


@dataclass(frozen=True)
class Exclusion:
    """Raison d'exclusion d'une technique (info debug FR7, archi 9.1).

    Trace POURQUOI une technique a ete ecartee : `technique_id` (l'id stable de
    la technique), `forbidden_tool` (l'ustensile interdit, normalise, qui a
    declenche le rejet) et `via_constraint` (la cle de contrainte utilisateur,
    ex. « pas_de_four », a l'origine de l'interdit). Alimente directement
    `DebugInfo.techniques` (techniques retenues / exclues) et la barriere LLM
    (archi 6.1 : « la remplacer ou refuser proprement »).

    La SUGGESTION d'une technique de remplacement est HORS perimetre B4
    (differee couche 4 / D1) : B4 fournit la matiere (technique exclue + raison),
    le generateur choisit l'alternative parmi les techniques RETENUES.
    """

    technique_id: str
    forbidden_tool: str
    via_constraint: str


# --------------------------------------------------------------------------- #
# Chargements (lecture seule, une seule fois via lru_cache).                   #
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=1)
def load_safety() -> SafetyTable:
    """Charge `safety-temperatures.json` UNE SEULE fois (lecture seule).

    Mappe chaque entree `standards[]` vers `SafetyStandard`. Tolerant aux cles
    manquantes (defauts surs) : ne plante pas si une valeur evolue (le fichier
    est edite en parallele ; seul le schema de cles est stable).
    """
    data = json.loads(SAFETY_PATH.read_text(encoding="utf-8"))
    standards = tuple(
        SafetyStandard(
            food_type=row.get("foodType", ""),
            min_internal_c=row.get("minInternalC"),
            min_internal_f=row.get("minInternalF"),
            rest_minutes=row.get("restMinutes"),
            critical=bool(row.get("critical", False)),
            source=row.get("source", ""),
            note=row.get("note", ""),
        )
        for row in data.get("standards", [])
    )
    return SafetyTable(standards=standards, meta=data.get("meta", {}))


def _build_technique(obj: dict) -> Technique:
    """Mappe un objet `techniques[]` JSON vers une `Technique`."""
    return Technique(
        id=obj.get("id", ""),
        name=obj.get("name", ""),
        category=obj.get("category", ""),
        parameters=obj.get("parameters", {}),
        required_tools=tuple(obj.get("requiredTools", [])),
        forbidden_if=obj.get("forbiddenIf", {}),
        raw=obj,
    )


def _build_cuisine(data: dict) -> Cuisine:
    """Mappe un fichier `cuisine-*.json` vers une `Cuisine`."""
    meta = data.get("meta", {})
    return Cuisine(
        id=meta.get("id", ""),
        name=meta.get("name", ""),
        techniques=tuple(_build_technique(t) for t in data.get("techniques", [])),
        cookware_constraints=data.get("cookwareConstraints", {}),
        llm_constraints=tuple(data.get("llmConstraints", [])),
        raw=data,
    )


@lru_cache(maxsize=1)
def load_cuisines() -> dict[str, Cuisine]:
    """Decouvre dynamiquement tous les `cuisine-*.json` (OA3, modularite).

    Scanne `BASE_TECHNIQUE_DIR` pour `cuisine-*.json` (ordre deterministe :
    chemins tries), indexe chaque cuisine par `meta.id`. AUCUNE cuisine ni nom
    de fichier code en dur : ajouter une cuisine = deposer un fichier conforme
    au schema, sans toucher au code.
    """
    cuisines: dict[str, Cuisine] = {}
    for path in sorted(BASE_TECHNIQUE_DIR.glob("cuisine-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        cuisine = _build_cuisine(data)
        if cuisine.id:
            cuisines[cuisine.id] = cuisine
    return cuisines


# --------------------------------------------------------------------------- #
# API metier.                                                                  #
# --------------------------------------------------------------------------- #


def safety_for(food_type: str) -> SafetyStandard | None:
    """Retourne la ligne de securite applicable a `food_type`, ou None.

    Matching insensible casse/accents : on retient la premiere ligne (dans
    l'ordre du fichier) dont les tokens normalises recoupent ceux de
    `food_type` (ex. « volaille » -> ligne volaille). Strategie souple, robuste
    au wording exact des libelles (qui peut evoluer).
    """
    query_tokens = set(_tokenize(food_type))
    if not query_tokens:
        return None
    for standard in load_safety().standards:
        row_tokens = set(_tokenize(standard.food_type))
        if query_tokens & row_tokens:
            return standard
    return None


def _forbidden_mapping(cuisine: Cuisine, constraints: Constraints) -> dict[str, str]:
    """Ustensiles interdits normalises -> cle de contrainte qui les interdit (B4).

    Pour chaque cle de `constraints.no_cookware` presente dans
    `cuisine.cookware_constraints`, agrege les ustensiles interdits NORMALISES
    (minuscule + accents supprimes) en les associant a la cle de contrainte
    d'origine (pour tracer la raison d'exclusion, FR7). Cle absente du mapping
    -> ignoree (contribue l'ensemble vide, pas d'erreur).

    Cas du chevauchement (un meme ustensile interdit par plusieurs cles) : on
    retient la PREMIERE cle rencontree dans l'ordre de `no_cookware`, pour un
    resultat deterministe ; l'ustensile reste interdit dans tous les cas.
    """
    mapping = cuisine.cookware_constraints
    forbidden: dict[str, str] = {}
    for key in constraints.no_cookware:
        for tool in mapping.get(key, []):
            normalized = _normalize(tool)
            forbidden.setdefault(normalized, key)
    return forbidden


def forbidden_cookware(cuisine: str, constraints: Constraints) -> set[str]:
    """Ensemble normalise des ustensiles #cookware interdits (API publique B4).

    A partir de `constraints.no_cookware` (ex. `["pas_de_four"]`) et du
    `cookwareConstraints` de la cuisine ciblee (resolue via `load_cuisines()`),
    retourne l'ENSEMBLE NORMALISE (minuscule, sans accents) des ustensiles
    interdits. Plusieurs contraintes cumulent leurs ensembles (union). Cle
    inconnue (absente de `cookwareConstraints`) -> ignoree. `no_cookware` vide
    ou cuisine inconnue -> ensemble vide.

    Source unique de verite consommee par `techniques_for` (exclusion) et par la
    couche 4 / D1 (injection dans le prompt : liste des #cookware interdits).

    [Source : docs/architecture.md#4.2 (signature `forbidden_cookware`), #6.1]
    """
    cuisine_obj = load_cuisines().get(cuisine)
    if cuisine_obj is None:
        return set()
    return set(_forbidden_mapping(cuisine_obj, constraints))


def _tool_is_forbidden(tool: str, forbidden_tokens: dict[tuple[str, ...], str]) -> str | None:
    """Retourne la cle de contrainte si `tool` (requis) est interdit, sinon None.

    Matching DURCI (B4, finding #1 revue B3) : on tokenise l'ustensile requis ET
    chaque ustensile interdit, puis on cherche la SEQUENCE de tokens interdite
    comme SOUS-SEQUENCE CONTIGUE des tokens du requis. Ainsi :
      - « four »            (['four'])           ⊂ « cocotte au four »
        (['cocotte','au','four'])  -> interdit ;
      - « robot culinaire » (['robot','culinaire']) ⊂ un requiredTools le
        contenant -> interdit (l'ancien helper B3 comparait la CHAINE entiere
        normalisee a des TOKENS mono-mot : faux negatif silencieux pour tout
        ustensile interdit MULTI-MOTS).

    Le matching par token entier (et non par sous-chaine) garantit l'absence de
    faux positif : « four » (['four']) n'est PAS une sous-sequence de
    « fourchette » (['fourchette']) car les tokens different. Meme strategie
    anti-faux-positif que l'AC2 de C1 (« ail » ⊄ « vol-au-vent »).
    """
    required = _tokenize(tool)
    for forbidden_seq, key in forbidden_tokens.items():
        if _is_subsequence(forbidden_seq, required):
            return key
    return None


def _is_subsequence(needle: tuple[str, ...], haystack: list[str]) -> bool:
    """True si `needle` apparait comme sous-sequence CONTIGUE dans `haystack`.

    Comparaison par token entier (pas de sous-chaine). `needle` vide -> False
    (un ustensile interdit sans token utile n'interdit rien).
    """
    n = len(needle)
    if n == 0:
        return False
    for start in range(len(haystack) - n + 1):
        if tuple(haystack[start : start + n]) == needle:
            return True
    return False


def _forbidden_token_sequences(
    cuisine: Cuisine, constraints: Constraints
) -> dict[tuple[str, ...], str]:
    """Ustensiles interdits TOKENISES (sequence) -> cle de contrainte (B4).

    Variante de `_forbidden_mapping` ou chaque ustensile interdit est represente
    par sa SEQUENCE de tokens (ex. « cocotte au four » -> ('cocotte','au','four'))
    pour le matching en sous-sequence contigue par `_tool_is_forbidden`. Les
    ustensiles ne produisant aucun token sont ignores.
    """
    sequences: dict[tuple[str, ...], str] = {}
    for normalized, key in _forbidden_mapping(cuisine, constraints).items():
        seq = tuple(_tokenize(normalized))
        if seq:
            sequences.setdefault(seq, key)
    return sequences


def _technique_exclusion(
    technique: Technique,
    forbidden_tokens: dict[tuple[str, ...], str],
) -> Exclusion | None:
    """Retourne l'`Exclusion` si la technique requiert un ustensile interdit.

    Combine DEUX causes d'exclusion (schema.md 2/3) :
      1. un `requiredTools` interdit (matching en sous-sequence de tokens) ;
      2. le champ optionnel `forbiddenIf.noCookware` de la technique, qui declare
         explicitement des ustensiles interdisant la technique (traite comme un
         requiredTools virtuel ; absent du JSON italien actuel mais respecte
         s'il apparait, pour rester generique — OA3 / F1).
    Premiere cause rencontree -> raison d'exclusion (ordre stable, deterministe).
    """
    # Cause 1 : ustensiles requis.
    for tool in technique.required_tools:
        key = _tool_is_forbidden(tool, forbidden_tokens)
        if key is not None:
            return Exclusion(technique.id, _normalize(tool), key)
    # Cause 2 : exclusion explicite declaree par la technique (schema.md 2).
    for tool in technique.forbidden_if.get("noCookware", []):
        key = _tool_is_forbidden(tool, forbidden_tokens)
        if key is not None:
            return Exclusion(technique.id, _normalize(tool), key)
    return None


def techniques_for(
    cuisine: str,
    ingredient: str | None,
    constraints: Constraints,
) -> list[Technique]:
    """Techniques applicables d'une cuisine, hors ustensile interdit (B3+B4).

    - Cuisine identifiee par sa cle `meta.id`. Cuisine INCONNUE -> liste vide
      (decision par defaut documentee ; l'API web traduit deja « cuisine
      inconnue » en 422 en amont).
    - EXCLUT toute technique dont un `requiredTools` (ou un `forbiddenIf.
      noCookware` declare) recoupe l'ensemble des ustensiles interdits deduits
      des contraintes (ex. « pas_de_four » exclut `searing_braising`, qui
      requiert « four »). Matching DURCI B4 : sous-sequence de tokens, donc un
      ustensile interdit multi-mots (« robot culinaire ») est aussi detecte.
    - Filtrage par `ingredient` SOUPLE (D14) : on n'ecarte PAS une technique si
      l'ingredient ne matche pas explicitement ; le rejet dur est reserve aux
      contraintes materielles. `ingredient` est accepte pour la signature
      prescrite et l'evolution future (annotation de pertinence).

    L'info debug FR7 (raisons d'exclusion) est exposee separement par
    `excluded_techniques(...)` pour preserver le type de retour `list[Technique]`.

    Pur/deterministe : meme (cuisine, ingredient, constraints) -> meme liste,
    dans l'ordre de declaration des techniques dans le fichier.
    """
    cuisine_obj = load_cuisines().get(cuisine)
    if cuisine_obj is None:
        return []

    forbidden_tokens = _forbidden_token_sequences(cuisine_obj, constraints)

    applicable: list[Technique] = []
    for technique in cuisine_obj.techniques:
        # Rejet DUR : un ustensile requis (ou declare) est interdit.
        if _technique_exclusion(technique, forbidden_tokens) is not None:
            continue
        # Filtrage souple par ingredient : volontairement non bloquant en v1.
        applicable.append(technique)
    return applicable


def excluded_techniques(
    cuisine: str,
    ingredient: str | None,
    constraints: Constraints,
) -> list[Exclusion]:
    """Techniques ECARTEES + raison (info debug FR7 / barriere LLM 6.1).

    Symetrique de `techniques_for` : retourne la liste des `Exclusion` (id de
    technique + ustensile interdit normalise + cle de contrainte) pour chaque
    technique exclue a cause d'un ustensile interdit. Alimente
    `DebugInfo.techniques` (retenues / exclues, archi 9.1) et fournit au
    generateur la matiere pour « remplacer ou refuser proprement » (archi 6.1).

    La SUGGESTION d'une alternative est HORS perimetre B4 (differee couche 4 /
    D1) : on expose la raison, pas le remplacement. Cuisine inconnue -> liste
    vide. `ingredient` accepte pour symetrie de signature (filtrage souple D14).

    Pur/deterministe : ordre = ordre de declaration des techniques.
    """
    cuisine_obj = load_cuisines().get(cuisine)
    if cuisine_obj is None:
        return []

    forbidden_tokens = _forbidden_token_sequences(cuisine_obj, constraints)

    exclusions: list[Exclusion] = []
    for technique in cuisine_obj.techniques:
        exclusion = _technique_exclusion(technique, forbidden_tokens)
        if exclusion is not None:
            exclusions.append(exclusion)
    return exclusions


if __name__ == "__main__":
    # Sanity-check rapide : python -m app.knowledge.loader
    table = load_safety()
    print(f"Securite : {len(table.standards)} lignes (autorite {table.meta.get('authority')!r})")
    for cid, cuisine in load_cuisines().items():
        print(f"Cuisine {cid!r} : {len(cuisine.techniques)} techniques")
    no_oven = Constraints(no_cookware=["pas_de_four"])
    print(f"  forbidden_cookware(pas_de_four) -> {sorted(forbidden_cookware('italian_savory_v1', no_oven))}")
    kept = [t.id for t in techniques_for("italian_savory_v1", None, no_oven)]
    print(f"  italian sans four -> {kept}")
    excluded = excluded_techniques("italian_savory_v1", None, no_oven)
    print(f"  exclues -> {[(e.technique_id, e.forbidden_tool, e.via_constraint) for e in excluded]}")
