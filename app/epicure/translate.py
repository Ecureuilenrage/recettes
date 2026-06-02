"""Traduction FR → clé Epicure (snake_case EN) — couche 1 (A4, lève RZ3).

Pont entre le héros saisi en français par l'utilisateur (ex. « huile d'olive »,
« basilic », « poivre noir ») et le vocabulaire Epicure en anglais snake_case
(ex. ``olive_oil``, ``basil``, ``black_pepper``). La fonction ``translate`` produit
une clé valide pour ``EpicureIndex.neighbors(hero, k)`` (app/epicure/loader.py) afin
que ce dernier ne lève pas ``KeyError`` à tort (R4 / archi §9.1).

Source de vérité : ``app/epicure/fr_aliases.json`` (co-localisé), table versionnée
``{ alias_FR_lisible : clé_Epicure }``. Le JSON est lu UNE SEULE fois (lecture
seule, ``functools.lru_cache``). La normalisation (casse / accents / apostrophe /
espaces) est appliquée des DEUX côtés au lookup ; le JSON source n'est jamais muté.

Contrat d'erreur : terme absent de la table → ``KeyError`` avec message clair en
français, cohérent avec ``EpicureIndex.neighbors`` (remontée homogène vers le 422
de l'API, archi §9.1).

Règle inter-couches (archi §3.1) : ce module n'importe NI ``app/knowledge/`` NI
``app/scaling/``. Les helpers de normalisation ``_strip_accents``/``_normalize``
sont RECOPIÉS depuis le patron ``app/scaling/table.py`` (lignes 52-60) — duplication
volontaire (≈ 10 lignes stdlib) préférable à un couplage inter-couches, comme en
B3/B4. Module pur/déterministe : aucune nouvelle dépendance (json, unicodedata,
pathlib, functools, typing suffisent), pas de random, pas d'I/O réseau.

Note ``guanciale`` : ABSENT du vocab Epicure (1790 entrées) → aliasé sur
``pancetta``, substitut cured-pork le plus proche présent au vocab. Approximation
FR→Epicure assumée (la couche 1 ne fournit que des associations), à réévaluer si
le vocab évolue.
"""

from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Iterable

# JSON co-localisé dans app/epicure/ (contrairement à loader.py/table.py qui lisent docs/).
FR_ALIASES_PATH = Path(__file__).resolve().parent / "fr_aliases.json"


def _strip_accents(text: str) -> str:
    """Supprime les accents (é -> e) sans dépendance externe.

    Recopié du patron app/scaling/table.py:52-55 (règle inter-couches archi §3.1 :
    on recopie, on n'importe pas une autre couche).
    """
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _normalize(text: str) -> str:
    """Minuscule + suppression des accents (recopié de app/scaling/table.py:58-60)."""
    return _strip_accents(text).lower()


def _normalize_term(term: str) -> str:
    """Forme normalisée servant de clé de lookup (alias ET terme saisi).

    Étapes (cf. stratégie de normalisation A4) :
      1. Apostrophe typographique « ’ » (U+2019) -> apostrophe droite « ' » (U+0027),
         pour que « huile d’olive » et « huile d'olive » convergent.
      2. Réduction des espaces multiples + ``strip()``.
      3. ``_normalize`` (suppression des accents NFKD + minuscule).
    """
    unified = term.replace("’", "'")
    unified = " ".join(unified.split())
    return _normalize(unified)


@lru_cache(maxsize=1)
def _load_index() -> dict[str, str]:
    """Charge ``fr_aliases.json`` UNE SEULE fois et construit l'index normalisé.

    Retourne ``{ _normalize_term(alias) : clé_Epicure }``. Le JSON source (alias
    lisibles, accentués) n'est jamais muté ; la normalisation est calculée ici, à
    la construction de l'index (lecture seule, cache module-level via lru_cache).
    """
    raw: dict[str, str] = json.loads(FR_ALIASES_PATH.read_text(encoding="utf-8"))
    return {_normalize_term(alias): key for alias, key in raw.items()}


def translate(term: str) -> str:
    """Traduit un nom d'ingrédient FR en clé Epicure snake_case EN.

    Exemple : ``translate("huile d'olive") == "olive_oil"``. Le lookup est tolérant
    à la casse, aux accents, à l'apostrophe typographique et aux espaces superflus.

    Lève ``KeyError`` (message clair en français) si le terme est absent de
    ``fr_aliases.json`` — comportement cohérent avec ``EpicureIndex.neighbors``,
    alimentant le 422 explicite de l'API (archi §9.1).
    """
    key = _load_index().get(_normalize_term(term))
    if key is None:
        raise KeyError(
            f"Ingrédient inconnu du vocabulaire FR→Epicure : {term!r} "
            "(à ajouter dans fr_aliases.json)"
        )
    return key


def translate_many(terms: Iterable[str]) -> list[str]:
    """Traduit une séquence de termes FR, dans l'ordre.

    Même politique d'erreur par terme que ``translate`` : un terme inconnu lève
    ``KeyError`` (la séquence n'est pas traduite partiellement de façon silencieuse).
    """
    return [translate(term) for term in terms]


def try_translate(term: str) -> str | None:
    """Variante non-levante (optionnelle, AC4) : retourne la clé ou ``None``.

    Le contrat principal reste ``translate`` -> ``KeyError``. Cette variante est
    fournie pour les appelants qui préfèrent un test d'absence sans exception
    (ex. suggestion UX en E2, hors périmètre A4).
    """
    return _load_index().get(_normalize_term(term))


if __name__ == "__main__":
    # Sanity-check rapide : python -m app.epicure.translate
    for fr in ["huile d'olive", "Huile d’Olive", "  câpres  ", "BASILIC", "guanciale", "spaghetti"]:
        print(f"  {fr!r} -> {translate(fr)}")
    try:
        translate("licorne")
    except KeyError as exc:
        print(f"  terme inconnu -> KeyError: {exc}")
