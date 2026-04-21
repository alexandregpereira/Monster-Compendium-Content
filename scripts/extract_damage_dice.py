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
        "concussão":   ("bludgeoning", "BLUDGEONING", "Contundente"),  # sources: de dano de concussão
        "contundente": ("bludgeoning", "BLUDGEONING", "Contundente"),
        "frio":        ("cold",        "COLD",        "Gélido"),        # sources: de dano por frio
        "gélido":      ("cold",        "COLD",        "Gélido"),
        "fogo":        ("fire",        "FIRE",        "Ígneo"),         # sources: de dano de fogo
        "ígneo":       ("fire",        "FIRE",        "Ígneo"),
        "energético":  ("force",       "FORCE",       "Força"),    # mm sources: energético
        "força":       ("force",       "FORCE",       "Força"),
        "raio":        ("lightning",   "LIGHTNING",   "Elétrico"),      # sources: de dano de raio
        "elétrico":    ("lightning",   "LIGHTNING",   "Elétrico"),
        "necrótico":   ("necrotic",    "NECROTIC",    "Necrótico"),
        "perfurante":  ("piercing",    "PIERCING",    "Perfurante"),
        "veneno":      ("poison",      "POISON",      "Venenoso"),      # sources: de dano de veneno
        "venenoso":    ("poison",      "POISON",      "Venenoso"),
        "psíquico":    ("psychic",     "PSYCHIC",     "Psíquico"),
        "radiante":    ("radiant",     "RADIANT",     "Radiante"),
        "cortante":    ("slashing",    "SLASHING",    "Cortante"),
        "trovão":      ("thunder",     "THUNDER",     "Trovejante"),    # sources: de dano de trovão
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

_DICE_CORE = r"(?P<total>\d+)\s*\((?P<formula>\d+d\d+(?:\s*[+\-]\s*\d+)?)\)"

# Patterns per language — each entry is a pattern template.
# Named groups: total (required), formula (optional), type_word (required).
# PT-BR sources use "de dano [de/por] TYPE"; the main file uses "[pontos de dano] TYPE".
_PATTERN_TEMPLATES: dict[str, list[str]] = {
    "en-us": [
        r"(?P<total>\d+)\s+(?P<type_word>{types})\s+damage",                           # "1 piercing damage"
        _DICE_CORE + r"\s+(?P<type_word>{types})\s+damage",
        _DICE_CORE + r"\s+(?P<type_word1>{types})\s+or\s+(?P<type_word2>{types})\s+damage",  # "22 (5d8) fire or radiant damage"
    ],
    "pt-br": [
        r"(?P<total>\d+)\s+(?:de\s+dano\s+(?:de\s+|por\s+)?)?(?P<type_word>{types})", # "1 perfurante" / "1 de dano perfurante"
        _DICE_CORE + r"\s+(?:pontos\s+de\s+dano\s+)?(?P<type_word>{types})",           # main file format
        _DICE_CORE + r"\s+de\s+dano\s+(?:de\s+|por\s+)?(?P<type_word>{types})",       # sources format
        _DICE_CORE + r"\s+de\s+dano\s+(?:de\s+)?(?P<type_word1>{types})\s+ou\s+(?:de\s+)?(?P<type_word2>{types})",  # "22 (5d8) de dano radiante ou de fogo"
        _DICE_CORE + r"\s+(?P<type_word1>{types})\s+ou\s+(?:de\s+)?(?P<type_word2>{types})",                         # "3 (1d6) elétrico ou trovejante"
    ],
    "es": [
        r"(?P<total>\d+)\s+de\s+daño\s+(?:de\s+|por\s+)?(?P<type_word>{types})",              # "1 de daño cortante"
        _DICE_CORE + r"\s+de\s+daño\s+(?:de\s+|por\s+)?(?P<type_word>{types})",
        _DICE_CORE + r"\s+de\s+daño\s+(?:de\s+)?(?P<type_word1>{types})\s+o\s+(?:de\s+)?(?P<type_word2>{types})",  # "22 (5d8) de daño radiante o de fuego"
    ],
}


def _build_patterns(lang: str, damage_map: dict[str, tuple]) -> list[re.Pattern]:
    words = sorted(damage_map.keys(), key=len, reverse=True)
    types_alt = "|".join(re.escape(w) for w in words)

    patterns = []
    for template in _PATTERN_TEMPLATES[lang]:
        compiled = re.compile(template.format(types=types_alt), re.IGNORECASE)
        patterns.append(compiled)
    return patterns


def find_damage_dices(
    description: str,
    damage_map: dict[str, tuple[str, str, str]],
    patterns: list[re.Pattern],
) -> list[dict]:
    if not description:
        return []

    results: list[dict] = []
    seen: set[tuple] = set()

    for pattern in patterns:
        for m in pattern.finditer(description):
            total = m.group("total")
            formula = m.group("formula") if "formula" in pattern.groupindex else None
            dice_str = f"{total} ({formula.replace(' ', '')})" if formula else total

            if "type_word1" in pattern.groupindex:
                type_words = [m.group("type_word1").lower(), m.group("type_word2").lower()]
            else:
                type_words = [m.group("type_word").lower()]

            for type_word in type_words:
                entry = damage_map.get(type_word)
                if entry is None:
                    continue

                index, damage_type, name = entry
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
    patterns: list[re.Pattern],
) -> int:
    updated = 0
    for action in actions:
        desc = action.get("description") or ""
        found = find_damage_dices(desc, damage_map, patterns)
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
    patterns = _build_patterns(args.lang, damage_map)

    with open(args.input, encoding="utf-8") as f:
        monsters: list[dict] = json.load(f)

    total_updated = 0
    for monster in monsters:
        total_updated += process_actions(
            monster.get("actions", []), damage_map, patterns
        )
        total_updated += process_actions(
            monster.get("legendary_actions", []), damage_map, patterns
        )

    output_path = args.output or args.input
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(monsters, f, ensure_ascii=False, indent=4)

    print(f"Done. {total_updated} action(s) updated. Written to {output_path}")


if __name__ == "__main__":
    main()
