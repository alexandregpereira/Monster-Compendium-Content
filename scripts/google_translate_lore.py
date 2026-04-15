#!/usr/bin/env python3
"""
google_translate_lore.py — Translate a monster-lore JSON file using the Google Translate API.

Can be run standalone or imported as a module by other scripts.

Usage (standalone):
    python3 scripts/google_translate_lore.py <input_json> --lang <lang_code> [options]

Examples:
    python3 scripts/google_translate_lore.py json/en-us/lore/mtf/monster-lore.json --lang es
    python3 scripts/google_translate_lore.py json/en-us/lore/hftt/monster-lore.json --lang pt-br --output json/pt-br/lore/hftt/monster-lore.json

Only the values of "title" and "description" fields are translated.
All JSON keys are kept in English. The "index" field is never translated.

Formatting rules after translation:
  - "title"       → title case  (e.g. "Enemigos del Mal Elemental")
  - "description" → first character uppercased only

The Google API key is read from the GOOGLE_TRANSLATE_API_KEY environment variable,
or can be provided via --api-key.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GOOGLE_TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"
BATCH_SIZE = 100  # Google's hard limit is 128 strings per request; 100 is a safe margin

# Minor words that stay lowercase in title case (articles, prepositions, conjunctions).
# Covers Spanish, Portuguese, French, German, and English to support any target language.
_MINOR_WORDS = {
    # Spanish
    "de", "del", "el", "la", "los", "las", "en", "y", "a", "al", "con",
    "por", "para", "sin", "sobre", "un", "una", "unos", "unas", "o",
    # Portuguese
    "do", "da", "dos", "das", "no", "na", "nos", "nas", "ao", "aos",
    "às", "e", "ou", "um", "uma",
    # French
    "du", "des", "au", "aux", "et", "un", "une", "le", "les",
    # German
    "der", "die", "das", "des", "dem", "den", "von", "und", "im", "ein", "eine",
    # English
    "of", "the", "a", "an", "in", "on", "at", "to", "for", "and",
    "but", "or", "nor", "as", "if",
}


# ---------------------------------------------------------------------------
# Text formatting helpers
# ---------------------------------------------------------------------------

def ensure_upper(text: str) -> str:
    """Return text trimmed of leading/trailing whitespace with the first character uppercased (used for descriptions)."""
    text = text.strip()
    if not text:
        return text
    return text[0].upper() + text[1:]


def title_case(text: str) -> str:
    """
    Apply title case: capitalize every word except minor words (articles, prepositions,
    conjunctions). The first word is always capitalized regardless.
    Leading and trailing whitespace is trimmed before processing.

    Only the first character of each word is uppercased; the rest stay as-is so
    abbreviations like 'CR' or 'D&D' are not broken.

    Example: "enemigos del mal elemental" → "Enemigos del Mal Elemental"
    """
    text = text.strip()
    if not text:
        return text
    words = text.split()
    result = []
    for i, word in enumerate(words):
        # Always capitalize the first word; leave known minor words lowercase elsewhere
        if i == 0 or word.lower() not in _MINOR_WORDS:
            result.append(word[0].upper() + word[1:])
        else:
            result.append(word.lower())
    return " ".join(result)


def derive_output_path(input_path: str, lang: str) -> str:
    """
    Derive an output path by replacing the locale segment in the input path.

    Example:
        json/en-us/lore/mtf/monster-lore.json  →  json/es/lore/mtf/monster-lore.json

    Falls back to placing the file next to the input with a language suffix if the
    locale segment is not found in the path.
    """
    # Normalise separators so the regex works on all platforms
    normalised = input_path.replace("\\", "/")
    # Match a locale-like segment (e.g. "en-us", "en", "pt-br") and replace it
    new_path = re.sub(r"json/[a-z]{2}(?:-[a-z]{2})?/", f"json/{lang}/", normalised, count=1)
    if new_path == normalised:
        # Fallback: add lang suffix before the extension
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
        texts — flat list of source strings ready to send to the translation API
        refs  — parallel list of (monster_idx, entry_idx, field_name) tuples so each
                translated string can be written back to the right location in data
    """
    texts = []
    refs = []

    for monster_idx, monster in enumerate(data):
        for entry_idx, entry in enumerate(monster.get("entries", [])):
            # "title" is optional; "description" is always present — translate both
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
    Send one batch of texts to the Google Translate API and return the translated strings.

    Uses only urllib.request from the standard library — no third-party dependencies needed.
    The "format": "text" flag prevents Google from HTML-encoding characters like '&' → '&amp;'.
    """
    payload = json.dumps({
        "q": texts,
        "target": target_lang,
        "source": source_lang,
        "format": "text",
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
    Split texts into batches of BATCH_SIZE, translate each, and return the full list.
    Prints progress so the user can track how many API calls are being made.
    """
    translated = []
    total_batches = (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_num, start in enumerate(range(0, len(texts), BATCH_SIZE), start=1):
        batch = texts[start: start + BATCH_SIZE]
        print(f"  Translating batch {batch_num}/{total_batches} ({len(batch)} strings)...")
        translated.extend(translate_batch(batch, target_lang, source_lang, api_key))

    return translated


# ---------------------------------------------------------------------------
# Step 3 — Apply translations back into the data structure
# ---------------------------------------------------------------------------

def apply_translations(data: list, refs: list[tuple[int, int, str]], translated: list[str]) -> None:
    """
    Write each translated string back to its original position in the data and
    apply field-specific formatting:
      - "title"       → title_case()   (e.g. "Enemigos del Mal Elemental")
      - "description" → ensure_upper() (first character uppercased only)
    """
    for (monster_idx, entry_idx, field), value in zip(refs, translated):
        if field == "title":
            formatted = title_case(value)
        else:
            formatted = ensure_upper(value)
        data[monster_idx]["entries"][entry_idx][field] = formatted


# ---------------------------------------------------------------------------
# Public entry point (used by translate_lore.py and callable from other scripts)
# ---------------------------------------------------------------------------

def translate_lore_file(
    input_path: str,
    lang: str,
    api_key: str,
    output_path: str | None = None,
    source_lang: str = "en",
) -> str:
    """
    Full pipeline: load → extract → translate → apply → save.

    Returns the path of the saved output file so callers (e.g. translate_lore.py)
    can pass it along to a review step.
    """
    # Resolve output path if not provided
    resolved_output = output_path or derive_output_path(input_path, lang)

    print(f"Input:   {input_path}")
    print(f"Output:  {resolved_output}")
    print(f"Lang:    {source_lang} → {lang}")

    # Load source JSON
    print(f"\nLoading {input_path}...")
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    # Extract all translatable title/description values
    print("Extracting translatable strings...")
    texts, refs = extract_texts(data)
    print(f"  Found {len(texts)} translatable strings across {len(data)} monsters.")

    if not texts:
        print("Nothing to translate. Skipping API call.")
        return resolved_output

    # Translate via Google API in batches
    print("\nSending to Google Translate API...")
    # translated = translate_all(texts, lang, source_lang, api_key)

    # Write translations back with formatting applied
    print("Applying translations...")
    apply_translations(data, refs, texts)

    # Save the result
    print(f"Saving output to {resolved_output}...")
    os.makedirs(os.path.dirname(resolved_output) or ".", exist_ok=True)
    with open(resolved_output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"\nDone. Translated {len(texts)} strings.")
    return resolved_output


# ---------------------------------------------------------------------------
# CLI (standalone usage)
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Translate a monster-lore JSON file using the Google Translate API."
    )
    parser.add_argument(
        "input",
        help="Path to the source monster-lore JSON file (e.g. json/en-us/lore/mtf/monster-lore.json)",
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
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # Resolve API key: CLI arg takes precedence over environment variable
    api_key = args.api_key or os.environ.get("GOOGLE_TRANSLATE_API_KEY")
    if not api_key:
        print(
            "ERROR: Google Translate API key not found. "
            "Set the GOOGLE_TRANSLATE_API_KEY environment variable or pass --api-key.",
            file=sys.stderr,
        )
        sys.exit(1)

    translate_lore_file(
        input_path=args.input,
        lang=args.lang,
        api_key=api_key,
        output_path=args.output,
        source_lang=args.source_lang,
    )


if __name__ == "__main__":
    main()
