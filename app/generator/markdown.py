"""Rendu Markdown lisible — story D4 (couche 4, dernière story du sprint 4).

Ce module expose une fonction PURE et DÉTERMINISTE de la couche 4
(``app/generator/``) :

  - ``to_markdown(recipe) -> str`` : produit un document Markdown LISIBLE par un
    humain à partir d'un ``StructuredRecipe`` (contrat figé D1, consommé en
    LECTURE SEULE). Le document comprend un titre ``# {title}``, une ligne de
    portions, une section ``## Ingrédients`` (liste à puces « quantité + unité +
    nom »), une section ``## Préparation`` (étapes numérotées avec restitution
    VISIBLE des températures + étiquettes ``[SÉCURITÉ]/[TECHNIQUE]/
    [PRÉFÉRENCE]``, des durées et du cookware), puis ``## Techniques`` et
    ``## Notes`` émises uniquement si non vides.

``to_markdown`` est le **pendant « lisible humain »** de ``to_cooklang`` (D3,
pendant « machine » téléchargeable). Il alimente ``GenerationResponse.markdown``
(archi §9.1) et constitue la **VITRINE de l'explicabilité** (archi §9.2 /
barrière 1 §6.1) : les températures de sécurité des protéines et leurs étiquettes
apparaissent clairement dans le rendu.

Signature à 1 paramètre (archi §4.4 : ``def to_markdown(recipe) -> str``).
**Décision par défaut figée** : contrairement à ``to_cooklang(recipe,
scaling_notes)`` (D3), ``to_markdown`` ne prend PAS ``scaling_notes`` ; il rend
la ``StructuredRecipe`` telle qu'elle est passée. Si le Markdown doit refléter le
scaling, l'orchestrateur/E1 construit/adapte la ``StructuredRecipe`` (quantités
scalées) AVANT l'appel. Cela respecte §4.4 (1 paramètre) et garde D4 pur,
déterministe et découplé de la couche 3.

Règle inter-couches STRICTE (archi §3.1) : ce module importe UNIQUEMENT
``app.generator.models`` (même couche 4, LECTURE SEULE). Il N'IMPORTE NI
``app/scaling/``, NI ``app/knowledge/``, NI ``app/epicure/`` au runtime, NI
``anthropic``, NI les autres modules de la couche (``cooklang.py``/``validate.py``
/``prompt.py``/``client.py``). Le helper de formatage des nombres est RECOPIÉ du
style D3 (≈ 10 lignes stdlib), PAS importé.

Conventions : ``from __future__ import annotations`` ; type hints PEP 585 ;
docstrings FR (accents corrects) ; identifiants/clés en anglais snake_case ;
module pur (aucune I/O, aucun ``random``, aucune horloge, aucun LLM/réseau).
"""

from __future__ import annotations

from app.generator.models import (
    Duration,
    Quantity,
    Step,
    StructuredRecipe,
    Temperature,
)

# --------------------------------------------------------------------------- #
# Helper de formatage des nombres RECOPIÉ du style D3 (`app/generator/         #
# cooklang.py#_format_number`) — PAS importé (autre module de la couche,       #
# lecture seule ; on recopie ≈ 10 lignes stdlib pour éviter tout couplage).    #
# --------------------------------------------------------------------------- #


def _format_number(value: float) -> str:
    """Formate un nombre de façon DÉTERMINISTE (entiers sans décimale superflue).

    ``2.0`` -> ``"2"`` ; ``2.5`` -> ``"2.5"`` ; ``0`` -> ``"0"``. On évite toute
    instabilité de représentation flottante cross-plateforme via
    ``format(.., "g")`` qui supprime les zéros non significatifs et l'exposant
    inutile. Aucune dépendance à la locale.
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
# Helpers de composition lisible (quantité, température, durée).               #
# --------------------------------------------------------------------------- #


def _format_quantity(qty: Quantity) -> str:
    """Compose un ingrédient lisible « quantité + unité + nom » (puce Markdown).

    Exemples : ``2 c.à.s huile d'olive`` ; ``3 œufs`` (unité vide) ;
    ``huile d'olive`` (quantité nulle ET unité vide). **Décision par défaut
    documentée** : on insère un simple espace entre unité et nom (format sobre,
    pas d'élision « d' »/« de » devant voyelle — bonus optionnel non retenu pour
    rester déterministe et neutre). Le champ ``fixed`` n'a PAS d'impact visuel
    (verrou ``=`` propre au ``.cook`` de D3 ; ignoré pour le rendu humain).
    """
    number = _format_number(qty.amount)
    unit = str(qty.unit).strip()
    name = str(qty.name).strip()

    parts: list[str] = []
    # On affiche la quantité sauf si elle est nulle ET qu'aucune unité n'est
    # portée (ex. « sel, poivre » sans quantité -> on n'écrit pas « 0 »).
    if number != "0" or unit:
        parts.append(number)
    if unit:
        parts.append(unit)
    if name:
        parts.append(name)
    return " ".join(parts)


def _format_temperature(temp: Temperature) -> str:
    """Rend une température lisible « {valeur} {°C|°F} [{label}] » (VISIBLE).

    Conserve l'étiquette ``[SÉCURITÉ]/[TECHNIQUE]/[PRÉFÉRENCE]`` (graphie
    accentuée du contrat D1 / corpus S0.6), exigence d'explicabilité (archi
    §9.2/§6.1). L'unité « C »/« F » du contrat est rendue ``°C``/``°F`` (style
    cohérent D3).
    """
    unit = str(temp.unit).strip().upper()
    symbol = "°F" if unit in {"F", "°F"} else "°C"
    label = str(temp.label).strip()
    rendered = f"{_format_number(temp.value)} {symbol}"
    if label:
        rendered = f"{rendered} [{label}]"
    return rendered


def _format_duration(duration: Duration) -> str:
    """Rend une durée lisible « {valeur} {unité} » (ex. « 9 minutes »)."""
    unit = str(duration.unit).strip()
    rendered = _format_number(duration.value)
    if unit:
        rendered = f"{rendered} {unit}"
    return rendered


def _step_detail_lines(step: Step) -> list[str]:
    """Compose les sous-puces de détails VISIBLES d'une étape (déterministe).

    Restitue, dans l'ordre figé température(s) -> durée(s) -> ustensile(s), les
    ``Step.temperatures`` (avec étiquette), ``Step.durations`` et
    ``Step.cookware`` quand présents. Les températures de **sécurité** (label
    « SÉCURITÉ ») sont rendues de manière non ambiguë sous un libellé dédié
    (AC3/§9.2). Anti-bruit : aucune sous-puce pour une collection vide (AC4).
    """
    details: list[str] = []
    for temp in step.temperatures:
        if str(temp.label).strip().upper() == "SÉCURITÉ":
            details.append(
                f"  - Température de sécurité : {_format_temperature(temp)}"
            )
        else:
            details.append(f"  - Température : {_format_temperature(temp)}")
    for duration in step.durations:
        details.append(f"  - Durée : {_format_duration(duration)}")
    cookware = [str(item).strip() for item in step.cookware if str(item).strip()]
    if cookware:
        details.append(f"  - Ustensiles : {', '.join(cookware)}")
    return details


# --------------------------------------------------------------------------- #
# Fonction publique : rendu Markdown lisible.                                  #
# --------------------------------------------------------------------------- #


def to_markdown(recipe: StructuredRecipe) -> str:
    """Rend un ``StructuredRecipe`` en document Markdown LISIBLE (archi §4.4/§7).

    Composition DÉTERMINISTE (ordre figé, aucun tri non déterministe) :

      1. **Titre** ``# {recipe.title}``.
      2. **Ligne de portions** ``**Portions : {recipe.servings}**`` (portions de
         BASE, archi §7).
      3. **``## Ingrédients``** : liste à puces « quantité + unité + nom » des
         ``recipe.ingredients`` (ou « _(aucun ingrédient)_ » si vide).
      4. **``## Préparation``** : liste numérotée des ``recipe.steps`` (texte +
         sous-puces VISIBLES température[+étiquette]/durée/cookware) (ou
         « _(aucune étape)_ » si vide).
      5. **``## Techniques``** : émise UNIQUEMENT si ``recipe.techniques`` non
         vide.
      6. **``## Notes``** : émise UNIQUEMENT si ``recipe.notes`` non vide.

    PUR/DÉTERMINISTE : aucune I/O, aucun ``random``, aucune horloge, aucun
    LLM/réseau ; même ``recipe`` -> exactement le même Markdown. Le document se
    termine par un ``"\\n"`` final stable.

    **Signature à 1 paramètre** (archi §4.4) : PAS de ``scaling_notes`` (cf. AC5).
    La ``StructuredRecipe`` passée porte déjà les valeurs voulues ; le scaling, s'il
    doit apparaître, est appliqué côté pipeline AVANT l'appel.

    Args:
        recipe: la recette structurée (contrat figé D1, LECTURE SEULE).

    Returns:
        Le document Markdown (str, UTF-8) lisible par un humain, alimentant
        ``GenerationResponse.markdown`` (archi §9.1).
    """
    lines: list[str] = []

    # --- 1. Titre + 2. Portions (toujours émis, archi AC4) ---------------------
    lines.append(f"# {recipe.title}")
    lines.append("")
    lines.append(f"**Portions : {recipe.servings}**")

    # --- 3. Ingrédients (section structurante toujours présente) ---------------
    lines.append("")
    lines.append("## Ingrédients")
    lines.append("")
    if recipe.ingredients:
        for qty in recipe.ingredients:
            lines.append(f"- {_format_quantity(qty)}")
    else:
        lines.append("_(aucun ingrédient)_")

    # --- 4. Préparation (section structurante toujours présente) ---------------
    lines.append("")
    lines.append("## Préparation")
    lines.append("")
    if recipe.steps:
        for index, step in enumerate(recipe.steps, start=1):
            text = str(step.text).strip()
            lines.append(f"{index}. {text}")
            lines.extend(_step_detail_lines(step))
    else:
        lines.append("_(aucune étape)_")

    # --- 5. Techniques (conditionnelle : seulement si non vide) ----------------
    techniques = [str(t).strip() for t in recipe.techniques if str(t).strip()]
    if techniques:
        lines.append("")
        lines.append("## Techniques")
        lines.append("")
        for technique in techniques:
            lines.append(f"- {technique}")

    # --- 6. Notes (conditionnelle : seulement si non vide) ---------------------
    notes = [str(n).strip() for n in recipe.notes if str(n).strip()]
    if notes:
        lines.append("")
        lines.append("## Notes")
        lines.append("")
        for note in notes:
            lines.append(f"- {note}")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":  # pragma: no cover - sanity-check manuel
    # Sanity-check : construire un StructuredRecipe minimal, imprimer le rendu.
    demo = StructuredRecipe(
        title="Poulet rôti aux herbes",
        servings=4,
        ingredients=(
            Quantity(name="huile d'olive", amount=2.0, unit="c.à.s"),
            Quantity(name="œufs", amount=3, unit=""),
            Quantity(name="gros sel", amount=10, unit="g", fixed=True),
        ),
        steps=(
            Step(
                text="[TECHNIQUE] Saisir le poulet sur toutes ses faces.",
                cookware=("grande poêle",),
                temperatures=(Temperature(value=180, unit="C", label="TECHNIQUE"),),
                durations=(Duration(value=5, unit="minutes"),),
                technique_id="searing",
            ),
            Step(
                text="[SÉCURITÉ] Cuire jusqu'à cœur à température de sécurité.",
                temperatures=(Temperature(value=74, unit="C", label="SÉCURITÉ"),),
                durations=(Duration(value=45, unit="minutes"),),
            ),
        ),
        techniques=("searing",),
        notes=("[PRÉFÉRENCE] Laisser reposer 10 minutes avant de découper.",),
    )
    print(to_markdown(demo))
