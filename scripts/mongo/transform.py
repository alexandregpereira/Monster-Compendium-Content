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

# Indent widths actually found in the tree: the 2024-era source files were
# written with 2, everything older with 4. Ordered most-common first.
INDENT_CANDIDATES = [4, 2, 3, 8, 1]
DEFAULT_INDENT = 4


# --------------------------------------------------------------------------- io

def detect_format(raw, parsed):
    """Recover the exact formatting of a file we are about to re-emit later.

    Formatting is a per-file property here, not a repo-wide convention, so it
    is measured rather than assumed. Returns (indent, trailing_newline, exact);
    exact is False when no candidate reproduces the file, which the caller
    reports rather than silently reformatting.
    """
    trailing = raw.endswith("\n")
    body = raw[:-1] if trailing else raw
    for indent in INDENT_CANDIDATES:
        if json.dumps(parsed, indent=indent, ensure_ascii=False) == body:
            return indent, trailing, True
    return DEFAULT_INDENT, trailing, False


def read_json_file(path):
    """Return (parsed, format metadata). Files in this repo disagree about both
    indent width and the trailing newline, so both are recorded."""
    with open(path, encoding="utf-8") as handle:
        raw = handle.read()
    parsed = json.loads(raw)
    indent, trailing, exact = detect_format(raw, parsed)
    return parsed, {"indent": indent, "trailing_newline": trailing, "format_exact": exact}


def serialize(payload, indent, trailing_newline):
    text = json.dumps(payload, indent=indent, ensure_ascii=False)
    return text + "\n" if trailing_newline else text


def content_hash(payload):
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------------------- files -> db

def _strip_injected(doc):
    """The original entry, with this pipeline's additions removed and the
    surviving keys left in their original order."""
    return {k: v for k, v in doc.items() if k not in mf.INJECTED_KEYS}


def _content_doc(entry, locale, acronym, kind):
    doc = dict(entry)  # injected keys append, so original order is preserved
    doc["locale"] = locale
    doc["source_acronym"] = acronym
    lineage, edition, role = mf.lineage_for(acronym)
    doc["lineage"] = lineage
    doc["edition"] = edition
    doc["role"] = role
    doc["_id"] = "%s:%s:%s" % (locale, acronym, entry["index"])
    return doc


def _source_doc(entry, locale, catalog):
    acronym = entry["source"]["acronym"]
    doc = {}
    for key, value in entry.items():
        doc[mf.SOURCE_FIELD_RENAMES.get(key, key)] = value
    doc["locale"] = locale
    doc["catalog"] = catalog
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
    collections = {"monsters": [], "spells": [], "conditions": [], "sources": []}
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
                for entry in load_entries(path):
                    if entry["index"] in seen:
                        duplicates.append((mf.rel(path), entry["index"]))
                    seen.add(entry["index"])
                    collections[kind].append(_content_doc(entry, locale, acronym, kind))

        conditions_path = mf.conditions_file(locale)
        if os.path.exists(conditions_path):
            for entry in load_entries(conditions_path):
                doc = dict(entry)
                doc["locale"] = locale
                doc["_id"] = "%s:%s" % (locale, entry["index"])
                collections["conditions"].append(doc)

        for catalog, path in mf.source_config_files(locale):
            for entry in load_entries(path):
                collections["sources"].append(_source_doc(entry, locale, catalog))

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
    for kind in ("monsters", "spells"):
        base = {}
        for doc in collections[kind]:
            if doc["locale"] == mf.BASE_LOCALE:
                key = (doc["source_acronym"], doc["index"])
                base[key] = content_hash(_strip_injected(doc))
        for doc in collections[kind]:
            if doc["locale"] == mf.BASE_LOCALE:
                continue
            key = (doc["source_acronym"], doc["index"])
            doc["translated_from_rev"] = base.get(key)


# ------------------------------------------------------------------- db -> files

def _unsource_doc(doc):
    inverse = {v: k for k, v in mf.SOURCE_FIELD_RENAMES.items()}
    return {inverse.get(k, k): v for k, v in doc.items() if k not in mf.INJECTED_KEYS}


def documents_to_files(collections, file_meta):
    """Rebuild the content tree. Returns {repo-relative path: file text}."""
    fmt = {m["_id"]: m for m in file_meta}
    grouped = {}

    def add(path, entry):
        grouped.setdefault(mf.rel(path), []).append(entry)

    for locale in mf.LOCALES:
        for kind in ("monsters", "spells"):
            by_key = {}
            for doc in collections.get(kind, []):
                if doc["locale"] == locale:
                    by_key.setdefault(doc["source_acronym"], []).append(doc)
            for acronym, path in mf.content_files(locale, kind):
                for doc in by_key.get(acronym, []):
                    add(path, _strip_injected(doc))

        conditions_path = mf.conditions_file(locale)
        if os.path.exists(conditions_path):
            for doc in collections.get("conditions", []):
                if doc["locale"] == locale:
                    add(conditions_path, _strip_injected(doc))

        for catalog, path in mf.source_config_files(locale):
            for doc in collections.get("sources", []):
                if doc["locale"] == locale and doc["catalog"] == catalog:
                    add(path, _unsource_doc(doc))

    out = {}
    for path, entries in grouped.items():
        meta = fmt.get(path, {})
        out[path] = serialize(
            entries,
            meta.get("indent", DEFAULT_INDENT),
            meta.get("trailing_newline", False),
        )
    return out
