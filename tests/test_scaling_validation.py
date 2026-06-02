"""Jeu de validation du scaling sur le corpus S0.6 — story E3 (épic E, sprint 5).

Ce module compare le **moteur de scaling déterministe** (couche 3,
``app/scaling/``) au **×N naïf** (``qty × k``) sur le **corpus réel** des 13
recettes italiennes ``recipes/*.cook`` (S0.6), aux facteurs **×2 / ÷2 / ×4**, en
**asserts chiffrés et déterministes**.

Garde-fous (archi §6.3, §11, §13 R7) :

  - **AUCUN LLM, AUCUN réseau, AUCUNE horloge, AUCUN ``random``** : le moteur est
    pur ; le corpus est lu localement (stdlib ``re``/``pathlib``).
  - **AUCUNE dépendance Epicure/Knowledge/Generator/main** : ce module n'importe
    QUE ``app.scaling`` + la bibliothèque standard. Un test garde-fou
    (``test_aucun_import_intercouche``) vérifie cette contrainte par analyse AST.
  - Les regex de parsing ``.cook`` sont **RECOPIÉES** de ``recipes/_check_cook.py``
    / ``app/generator/cooklang.py`` (``recipes/`` n'est pas un package importable),
    pas importées.

Ce jeu **alimente** la calibration F2/RZ2 (il chiffre l'écart moteur vs ×N naïf
sur de vraies recettes) mais ne **résout PAS** RZ2 : les coefficients de
``docs/scaling/table-scaling-sale.json`` restent « de départ, à calibrer F2 ».

Lancer (CIBLÉ) : ``python -m pytest tests/test_scaling_validation.py -q``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.scaling import (
    ScaledEggs,
    ScaledQuantity,
    ScaledTime,
    classify,
    scale,
    scale_eggs,
    scale_time,
)

# --------------------------------------------------------------------------- #
# Corpus S0.6 : 13 recettes italiennes `.cook`. Chemin relatif au repo (depuis  #
# tests/, la racine est à parents[1]).                                          #
# --------------------------------------------------------------------------- #

RECIPES_DIR = Path(__file__).resolve().parents[1] / "recipes"

# Facteurs de scaling validés (×2 / ÷2 / ×4). Documentés comme « cas canoniques »
# de la calibration F2 (doublement, division par deux, quadruplement).
FACTEURS = (2.0, 0.5, 4.0)

# --------------------------------------------------------------------------- #
# Regex RECOPIÉES de `recipes/_check_cook.py` / `app/generator/cooklang.py`.     #
# `recipes/` n'est PAS un package importable -> on recopie le patron éprouvé.    #
# RE_INGREDIENT capture un marqueur `@nom{qty%unité}` complet ; on en réextrait  #
# nom / quantité / unité avec RE_INGREDIENT_PARTS ci-dessous.                    #
# --------------------------------------------------------------------------- #

RE_INGREDIENT = re.compile(r"@[^@#~\n]+?\{[^}]*?%[^}]*?\}")
# Décompose un marqueur ingrédient en (nom, contenu des accolades). Le contenu
# peut commencer par le verrou `=` (quantité figée -> fixed) et contient `qty%unité`.
RE_INGREDIENT_PARTS = re.compile(r"@([^@#~\n]+?)\{(=?)([^}]*?)%([^}]*?)\}")
# Tolère une quantité numérique « 4 », « 0.5 », « 1,5 » (virgule décimale FR) ou
# des fractions simples « 1/2 ». Les quantités non numériques (« q.s. », « 1 »
# suivi de texte) sont ignorées par la conversion robuste `_to_float`.
RE_NUMBER = re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)?|[0-9]+/[0-9]+)\s*$")


# --------------------------------------------------------------------------- #
# Helpers de parsing du corpus (déterministes, stdlib seule).                  #
# --------------------------------------------------------------------------- #


def _to_float(raw: str) -> float | None:
    """Convertit une quantité textuelle en float, ou ``None`` si non numérique.

    Robuste (E3) : accepte « 4 », « 0.5 », « 1,5 » (virgule FR -> point) et les
    fractions simples « 1/2 ». Renvoie ``None`` pour « q.s. », « », ou tout texte
    non chiffrable (ces quantités sont alors ignorées du jeu de validation).
    """
    match = RE_NUMBER.match(raw)
    if not match:
        return None
    token = match.group(1)
    if "/" in token:
        num, _, den = token.partition("/")
        try:
            return float(num) / float(den)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(token.replace(",", "."))
    except ValueError:
        return None


def _parse_ingredients(text: str) -> list[dict]:
    """Extrait les ingrédients numériques d'un texte ``.cook``.

    Renvoie une liste de dicts ``{name, qty, unit, locked}`` où ``name`` est le
    libellé brut (strippé), ``qty`` un float, ``unit`` l'unité (peut être vide),
    et ``locked`` True si le verrou ``=`` (quantité figée -> ``fixed``) est posé.
    Les marqueurs à quantité non numérique sont ignorés (conversion robuste).
    """
    out: list[dict] = []
    for match in RE_INGREDIENT_PARTS.finditer(text):
        name = match.group(1).strip()
        locked = match.group(2) == "="
        qty = _to_float(match.group(3))
        unit = match.group(4).strip()
        if qty is None:
            continue
        out.append({"name": name, "qty": qty, "unit": unit, "locked": locked})
    return out


def _load_corpus() -> dict[str, list[dict]]:
    """Charge le corpus ``recipes/*.cook`` -> ``{nom_fichier: [ingrédients]}``.

    Lecture seule, UTF-8, déterministe (fichiers triés par nom). Aucune écriture,
    aucun réseau.
    """
    corpus: dict[str, list[dict]] = {}
    for path in sorted(RECIPES_DIR.glob("*.cook")):
        text = path.read_text(encoding="utf-8")
        corpus[path.name] = _parse_ingredients(text)
    return corpus


# Chargé une seule fois au niveau module (pur : même corpus -> mêmes résultats).
CORPUS = _load_corpus()
# Aplatissement (recette, ingrédient) pour les parcours globaux.
ALL_INGREDIENTS = [
    {**ing, "recipe": name} for name, ings in CORPUS.items() for ing in ings
]


# --------------------------------------------------------------------------- #
# Tolérances (décisions par défaut DOCUMENTÉES).                              #
# --------------------------------------------------------------------------- #
#   - REL_LINEAR : tolérance relative pour l'égalité moteur == ×N naïf sur le
#     linéaire (flottants ; 1e-9 = égalité stricte cross-plateforme).
#   - ABS_TIME   : tolérance absolue (minutes) pour la loi géométrique du temps.
#     Le moteur utilise l'exposant 0.6667 LU dans la table (≈ 2/3 mais pas
#     exactement) -> on borne à 0.1 min l'écart à `t * k^(2/3)` théorique.
REL_LINEAR = 1e-9
ABS_TIME = 0.1


# --------------------------------------------------------------------------- #
# 1. Comparaison moteur vs ×N naïf sur le corpus — par type de scaling.        #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("k", FACTEURS)
def test_lineaire_egale_x_n_naif_sur_le_corpus(k: float) -> None:
    """Ingrédients LINÉAIRES (défaut) : ``scale(...).value ≈ qty*k`` (==×N naïf).

    Pour tout ingrédient du corpus classé ``linear`` (pâtes, tomates, liquides,
    fromages...), le moteur DOIT égaler la règle de trois. Assert chiffré sur
    chaque ingrédient linéaire rencontré, aux trois facteurs.
    """
    linear_seen = 0
    for ing in ALL_INGREDIENTS:
        rule = classify(ing["name"])
        if rule.type != "linear" or ing["locked"]:
            continue
        linear_seen += 1
        q = scale(ing["name"], ing["qty"], ing["unit"], k)
        assert q.type == "linear"
        assert q.value == pytest.approx(ing["qty"] * k, rel=REL_LINEAR), (
            f"{ing['recipe']}::{ing['name']} (linéaire) devrait égaler le ×N naïf"
        )
    # Le corpus DOIT contenir des ingrédients linéaires (sinon le test est vide).
    assert linear_seen > 0, "aucun ingrédient linéaire rencontré dans le corpus"


@pytest.mark.parametrize("k", FACTEURS)
def test_sous_lineaire_diverge_dans_le_bon_sens(k: float) -> None:
    """Ingrédients SOUS-LINÉAIRES (sel, poivre, ail, basilic...) : sens de l'écart.

    Le ×N naïf sur-assaisonne quand on agrandit (k>1) et sous-assaisonne quand on
    réduit (k<1). Le moteur (``qty*k^coeff``, 0<coeff<1) corrige ce travers :

      - k > 1  ->  ``scale(...).value < qty*k`` STRICTEMENT (le naïf sur-sale) ;
      - k < 1  ->  ``scale(...).value > qty*k`` STRICTEMENT (le naïf sous-sale).

    On borne aussi l'écart (l'assaisonnement scalé reste du même ordre que la
    base) et on asserte le SENS, chiffré, sur chaque sous-linéaire du corpus.
    """
    sublinear_seen = 0
    for ing in ALL_INGREDIENTS:
        rule = classify(ing["name"])
        if rule.type != "sublinear" or ing["locked"]:
            continue
        sublinear_seen += 1
        naif = ing["qty"] * k
        q = scale(ing["name"], ing["qty"], ing["unit"], k)
        assert q.type == "sublinear"
        if k > 1.0:
            assert q.value < naif, (
                f"{ing['recipe']}::{ing['name']} : à ×{k}, le moteur doit sous-doser "
                "vs le ×N naïf (qui sur-assaisonne)"
            )
            # Borne : le moteur reste >= la quantité de base (k^coeff >= 1 pour k>1).
            assert q.value >= ing["qty"] - REL_LINEAR
        elif k < 1.0:
            assert q.value > naif, (
                f"{ing['recipe']}::{ing['name']} : à ÷{1 / k:g}, le moteur doit "
                "sur-doser vs le ×N naïf (qui sous-assaisonne)"
            )
            # Borne : le moteur reste <= la quantité de base (k^coeff <= 1 pour k<1).
            assert q.value <= ing["qty"] + REL_LINEAR
    assert sublinear_seen > 0, "aucun ingrédient sous-linéaire rencontré dans le corpus"


# --------------------------------------------------------------------------- #
# 2. Œufs (discrete) — règle RZ1 « œufs liants », chiffré.                     #
# --------------------------------------------------------------------------- #


def test_oeufs_regle_rz1_chiffree() -> None:
    """Œufs (``scale_eggs``) : doublement franc borné (RZ1) + cas non corrigé.

    - ``scale_eggs(3, 2.0).whole_eggs == 5`` (PAS 6 : l'œuf est liant, on borne
      par le bas) avec un reste volumique (~50 g / 3 c.à.s).
    - ``scale_eggs(2, 1.5).whole_eggs == 3`` (facteur fractionnaire : plancher,
      pas de borne basse RZ1).
    """
    r = scale_eggs(3, 2.0)
    assert isinstance(r, ScaledEggs)
    assert r.whole_eggs == 5  # 6 théoriques -> 5 (RZ1), pas le ×N naïf (=6)
    assert r.remainder["grams"] == pytest.approx(50.0)
    assert r.remainder["tbsp"] == pytest.approx(3.0)

    # Cas fractionnaire NON corrigé par RZ1 : 2 × 1.5 = 3.0 -> 3 entiers (plancher).
    r2 = scale_eggs(2, 1.5)
    assert r2.whole_eggs == 3


@pytest.mark.parametrize("k", FACTEURS)
def test_oeufs_du_corpus_ne_depassent_pas_le_x_n_naif(k: float) -> None:
    """Sur les œufs réels du corpus, ``whole_eggs <= ceil(count*k)`` (jamais au-dessus).

    Le moteur ne produit JAMAIS plus d'œufs entiers que le ×N naïf arrondi au
    plafond ; pour un doublement franc (count entier, k entier >= 2) il en produit
    STRICTEMENT moins (RZ1). Assert chiffré sur les œufs trouvés dans le corpus.
    """
    import math

    eggs_seen = 0
    for ing in ALL_INGREDIENTS:
        if classify(ing["name"]).type != "discrete":
            continue
        eggs_seen += 1
        count = ing["qty"]
        r = scale_eggs(count, k)
        assert r.whole_eggs <= math.ceil(count * k) + 1e-9
        # Doublement franc d'un compte entier -> RZ1 borne STRICTEMENT par le bas.
        if float(count).is_integer() and float(k).is_integer() and k >= 2:
            assert r.whole_eggs == int(round(count * k)) - 1
    # Le corpus contient des œufs (carbonara, etc.).
    assert eggs_seen > 0, "aucun œuf (discrete) rencontré dans le corpus"


# --------------------------------------------------------------------------- #
# 3. Temps (geometric) — loi k^(2/3), strictement < ×N naïf pour k>1.         #
# --------------------------------------------------------------------------- #


def test_temps_loi_geometrique_x2() -> None:
    """``scale_time(20, 2.0).minutes ≈ 20*2**(2/3) (~31.75) < 40`` (×N naïf).

    Le temps de cuisson n'est PAS linéaire : un plat doublé ne demande pas le
    double de cuisson. Le moteur applique ``t * k^(2/3)`` ; le ×N naïf (40 min)
    sur-cuirait.
    """
    t = scale_time(20, 2.0)
    assert isinstance(t, ScaledTime)
    assert t.minutes == pytest.approx(20 * 2 ** (2 / 3), abs=ABS_TIME)  # ~31.75
    assert t.minutes < 40  # le ×N naïf doublerait à 40
    assert t.nonlinear is True


def test_temps_loi_geometrique_demi_et_quadruple() -> None:
    """Vérifie la loi géométrique du temps aussi à ÷2 et ×4.

    - ÷2 : ``scale_time(20, 0.5).minutes ≈ 20*0.5**(2/3) (~12.6) > 10`` (le ×N
      naïf descendrait à 10) ;
    - ×4 : ``scale_time(20, 4.0).minutes ≈ 20*4**(2/3) (~50.4) < 80`` (le ×N naïf
      quadruplerait à 80).
    """
    t_half = scale_time(20, 0.5)
    assert t_half.minutes == pytest.approx(20 * 0.5 ** (2 / 3), abs=ABS_TIME)
    assert t_half.minutes > 10  # le ×N naïf descendrait à 10

    t_quad = scale_time(20, 4.0)
    assert t_quad.minutes == pytest.approx(20 * 4 ** (2 / 3), abs=ABS_TIME)
    assert t_quad.minutes < 80  # le ×N naïf quadruplerait à 80


# --------------------------------------------------------------------------- #
# 4. Fixed (verrou `=` / température) — inchangé quel que soit k.              #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("k", FACTEURS)
def test_fixed_temperature_inchangee(k: float) -> None:
    """Une température (``four``/``feu``) reste INCHANGÉE quel que soit k.

    Type ``fixed`` (verrou ``=`` Cooklang) : ``scale("four", 180, "°C", k).value
    == 180`` pour tout k. Une température ne se multiplie jamais.
    """
    q = scale("four", 180, "°C", k)
    assert q.type == "fixed"
    assert q.fixed is True
    assert q.value == 180


@pytest.mark.parametrize("k", FACTEURS)
def test_fixed_verrou_du_corpus_inchange(k: float) -> None:
    """Un ingrédient VERROUILLÉ (``=``) dans le corpus reste inchangé.

    Le corpus pose des verrous ``=`` sur les températures de l'eau/du four
    (``(=100%°C)``, ``(=85%°C)``...). Ces marqueurs ne sont pas des ingrédients
    ``@`` (donc absents de ``ALL_INGREDIENTS``), mais on valide ici le contrat
    ``fixed`` du moteur : un ingrédient classé ``fixed`` ne bouge pas. On force
    un cas représentatif (``temperature``) pour garantir la couverture du type.
    """
    q = scale("temperature", 100, "°C", k)
    assert q.type == "fixed"
    assert q.value == 100


# --------------------------------------------------------------------------- #
# 5. Déterminisme — même (corpus, k) -> mêmes résultats sur N >= 20.           #
# --------------------------------------------------------------------------- #


def test_determinisme_sur_le_corpus() -> None:
    """Le moteur est PUR : même (corpus, k) -> exactement les mêmes valeurs.

    On (re)scale tout le corpus N=25 fois aux trois facteurs et on vérifie que la
    signature des résultats est rigoureusement identique d'une exécution à l'autre
    (aucun ``random``, aucune horloge).
    """

    def signature() -> list:
        out: list = []
        for ing in ALL_INGREDIENTS:
            for k in FACTEURS:
                rule = classify(ing["name"])
                if rule.type == "discrete":
                    out.append(scale_eggs(ing["qty"], k).whole_eggs)
                else:
                    out.append(scale(ing["name"], ing["qty"], ing["unit"], k).value)
        # Inclut un temps déterministe (hors corpus @ mais pertinent pour la loi).
        for k in FACTEURS:
            out.append(scale_time(20, k).minutes)
        return out

    reference = signature()
    for _ in range(25):
        assert signature() == reference


# --------------------------------------------------------------------------- #
# 6. Couverture corpus — le jeu porte bien « sur le corpus », pas sur 1 cas.   #
# --------------------------------------------------------------------------- #


def test_couverture_corpus() -> None:
    """Asserte que le jeu couvre réellement le corpus et ses types représentatifs.

    - Au moins 10 recettes ``.cook`` parsées (le corpus S0.6 en compte 13).
    - Au moins un ingrédient de chaque type représentatif rencontré : ``linear``
      ET ``sublinear`` (le cœur de la divergence moteur vs ×N naïf).
    - Un volume significatif d'ingrédients numériques extraits (> 40).
    """
    assert len(CORPUS) >= 10, f"corpus trop petit : {len(CORPUS)} recettes"
    types = {classify(ing["name"]).type for ing in ALL_INGREDIENTS}
    assert "linear" in types, "aucun ingrédient linéaire dans le corpus parsé"
    assert "sublinear" in types, "aucun ingrédient sous-linéaire dans le corpus parsé"
    assert len(ALL_INGREDIENTS) > 40, (
        f"trop peu d'ingrédients numériques extraits : {len(ALL_INGREDIENTS)}"
    )


def test_corpus_contient_sel_ou_poivre_sous_lineaire() -> None:
    """Garantit la présence d'au moins un assaisonnement sous-linéaire nommé.

    Le sel et le poivre noir (cités dans la story comme cas représentatifs) sont
    présents dans le corpus (cacio e pepe, carbonara, pomodoro...) -> on vérifie
    qu'au moins l'un d'eux est rencontré et bien classé ``sublinear``.
    """
    names = {ing["name"].lower() for ing in ALL_INGREDIENTS}
    assert any(
        classify(n).type == "sublinear" and ("sel" in n or "poivre" in n or "ail" in n)
        for n in names
    ), "ni sel, ni poivre, ni ail sous-linéaire trouvé dans le corpus"


# --------------------------------------------------------------------------- #
# 7. Garde-fou : aucun import inter-couche / réseau / LLM (analyse AST).       #
# --------------------------------------------------------------------------- #


def test_aucun_import_intercouche() -> None:
    """Ce module de test n'importe QUE ``app.scaling`` + la stdlib.

    Analyse AST des ``import``/``from ... import`` réels du fichier de test :
    aucun ``anthropic``, aucun ``app.epicure``/``app.generator``/``app.knowledge``/
    ``app.main`` ne doit apparaître (garde-fou R7 / archi §3.1 / §6.3).
    """
    import ast

    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
            imported.add(node.module)

    interdits = {
        "anthropic",
        "app.epicure",
        "app.generator",
        "app.knowledge",
        "app.main",
    }
    for module in interdits:
        racine = module.split(".")[0]
        if module.startswith("app."):
            assert module not in imported, f"import interdit détecté : {module}"
        else:
            assert racine not in imported, f"import interdit détecté : {module}"

    # Le seul import métier autorisé est `app.scaling`.
    app_modules = {m for m in imported if m.startswith("app")}
    assert app_modules <= {"app", "app.scaling"}, (
        f"imports `app.*` inattendus : {app_modules - {'app', 'app.scaling'}}"
    )


def test_api_publique_importee() -> None:
    """Sanity-check : l'API publique de la couche 3 est bien importable/typée."""
    assert callable(scale) and callable(scale_eggs) and callable(scale_time)
    assert callable(classify)
    q = scale("tomate", 100, "g", 2.0)
    assert isinstance(q, ScaledQuantity)
    assert isinstance(scale_eggs(2, 2.0), ScaledEggs)
    assert isinstance(scale_time(10, 2.0), ScaledTime)
