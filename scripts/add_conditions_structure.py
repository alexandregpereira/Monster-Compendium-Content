#!/usr/bin/env python3
"""
add_conditions_structure.py — Parse DC saving throws and conditions from action/ability
descriptions and add structured fields to special_abilities, actions, and legendary_actions.

Usage:
    python3 scripts/add_conditions_structure.py json/en-us/monsters.json --lang en-us
    python3 scripts/add_conditions_structure.py json/pt-br/monsters.json --lang pt-br
    python3 scripts/add_conditions_structure.py json/es/monsters.json --lang es
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

# Extra search terms per language for conditions whose translations differ from
# the canonical condition name in conditions.json.
# Maps: lang → { condition_index → [alternate_words, ...] }
CONDITION_SYNONYMS: dict[str, dict[str, list[str]]] = {
    "en-us": {},
    "pt-br": {
        # "charmed" → conditions.json uses "Encantado" but descriptions say "enfeitiçado"
        "charmed": ["enfeitiçado", "enfeitiçada"],
        # "frightened" → conditions.json uses "Amedrontado" but descriptions use feminine "amedrontada"
        "frightened": ["amedrontada"],
    },
    "es": {
        # "frightened" → conditions.json uses "Atemorizado" but descriptions say "asustado/a"
        "frightened": ["asustado", "asustada", "atemorizada"],
        # "charmed" → conditions.json uses "Encantado" but descriptions say "hechizado/a"
        "charmed": ["hechizado", "hechizada"],
        # "prone" → conditions.json uses "Caído" but descriptions say "derribado/a"
        "prone": ["derribado", "derribada", "derribadas"],
    },
}

# Ability name (localized) → (ENUM type, abbreviation)
ABILITY_MAPS: dict[str, dict[str, tuple[str, str]]] = {
    "en-us": {
        "Strength":     ("STRENGTH",     "str"),
        "Dexterity":    ("DEXTERITY",    "dex"),
        "Constitution": ("CONSTITUTION", "con"),
        "Intelligence": ("INTELLIGENCE", "int"),
        "Wisdom":       ("WISDOM",       "wis"),
        "Charisma":     ("CHARISMA",     "cha"),
    },
    "pt-br": {
        "Força":        ("STRENGTH",     "str"),
        "Destreza":     ("DEXTERITY",    "dex"),
        "Constituição": ("CONSTITUTION", "con"),
        "Inteligência": ("INTELLIGENCE", "int"),
        "Sabedoria":    ("WISDOM",       "wis"),
        "Carisma":      ("CHARISMA",     "cha"),
    },
    "es": {
        "Fuerza":        ("STRENGTH",     "str"),
        "Destreza":      ("DEXTERITY",    "dex"),
        "Constitución":  ("CONSTITUTION", "con"),
        "Inteligencia":  ("INTELLIGENCE", "int"),
        "Sabiduría":     ("WISDOM",       "wis"),
        "Carisma":       ("CHARISMA",     "cha"),
    },
}


def _build_ability_pattern(ability_map: dict[str, tuple[str, str]]) -> str:
    return "|".join(re.escape(name) for name in ability_map)


def _lookup_ability(matched_name: str, ability_map: dict[str, tuple[str, str]]) -> tuple[str, str]:
    lower = matched_name.lower()
    for key, value in ability_map.items():
        if key.lower() == lower:
            return value
    raise KeyError(matched_name)


def find_saving_throws(
    description: str, ability_map: dict[str, tuple[str, str]]
) -> list[dict]:
    if not description:
        return []

    ability_pattern = _build_ability_pattern(ability_map)
    results: list[dict] = []
    seen: set[tuple] = set()

    def _add(ability_name: str, dc_value: int) -> None:
        ability_type, ability_abbr = _lookup_ability(ability_name, ability_map)
        key = (ability_type, dc_value)
        if key not in seen:
            seen.add(key)
            results.append({
                "index": f"saving-throw-{ability_abbr}",
                "type": ability_type,
                "modifier": dc_value,
            })

    # English: "DC 14 Constitution saving throw"
    for m in re.finditer(rf"\bDC\s+(\d+)\s+({ability_pattern})\s+(?:saving)", description, re.IGNORECASE):
        _add(m.group(2), int(m.group(1)))

    # pt-br / es: "Constituição CD 14" / "Constitución CD 14"
    for m in re.finditer(rf"\b({ability_pattern})\s+CD\s+(\d+)", description, re.IGNORECASE):
        _add(m.group(1), int(m.group(2)))

    return results


def _matches_any(description: str, terms: list[str]) -> bool:
    return any(
        re.search(r"\b" + re.escape(t) + r"\b", description, re.IGNORECASE)
        for t in terms
    )


def find_conditions(
    description: str,
    conditions_by_name: dict[str, dict],
    synonyms: dict[str, list[str]],
) -> list[dict]:
    if not description:
        return []

    results: list[dict] = []
    seen: set[str] = set()

    # Longest canonical name first to avoid partial matches
    sorted_names = sorted(conditions_by_name, key=len, reverse=True)
    for name in sorted_names:
        cond = conditions_by_name[name]
        if cond["index"] in seen:
            continue
        extra = synonyms.get(cond["index"], [])
        if _matches_any(description, [name] + extra):
            seen.add(cond["index"])
            results.append({
                "index": cond["index"],
                "type": cond["type"],
                "name": cond["name"],
            })

    return results


def process_entries(
    entries: list[dict],
    desc_key: str,
    ability_map: dict[str, tuple[str, str]],
    conditions_by_name: dict[str, dict],
    synonyms: dict[str, list[str]],
) -> None:
    for entry in entries:
        # Remove singular fields written by previous script versions
        entry.pop("saving_throw", None)
        entry.pop("condition", None)

        desc = entry.get(desc_key) or ""

        saving_throws = find_saving_throws(desc, ability_map)
        if saving_throws:
            entry["saving_throws"] = saving_throws

        conditions = find_conditions(desc, conditions_by_name, synonyms)
        if conditions:
            entry["conditions"] = conditions


def derive_conditions_path(monsters_path: str, lang: str) -> str:
    # Walk up from the input file until we find the lang directory, then use that
    # as the root for conditions.json. This works for nested paths like
    # json/en-us/sources/mm/monsters.json as well as json/en-us/monsters.json.
    parts = os.path.abspath(monsters_path).split(os.sep)
    for i, part in enumerate(parts):
        if part == lang:
            lang_dir = os.sep.join(parts[: i + 1])
            return os.path.join(lang_dir, "conditions.json")
    raise FileNotFoundError(
        f"Could not locate '{lang}' directory in path: {monsters_path}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Add structured saving_throw and condition fields to "
            "special_abilities, actions, and legendary_actions in monsters.json."
        )
    )
    parser.add_argument(
        "input",
        help="Path to monsters.json (e.g. json/en-us/monsters.json)",
    )
    parser.add_argument(
        "--lang", "-l",
        required=True,
        choices=list(ABILITY_MAPS),
        help="Language code (en-us, pt-br, es)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file path (default: overwrite input file)",
    )
    parser.add_argument(
        "--conditions", "-c",
        default=None,
        help="Explicit path to conditions.json (overrides auto-derived path)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ability_map = ABILITY_MAPS[args.lang]
    synonyms = CONDITION_SYNONYMS.get(args.lang, {})

    conditions_path = args.conditions or derive_conditions_path(args.input, args.lang)
    if not os.path.exists(conditions_path):
        print(f"ERROR: conditions.json not found at {conditions_path}", file=sys.stderr)
        sys.exit(1)

    with open(conditions_path, encoding="utf-8") as f:
        conditions: list[dict] = json.load(f)

    conditions_by_name = {c["name"]: c for c in conditions}

    with open(args.input, encoding="utf-8") as f:
        monsters: list[dict] = json.load(f)

    for monster in monsters:
        process_entries(
            monster.get("special_abilities", []), "desc", ability_map, conditions_by_name, synonyms
        )
        process_entries(
            monster.get("actions", []), "description", ability_map, conditions_by_name, synonyms
        )
        process_entries(
            monster.get("legendary_actions", []), "description", ability_map, conditions_by_name, synonyms
        )

    output_path = args.output or args.input
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(monsters, f, ensure_ascii=False, indent=4)

    print(f"Done. Written to {output_path}")


if __name__ == "__main__":
    main()
