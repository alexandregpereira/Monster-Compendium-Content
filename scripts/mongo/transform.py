"""Pure file <-> document mapping. No database involved.

Both directions live here so that round-trip fidelity can be tested without a
running MongoDB, and so that the future /publish endpoint and the import share
one definition of the mapping.

The contract: documents_to_files(files_to_documents(x)) reproduces x byte for
byte. Everything else in this pipeline depends on that holding.
"""

import hashlib
import json
import os

from . import manifest as mf

# Serialization styles found in the tree. The content files are not formatted
# consistently -- the 2024-era sources use indent=2, everything older uses 4,
# the legacy aggregated lore files are minified, and a handful carry stray
# trailing whitespace. Formatting is therefore measured per file, never assumed.
INDENT_CANDIDATES = [4, 2, 3, 8, 1]
DEFAULT_INDENT = 4

STYLE_INDENT = "indent"
STYLE_COMPACT = "compact"          # separators=(",", ":")
STYLE_COMPACT_SPACED = "compact-spaced"  # separators=(", ", ": ")
STYLE_EMPTY_NEWLINE = "empty-newline"    # the literal text "[\n]"

EMPTY_NEWLINE_TEXT = "[\n]"


# --------------------------------------------------------------------------- io

def _render(payload, style, indent):
    if style == STYLE_COMPACT:
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    if style == STYLE_COMPACT_SPACED:
        return json.dumps(payload, separators=(", ", ": "), ensure_ascii=False)
    if style == STYLE_EMPTY_NEWLINE:
        return EMPTY_NEWLINE_TEXT
    return json.dumps(payload, indent=indent, ensure_ascii=False)


def detect_format(raw, parsed):
    """Recover the exact formatting of a file we may have to re-emit later.

    Returns a dict with style, indent, trailing and format_exact. trailing is
    the literal whitespace run at end of file, not a boolean: one file ends
    with a newline followed by sixteen spaces, and a bool cannot carry that.

    format_exact is False when no candidate reproduces the file. The caller
    reports those rather than pretending the round trip is lossless -- one file
    in the tree has hand-edited indentation that no serializer setting emits.
    """
    body = raw.rstrip()
    trailing = raw[len(body):]

    candidates = [(STYLE_INDENT, i) for i in INDENT_CANDIDATES]
    candidates += [(STYLE_COMPACT, None), (STYLE_COMPACT_SPACED, None),
                   (STYLE_EMPTY_NEWLINE, None)]
    for style, indent in candidates:
        if _render(parsed, style, indent) == body:
            return {"style": style, "indent": indent, "trailing": trailing,
                    "format_exact": True}
    return {"style": STYLE_INDENT, "indent": DEFAULT_INDENT, "trailing": trailing,
            "format_exact": False}


def read_json_file(path):
    """Return (parsed, format metadata)."""
    with open(path, encoding="utf-8") as handle:
        raw = handle.read()
    parsed = json.loads(raw)
    return parsed, detect_format(raw, parsed)


def serialize(payload, meta):
    text = _render(payload, meta.get("style", STYLE_INDENT),
                   meta.get("indent", DEFAULT_INDENT))
    return text + meta.get("trailing", "")


def content_hash(payload):
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------------------- files -> db

UNPOSITIONED = 1 << 30


def _position_of(doc):
    """Recorded index within the source file; appended last when absent."""
    value = doc.get("file_position")
    return value if isinstance(value, int) else UNPOSITIONED


def _strip_injected(doc):
    """The original entry, with this pipeline's additions removed and the
    surviving keys left in their original order."""
    return {k: v for k, v in doc.items() if k not in mf.INJECTED_KEYS}


def _content_doc(entry, locale, acronym, kind, position):
    doc = dict(entry)  # injected keys append, so original order is preserved
    doc["locale"] = locale
    doc["source_acronym"] = acronym
    doc["file_position"] = position
    lineage, edition, role = mf.lineage_for(acronym)
    doc["lineage"] = lineage
    doc["edition"] = edition
    doc["role"] = role
    doc["_id"] = "%s:%s:%s" % (locale, acronym, entry["index"])
    return doc


def _lore_doc(entry, locale, lore_source, position):
    doc = dict(entry)
    doc["locale"] = locale
    doc["lore_source"] = lore_source
    doc["file_position"] = position
    doc["_id"] = "%s:%s:%s" % (locale, lore_source, entry["index"])
    return doc


def _image_doc(entry, catalog, position):
    doc = dict(entry)
    doc["catalog"] = catalog
    doc["file_position"] = position
    doc["_id"] = "%s:%s" % (catalog, entry["monster_index"])
    return doc


def _source_doc(entry, locale, catalog, position):
    acronym = entry["source"]["acronym"]
    doc = {}
    for key, value in entry.items():
        doc[mf.SOURCE_FIELD_RENAMES.get(key, key)] = value
    doc["locale"] = locale
    doc["catalog"] = catalog
    doc["file_position"] = position
    doc["acronym"] = acronym
    doc["_id"] = "%s:%s:%s" % (locale, catalog, acronym)
    return doc


def files_to_documents():
    """Read the whole content tree.

    Returns (collections, file_meta, duplicates) where collections maps a
    collection name to a list of documents, file_meta records per-file
    formatting needed to rebuild the files, and duplicates lists any
    (file, index) that appeared twice inside a single file.
    """
    collections = {"monsters": [], "spells": [], "conditions": [], "sources": [],
                   "monster_lore": [], "monster_images": []}
    file_meta = []
    duplicates = []

    def load_entries(path):
        entries, fmt = read_json_file(path)
        meta = {"_id": mf.rel(path)}
        meta.update(fmt)
        file_meta.append(meta)
        return entries

    for locale in mf.LOCALES:
        for kind in ("monsters", "spells"):
            for acronym, path in mf.content_files(locale, kind):
                seen = set()
                for position, entry in enumerate(load_entries(path)):
                    if entry["index"] in seen:
                        duplicates.append((mf.rel(path), entry["index"]))
                    seen.add(entry["index"])
                    collections[kind].append(
                        _content_doc(entry, locale, acronym, kind, position))

        conditions_path = mf.conditions_file(locale)
        if os.path.exists(conditions_path):
            for position, entry in enumerate(load_entries(conditions_path)):
                doc = dict(entry)
                doc["locale"] = locale
                doc["file_position"] = position
                doc["_id"] = "%s:%s" % (locale, entry["index"])
                collections["conditions"].append(doc)

        for catalog, path in mf.source_config_files(locale):
            for position, entry in enumerate(load_entries(path)):
                collections["sources"].append(
                    _source_doc(entry, locale, catalog, position))

        for lore_source, path in mf.lore_files(locale):
            seen = set()
            for position, entry in enumerate(load_entries(path)):
                if entry["index"] in seen:
                    duplicates.append((mf.rel(path), entry["index"]))
                seen.add(entry["index"])
                collections["monster_lore"].append(
                    _lore_doc(entry, locale, lore_source, position))

    for catalog, path in mf.image_files():
        seen = set()
        for position, entry in enumerate(load_entries(path)):
            if entry["monster_index"] in seen:
                duplicates.append((mf.rel(path), entry["monster_index"]))
            seen.add(entry["monster_index"])
            collections["monster_images"].append(
                _image_doc(entry, catalog, position))

    _attach_translation_revisions(collections)
    return collections, file_meta, duplicates


def _attach_translation_revisions(collections):
    """Stamp non-base-locale content with the hash of the base-locale entry it
    corresponds to.

    Missing translations are already findable with a set difference. Stale ones
    -- English edited after the translation was written -- are invisible without
    this, and that is the failure mode that ships wrong content. On a first
    import every existing translation is stamped as current; that is a baseline
    to measure future drift against, not a claim that it is accurate today.
    """
    scoped = {"monsters": "source_acronym", "spells": "source_acronym",
              "monster_lore": "lore_source"}
    for kind, scope_field in scoped.items():
        base = {}
        for doc in collections[kind]:
            if doc["locale"] == mf.BASE_LOCALE:
                key = (doc[scope_field], doc["index"])
                base[key] = content_hash(_strip_injected(doc))
        for doc in collections[kind]:
            if doc["locale"] == mf.BASE_LOCALE:
                continue
            key = (doc[scope_field], doc["index"])
            doc["translated_from_rev"] = base.get(key)


# ------------------------------------------------------------------- db -> files

def _unsource_doc(doc):
    inverse = {v: k for k, v in mf.SOURCE_FIELD_RENAMES.items()}
    return {inverse.get(k, k): v for k, v in doc.items() if k not in mf.INJECTED_KEYS}


def documents_to_files(collections, file_meta):
    """Rebuild the content tree. Returns {repo-relative path: file text}."""
    fmt = {m["_id"]: m for m in file_meta}
    grouped = {}

    # Documents are placed by their recorded position in the file, never by
    # the order the database happens to return them. Relying on that order
    # worked only because a fresh import inserted documents in file order; one
    # later insert reshuffles a whole file, which would show up as a publish
    # diff touching content nobody edited. Documents created through the API
    # have no recorded position and are appended, keeping a stable order.
    def add(path, entry, position):
        grouped.setdefault(mf.rel(path), []).append((position, entry))

    for locale in mf.LOCALES:
        for kind in ("monsters", "spells"):
            by_key = {}
            for doc in collections.get(kind, []):
                if doc["locale"] == locale:
                    by_key.setdefault(doc["source_acronym"], []).append(doc)
            for acronym, path in mf.content_files(locale, kind):
                for doc in by_key.get(acronym, []):
                    add(path, _strip_injected(doc), _position_of(doc))

        conditions_path = mf.conditions_file(locale)
        if os.path.exists(conditions_path):
            for doc in collections.get("conditions", []):
                if doc["locale"] == locale:
                    add(conditions_path, _strip_injected(doc), _position_of(doc))

        for catalog, path in mf.source_config_files(locale):
            for doc in collections.get("sources", []):
                if doc["locale"] == locale and doc["catalog"] == catalog:
                    add(path, _unsource_doc(doc), _position_of(doc))

        by_book = {}
        for doc in collections.get("monster_lore", []):
            if doc["locale"] == locale:
                by_book.setdefault(doc["lore_source"], []).append(doc)
        for lore_source, path in mf.lore_files(locale):
            for doc in by_book.get(lore_source, []):
                add(path, _strip_injected(doc), _position_of(doc))
            grouped.setdefault(mf.rel(path), [])  # empty books still emit "[]"

    for catalog, path in mf.image_files():
        for doc in collections.get("monster_images", []):
            if doc["catalog"] == catalog:
                add(path, _strip_injected(doc), _position_of(doc))

    out = {}
    for path, pairs in grouped.items():
        ordered = [entry for _, entry in sorted(pairs, key=lambda pair: pair[0])]
        out[path] = serialize(ordered, fmt.get(path, {}))
    return out
