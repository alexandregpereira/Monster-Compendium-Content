"""Static description of the content tree: locales, sources, and where files live.

Adding a locale or a source book should be a change to the tables here and
nothing else.
"""

import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
JSON_ROOT = os.path.join(REPO_ROOT, "json")

LOCALES = ["en-us", "pt-br", "es"]
BASE_LOCALE = "en-us"

# Directory name under json/<locale>/sources/ -> the acronym expected inside the
# files it contains. Directories are lowercase, acronyms are uppercase.
DIR_TO_ACRONYM = {
    "erlw": "ERLW",
    "ggr": "GGR",
    "mm": "MM",
    "mm-legacy": "MM-LEGACY",
    "mm2024": "MM2024",
    "mtf": "MTF",
    "phb2024": "PHB2024",
    "psb3": "PSB3",
    "srd-legacy": "SRD-LEGACY",
    "srd2024": "SRD2024",
    "vgm": "VGM",
    "vrgr": "VRGR",
}

# The locale-root monsters.json / spells.json have no source directory. Every
# config file refers to that content as the "SRD" source, so it is imported
# under a virtual acronym.
VIRTUAL_SOURCE = "SRD"

# Edition lineage. The *-LEGACY sources are deltas -- they hold exactly the
# entries dropped from the 2024 edition, not a full 2014 catalog -- so acronym
# alone does not tell you how two sources relate.
#   lineage: the book family
#   edition: which ruleset the stat blocks are written for
#   role:    "full" = a complete catalog, "legacy-remainder" = dropped entries
LINEAGE = {
    "SRD":         ("SRD", 2014, "full"),
    "SRD2024":     ("SRD", 2024, "full"),
    "SRD-LEGACY":  ("SRD", 2014, "legacy-remainder"),
    "MM":          ("MM", 2014, "full"),
    "MM2024":      ("MM", 2024, "full"),
    "MM-LEGACY":   ("MM", 2014, "legacy-remainder"),
    "PHB2024":     ("PHB", 2024, "full"),
    "MTF":         ("MTF", 2014, "full"),
    "GGR":         ("GGR", 2014, "full"),
    "VGM":         ("VGM", 2014, "full"),
    "VRGR":        ("VRGR", 2014, "full"),
    "ERLW":        ("ERLW", 2014, "full"),
    "PSB3":        ("PSB3", 2014, "full"),
}

# Source-config files. The alternative-sources*/default-sources trio they
# replaced is deliberately not imported -- content-sources.json is their union
# plus the 2024 entries, and the older files have not been touched since the
# 2024 content landed.
SOURCE_CONFIGS = [
    ("full", "content-sources.json"),
    ("basic", "content-sources-basic.json"),
]

# Keys this pipeline adds to every document. Stripped again on export, so the
# original key order of the untouched keys survives a round trip.
INJECTED_KEYS = [
    "_id",
    "locale",
    "source_acronym",
    "catalog",
    "acronym",
    "lineage",
    "edition",
    "role",
    "translated_from_rev",
]

# Reversible renames applied to source-config documents, so that a field named
# totalMonsters in the database can never be mistaken for the authoritative
# count (the real one is an aggregation over the monsters collection).
SOURCE_FIELD_RENAMES = {
    "totalMonsters": "declared_total_monsters",
    "totalSpells": "declared_total_spells",
}

FILE_META_COLLECTION = "_file_meta"


def rel(path):
    """Repo-relative path, used as the stable id for per-file metadata."""
    return os.path.relpath(path, REPO_ROOT)


def locale_dir(locale):
    return os.path.join(JSON_ROOT, locale)


def source_dir(locale, dirname):
    return os.path.join(JSON_ROOT, locale, "sources", dirname)


def lineage_for(acronym):
    return LINEAGE.get(acronym, (acronym, None, "full"))


def content_files(locale, kind):
    """Yield (acronym, absolute path) for a locale and kind ("monsters"/"spells").

    Missing files are skipped -- phb2024 is spells-only, and not every source
    dir exists in every locale.
    """
    root_file = os.path.join(locale_dir(locale), kind + ".json")
    if os.path.exists(root_file):
        yield VIRTUAL_SOURCE, root_file
    for dirname in sorted(DIR_TO_ACRONYM):
        path = os.path.join(source_dir(locale, dirname), kind + ".json")
        if os.path.exists(path):
            yield DIR_TO_ACRONYM[dirname], path


def conditions_file(locale):
    return os.path.join(locale_dir(locale), "conditions.json")


def source_config_files(locale):
    for catalog, filename in SOURCE_CONFIGS:
        path = os.path.join(locale_dir(locale), filename)
        if os.path.exists(path):
            yield catalog, path
