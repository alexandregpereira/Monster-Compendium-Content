#!/usr/bin/env python3
"""
translate_spells.py — Full pipeline: Google Translate a spells file, then optionally review with Claude.

This script orchestrates the two standalone scripts:
  - google_translate_spells.py  (translation step)
  - claude_review_spells.py     (review and fix step)

Both can also be run independently when only one step is needed.

Usage:
    python3 scripts/translate_spells.py <input_json> --lang <lang_code> [options]

Examples:
    # Translate only
    python3 scripts/translate_spells.py json/en-us/spells.json --lang es

    # Translate then review and fix with Claude Code
    python3 scripts/translate_spells.py json/en-us/spells.json --lang es --review

    # Translate with explicit output path and API key
    python3 scripts/translate_spells.py json/en-us/spells.json \\
        --lang pt-br --output json/pt-br/spells.json --api-key YOUR_KEY
"""

from __future__ import annotations

import argparse
import os
import sys

# Allow importing sibling scripts from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from google_translate_spells import translate_spells_file  # noqa: E402
from claude_review_spells import run_claude_review         # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Translate a spells JSON file with Google Translate, "
            "then optionally review and fix the result with Claude Code."
        )
    )

    parser.add_argument(
        "input",
        help="Path to the source spells JSON file (e.g. json/en-us/spells.json)",
    )

    parser.add_argument(
        "--lang", "-l",
        required=True,
        help="Target language code (e.g. es, pt-br, fr, de)",
    )

    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file path. Defaults to replacing the locale segment in the input path.",
    )

    parser.add_argument(
        "--source-lang", "-s",
        default="en",
        help="Source language code (default: en)",
    )

    parser.add_argument(
        "--api-key", "-k",
        default=None,
        help="Google Translate API key. Falls back to the GOOGLE_TRANSLATE_API_KEY env var.",
    )

    parser.add_argument(
        "--review",
        action="store_true",
        help=(
            "After saving the translation, invoke Claude Code to review and fix the file. "
            "Requires the `claude` CLI to be installed and on PATH."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    api_key = args.api_key or os.environ.get("GOOGLE_TRANSLATE_API_KEY")
    if not api_key:
        print(
            "ERROR: Google Translate API key not found. "
            "Set the GOOGLE_TRANSLATE_API_KEY environment variable or pass --api-key.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Step 1 — Translate the spells file using Google Translate
    output_path = translate_spells_file(
        input_path=args.input,
        lang=args.lang,
        api_key=api_key,
        output_path=args.output,
        source_lang=args.source_lang,
    )

    # Step 2 — Optionally review and fix with Claude Code
    if args.review:
        run_claude_review(
            translated_path=output_path,
            target_lang=args.lang,
            source_lang=args.source_lang,
        )


if __name__ == "__main__":
    main()
