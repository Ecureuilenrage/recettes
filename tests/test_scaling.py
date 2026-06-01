"""Tests du moteur de scaling (Epic C).

Le moteur etant deterministe, c'est la partie la mieux testee du projet.
Lancer : pytest tests/test_scaling.py

C1 couvre linear / sublinear / fixed ; C2 discrete (oeufs) ; C3 geometric
(temps) ; C4 flags non-linearite + reserve. C5 ajoute le determinisme N>=100 et
les scenarios x2 / /2 / x4 : la suite est verte SANS aucun skip.
"""

import pytest

from app.scaling.engine import (
    K_NONLINEAR_THRESHOLD,
    NONLINEAR_NOTE,
    scale,
    scale_eggs,
    scale_time,
)
from app.scaling.table import classify


def test_sel_sous_lineaire():
    # scale("sel", 1, "c.a.c", 2.0) doit etre < 2 (sous-lineaire coeff 0.75 ~ 1.68)
    q = scale("sel", 1, "c.a.c", 2.0)
    assert q.type == "sublinear"
    assert q.value < 2
    assert q.value == pytest.approx(1.68, abs=0.01)


def test_tomate_lineaire():
    # tomate : aucune categorie ne matche -> defaut linear -> 200 * 2.0 = 400
    q = scale("tomate", 200, "g", 2.0)
    assert q.type == "linear"
    assert q.value == 400


def test_temperature_figee():
    # une temperature (four/feu) ne doit jamais etre multipliee ; fixed=True
    q = scale("four", 180, "°C", 2.0)
    assert q.type == "fixed"
    assert q.fixed is True
    assert q.value == 180


def test_matching_token_entier():
    # « ail » est sublinear, mais ne doit PAS matcher en sous-chaine.
    assert classify("ail").type == "sublinear"
    # « vol-au-vent » contient « ... au ... » mais pas le token « ail » -> linear.
    assert classify("vol-au-vent").type == "linear"
    # casse + accents : « SEL » et un nom accentue restent classes correctement.
    assert classify("SEL").type == "sublinear"
    assert scale("tomate", 200, "g", 2.0).value == 400


def test_oeufs_discrets():
    # RZ1 : scale_eggs(3, 2.0) -> 5 oeufs entiers (pas 6, l'oeuf est liant), avec
    # un reste en volume/poids (~50 g / 3 c.a.s) et une note explicative.
    r = scale_eggs(3, 2.0)
    assert r.whole_eggs == 5
    assert r.whole_eggs != 6
    # reste = 1 oeuf retranche -> ~50 g / 3 c.a.s (valeurs lues dans la table).
    assert r.remainder["grams"] == pytest.approx(50)
    assert r.remainder["tbsp"] == pytest.approx(3)
    assert any(v > 0 for v in r.remainder.values())  # reste non nul
    assert isinstance(r.note, str) and r.note.strip() != ""  # note non vide


def test_oeufs_sans_correction():
    # Facteur non entier (1.5) -> pas de borne basse RZ1 : plancher 'down' de la
    # table. scale_eggs(2, 1.5) -> floor(3.0) = 3 oeufs, reste nul/negligeable.
    r = scale_eggs(2, 1.5)
    assert r.whole_eggs == 3
    assert r.remainder["grams"] == pytest.approx(0, abs=1e-6)
    assert r.remainder["tbsp"] == pytest.approx(0, abs=1e-6)


def test_oeufs_deterministe():
    # Pur/deterministe : deux appels identiques renvoient des ScaledEggs egaux.
    a = scale_eggs(3, 2.0)
    b = scale_eggs(3, 2.0)
    assert a.whole_eggs == b.whole_eggs
    assert a.remainder == b.remainder
    assert a.note == b.note


def test_temps_geometrique():
    # 20 min a x2 -> ~32 min (k^(2/3)), pas 40. Exposant (0.6667) lu dans la
    # table : 20 * 2^0.6667 ~= 31.75, cible backlog « ~32, pas 40 » (tol +-0.5).
    r = scale_time(20, 2.0)
    assert r.minutes == pytest.approx(32, abs=0.5)
    # AC4 : le temps est toujours non lineaire (type geometric + nonlinearFlag).
    assert r.nonlinear is True


def test_temps_note_contenant_au_seuil():
    # AC3 : k = 2.0 (>= seuil 1.5) -> une note `--` de changement de contenant.
    fort = scale_time(20, 2.0)
    assert fort.note is not None
    assert "--" in fort.note
    assert any("--" in n for n in fort.notes)

    # En deca du seuil (k = 1.2 < 1.5) -> aucune note de contenant.
    faible = scale_time(20, 1.2)
    assert faible.note is None
    assert faible.notes == []
    # Le scaling geometrique s'applique quel que soit le facteur.
    assert faible.nonlinear is True


def test_temps_seuil_unique():
    # AC2 / RZ2 : le seuil est une constante module unique, importable (par C4).
    assert K_NONLINEAR_THRESHOLD == 1.5


def test_temps_deterministe():
    # Pur/deterministe : deux appels identiques renvoient le meme resultat.
    a = scale_time(20, 2.0)
    b = scale_time(20, 2.0)
    assert a.minutes == b.minutes
    assert a.notes == b.notes
    assert a.nonlinear == b.nonlinear


# --- C4 : flags de non-linearite + reserve 10 % ------------------------------

# Note verbatim (AC1) : tiret cadratin « – », « × » multiplicatif.
_NOTE_NL = "-- ne se double pas proprement au-delà de ~1.5–2×"


def test_flag_non_lineaire_actif():
    # AC1 : « piment » porte nonlinearFlag:true. A k=2.0 (>= seuil 1.5), la note
    # de non-linearite EXACTE est attachee a ScaledQuantity.notes.
    q = scale("piment", 5, "g", 2.0)
    assert _NOTE_NL in q.notes
    # La constante exportee correspond au texte verbatim (pas de divergence).
    assert NONLINEAR_NOTE == _NOTE_NL


def test_flag_non_lineaire_inactif():
    # AC1 : a k=1.2 (< seuil 1.5), AUCUNE note de non-linearite n'est emise.
    q = scale("piment", 5, "g", 1.2)
    assert _NOTE_NL not in q.notes
    assert all(_NOTE_NL not in n for n in q.notes)


def test_reserve_sel():
    # AC2 : « sel » porte reserve_pct:10. La valeur scalee est scindee 90/10.
    q = scale("sel", 1, "c.a.c", 2.0)
    assert q.reserve is not None
    incorporate = q.reserve["incorporate"]
    reserve = q.reserve["reserve"]
    assert q.reserve["pct"] == 10
    # incorporate ~ 90 %, reserve ~ 10 % de la valeur scalee.
    assert incorporate == pytest.approx(q.value * 0.90)
    assert reserve == pytest.approx(q.value * 0.10)
    # Aucune perte : incorporate + reserve == value (tolerance flottante).
    assert incorporate + reserve == pytest.approx(q.value)
    # Une note de reserve `--` est presente.
    assert any(n.startswith("--") and "réserver" in n for n in q.notes)


def test_pas_de_reserve_hors_categorie():
    # AC2 : un ingredient sans reserve_pct (tomate, linear par defaut) -> pas de
    # reserve et aucune note de reserve.
    q = scale("tomate", 200, "g", 2.0)
    assert q.reserve is None
    assert all("réserver" not in n for n in q.notes)
    # AC5 : non-regression C1 (valeur lineaire inchangee).
    assert q.value == 400


def test_remontee_debug():
    # AC3 : debug["nonlinear"] et debug["threshold"] sont systematiquement
    # renseignes ; debug["reserve_pct"] l'est pour le sel.
    piment = scale("piment", 5, "g", 2.0)
    assert piment.debug["nonlinear"] is True
    assert piment.debug["threshold"] == K_NONLINEAR_THRESHOLD

    tomate = scale("tomate", 200, "g", 2.0)
    assert tomate.debug["nonlinear"] is False
    assert tomate.debug["threshold"] == K_NONLINEAR_THRESHOLD

    sel = scale("sel", 1, "c.a.c", 2.0)
    assert sel.debug["reserve_pct"] == 10


def test_c4_deterministe():
    # AC5 : meme entree -> exactement la meme sortie (notes, reserve, debug).
    a = scale("sel", 1, "c.a.c", 2.0)
    b = scale("sel", 1, "c.a.c", 2.0)
    assert a.value == b.value
    assert a.notes == b.notes
    assert a.reserve == b.reserve
    assert a.debug == b.debug


def test_c1_non_regression_sel():
    # AC5 : la valeur scalee du sel (sublinear ~1.68) reste inchangee malgre la
    # couche de decoration C4 (reserve calculee SUR cette valeur).
    q = scale("sel", 1, "c.a.c", 2.0)
    assert q.value == pytest.approx(1.68, abs=0.01)
    assert q.type == "sublinear"


# =============================================================================
# C5 — Tests deterministes (N executions) + scenarios x2 / /2 / x4
# -----------------------------------------------------------------------------
# C5 n'implemente AUCUNE logique metier : il PROUVE le contrat de purete /
# determinisme du coeur (OA1, archi 5.1, 11) livre par C1-C4 et couvre
# explicitement les facteurs x2, /2, x4 sur des ingredients representatifs.
# Aucun I/O hors lecture de la table (deja faite par le moteur), aucun random,
# aucun horodatage. Source : docs/stories/C5.md (AC1-AC4).
# =============================================================================

# Nombre d'executions du test de determinisme (AC2 : N >= 100).
N_RUNS = 200


def _snapshot_quantity(q):
    """Fige les champs porteurs de sens d'un ScaledQuantity en tuple comparable.

    On ne se fie pas a l'identite d'objet : on compare structurellement
    name / value / unit / type / fixed / notes / reserve (AC2). `notes` est une
    liste ordonnee (l'ordre d'emission est fige par le moteur), `reserve` un dict
    -> on les rend hashables/comparables via tuple(sorted(...)).
    """
    reserve = q.reserve
    reserve_key = (
        tuple(sorted(reserve.items())) if isinstance(reserve, dict) else reserve
    )
    return (
        q.name,
        q.value,
        q.unit,
        q.type,
        q.fixed,
        tuple(q.notes),
        reserve_key,
    )


def _snapshot_eggs(e):
    """Fige les champs porteurs de sens d'un ScaledEggs (AC2)."""
    return (e.whole_eggs, tuple(sorted(e.remainder.items())), e.note, e.type)


def _snapshot_time(t):
    """Fige les champs porteurs de sens d'un ScaledTime (AC2)."""
    return (t.minutes, t.nonlinear, tuple(t.notes), t.type)


def test_determinisme_scale_n_executions():
    # AC2 : une meme entree -> un ScaledQuantity IDENTIQUE sur N >= 100 executions.
    # ScaledQuantity est une @dataclass -> l'egalite structurelle `==` suffit ; on
    # double avec un snapshot fige pour verrouiller les champs porteurs de sens.
    reference = scale("sel", 1, "c.a.c", 2.0)
    ref_snap = _snapshot_quantity(reference)
    snapshots = {_snapshot_quantity(scale("sel", 1, "c.a.c", 2.0)) for _ in range(N_RUNS)}
    # Tous les snapshots sont identiques -> un seul element dans le set.
    assert len(snapshots) == 1
    assert snapshots == {ref_snap}
    # Egalite structurelle dataclass (champs complets, debug inclus).
    assert all(scale("sel", 1, "c.a.c", 2.0) == reference for _ in range(N_RUNS))


def test_determinisme_scale_eggs_n_executions():
    # AC2 : le determinisme s'applique aussi a scale_eggs (RZ1, oeufs liants).
    reference = scale_eggs(3, 2.0)
    snapshots = {_snapshot_eggs(scale_eggs(3, 2.0)) for _ in range(N_RUNS)}
    assert len(snapshots) == 1
    assert snapshots == {_snapshot_eggs(reference)}
    assert all(scale_eggs(3, 2.0) == reference for _ in range(N_RUNS))


def test_determinisme_scale_time_n_executions():
    # AC2 : le determinisme s'applique aussi a scale_time (loi geometrique).
    reference = scale_time(20, 2.0)
    snapshots = {_snapshot_time(scale_time(20, 2.0)) for _ in range(N_RUNS)}
    assert len(snapshots) == 1
    assert snapshots == {_snapshot_time(reference)}
    assert all(scale_time(20, 2.0) == reference for _ in range(N_RUNS))


# --- AC3 : scenarios parametres x2 / /2 / x4 ---------------------------------

# Facteurs imposes par l'AC3 (DoD : "x2 / /2 / x4 couverts").
_K_SCENARIOS = [0.5, 2.0, 4.0]


@pytest.mark.parametrize("k", _K_SCENARIOS)
def test_scenario_tomate_lineaire(k):
    # Linear (defaut) : value = 200 * k exactement, a tout facteur (x2/ /2 /x4).
    q = scale("tomate", 200, "g", k)
    assert q.type == "linear"
    assert q.value == pytest.approx(200 * k)
    assert q.fixed is False


@pytest.mark.parametrize("k", _K_SCENARIOS)
def test_scenario_sel_sous_lineaire(k):
    # Sublinear (coeff 0.75) : 0 < value, et value = 200 * k^0.75 (coeff lu dans
    # la table, jamais code en dur ici). Pour k > 1 le sous-lineaire reste SOUS
    # le x N naif ; pour 0 < k < 1, k^0.75 > k -> on n'asserte `< naif` que k > 1.
    q = scale("sel", 200, "g", k)
    assert q.type == "sublinear"
    assert q.value > 0
    if k > 1:
        assert q.value < 200 * k
    assert q.value == pytest.approx(200 * (k ** 0.75))


@pytest.mark.parametrize("k", _K_SCENARIOS)
def test_scenario_temperature_figee(k):
    # Fixed : la temperature ne bouge JAMAIS, quel que soit k (x2 / /2 / x4).
    q = scale("four", 180, "°C", k)
    assert q.type == "fixed"
    assert q.fixed is True
    assert q.value == 180


@pytest.mark.parametrize("k", _K_SCENARIOS)
def test_scenario_oeuf_discret(k):
    # Discrete : whole_eggs est un entier coherent avec count * k (borne basse
    # RZ1 pour k entier >= 2, plancher sinon). Reste non negatif.
    r = scale_eggs(3, k)
    assert isinstance(r.whole_eggs, int)
    assert r.whole_eggs >= 0
    assert all(v >= 0 for v in r.remainder.values())
    # x2 : 6 theoriques -> 5 (oeuf liant) ; x4 : 12 -> 11 ; /2 : floor(1.5)=1.
    expected = {0.5: 1, 2.0: 5, 4.0: 11}
    assert r.whole_eggs == expected[k]


@pytest.mark.parametrize("k", _K_SCENARIOS)
def test_scenario_temps_geometrique(k):
    # Geometric : minutes = 20 * k^0.6667 (exponent lu dans la table). x2 -> ~32,
    # x4 -> ~50.4, /2 -> ~12.6. Toujours nonlinear=True.
    r = scale_time(20, k)
    assert r.nonlinear is True
    assert r.minutes == pytest.approx(20 * (k ** 0.6667), abs=0.1)
    # Repere chiffre (geometricTimeExamples de la table) : x2=1.59, x4=2.52.
    cible = {0.5: 12.6, 2.0: 32.0, 4.0: 50.4}
    assert r.minutes == pytest.approx(cible[k], abs=0.5)


def test_scenario_monotonie_et_reduction():
    # AC3 : monotonie (k croissant => valeur croissante) pour linear & sublinear ;
    # k = 0.5 reduit STRICTEMENT la quantite sous la base (linear & sublinear) ;
    # fixed inchange a tout k.
    base_lin = scale("tomate", 200, "g", 1.0).value
    base_sub = scale("sel", 200, "g", 1.0).value
    lin = [scale("tomate", 200, "g", k).value for k in _K_SCENARIOS]
    sub = [scale("sel", 200, "g", k).value for k in _K_SCENARIOS]

    # Monotonie stricte (les facteurs _K_SCENARIOS sont tries croissants).
    assert lin == sorted(lin) and len(set(lin)) == len(lin)
    assert sub == sorted(sub) and len(set(sub)) == len(sub)

    # k = 0.5 (/2) reduit sous la base.
    assert scale("tomate", 200, "g", 0.5).value < base_lin
    assert scale("sel", 200, "g", 0.5).value < base_sub

    # fixed : inchange a x2, /2, x4.
    assert {scale("four", 180, "°C", k).value for k in _K_SCENARIOS} == {180}


def test_scenario_temps_x4_repere_backlog():
    # AC3 (cas chiffre backlog) : scale_time(20, 4.0) ~= 50.4 (20 * 4^0.6667).
    assert scale_time(20, 4.0).minutes == pytest.approx(50.4, abs=0.5)
    # AC3 (cas chiffre backlog) : sel a x2 ~= 1.68.
    assert scale("sel", 1, "c.a.c", 2.0).value == pytest.approx(1.68, abs=0.01)
