#!/usr/bin/env python3
"""
extract_damage_dice.py — Parse damage dice from action/legendary_action descriptions
and populate the damage_dices array with structured entries.

Usage:
    python3 scripts/extract_damage_dice.py json/en-us/monsters.json --lang en-us
    python3 scripts/extract_damage_dice.py json/pt-br/monsters.json --lang pt-br
    python3 scripts/extract_damage_dice.py json/es/monsters.json --lang es
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

# Maps: localized damage word → (index, TYPE, Name)
DAMAGE_MAPS: dict[str, dict[str, tuple[str, str, str]]] = {
    "en-us": {
        "acid":        ("acid",        "ACID",        "Acid"),
        "bludgeoning": ("bludgeoning", "BLUDGEONING", "Bludgeoning"),
        "cold":        ("cold",        "COLD",        "Cold"),
        "fire":        ("fire",        "FIRE",        "Fire"),
        "force":       ("force",       "FORCE",       "Force"),
        "lightning":   ("lightning",   "LIGHTNING",   "Lightning"),
        "necrotic":    ("necrotic",    "NECROTIC",    "Necrotic"),
        "piercing":    ("piercing",    "PIERCING",    "Piercing"),
        "poison":      ("poison",      "POISON",      "Poison"),
        "psychic":     ("psychic",     "PSYCHIC",     "Psychic"),
        "radiant":     ("radiant",     "RADIANT",     "Radiant"),
        "slashing":    ("slashing",    "SLASHING",    "Slashing"),
        "thunder":     ("thunder",     "THUNDER",     "Thunder"),
    },
    "pt-br": {
        "ácido":       ("acid",        "ACID",        "Ácido"),
        "contundente": ("bludgeoning", "BLUDGEONING", "Contundente"),
        "gélido":      ("cold",        "COLD",        "Gélido"),
        "ígneo":       ("fire",        "FIRE",        "Ígneo"),
        "força":       ("force",       "FORCE",       "Força"),
        "elétrico":    ("lightning",   "LIGHTNING",   "Elétrico"),
        "necrótico":   ("necrotic",    "NECROTIC",    "Necrótico"),
        "perfurante":  ("piercing",    "PIERCING",    "Perfurante"),
        "venenoso":    ("poison",      "POISON",      "Venenoso"),
        "psíquico":    ("psychic",     "PSYCHIC",     "Psíquico"),
        "radiante":    ("radiant",     "RADIANT",     "Radiante"),
        "cortante":    ("slashing",    "SLASHING",    "Cortante"),
        "trovejante":  ("thunder",     "THUNDER",     "Trovejante"),
    },
    "es": {
        "ácido":       ("acid",        "ACID",        "Ácido"),
        "contundente": ("bludgeoning", "BLUDGEONING", "Contundente"),
        "frío":        ("cold",        "COLD",        "Frío"),
        "fuego":       ("fire",        "FIRE",        "Fuego"),
        "fuerza":      ("force",       "FORCE",       "Fuerza"),
        "rayo":        ("lightning",   "LIGHTNING",   "Rayo"),
        "necrótico":   ("necrotic",    "NECROTIC",    "Necrótico"),
        "perforante":  ("piercing",    "PIERCING",    "Perforante"),
        "veneno":      ("poison",      "POISON",      "Veneno"),
        "venenoso":    ("poison",      "POISON",      "Veneno"),
        "psíquico":    ("psychic",     "PSYCHIC",     "Psíquico"),
        "radiante":    ("radiant",     "RADIANT",     "Radiante"),
        "cortante":    ("slashing",    "SLASHING",    "Cortante"),
        "trueno":      ("thunder",     "THUNDER",     "Trueno"),
    },
}

_DICE_CORE = r"(\d+)\s*\((\d+d\d+(?:\s*[+\-]\s*\d+)?)\)"

# Patterns per language — the capture group after the dice is the damage type word.
_PATTERNS: dict[str, str] = {
    "en-us": _DICE_CORE + r"\s+({types})\s+damage",
    "pt-br": _DICE_CORE + r"\s+(?:pontos de dano\s+)?({types})",
    "es":    _DICE_CORE + r"\s+de\s+daño\s+(?:de\s+)?({types})",
}


def _build_pattern(lang: str, damage_map: dict[str, tuple]) -> re.Pattern:
    words = sorted(damage_map.keys(), key=len, reverse=True)
    types_alt = "|".join(re.escape(w) for w in words)
    template = _PATTERNS[lang].format(types=types_alt)
    return re.compile(template, re.IGNORECASE)


def find_damage_dices(
    description: str,
    damage_map: dict[str, tuple[str, str, str]],
    pattern: re.Pattern,
) -> list[dict]:
    if not description:
        return []

    results: list[dict] = []
    seen: set[tuple] = set()

    for m in pattern.finditer(description):
        total = m.group(1)
        formula = m.group(2).replace(" ", "")
        type_word = m.group(3).lower()

        entry = damage_map.get(type_word)
        if entry is None:
            continue

        index, damage_type, name = entry
        dice_str = f"{total} ({formula})"
        key = (dice_str, index)
        if key in seen:
            continue
        seen.add(key)

        results.append({
            "dice": dice_str,
            "damage": {
                "index": index,
                "type": damage_type,
                "name": name,
            },
        })

    return results


def process_actions(
    actions: list[dict],
    damage_map: dict[str, tuple[str, str, str]],
    pattern: re.Pattern,
) -> int:
    updated = 0
    for action in actions:
        desc = action.get("description") or ""
        found = find_damage_dices(desc, damage_map, pattern)
        if found:
            action["damage_dices"] = found
            updated += 1
    return updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract damage dice from action descriptions and populate "
            "the damage_dices array in monsters.json."
        )
    )
    parser.add_argument(
        "input",
        help="Path to monsters.json (e.g. json/en-us/monsters.json)",
    )
    parser.add_argument(
        "--lang", "-l",
        required=True,
        choices=list(DAMAGE_MAPS),
        help="Language code (en-us, pt-br, es)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file path (default: overwrite input file)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    damage_map = DAMAGE_MAPS[args.lang]
    pattern = _build_pattern(args.lang, damage_map)

    with open(args.input, encoding="utf-8") as f:
        monsters: list[dict] = json.load(f)

    total_updated = 0
    for monster in monsters:
        total_updated += process_actions(
            monster.get("actions", []), damage_map, pattern
        )
        total_updated += process_actions(
            monster.get("legendary_actions", []), damage_map, pattern
        )

    output_path = args.output or args.input
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(monsters, f, ensure_ascii=False, indent=4)

    print(f"Done. {total_updated} action(s) updated. Written to {output_path}")


if __name__ == "__main__":
    main()
