#!/usr/bin/env python3
"""
claude_review_spells.py — Review and fix a translated spells JSON file using Claude Code.

Can be run standalone or imported as a module by other scripts.

Claude Code is invoked in non-interactive print mode (-p) with Read and Edit tools allowed,
so it can open the file, apply corrections directly, and print a summary of changes.

Usage (standalone):
    python3 scripts/claude_review_spells.py <translated_json> --lang <target_lang_code> [options]

Examples:
    python3 scripts/claude_review_spells.py json/es/spells.json --lang es
    python3 scripts/claude_review_spells.py json/fr/spells.json --lang fr --source-lang en

Requirements:
    - Claude Code must be installed and the `claude` command must be available on PATH.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

# Languages that use imperial units (feet, miles) — all others get metric conversion review
_IMPERIAL_LANGUAGES = {"en", "en-us"}


# ---------------------------------------------------------------------------
# Core review function (importable by other scripts)
# ---------------------------------------------------------------------------

def run_claude_review(translated_path: str, target_lang: str, source_lang: str = "en") -> None:
    """
    Invoke Claude Code to review and fix a translated spells JSON file.

    Claude is given Read and Edit tools so it can:
      1. Read the translated file to assess quality
      2. Edit the file in-place to fix any issues it finds
      3. Print a short summary of what was changed and why

    Review criteria:
      - Correct D&D/RPG-specific terminology in the target language
        (e.g. spell school names, spell component descriptions, damage types)
      - Consistency of tone and terminology across entries
      - Obvious mistranslations, literal errors, or unnatural phrasing
      - The "name" field must use title case
      - All other text fields must start with an uppercase letter

    Args:
        translated_path: Path to the translated JSON file to review and fix.
        target_lang:     Language code of the translation (e.g. 'es', 'fr', 'pt-br').
        source_lang:     Language code of the original source (default: 'en').
    """
    print(f"\nRunning Claude Code review on: {translated_path}")
    print(f"Lang: {source_lang} → {target_lang}\n")

    if target_lang.lower() not in _IMPERIAL_LANGUAGES:
        if target_lang.lower() == "es":
            _fmt_example = "9 metros [30 pies], 1,5 kilómetros [1 milla]"
        elif target_lang.lower() == "pt-br":
            _fmt_example = "9m [30 ft.], 1,6 km [1 mile]"
        else:
            _fmt_example = "9 meters [30 feet], 1.5 kilometers [1 mile]"
        _measurement_criterion = (
            "4) Verify feet-to-meters conversions: every distance originally in feet must be "
            "converted to meters using n × 0.3 (use centimeters for values under 5 feet), and "
            "every distance in miles must be converted to kilometers using n × 1.5. "
            "The original imperial value must appear in brackets immediately after the metric value "
            f"(e.g. {_fmt_example}). "
            "Check that the arithmetic is correct and fix any wrong conversions. "
            "Use a comma as the decimal separator where appropriate for this language. "
        )
    else:
        _measurement_criterion = ""

    prompt = (
        f"You are reviewing a machine-translated spells JSON file: '{translated_path}'. "
        f"The source language was '{source_lang}' and the target language is '{target_lang}'. "
        "Read the file, then fix any issues you find directly in the file. "
        "Focus on: "
        "1) Correct D&D/RPG-specific terminology in the target language "
        "(e.g. spell school names, spell component descriptions, casting time phrasing, damage types), "
        "2) Consistency of tone and terminology across all spell entries, "
        "3) Obvious translation errors, literal mistranslations, or unnatural phrasing. "
        + _measurement_criterion +
        "Important rules to follow when editing: "
        "- Keep all JSON keys in English (never translate keys like 'index', 'name', 'casting_time', "
        "  'components', 'duration', 'range', 'description', 'higher_level'). "
        "- Never change any 'index' field values. "
        "- Never change the values of 'level', 'ritual', 'concentration', "
        "  'saving_throw_type', 'damage_type', or 'school'. "
        "- Every 'name' value must use title case (capitalize each major word, "
        "  but leave articles, prepositions, and conjunctions lowercase unless they are the first word). "
        "- Every other text field ('casting_time', 'components', 'duration', 'range', "
        "  'description', 'higher_level') must start with an uppercase letter. "
        "After editing, print a short summary of what was changed and why, "
        "referencing the spell index and field for each fix."
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
            "Review and fix a translated spells JSON file using Claude Code. "
            "Claude reads the file, applies corrections in-place, and prints a summary."
        )
    )
    parser.add_argument(
        "input",
        help="Path to the translated spells JSON file to review (e.g. json/es/spells.json)",
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
