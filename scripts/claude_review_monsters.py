#!/usr/bin/env python3
"""
claude_review_monsters.py — Review and fix a translated monster stat block JSON file using Claude Code.

Can be run standalone or imported as a module by other scripts.

Claude Code is invoked in non-interactive print mode (-p) with Read and Edit tools allowed,
so it can open the file, apply corrections directly, and print a summary of changes.

Usage (standalone):
    python3 scripts/claude_review_monsters.py <translated_json> --lang <target_lang_code> [options]

Examples:
    python3 scripts/claude_review_monsters.py json/es/monsters.json --lang es
    python3 scripts/claude_review_monsters.py json/pt-br/sources/mtf/monsters.json --lang pt-br --source-lang en

Requirements:
    - Claude Code must be installed and the `claude` command must be available on PATH.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Core review function (importable by other scripts)
# ---------------------------------------------------------------------------

def run_claude_review(translated_path: str, target_lang: str, source_lang: str = "en") -> None:
    """
    Invoke Claude Code to review and fix a translated monster stat block JSON file.

    Claude is given Read and Edit tools so it can:
      1. Read the translated file to assess quality
      2. Edit the file in-place to fix any issues it finds
      3. Print a short summary of what was changed and why

    Review criteria:
      - Correct D&D/RPG-specific terminology in the target language
      - Consistency of terminology across all monsters (same damage type, condition,
        and creature type always translated the same way)
      - Obvious mistranslations, literal errors, or unnatural phrasing in
        descriptions and special ability text
      - Title case for name fields; sentence case for description/desc text

    Args:
        translated_path: Path to the translated JSON file to review and fix.
        target_lang:     Language code of the translation (e.g. 'es', 'fr', 'pt-br').
        source_lang:     Language code of the original source (default: 'en').
    """
    print(f"\nRunning Claude Code review on: {translated_path}")
    print(f"Lang: {source_lang} → {target_lang}\n")

    repo_root = Path(__file__).resolve().parent.parent
    conditions_path = repo_root / "json" / target_lang / "conditions.json"

    prompt = (
        f"You are reviewing a machine-translated monster stat block JSON file: '{translated_path}'. "
        f"The source language was '{source_lang}' and the target language is '{target_lang}'. "
        f"Before reviewing, read the conditions reference file at '{conditions_path}' "
        f"to get the authoritative translated names for all conditions in {target_lang}. "
        "Use the 'name' field from each entry as the correct translation for that condition "
        "when checking monster text — condition names in the monster file must match exactly. "
        "Read the monster file, then fix any issues you find directly in it. "
        "Focus on: "
        "1) Correct D&D/RPG-specific terminology in the target language "
        "(e.g. creature types, damage types, condition names, action names, "
        "skill names, sense descriptions, spell names, ability score names), "
        "2) Consistency of terminology across all monsters "
        "(e.g. the same damage type or condition must always be translated the same way), "
        "3) Obvious translation errors, literal mistranslations, or unnatural phrasing in "
        "descriptions and special ability text. "
        "Important rules to follow when editing: "
        "- Keep all JSON keys in English (never translate keys like 'index', 'name', 'subtitle', "
        "  'description', 'desc', 'special_abilities', 'actions', 'bonus_actions', 'reactions', "
        "  'legendary_actions', 'damage_dices', 'conditions', 'spells_by_group', 'spellcasting', "
        "  'source', 'skills', 'senses', 'languages'). "
        "- Never change any 'index' field values. "
        "- Never change 'type' enum values (e.g. UNDEAD, BLUDGEONING, CHARMED), "
        "  numeric values, dice notation, 'hover', 'measurement_unit', 'value', 'modifier', "
        "  'attack_bonus', 'level', 'ritual', 'concentration', 'school', or 'acronym'. "
        "- Spell terminology: for pt-br, always use 'magia'/'magias' instead of 'feitiço'/'feitiços'; "
        "  'Contrafeitiço' should be 'Contramagia'; do NOT change 'Enfeitiçado'/'Enfeitiçada' "
        "  (the Charmed condition — different word root). "
        "  For es, always use 'magia'/'magias' instead of 'hechizo'/'hechizos'. "
        "- Alignment translations in 'subtitle' field: the alignment is always the last part "
        "  after the final ', '. For pt-br use: lawful good=ordeiro e bom, neutral good=neutro e bom, "
        "  chaotic good=caótico e bom, lawful neutral=ordeiro e neutro, neutral=neutro, "
        "  chaotic neutral=caótico e neutro, lawful evil=ordeiro e mal, neutral evil=neutro e mal, "
        "  chaotic evil=caótico e mal, unaligned=sem alinhamento, evil=mal, good=bom. "
        "  Use the 'alignment' field (English) to identify the correct entry and fix the subtitle. "
        "- Measurement conversions: if 'senses' strings or action 'description'/'desc' fields "
        "  still contain 'X pés' that has NOT yet been converted to meters, convert them to "
        "  'Y metros [X feet]' where Y = X × 0.3, using a comma as the decimal separator "
        "  (e.g. '120 pés' → '36 metros [120 feet]', '5 pés' → '1,5 metro [5 feet]'). "
        "- Fields that must use title case (capitalize each major word, but leave articles, "
        "  prepositions, and conjunctions lowercase unless they are the first word): "
        "  monster 'name', 'group', skill 'name', damage type 'name', condition 'name', "
        "  special ability 'name', action 'name', bonus action 'name', reaction 'name', "
        "  legendary action 'name', spell 'name', and source 'name'. "
        "- Fields that must start with a single uppercase letter (sentence case): "
        "  'subtitle', 'subtype', 'languages', all 'senses' array strings, "
        "  'desc' (in special_abilities and reactions), "
        "  'description' (in actions, bonus_actions, and legendary_actions), "
        "  'spellcasting[].desc', and all 'spells_by_group[].group' strings "
        "  (note: group strings contain markdown like '**At will:** *Spell Name*' — "
        "  preserve the ** and * markers exactly). "
        "After editing, print a short summary of what was changed and why, "
        "referencing the monster index and field for each fix."
    )

    result = subprocess.run(
        ["claude", "-p", prompt, "--allowedTools", "Read,Edit"],
        check=False,
    )

    if result.returncode != 0:
        print(
            f"WARNING: Claude Code exited with status {result.returncode}.",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# CLI (standalone usage)
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Review and fix a translated monster stat block JSON file using Claude Code. "
            "Claude reads the file, applies corrections in-place, and prints a summary."
        )
    )
    parser.add_argument(
        "input",
        help="Path to the translated monsters JSON file to review (e.g. json/es/monsters.json)",
    )
    parser.add_argument(
        "--lang", "-l",
        required=True,
        help="Target language code of the translation (e.g. es, pt-br, fr, de)",
    )
    parser.add_argument(
        "--source-lang", "-s",
        default="en",
        help="Source language code (default: en)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    run_claude_review(
        translated_path=args.input,
        target_lang=args.lang,
        source_lang=args.source_lang,
    )


if __name__ == "__main__":
    main()
