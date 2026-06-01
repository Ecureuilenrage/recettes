"""Chargement de la table de scaling et classification des ingredients (C1).

Source de verite : docs/scaling/table-scaling-sale.json (lue UNE SEULE fois, en
lecture seule). Aucun coefficient n'est code en dur ici : tout provient de la
table (contrainte D7 / DoD C1).

Expose :
  - ScalingRule  : regle de scaling resolue pour un ingredient.
  - classify(name) -> ScalingRule : matching par token entier, insensible a la
    casse et aux accents ; defaut `linear` (defaults.main_ingredients).

Module pur/deterministe (archi 5.1) : meme `name` -> meme ScalingRule.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# Chemin relatif au repo (cf. patron loader.py) : depuis app/scaling/, la racine
# du depot est a parents[2].
TABLE_PATH = Path(__file__).resolve().parents[2] / "docs" / "scaling" / "table-scaling-sale.json"


@dataclass(frozen=True)
class ScalingRule:
    """Regle de scaling resolue pour un ingredient.

    `type` couvre les cinq types de la table (linear/sublinear/fixed traites en
    C1 ; discrete/geometric delegues a C2/C3). Les champs optionnels (exponent,
    grams_per_unit, tbsp_per_unit, round, nonlinear_flag, reserve_pct) sont
    exposes des C1 pour que C2/C3/C4 les consomment sans refondre `classify`.
    """

    type: str
    coeff: float | None = None
    reason: str = ""
    nonlinear_flag: bool = False
    reserve_pct: int | None = None
    # Parametres reutilises par les stories suivantes (non appliques en C1).
    grams_per_unit: float | None = None
    tbsp_per_unit: float | None = None
    round: str | None = None
    exponent: float | None = None
    # Tokens normalises ayant declenche le match (utile pour le debug FR7).
    matched_on: tuple[str, ...] = field(default_factory=tuple)


def _strip_accents(text: str) -> str:
    """Supprime les accents (e -> e) sans dependance externe."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _normalize(text: str) -> str:
    """Minuscule + suppression des accents."""
    return _strip_accents(text).lower()


def _tokenize(text: str) -> list[str]:
    """Decoupe en tokens alphanumeriques (les separateurs ., -, espaces, etc.
    deviennent des frontieres de token). Garantit le matching par token entier :
    « ail » ne matche pas « vol-au-vent »."""
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


@lru_cache(maxsize=1)
def load_table() -> dict:
    """Charge la table JSON UNE SEULE fois (cache module-level via lru_cache).

    La structure retournee ne doit JAMAIS etre mutee (lecture seule).
    """
    return json.loads(TABLE_PATH.read_text(encoding="utf-8"))


def _matches(name_tokens: list[str], pattern: str) -> tuple[str, ...]:
    """Retourne les tokens du nom couverts par `pattern` (token entier), ou ().

    Un motif multi-mots (ex. « sauce soja ») ne matche que si sa sequence de
    tokens apparait dans l'ordre, contigue, dans les tokens du nom.
    """
    pattern_tokens = _tokenize(pattern)
    if not pattern_tokens:
        return ()
    n = len(pattern_tokens)
    for i in range(len(name_tokens) - n + 1):
        if name_tokens[i:i + n] == pattern_tokens:
            return tuple(pattern_tokens)
    return ()


def classify(name: str) -> ScalingRule:
    """Classe un ingredient en parcourant `categories[]` dans l'ordre.

    Matching par token entier, insensible casse/accents. Premiere categorie dont
    un motif `match` correspond -> sa regle. Aucun match -> defaut `linear`
    (defaults.main_ingredients).
    """
    table = load_table()
    name_tokens = _tokenize(name)

    for category in table.get("categories", []):
        for pattern in category.get("match", []):
            matched = _matches(name_tokens, pattern)
            if matched:
                return ScalingRule(
                    type=category["type"],
                    coeff=category.get("coeff"),
                    reason=category.get("reason", ""),
                    nonlinear_flag=bool(category.get("nonlinearFlag", False)),
                    reserve_pct=category.get("reserve_pct"),
                    grams_per_unit=category.get("grams_per_unit"),
                    tbsp_per_unit=category.get("tbsp_per_unit"),
                    round=category.get("round"),
                    exponent=category.get("exponent"),
                    matched_on=matched,
                )

    default = table.get("defaults", {}).get("main_ingredients", {"type": "linear"})
    return ScalingRule(type=default.get("type", "linear"), reason=default.get("note", ""))
