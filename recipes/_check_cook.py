"""Contrôle de bonne formation des .cook (S0.6).

Vérifie pour chaque recipes/*.cook : frontmatter `servings`, au moins un
marqueur d'ingrédient `@...{...%...}`, et accolades `{}` équilibrées.
Stdlib uniquement (re, pathlib) — aucune dépendance nouvelle.

Usage : python recipes/_check_cook.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RE_SERVINGS = re.compile(r"^---\s*\nservings:\s*\d+", re.MULTILINE)
RE_INGREDIENT = re.compile(r"@[^@#~\n]+?\{[^}]*?%[^}]*?\}")
RE_TIMER = re.compile(r"~\{[^}]*?\}")
RE_COOKWARE = re.compile(r"#[^\s#@~{]+")


def check(path: Path) -> tuple[bool, list[str]]:
    text = path.read_text(encoding="utf-8")
    problems: list[str] = []
    if not RE_SERVINGS.search(text):
        problems.append("frontmatter 'servings' manquant")
    if not RE_INGREDIENT.search(text):
        problems.append("aucun marqueur @ingredient{qty%unit}")
    if text.count("{") != text.count("}"):
        problems.append(
            f"accolades desequilibrees ({text.count('{')} '{{' vs {text.count('}')} '}}')"
        )
    return (not problems), problems


def main() -> int:
    root = Path(__file__).resolve().parent
    files = sorted(root.glob("*.cook"))
    if not files:
        print("AUCUNE recette .cook trouvee.")
        return 1
    ok_count = 0
    for f in files:
        ok, problems = check(f)
        ing = len(RE_INGREDIENT.findall(f.read_text(encoding="utf-8")))
        cw = len(RE_COOKWARE.findall(f.read_text(encoding="utf-8")))
        tm = len(RE_TIMER.findall(f.read_text(encoding="utf-8")))
        status = "OK " if ok else "ERR"
        detail = "" if ok else " -> " + "; ".join(problems)
        print(f"[{status}] {f.name:38s} @={ing:2d} #={cw:2d} ~={tm:2d}{detail}")
        ok_count += int(ok)
    print(f"\nRecettes : {len(files)} | bien formees : {ok_count} | en erreur : {len(files) - ok_count}")
    return 0 if ok_count == len(files) else 1


if __name__ == "__main__":
    sys.exit(main())
