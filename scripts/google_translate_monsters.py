#!/usr/bin/env python3
"""
google_translate_monsters.py — Translate a monster stat block JSON file using the Google Translate API.

Can be run standalone or imported as a module by other scripts.

Usage (standalone):
    python3 scripts/google_translate_monsters.py <input_json> --lang <lang_code> [options]

Examples:
    python3 scripts/google_translate_monsters.py json/en-us/monsters.json --lang es
    python3 scripts/google_translate_monsters.py json/en-us/sources/mtf/monsters.json --lang pt-br --output json/pt-br/sources/mtf/monsters.json

Translatable fields per monster (all others are kept as-is):
    name, subtitle, subtype, group, languages          (top-level scalars)
    senses[]                                            (array of strings)
    skills[].name
    damage_vulnerabilities[].name
    damage_resistances[].name
    damage_immunities[].name
    condition_immunities[].name
    special_abilities[].name, .desc, .conditions[].name, .spells_by_group[].*
    actions[].name, .description, .damage_dices[].damage.name,
            .conditions[].name, .spells_by_group[].*
    bonus_actions[].name, .description, .damage_dices[].damage.name,
                 .conditions[].name, .spells_by_group[].*
    reactions[].name, .desc, .spells_by_group[].*
    legendary_actions[].name, .description, .damage_dices[].damage.name,
                      .conditions[].name, .spells_by_group[].*
    spellcasting[].desc, .spells_by_group[].*
    source.name

    For spells_by_group[]:
        group   (markdown-formatted label, e.g. "**At will:** *Fireball*")
        spells[].name

Non-translatable fields (kept as-is):
    index, type, size, alignment, all numeric values, dice notation,
    hover, measurement_unit, value, modifier, attack_bonus, level,
    ritual, concentration, school, acronym, saving_throws

Formatting rules after translation:
  - name fields and monster group labels → title_case()
  - all other text (desc/description, subtitle, senses, languages, etc.) → ensure_upper()

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

# Correct D&D alignment translations per language.
# The alignment field is excluded from Google Translate (it stays in English),
# but the subtitle field is translated and ends with the alignment text.
# After translation, normalize_alignments() replaces the alignment portion
# of each subtitle using these lookup tables.
ALIGNMENT_TRANSLATIONS: dict[str, dict[str, str]] = {
    "pt-br": {
        "lawful good":    "ordeiro e bom",
        "neutral good":   "neutro e bom",
        "chaotic good":   "caótico e bom",
        "lawful neutral": "ordeiro e neutro",
        "neutral":        "neutro",
        "chaotic neutral": "caótico e neutro",
        "lawful evil":    "ordeiro e mal",
        "neutral evil":   "neutro e mal",
        "chaotic evil":   "caótico e mal",
        "evil":           "mal",
        "good":           "bom",
        "unaligned":      "sem alinhamento",
    },
}

# Languages that use the metric system — feet-to-meters conversion will be applied.
_METRIC_LANGS = {"pt-br", "es", "fr", "de", "it", "pl", "cs", "hu", "ro", "nl"}

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
    """Return text trimmed of leading/trailing whitespace with the first character uppercased."""
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

    Example: "golpe del dragón" → "Golpe del Dragón"
    """
    text = text.strip()
    if not text:
        return text
    words = text.split()
    result = []
    for i, word in enumerate(words):
        if i == 0 or word.lower() not in _MINOR_WORDS:
            result.append(word[0].upper() + word[1:])
        else:
            result.append(word.lower())
    return " ".join(result)


def derive_output_path(input_path: str, lang: str) -> str:
    """
    Derive an output path by replacing the locale segment in the input path.

    Example:
        json/en-us/sources/mtf/monsters.json  →  json/es/sources/mtf/monsters.json

    Falls back to placing the file next to the input with a language suffix if the
    locale segment is not found in the path.
    """
    normalised = input_path.replace("\\", "/")
    new_path = re.sub(r"json/[a-z]{2}(?:-[a-z]{2})?/", f"json/{lang}/", normalised, count=1)
    if new_path == normalised:
        base, ext = os.path.splitext(input_path)
        new_path = f"{base}-{lang}{ext}"
    return new_path


# ---------------------------------------------------------------------------
# Post-processing helpers
# ---------------------------------------------------------------------------

def normalize_alignments(data: list, target_lang: str) -> None:
    """
    Fix alignment translations in the subtitle field of each monster.

    The subtitle format is "Size Type, alignment" — alignment is always after
    the last ", ". We replace that portion with the correct translated alignment
    looked up from ALIGNMENT_TRANSLATIONS, using the untouched `alignment` field
    (which stays in English) as the key.
    """
    lang_table = ALIGNMENT_TRANSLATIONS.get(target_lang)
    if not lang_table:
        return

    for monster in data:
        alignment_en = monster.get("alignment", "")
        subtitle = monster.get("subtitle", "")
        if not alignment_en or not subtitle:
            continue

        translated_alignment = lang_table.get(alignment_en.lower())
        if not translated_alignment:
            continue

        # Subtitle ends with ", <alignment>" — find the last ", " separator.
        sep_idx = subtitle.rfind(", ")
        if sep_idx == -1:
            continue

        prefix = subtitle[:sep_idx]
        suffix = subtitle[sep_idx + 2:]  # everything after ", "

        # Preserve any trailing punctuation (e.g. ".") that was on the old alignment.
        trailing = ""
        if suffix and suffix[-1] in ".!?":
            trailing = suffix[-1]

        monster["subtitle"] = f"{prefix}, {translated_alignment}{trailing}"


def _feet_to_meters_str(feet: int) -> str:
    """Return feet converted to a pt-BR-style metric string, e.g. '36 metros' or '1,5 metro'."""
    meters = round(feet * 0.3, 1)
    meters_str = f"{meters:g}".replace(".", ",")
    unit = "metro" if meters == 1.0 else "metros"
    return f"{meters_str} {unit}"


def _replace_feet_in_text(text: str) -> str:
    """Replace foot measurements in a string with metric equivalents + feet brackets.

    Handles:
      - 'X pés' / 'X pé'  (Portuguese translation of feet)
      - 'X ft.'            (English abbreviation left untranslated by Google)
      - 'X/Y ft.'          (English slash-range, e.g. '30/120 ft.')
    """
    def repl_single(m: re.Match) -> str:
        feet = int(m.group(1))
        return f"{_feet_to_meters_str(feet)} [{feet} feet]"

    def repl_range(m: re.Match) -> str:
        feet1, feet2 = int(m.group(1)), int(m.group(2))
        m1 = round(feet1 * 0.3, 1)
        m2 = round(feet2 * 0.3, 1)
        m1_str = f"{m1:g}".replace(".", ",")
        m2_str = f"{m2:g}".replace(".", ",")
        return f"{m1_str}/{m2_str}m [{feet1}/{feet2} feet]"

    # Range pattern first to avoid "120" in "30/120 ft." being consumed alone.
    text = re.sub(r'(\d+)/(\d+)\s*ft\.', repl_range, text)
    text = re.sub(r'(\d+)\s*ft\.', repl_single, text)
    text = re.sub(r'(\d+)\s*pés?', repl_single, text)
    return text


def convert_feet_to_meters(data: list, target_lang: str) -> None:
    """
    Convert foot measurements in text fields to meters for metric-system locales.

    Handles:
      - senses[] strings: "Visão no escuro 120 pés." → "Visão no escuro 36 metros [120 feet]."
      - description/desc in actions and ability blocks: "alcance 10 pés." → "alcance 3 metros [10 feet]."
      - description/desc with English abbreviation: "reach 5 ft." → "1,5 metro [5 feet]"
      - description/desc with English range: "range 30/120 ft." → "9/36m [30/120 feet]"
      - speed value_formatted: "10 ft." → "3m [10 ft.]"
    """
    if target_lang in ("en", "en-us") or target_lang not in _METRIC_LANGS:
        return

    _action_keys = ("special_abilities", "actions", "bonus_actions", "reactions", "legendary_actions")

    for monster in data:
        # senses
        monster["senses"] = [_replace_feet_in_text(s) for s in monster.get("senses", [])]

        # action-like blocks
        for key in _action_keys:
            desc_field = "description" if key in ("special_abilities", "reactions") else "description"
            for entry in monster.get(key, []):
                if desc_field in entry and isinstance(entry[desc_field], str):
                    entry[desc_field] = _replace_feet_in_text(entry[desc_field])

        # spellcasting desc
        for sc in monster.get("spellcasting", []):
            if isinstance(sc.get("desc"), str):
                sc["desc"] = _replace_feet_in_text(sc["desc"])

        # speed value_formatted ("10 ft." → "3m [10 ft.]")
        for speed_entry in monster.get("speed", {}).get("value", []):
            vf = speed_entry.get("value_formatted", "")
            if "ft." in vf:
                feet_val = speed_entry.get("value")
                if isinstance(feet_val, (int, float)):
                    meters = round(feet_val * 0.3, 1)
                    meters_str = f"{meters:g}".replace(".", ",")
                    speed_entry["value_formatted"] = f"{meters_str}m [{feet_val} ft.]"


def add_missing_feet_brackets(data: list) -> None:
    """
    Add [X feet] brackets to meter values in text fields that are missing them.

    For files that were previously converted from feet to meters but had the brackets
    omitted, this function reverse-calculates the original feet value and appends it.
    Entries that already have brackets (e.g. "18 metros [60 feet]") are skipped.
    Also fixes the abbreviated form "X m [Y ft.]" → "Xm [Y ft.]" in value_formatted.

    Handles: senses[], languages, description/desc in action blocks, spellcasting[].desc,
    and speed value_formatted.
    """
    # Match "X metros" or "X,X metro" NOT already followed by a digit bracket like "[60 feet]".
    # Using (?!\s*\[\d) instead of (?!\s*\[) so non-digit brackets like "[Área de Efeito]"
    # and "[pairando]" are NOT skipped — feet need to be inserted before those too.
    # \b after metros? prevents backtracking from matching "metro" inside "metros [".
    _metro_pat = re.compile(r'(\d+(?:,\d+)?)\s*(metros?)\b(?!\s*\[\d)', re.IGNORECASE)

    # Same logic for abbreviated "X m" / "Xm" form.
    _abbrev_m_pat = re.compile(r'(\d+(?:,\d+)?)\s*m\b(?!etros?\b)(?!\s*\[\d)', re.IGNORECASE)

    # Slash-separated range in abbreviated meters: "9/36 m" → "9/36m [30/120 feet]".
    # Must be applied before _abbrev_m_pat so "36" in "9/36 m" is not consumed alone.
    _range_m_pat = re.compile(
        r'(\d+(?:,\d+)?)/(\d+(?:,\d+)?)\s*m\b(?!etros?\b)(?!\s*\[\d)',
        re.IGNORECASE,
    )

    def _add_brackets(text: str) -> str:
        def repl(m: re.Match) -> str:
            meters_val = float(m.group(1).replace(",", "."))
            feet = round(meters_val / 0.3)
            return f"{m.group(1)} {m.group(2)} [{feet} feet]"
        return _metro_pat.sub(repl, text)

    def _add_brackets_range(text: str) -> str:
        def repl(m: re.Match) -> str:
            m1 = float(m.group(1).replace(",", "."))
            m2 = float(m.group(2).replace(",", "."))
            feet1 = round(m1 / 0.3)
            feet2 = round(m2 / 0.3)
            return f"{m.group(1)}/{m.group(2)}m [{feet1}/{feet2} feet]"
        return _range_m_pat.sub(repl, text)

    def _add_brackets_abbrev(text: str) -> str:
        def repl(m: re.Match) -> str:
            meters_val = float(m.group(1).replace(",", "."))
            feet = round(meters_val / 0.3)
            return f"{m.group(1)}m [{feet} feet]"  # no space before m
        return _abbrev_m_pat.sub(repl, text)

    def _fix_text(text: str) -> str:
        # Repair corruption from a previous buggy run that matched "metro" (without "s")
        # inside "metros [Área de Efeito]", producing "metro [X feet]s [Área de Efeito]".
        text = re.sub(r'metro (\[\d+ feet\])s', r'metros \1', text)
        return _add_brackets_abbrev(_add_brackets_range(_add_brackets(text)))

    _action_keys = ("special_abilities", "actions", "bonus_actions", "reactions", "legendary_actions")

    for monster in data:
        monster["senses"] = [_fix_text(s) for s in monster.get("senses", [])]

        if isinstance(monster.get("languages"), str):
            monster["languages"] = _fix_text(monster["languages"])

        for key in _action_keys:
            desc_field = "desc" if key in ("special_abilities", "reactions") else "description"
            for entry in monster.get(key, []):
                if isinstance(entry.get(desc_field), str):
                    entry[desc_field] = _fix_text(entry[desc_field])

        for sc in monster.get("spellcasting", []):
            if isinstance(sc.get("desc"), str):
                sc["desc"] = _fix_text(sc["desc"])

        # Fix "3 m [10 ft.]" → "3m [10 ft.]" in value_formatted
        for speed_entry in monster.get("speed", {}).get("value", []):
            vf = speed_entry.get("value_formatted", "")
            if " m [" in vf:
                speed_entry["value_formatted"] = re.sub(r'(\S)\s+m\s+\[', r'\1m [', vf)


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
# Step 1 — Extract translatable strings and record their positions
# ---------------------------------------------------------------------------

def extract_texts(data: list) -> tuple[list[str], list[tuple]]:
    """
    Walk the monsters data and collect every translatable string value.

    Returns:
        texts — flat list of source strings ready to send to the translation API
        refs  — parallel list of (container, key_or_index, fmt) tuples so each
                translated string can be written back to the right location in data.
                'container' is the actual dict or list object (by reference).
                'key_or_index' is a dict key (str) or list index (int).
                'fmt' is "title" or "desc" to select the post-processing function.
    """
    texts: list[str] = []
    refs: list[tuple] = []

    def add(container, key, fmt: str) -> None:
        value = container[key]
        if isinstance(value, str) and value:
            texts.append(value)
            refs.append((container, key, fmt))

    def add_spells_by_group(entry: dict) -> None:
        for grp in entry.get("spells_by_group", []):
            add(grp, "group", "desc")
            for spell in grp.get("spells", []):
                add(spell, "name", "title")

    def add_action_entry(entry: dict, desc_field: str) -> None:
        """
        Translate a single action-like entry (actions, bonus_actions, legendary_actions,
        reactions, special_abilities). desc_field is "description" or "desc" depending
        on which container this entry belongs to.
        """
        add(entry, "name", "title")
        if desc_field in entry:
            add(entry, desc_field, "desc")
        for dd in entry.get("damage_dices", []):
            dmg = dd.get("damage")
            if dmg and dmg.get("name"):
                add(dmg, "name", "title")
        for cond in entry.get("conditions", []):
            add(cond, "name", "title")
        add_spells_by_group(entry)

    for monster in data:
        # ── Top-level scalar fields ────────────────────────────────────────
        add(monster, "name", "title")
        if monster.get("subtitle"):
            add(monster, "subtitle", "desc")
        if monster.get("subtype") is not None and isinstance(monster["subtype"], str):
            add(monster, "subtype", "desc")
        if monster.get("group") is not None and isinstance(monster["group"], str):
            add(monster, "group", "title")
        if monster.get("languages") is not None and isinstance(monster["languages"], str):
            add(monster, "languages", "desc")

        # ── senses (list of strings) ───────────────────────────────────────
        for i, sense in enumerate(monster.get("senses", [])):
            if isinstance(sense, str) and sense:
                texts.append(sense)
                refs.append((monster["senses"], i, "desc"))

        # ── skills[].name ──────────────────────────────────────────────────
        for skill in monster.get("skills", []):
            add(skill, "name", "title")

        # ── damage & condition arrays ──────────────────────────────────────
        for arr_key in ("damage_vulnerabilities", "damage_resistances",
                        "damage_immunities", "condition_immunities"):
            for entry in monster.get(arr_key, []):
                add(entry, "name", "title")

        # ── action-like containers ─────────────────────────────────────────
        # special_abilities and reactions use "desc"; others use "description"
        for sa in monster.get("special_abilities", []):
            add_action_entry(sa, "desc")

        for action in monster.get("actions", []):
            add_action_entry(action, "description")

        for ba in monster.get("bonus_actions", []):
            add_action_entry(ba, "description")

        for reaction in monster.get("reactions", []):
            add_action_entry(reaction, "desc")

        for la in monster.get("legendary_actions", []):
            add_action_entry(la, "description")

        # ── spellcasting (top-level, older format) ────────────────────────
        for sc in monster.get("spellcasting", []):
            if sc.get("desc"):
                add(sc, "desc", "desc")
            add_spells_by_group(sc)

        # ── source.name ───────────────────────────────────────────────────
        src = monster.get("source")
        if src and src.get("name"):
            add(src, "name", "title")

    return texts, refs


# ---------------------------------------------------------------------------
# Step 3 — Apply translations back into the data structure
# ---------------------------------------------------------------------------

def apply_translations(refs: list[tuple], translated: list[str]) -> None:
    """
    Write each translated string back to its original position in the data and
    apply field-specific formatting:
      - fmt == "title"  → title_case()
      - fmt == "desc"   → ensure_upper()
    """
    for (container, key, fmt), value in zip(refs, translated):
        container[key] = title_case(value) if fmt == "title" else ensure_upper(value)


# ---------------------------------------------------------------------------
# Public entry point (used by translate_monster.py and callable from other scripts)
# ---------------------------------------------------------------------------

def translate_monsters_file(
    input_path: str,
    lang: str,
    api_key: str,
    output_path: str | None = None,
    source_lang: str = "en",
) -> str:
    """
    Full pipeline: load → extract → translate → apply → save.

    Returns the path of the saved output file so callers (e.g. translate_monster.py)
    can pass it along to a review step.
    """
    resolved_output = output_path or derive_output_path(input_path, lang)

    print(f"Input:   {input_path}")
    print(f"Output:  {resolved_output}")
    print(f"Lang:    {source_lang} → {lang}")

    print(f"\nLoading {input_path}...")
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    print("Extracting translatable strings...")
    texts, refs = extract_texts(data)
    print(f"  Found {len(texts)} translatable strings across {len(data)} monsters.")

    if not texts:
        print("Nothing to translate. Skipping API call.")
        return resolved_output

    print("\nSending to Google Translate API...")
    translated = translate_all(texts, lang, source_lang, api_key)

    print("Applying translations...")
    apply_translations(refs, translated)

    print("Normalizing alignments...")
    normalize_alignments(data, lang)

    print("Converting feet to meters...")
    convert_feet_to_meters(data, lang)

    print(f"Saving output to {resolved_output}...")
    os.makedirs(os.path.dirname(resolved_output) or ".", exist_ok=True)
    with open(resolved_output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print(f"\nDone. Translated {len(texts)} strings.")
    return resolved_output


def fix_translated_file(file_path: str, lang: str) -> None:
    """
    Apply post-processing fixes to an already-translated file without calling
    the Google Translate API. Saves in-place.

    Steps:
      1. add_missing_feet_brackets — adds [X feet] to meter values that lack brackets,
         and fixes "X m [Y ft.]" → "Xm [Y ft.]" in speed value_formatted
      2. normalize_alignments — corrects alignment text in subtitle fields
      3. convert_feet_to_meters — converts any remaining "X pés" to "X metros [Y feet]"
    """
    print(f"Loading {file_path}...")
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)

    print("Adding missing feet brackets...")
    add_missing_feet_brackets(data)

    print("Normalizing alignments...")
    normalize_alignments(data, lang)

    print("Converting feet to meters...")
    convert_feet_to_meters(data, lang)

    print(f"Saving {file_path}...")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    print("Done.")


# ---------------------------------------------------------------------------
# CLI (standalone usage)
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Translate a monster stat block JSON file using the Google Translate API."
    )
    parser.add_argument(
        "input",
        help="Path to the source monsters JSON file (e.g. json/en-us/monsters.json)",
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
        "--fix",
        action="store_true",
        help=(
            "Fix an already-translated file in-place: apply alignment normalization and "
            "feet-to-meters conversion without calling the Google Translate API."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if args.fix:
        fix_translated_file(file_path=args.input, lang=args.lang)
        return

    api_key = args.api_key or os.environ.get("GOOGLE_TRANSLATE_API_KEY")
    if not api_key:
        print(
            "ERROR: Google Translate API key not found. "
            "Set the GOOGLE_TRANSLATE_API_KEY environment variable or pass --api-key.",
            file=sys.stderr,
        )
        sys.exit(1)

    translate_monsters_file(
        input_path=args.input,
        lang=args.lang,
        api_key=api_key,
        output_path=args.output,
        source_lang=args.source_lang,
    )


if __name__ == "__main__":
    main()
