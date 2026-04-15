#!/usr/bin/env python3
"""
translate_lore.py — Translate a monster-lore JSON file using the Google Translate API.

Usage:
    python3 scripts/translate_lore.py <input_json> --lang <lang_code> [options]

Examples:
    python3 scripts/translate_lore.py json/en-us/lore/mtf/monster-lore.json --lang es
    python3 scripts/translate_lore.py json/en-us/lore/mtf/monster-lore.json --lang fr --review
    python3 scripts/translate_lore.py json/en-us/lore/hftt/monster-lore.json --lang pt-br --output json/pt-br/lore/hftt/monster-lore.json

Only the values of "title" and "description" fields are translated.
All JSON keys are kept in English. The "index" field is never translated.
Both "title" and "description" values are guaranteed to start with an uppercase letter.

The Google API key is read from the GOOGLE_TRANSLATE_API_KEY environment variable,
or can be provided via --api-key.

Optionally, after saving the translated file, a Claude Code review can be triggered
via the --review flag, which invokes `claude -p` in non-interactive mode.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GOOGLE_TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"
BATCH_SIZE = 100  # Google's limit is 128; 100 keeps us safely under


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_upper(text: str) -> str:
    """Return text with the first character forced to uppercase."""
    if not text:
        return text
    return text[0].upper() + text[1:]


def derive_output_path(input_path: str, lang: str) -> str:
    """
    Derive an output path by replacing the locale segment in the input path.

    Example:
        json/en-us/lore/mtf/monster-lore.json  →  json/es/lore/mtf/monster-lore.json
    """
    # Normalise separators so the regex works on all platforms
    normalised = input_path.replace("\\", "/")
    # Replace a locale-like segment (e.g. "en-us", "en", "pt-br") with the target lang
    new_path = re.sub(r"json/[a-z]{2}(?:-[a-z]{2})?/", f"json/{lang}/", normalised, count=1)
    if new_path == normalised:
        # Fallback: place next to the input file with lang suffix
        base, ext = os.path.splitext(input_path)
        new_path = f"{base}-{lang}{ext}"
    return new_path


# ---------------------------------------------------------------------------
# Step 1 — Extract translatable strings and record their positions
# ---------------------------------------------------------------------------

def extract_texts(data: list) -> tuple[list[str], list[tuple[int, int, str]]]:
    """
    Walk the lore data and collect every translatable string value.

    Returns:
        texts  — flat list of source strings to translate
        refs   — list of (monster_idx, entry_idx, field_name) tuples that map
                 each text back to its location in the data structure
    """
    texts = []
    refs = []

    for monster_idx, monster in enumerate(data):
        for entry_idx, entry in enumerate(monster.get("entries", [])):
            # "title" is optional; "description" is always present
            for field in ("title", "description"):
                if field in entry:
                    texts.append(entry[field])
                    refs.append((monster_idx, entry_idx, field))

    return texts, refs


# ---------------------------------------------------------------------------
# Step 2 — Batch-translate via Google Translate REST API (stdlib only)
# ---------------------------------------------------------------------------

def translate_batch(texts: list[str], target_lang: str, source_lang: str, api_key: str) -> list[str]:
    """
    Send one batch of texts to the Google Translate API and return translated strings.

    Uses urllib.request so no third-party dependencies are needed.
    """
    payload = json.dumps({
        "q": texts,
        "target": target_lang,
        "source": source_lang,
        "format": "text",  # "text" avoids HTML entity encoding in the response
    }).encode("utf-8")

    url = f"{GOOGLE_TRANSLATE_URL}?key={urllib.parse.quote(api_key, safe='')}"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            response_body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        print(f"ERROR: Google Translate API returned {exc.code}: {error_body}", file=sys.stderr)
        sys.exit(1)

    return [item["translatedText"] for item in response_body["data"]["translations"]]


def translate_all(texts: list[str], target_lang: str, source_lang: str, api_key: str) -> list[str]:
    """
    Split texts into batches, translate each, and return the full translated list.
    Prints progress so the user knows how many API calls are being made.
    """
    translated = []
    total_batches = (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_num, start in enumerate(range(0, len(texts), BATCH_SIZE), start=1):
        batch = texts[start : start + BATCH_SIZE]
        print(f"  Translating batch {batch_num}/{total_batches} ({len(batch)} strings)...")
        translated.extend(translate_batch(batch, target_lang, source_lang, api_key))

    return translated


# ---------------------------------------------------------------------------
# Step 3 — Apply translations back into the data structure
# ---------------------------------------------------------------------------

def apply_translations(data: list, refs: list[tuple[int, int, str]], translated: list[str]) -> None:
    """
    Write each translated string back to its original position in the data.
    Also enforces that the first character of every value is uppercase.
    """
    for (monster_idx, entry_idx, field), value in zip(refs, translated):
        data[monster_idx]["entries"][entry_idx][field] = ensure_upper(value)


# ---------------------------------------------------------------------------
# Step 4 — Optional Claude Code review
# ---------------------------------------------------------------------------

def run_claude_review(output_path: str, source_lang: str, target_lang: str) -> None:
    """
    Invoke Claude Code in non-interactive print mode (-p) to review the translated file.
    Claude Code must be installed and accessible on PATH as `claude`.
    """
    print("\nRunning Claude Code review...")

    prompt = (
        f"Review the translation quality in the file '{output_path}'. "
        f"The source language was '{source_lang}' and the target language is '{target_lang}'. "
        "Please check for: "
        "1) Correct D&D/RPG-specific terminology in the target language, "
        "2) Consistency of tone and terminology across all entries, "
        "3) Obvious translation errors, unnatural phrasing, or missing context. "
        "Report any issues found with the monster index and entry field where the problem occurs."
    )

    # -p runs Claude Code in non-interactive (print) mode — outputs result to stdout
    result = subprocess.run(["claude", "-p", prompt], check=False)
    if result.returncode != 0:
        print("WARNING: Claude review exited with a non-zero status.", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Translate a monster-lore JSON file using the Google Translate API."
    )

    # Positional: path to the source JSON file
    parser.add_argument(
        "input",
        help="Path to the source monster-lore JSON file (e.g. json/en-us/lore/mtf/monster-lore.json)",
    )

    # Required: target language code
    parser.add_argument(
        "--lang", "-l",
        required=True,
        help="Target language code (e.g. es, pt-br, fr, de)",
    )

    # Optional: explicit output path (auto-derived from input path if omitted)
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file path. Defaults to replacing the locale segment in the input path.",
    )

    # Optional: source language (defaults to English)
    parser.add_argument(
        "--source-lang", "-s",
        default="en",
        help="Source language code (default: en)",
    )

    # Optional: API key (falls back to GOOGLE_TRANSLATE_API_KEY env var)
    parser.add_argument(
        "--api-key", "-k",
        default=None,
        help="Google Translate API key. Falls back to the GOOGLE_TRANSLATE_API_KEY env var.",
    )

    # Flag: trigger a Claude Code review after saving
    parser.add_argument(
        "--review",
        action="store_true",
        help="After saving, run a Claude Code review of the translation quality.",
    )

    return parser.parse_args()


def main() -> None:
    # --- Parse CLI arguments ---
    args = parse_args()

    # --- Resolve the Google API key (arg takes precedence over env var) ---
    api_key = args.api_key or os.environ.get("GOOGLE_TRANSLATE_API_KEY")
    if not api_key:
        print(
            "ERROR: Google Translate API key not found. "
            "Set the GOOGLE_TRANSLATE_API_KEY environment variable or pass --api-key.",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- Resolve the output file path ---
    output_path = args.output or derive_output_path(args.input, args.lang)

    print(f"Input:   {args.input}")
    print(f"Output:  {output_path}")
    print(f"Lang:    {args.source_lang} → {args.lang}")

    # --- Load the source JSON ---
    print(f"\nLoading {args.input}...")
    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)

    # --- Extract all translatable strings and record their positions ---
    print("Extracting translatable strings...")
    texts, refs = extract_texts(data)
    print(f"  Found {len(texts)} translatable strings across {len(data)} monsters.")

    if not texts:
        print("Nothing to translate. Exiting.")
        sys.exit(0)

    # --- Translate all strings via Google Translate API ---
    print(f"\nSending to Google Translate API...")
    translated = translate_all(texts, args.lang, args.source_lang, api_key)

    # --- Apply translated values back into the data structure ---
    print("Applying translations...")
    apply_translations(data, refs, translated)

    # --- Save the translated JSON file ---
    print(f"Saving output to {output_path}...")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"\nDone. Translated {len(texts)} strings.")

    # --- Optionally trigger a Claude Code review ---
    if args.review:
        run_claude_review(output_path, args.source_lang, args.lang)


if __name__ == "__main__":
    main()
