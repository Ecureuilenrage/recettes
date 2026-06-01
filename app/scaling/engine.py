"""Moteur de scaling : fonction `scale` (linear / sublinear / fixed) — C1.

S'appuie sur `classify` (table.py) pour resoudre le type de scaling d'un
ingredient, puis applique la formule correspondante. Pur/deterministe (archi
5.1) : meme (name, qty, unit, k) -> exactement le meme ScaledQuantity.

Perimetre C1 : linear (qty*k), sublinear (qty*k^coeff), fixed (inchange -> verrou
`=` Cooklang). Les types `discrete` (oeufs, C2) et `geometric` (temps, C3) ne sont
PAS scales ici : `scale` ne plante pas, elle renvoie la valeur non scalee + une
note explicite et delegue le calcul aux fonctions dediees a venir.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.scaling.table import ScalingRule, classify

# Tolerance d'arrondi explicite (determinisme cross-plateforme) : on compare la
# cible a son entier le plus proche via une borne plutot que via l'egalite
# flottante. Voir RZ1 dans scale_eggs.
EPS = 1e-9

# RZ2 : seuil de non-linearite (facteur k a partir duquel le plat « ne se double
# pas proprement » -> note de changement de contenant). Valeur non chiffree dans
# la table ; [HYPOTHESE] alignee sur le flag de non-linearite (~1.5-2x).
# Definie ICI une seule fois (source de verite unique) ; importee par C4
# (reserves.RZ2.story: [C3, C4]) — ne pas la redefinir ailleurs.
# a calibrer F2.
K_NONLINEAR_THRESHOLD = 1.5  # RZ2 — a calibrer F2 — partage C3/C4

# Note de non-linearite emise par `scale` (C4) pour toute categorie portant
# `nonlinearFlag: true` des que k >= K_NONLINEAR_THRESHOLD. Texte VERBATIM
# (tiret cadratin « – » dans « 1.5–2 », « × » multiplicatif) : conserve a
# l'identique pour la coherence des tests et de l'emission Cooklang (archi 8.4).
NONLINEAR_NOTE = "-- ne se double pas proprement au-delà de ~1.5–2×"


@dataclass
class ScaledQuantity:
    """Resultat d'un scaling pour une quantite.

    Champs minimaux exposes (AC6) : name, value, unit, type, fixed, notes, debug.
    `reserve` est prevu pour C4 (None en C1). `debug` alimente le panneau FR7.
    """

    name: str
    value: float
    unit: str
    type: str
    fixed: bool
    notes: list[str] = field(default_factory=list)
    # Rempli par C4 : scission de la quantite scalee en incorporation (90 %) +
    # ajustement final (10 %). Structure : {"incorporate", "reserve", "pct"}.
    # None tant qu'aucune categorie ne porte `reserve_pct` (cas general).
    reserve: dict | None = None
    debug: dict = field(default_factory=dict)


@dataclass
class ScaledEggs:
    """Resultat du scaling d'un ingredient `discrete` (oeufs) — C2.

    L'oeuf est une unite non secable et liante : on ne le coupe pas en deux dans
    une recette. On rend donc un nombre entier d'oeufs (`whole_eggs`) plus un
    reliquat exprime en volume/poids (`remainder`, ex. {grams, tbsp}) et une note
    explicative (`note`). Style aligne sur `ScaledQuantity` (dataclass, `debug`
    optionnel) pour que C5 traite les deux uniformement.
    """

    whole_eggs: int
    remainder: dict  # reliquat en volume/poids, ex. {"grams": float, "tbsp": float}
    note: str
    type: str = "discrete"
    debug: dict = field(default_factory=dict)


@dataclass
class ScaledTime:
    """Resultat du scaling `geometric` d'un temps de cuisson — C3.

    Loi geometrique `t_scaled = t * k^(2/3)` : un plat double ne demande pas le
    double de temps (diffusion surface/volume). Le temps porte toujours
    `nonlinear=True` (flag `nonlinearFlag` de la table). `note` porte la (les)
    suggestion(s) de changement de contenant `--` emise(s) quand `k` depasse le
    seuil de non-linearite (RZ2). Style aligne sur `ScaledQuantity`/`ScaledEggs`
    (dataclass, `notes` en list[str], `debug` optionnel) pour un traitement
    uniforme en C5.
    """

    minutes: float
    nonlinear: bool
    notes: list[str] = field(default_factory=list)
    type: str = "geometric"
    debug: dict = field(default_factory=dict)

    @property
    def note(self) -> str | None:
        """Note de contenant `--` (ou None si aucune) — alias de commodite.

        L'AC4 nomme le champ `note` ; on conserve `notes: list[str]` pour
        l'homogeneite avec `ScaledQuantity.notes`, et on expose `note` comme
        premiere note (ou None) pour les appelants qui attendent un scalaire.
        """
        return self.notes[0] if self.notes else None


def scale(name: str, qty: float, unit: str, k: float) -> ScaledQuantity:
    """Scale une quantite selon le type de l'ingredient (lu dans la table).

    - linear    -> value = qty * k
    - sublinear -> value = qty * k^coeff
    - fixed     -> value = qty (inchange), fixed=True (verrou `=`)
    - discrete / geometric -> hors C1 : value = qty non scalee + note de
      delegation (le calcul reel viendra en C2/C3). Comportement sur et stable
      pour ne pas planter le moteur.
    """
    rule: ScalingRule = classify(name)
    notes: list[str] = []
    fixed = False

    if rule.type == "linear":
        value = qty * k
        formula = "qty * k"

    elif rule.type == "sublinear":
        # coeff vient de la table (aucun coefficient code en dur).
        coeff = rule.coeff if rule.coeff is not None else 1.0
        value = qty * (k ** coeff)
        formula = "qty * k^coeff"

    elif rule.type == "fixed":
        value = qty
        fixed = True
        formula = "qty (inchange)"

    else:
        # discrete (C2) / geometric (C3) : non scales en C1, on delegue.
        value = qty
        formula = "qty (non scale)"
        notes.append(f"scaling {rule.type} delegue a C2/C3")

    debug = {
        "rule": rule.type,
        "coeff": rule.coeff,
        "formula": formula,
        "reasoning": rule.reason,
        "k": k,
        "matched_on": list(rule.matched_on),
    }

    # --- C4 : couche de decoration (flags non-linearite + reserve) ------------
    # Decision pure/deterministe : meme (name, qty, unit, k) -> meme sortie.
    # Ordre d'emission des notes FIXE (flag puis reserve) pour la stabilite (AC5).

    # Flag de non-linearite (AC1, AC3, AC4) : le seuil vient de la constante
    # partagee K_NONLINEAR_THRESHOLD (C3/RZ2), jamais d'un litteral 1.5.
    nonlinear = bool(rule.nonlinear_flag)
    debug["nonlinear"] = nonlinear
    debug["threshold"] = K_NONLINEAR_THRESHOLD
    if nonlinear and k >= K_NONLINEAR_THRESHOLD:
        # Idempotence : ne pas dupliquer si la note est deja presente (un autre
        # chemin pourrait l'avoir ajoutee).
        if NONLINEAR_NOTE not in notes:
            notes.append(NONLINEAR_NOTE)

    # Reserve (AC2, AC3, AC4) : appliquee a TOUTE categorie portant `reserve_pct`
    # (en l'etat, seul `sel` la porte -> seul le sel la recoit). Le taux (10) est
    # LU dans la table (`rule.reserve_pct`), jamais code en dur. Les seuls
    # litteraux admis sont les conversions arithmetiques de pourcentage (100).
    reserve: dict | None = None
    reserve_pct = rule.reserve_pct
    if reserve_pct is not None and reserve_pct > 0:
        incorporate = value * (100 - reserve_pct) / 100
        reserve_amount = value * reserve_pct / 100
        reserve = {
            "incorporate": incorporate,
            "reserve": reserve_amount,
            "pct": reserve_pct,
        }
        debug["reserve_pct"] = reserve_pct
        note = f"-- réserver ~{reserve_pct} % et ajuster en fin de cuisson"
        if note not in notes:
            notes.append(note)

    return ScaledQuantity(
        name=name,
        value=value,
        unit=unit,
        type=rule.type,
        fixed=fixed,
        notes=notes,
        reserve=reserve,
        debug=debug,
    )


def scale_eggs(count: float, k: float) -> ScaledEggs:
    """Scale un nombre d'oeufs (type `discrete`) en unites entieres + reste.

    L'oeuf est un ingredient liant et non secable : un doublement franc de la
    cible entiere surcharge la liaison/texture. La regle RZ1 (figee dans la
    story C2) borne par le bas dans le cas « x2/x3/x4 propre » et reporte l'oeuf
    retranche en reste volumique.

    Tous les parametres (grams_per_unit, tbsp_per_unit, round) sont LUS dans la
    table via `classify("oeuf")` — aucun n'est code en dur ici (DoD D7).
    Pur/deterministe : meme (count, k) -> exactement le meme ScaledEggs.
    """
    rule: ScalingRule = classify("oeuf")
    # Parametres oeufs lus dans la table (jamais codes en dur). Defauts surs au
    # cas ou la categorie ne porterait pas ces champs.
    g = rule.grams_per_unit if rule.grams_per_unit is not None else 0.0
    t = rule.tbsp_per_unit if rule.tbsp_per_unit is not None else 0.0

    target = count * k  # cible theorique (FR : count x k)

    # --- RZ1 : algorithme oeufs deterministe ---------------------------------
    # Formule : cible theorique `count * k`.
    # Condition de la borne basse « oeufs liants » : la cible tombe sur un
    # ENTIER EXACT (|target - round(target)| < EPS) ET le facteur `k` est un
    # ENTIER >= 2 (cas x2/x3/x4 propre). Alors on retranche UN oeuf entier de la
    # cible et on le reporte en reste volumique (l'oeuf liant, recuperable).
    # Sinon (k fractionnaire) : round == "down" de la table -> plancher
    # (math.floor) + reliquat fractionnaire en reste. Arrondis explicites (EPS,
    # math.floor) -> determinisme cross-plateforme, aucun alea.
    if abs(target - round(target)) < EPS and float(k).is_integer() and k >= 2:
        # RZ1 : cible entiere issue d'un facteur entier >= 2 -> oeuf liant, on
        # borne par le bas : un oeuf entier de moins, reporte en reste volumique.
        whole_eggs = int(round(target)) - 1
        leftover_units = 1.0  # l'oeuf retranche, en reste
        note = (
            f"{int(round(target))} oeufs theoriques -> {whole_eggs} entiers "
            f"+ ~{leftover_units * g:g} g ({leftover_units * t:g} c.a.s) battu "
            "reserves : l'oeuf est liant, on borne par le bas pour ne pas "
            "surcharger (regle RZ1, coefficient a calibrer)."
        )
    else:
        # round == "down" (table) : plancher + reliquat fractionnaire en reste.
        whole_eggs = math.floor(target)
        leftover_units = target - whole_eggs
        if leftover_units < EPS:
            note = (
                f"{count} oeufs x{k:g} -> {whole_eggs} entiers, reste negligeable "
                "(facteur non entier : plancher, pas de borne basse RZ1)."
            )
        else:
            note = (
                f"{count} oeufs x{k:g} -> {whole_eggs} entiers + ~{leftover_units * g:g} g "
                f"({leftover_units * t:g} c.a.s) battu reserves (plancher 'down' de la table)."
            )
    # -------------------------------------------------------------------------

    remainder = {"grams": leftover_units * g, "tbsp": leftover_units * t}

    debug = {
        "rule": rule.type,
        "target": target,
        "grams_per_unit": g,
        "tbsp_per_unit": t,
        "round": rule.round,
        "leftover_units": leftover_units,
        "reasoning": rule.reason,
        "k": k,
        "matched_on": list(rule.matched_on),
    }

    return ScaledEggs(
        whole_eggs=whole_eggs,
        remainder=remainder,
        note=note,
        debug=debug,
    )


def scale_time(minutes: float, k: float) -> ScaledTime:
    """Scale un temps de cuisson (type `geometric`) : `t * k^(2/3)`.

    Le temps n'est PAS lineaire : doubler les quantites ne double pas la cuisson
    (diffusion surface/volume, archi 5.5). On applique `t_scaled = t * k^exponent`
    ou `exponent` (= 0.6667) est LU dans la table via `classify("temps")` — jamais
    code en dur ici (contrainte D7 / DoD C3). Ex. : 20 min a x2 -> ~31.75 (~32),
    pas 40.

    Au-dela du seuil de non-linearite (`K_NONLINEAR_THRESHOLD`, RZ2), on emet une
    note `--` de changement de contenant (le plat « ne se double pas proprement »
    -> privilegier une cocotte large, reduction plus longue).

    Pur/deterministe : seule lecture admise = la table (via `classify`, cache C1) ;
    meme `(minutes, k)` -> exactement le meme `ScaledTime`.
    """
    rule: ScalingRule = classify("temps")
    # Exposant lu dans la table (categorie temps -> `exponent`). Defaut sur (loi
    # lineaire) si la categorie ne portait pas le champ — mais on ne fige JAMAIS
    # 0.6667 en litteral ici.
    exponent = rule.exponent if rule.exponent is not None else 1.0

    minutes_scaled = minutes * (k ** exponent)

    # Le temps est geometric + nonlinearFlag:true (table) -> toujours non lineaire.
    nonlinear = True

    notes: list[str] = []
    if k >= K_NONLINEAR_THRESHOLD:
        # RZ2 : au-dela du seuil, le contenant doit etre repense (profondeur/
        # surface). Note `--` style Cooklang (cf. rules[0]/rules[3] de la table).
        notes.append(
            f"-- a x{k:g}, le plat ne se double pas proprement : privilegier une "
            "cocotte large, reduction plus longue (raisonner profondeur/surface "
            "du contenant)."
        )

    debug = {
        "rule": rule.type,
        "exponent": exponent,
        "formula": "minutes * k^exponent",
        "reasoning": rule.reason,
        "k": k,
        "threshold": K_NONLINEAR_THRESHOLD,
        "matched_on": list(rule.matched_on),
    }

    return ScaledTime(
        minutes=minutes_scaled,
        nonlinear=nonlinear,
        notes=notes,
        debug=debug,
    )
