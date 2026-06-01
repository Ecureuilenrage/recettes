"""Tests de la couche 2 (base technique) — story B3.

Tests ROBUSTES / NON FRAGILES (consigne projet) : ils portent sur des proprietes
structurelles et comportementales (ids de techniques, cardinalite, exclusion
cookware, `critical is True`, presence de `min_internal_c`) et JAMAIS sur le
wording exact des valeurs de securite (le fichier safety-temperatures.json est
edite en parallele ; seul le schema de cles est stable).

Lancer depuis la racine du repo :
    python -m pytest tests/test_knowledge.py -q
"""

from __future__ import annotations

from app.knowledge.loader import (
    Constraints,
    Exclusion,
    Technique,
    _is_subsequence,
    _tokenize,
    _tool_is_forbidden,
    excluded_techniques,
    forbidden_cookware,
    load_cuisines,
    load_safety,
    safety_for,
    techniques_for,
)

CUISINE_ID = "italian_savory_v1"
# Les 5 techniques attendues du module pilote italien (ids = cles anglaises stables).
EXPECTED_TECHNIQUES = {
    "pasta_al_dente",
    "risotto",
    "soffritto",
    "sugo_pomodoro",
    "searing_braising",
}


def test_load_cuisines_decouvre_italien():
    """AC2 : decouverte dynamique -> cle italian_savory_v1 + 5 techniques."""
    cuisines = load_cuisines()
    assert CUISINE_ID in cuisines, "la cuisine italienne doit etre decouverte par glob"
    cuisine = cuisines[CUISINE_ID]
    assert len(cuisine.techniques) == 5
    ids = {t.id for t in cuisine.techniques}
    assert ids == EXPECTED_TECHNIQUES


def test_techniques_for_sans_contrainte():
    """AC3 : sans contrainte -> les 5 techniques sont applicables."""
    techniques = techniques_for(CUISINE_ID, None, Constraints())
    assert len(techniques) == 5
    assert {t.id for t in techniques} == EXPECTED_TECHNIQUES
    assert all(isinstance(t, Technique) for t in techniques)


def test_techniques_for_exclut_four():
    """AC3 : « pas_de_four » exclut searing_braising (requiert « four »),
    conserve pasta_al_dente / risotto / soffritto / sugo_pomodoro."""
    constraints = Constraints(no_cookware=["pas_de_four"])
    ids = {t.id for t in techniques_for(CUISINE_ID, None, constraints)}
    assert "searing_braising" not in ids
    assert ids == {"pasta_al_dente", "risotto", "soffritto", "sugo_pomodoro"}


def test_safety_for_proteine():
    """AC1 : safety_for(volaille) -> ligne critique avec min_internal_c present.

    On n'asserte PAS le wording exact (note/libelle) : seules les proprietes
    structurelles sont verifiees (le fichier securite peut evoluer)."""
    standard = safety_for("volaille")
    assert standard is not None
    assert standard.critical is True
    assert standard.min_internal_c is not None


def test_safety_for_inconnu_renvoie_none():
    """safety_for sur un type absent -> None (pas d'exception)."""
    assert safety_for("ingredient_totalement_inexistant_xyz") is None


def test_load_safety_structure():
    """AC1/AC4 : SafetyTable typee, lecture unique, lignes critiques presentes."""
    table = load_safety()
    assert len(table.standards) >= 1
    # Au moins une proteine critique avec temperature a coeur renseignee.
    assert any(s.critical and s.min_internal_c is not None for s in table.standards)
    # Chargement unique (lru_cache) : meme objet retourne.
    assert load_safety() is table


def test_cuisine_inconnue_liste_vide():
    """Decision par defaut B3 : cuisine inconnue -> liste vide (pas d'exception)."""
    assert techniques_for("cuisine_inexistante_v0", None, Constraints()) == []


def test_filtrage_ingredient_souple():
    """D14 : le filtrage par ingredient est souple -> un ingredient quelconque
    n'ecarte aucune technique par defaut (seul le cookware interdit le fait)."""
    avec_ingredient = techniques_for(CUISINE_ID, "tomate", Constraints())
    sans_ingredient = techniques_for(CUISINE_ID, None, Constraints())
    assert {t.id for t in avec_ingredient} == {t.id for t in sans_ingredient}


def test_determinisme():
    """Module pur : meme appel -> meme resultat (ids identiques) sur N executions."""
    constraints = Constraints(no_cookware=["pas_de_four"])
    reference = [t.id for t in techniques_for(CUISINE_ID, None, constraints)]
    for _ in range(100):
        assert [t.id for t in techniques_for(CUISINE_ID, None, constraints)] == reference
    # safety_for egalement deterministe.
    ref_safety = safety_for("volaille")
    for _ in range(100):
        assert safety_for("volaille") == ref_safety


# --------------------------------------------------------------------------- #
# Story B4 — API publique forbidden_cookware, matching durci, info debug FR7.  #
# --------------------------------------------------------------------------- #


def test_forbidden_cookware_pas_de_four():
    """AC1 : forbidden_cookware retourne l'ensemble NORMALISE des ustensiles
    interdits par « pas_de_four » (four + variantes multi-mots normalisees)."""
    forbidden = forbidden_cookware(CUISINE_ID, Constraints(no_cookware=["pas_de_four"]))
    assert forbidden == {"four", "moule a four", "cocotte au four"}


def test_forbidden_cookware_contrainte_inconnue_vide():
    """AC1/AC5(b) : une cle absente de cookwareConstraints -> ensemble vide."""
    forbidden = forbidden_cookware(CUISINE_ID, Constraints(no_cookware=["pas_de_micro_ondes"]))
    assert forbidden == set()


def test_forbidden_cookware_no_cookware_vide():
    """AC1/AC5(c) : no_cookware vide -> ensemble vide."""
    assert forbidden_cookware(CUISINE_ID, Constraints(no_cookware=[])) == set()


def test_forbidden_cookware_union_plusieurs_contraintes():
    """AC1 : plusieurs contraintes cumulent leurs ensembles (union)."""
    forbidden = forbidden_cookware(
        CUISINE_ID, Constraints(no_cookware=["pas_de_four", "pas_de_robot"])
    )
    assert forbidden == {"four", "moule a four", "cocotte au four", "robot culinaire"}


def test_forbidden_cookware_cuisine_inconnue_vide():
    """Cuisine inconnue -> ensemble vide (pas d'exception), comme techniques_for."""
    assert forbidden_cookware("cuisine_inexistante_v0", Constraints(no_cookware=["pas_de_four"])) == set()


def test_techniques_for_exclut_searing_braising_conserve_les_4():
    """AC3/AC5(a) : « pas_de_four » exclut searing_braising (requiert « four »)
    et conserve pasta_al_dente / risotto / soffritto / sugo_pomodoro."""
    constraints = Constraints(no_cookware=["pas_de_four"])
    ids = {t.id for t in techniques_for(CUISINE_ID, None, constraints)}
    assert "searing_braising" not in ids
    assert ids == {"pasta_al_dente", "risotto", "soffritto", "sugo_pomodoro"}


def test_contrainte_inconnue_no_op():
    """AC5(b) : contrainte inconnue -> techniques_for est un no-op (5 techniques)."""
    constraints = Constraints(no_cookware=["pas_de_micro_ondes"])
    ids = {t.id for t in techniques_for(CUISINE_ID, None, constraints)}
    assert ids == EXPECTED_TECHNIQUES


def test_no_cookware_vide_conserve_les_5():
    """AC5(c) : no_cookware vide -> les 5 techniques restent."""
    ids = {t.id for t in techniques_for(CUISINE_ID, None, Constraints(no_cookware=[]))}
    assert ids == EXPECTED_TECHNIQUES


def test_excluded_techniques_expose_la_raison():
    """AC4 (FR7) : excluded_techniques expose technique + ustensile + contrainte.

    searing_braising est exclue via l'ustensile « four » interdit par
    « pas_de_four » ; aucune autre technique n'est exclue."""
    exclusions = excluded_techniques(CUISINE_ID, None, Constraints(no_cookware=["pas_de_four"]))
    assert exclusions == [Exclusion(technique_id="searing_braising", forbidden_tool="four", via_constraint="pas_de_four")]


def test_excluded_techniques_vide_sans_contrainte():
    """AC4 : sans contrainte materielle, aucune technique n'est exclue."""
    assert excluded_techniques(CUISINE_ID, None, Constraints()) == []


def test_matching_token_entier_multi_mots_regression_b3():
    """Anti-regression finding #1 de la revue B3 : un ustensile interdit
    MULTI-MOTS doit etre matche en sous-sequence de tokens.

    L'ancien helper B3 ajoutait « robot culinaire » comme CHAINE entiere
    normalisee et la comparait a des TOKENS mono-mot : l'intersection
    {'robot culinaire'} & {'robot','culinaire'} == set() -> faux negatif
    silencieux. Le matching durci B4 corrige ce cas."""
    # Demonstration explicite du bug B3 (asymetrie chaine entiere vs tokens).
    assert {"robot culinaire"} & set(_tokenize("grand robot culinaire pro")) == set()
    # Le matching durci B4 (sous-sequence de tokens) detecte bien l'interdit.
    forbidden = {("robot", "culinaire"): "pas_de_robot"}
    assert _tool_is_forbidden("grand robot culinaire pro", forbidden) == "pas_de_robot"
    # « four » (mono-mot) reste matche dans un libelle multi-mots.
    assert _tool_is_forbidden("cocotte au four", {("four",): "pas_de_four"}) == "pas_de_four"


def test_matching_pas_de_faux_positif_sous_chaine():
    """AC2 : pas de faux positif de SOUS-CHAINE — « four » (token) ne matche pas
    « fourchette » ni « fourneau » (tokens distincts), seulement le token
    « four » entier. Meme garde anti-faux-positif que l'AC2 de C1."""
    forbidden = {("four",): "pas_de_four"}
    assert _tool_is_forbidden("fourchette a fondue", forbidden) is None
    assert _tool_is_forbidden("fourneau a bois", forbidden) is None
    assert _tool_is_forbidden("four", forbidden) == "pas_de_four"
    assert _tool_is_forbidden("cocotte au four", forbidden) == "pas_de_four"
    # _is_subsequence opere par token entier (pas de sous-chaine).
    assert _is_subsequence(("four",), ["fourchette"]) is False
    assert _is_subsequence(("four",), ["cocotte", "au", "four"]) is True


def test_b4_determinisme():
    """AC5(d) : forbidden_cookware / techniques_for / excluded_techniques sont
    deterministes (memes entrees -> memes resultats sur N executions)."""
    constraints = Constraints(no_cookware=["pas_de_four", "pas_de_robot"])
    ref_forbidden = forbidden_cookware(CUISINE_ID, constraints)
    ref_kept = [t.id for t in techniques_for(CUISINE_ID, None, constraints)]
    ref_excluded = excluded_techniques(CUISINE_ID, None, constraints)
    for _ in range(100):
        assert forbidden_cookware(CUISINE_ID, constraints) == ref_forbidden
        assert [t.id for t in techniques_for(CUISINE_ID, None, constraints)] == ref_kept
        assert excluded_techniques(CUISINE_ID, None, constraints) == ref_excluded
