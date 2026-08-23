"""Integrity findings.

Everything reported here is a pre-existing condition in the content tree, not
an import bug. Nothing is repaired automatically: the JSON files remain the
app's delivery mechanism, so a migration that silently "cleans up" data would
produce a publish diff nobody asked for. The report exists to make these
visible for the first time; fixing them is content work to do afterwards.
"""

import collections
import os

from . import manifest as mf


class Finding(object):
    def __init__(self, kind, severity, message):
        self.kind = kind
        self.severity = severity  # "error" | "warning" | "info"
        self.message = message

    def __repr__(self):
        return "[%s] %s: %s" % (self.severity.upper(), self.kind, self.message)


def _actual_counts(docs):
    counts = collections.Counter()
    for doc in docs:
        counts[(doc["locale"], doc["source_acronym"])] += 1
    return counts


def duplicate_keys(collections_map):
    findings = []
    for name in ("monsters", "spells"):
        seen = collections.Counter(
            (d["locale"], d["source_acronym"], d["index"]) for d in collections_map[name]
        )
        for key, count in sorted(seen.items()):
            if count > 1:
                findings.append(Finding(
                    "duplicate-key", "error",
                    "%s: %s appears %d times" % (name, ":".join(key), count),
                ))
    return findings


def missing_translations(collections_map):
    findings = []
    for name in ("monsters", "spells", "conditions"):
        docs = collections_map[name]
        if name == "conditions":
            key = lambda d: (d["index"],)
        else:
            key = lambda d: (d["source_acronym"], d["index"])
        base = {key(d) for d in docs if d["locale"] == mf.BASE_LOCALE}
        for locale in mf.LOCALES:
            if locale == mf.BASE_LOCALE:
                continue
            here = {key(d) for d in docs if d["locale"] == locale}
            missing = base - here
            extra = here - base
            if missing:
                by_source = collections.Counter(k[0] for k in missing)
                detail = ", ".join("%s: %d" % (s, n) for s, n in sorted(by_source.items()))
                findings.append(Finding(
                    "missing-translation", "warning",
                    "%s/%s: %d entries exist in %s but not here (%s)"
                    % (name, locale, len(missing), mf.BASE_LOCALE, detail),
                ))
            if extra:
                findings.append(Finding(
                    "orphan-translation", "warning",
                    "%s/%s: %d entries have no %s counterpart"
                    % (name, locale, len(extra), mf.BASE_LOCALE),
                ))
    return findings


def declared_vs_actual(collections_map):
    """Compare the totals written in the source configs against reality.

    Only the "full" catalog is checked. The "basic" catalog deliberately
    renames acronyms in en-us (MM2024 -> MM, SRD-LEGACY -> SRD) while keeping
    the 2024 payload counts, so its totals describe different content than its
    acronyms suggest and a naive comparison would be noise.
    """
    findings = []
    monsters = _actual_counts(collections_map["monsters"])
    spells = _actual_counts(collections_map["spells"])
    for src in collections_map["sources"]:
        if src["catalog"] != "full":
            continue
        locale, acronym = src["locale"], src["acronym"]
        for label, declared_key, actual in (
            ("monsters", "declared_total_monsters", monsters),
            ("spells", "declared_total_spells", spells),
        ):
            declared = src.get(declared_key)
            if declared is None:
                continue
            real = actual.get((locale, acronym), 0)
            if declared != real:
                findings.append(Finding(
                    "count-mismatch", "warning",
                    "%s/%s: config declares %d %s, tree has %d"
                    % (locale, acronym, declared, label, real),
                ))
    return findings


def acronym_consistency(collections_map):
    """The acronym inside each document must match the directory it came from."""
    findings = []
    seen = collections.defaultdict(collections.Counter)
    for name in ("monsters", "spells"):
        for doc in collections_map[name]:
            embedded = (doc.get("source") or {}).get("acronym")
            if embedded is not None:
                seen[(doc["locale"], doc["source_acronym"], name)][embedded] += 1
    for (locale, acronym, name), counts in sorted(seen.items()):
        wrong = {k: v for k, v in counts.items() if k != acronym}
        if wrong:
            detail = ", ".join("%s x%d" % (k, v) for k, v in sorted(wrong.items()))
            findings.append(Finding(
                "acronym-mismatch", "error",
                "%s/%s/%s: documents carry a different source.acronym (%s)"
                % (locale, acronym, name, detail),
            ))
    return findings


def config_coverage(collections_map):
    findings = []
    known = set(mf.DIR_TO_ACRONYM.values()) | {mf.VIRTUAL_SOURCE}
    configured = collections.defaultdict(set)
    for src in collections_map["sources"]:
        if src["catalog"] == "full":
            configured[src["locale"]].add(src["acronym"])

    on_disk = collections.defaultdict(set)
    for name in ("monsters", "spells"):
        for doc in collections_map[name]:
            on_disk[doc["locale"]].add(doc["source_acronym"])

    for locale in mf.LOCALES:
        undeclared = on_disk[locale] - configured[locale]
        if undeclared:
            findings.append(Finding(
                "source-not-configured", "warning",
                "%s: content exists for %s but no content-sources.json entry "
                "exposes it" % (locale, ", ".join(sorted(undeclared))),
            ))
        phantom = configured[locale] - on_disk[locale]
        if phantom:
            findings.append(Finding(
                "source-without-content", "info",
                "%s: config lists %s with no content in the tree"
                % (locale, ", ".join(sorted(phantom))),
            ))
        unknown = configured[locale] - known
        if unknown:
            findings.append(Finding(
                "unknown-acronym", "warning",
                "%s: config lists %s, which is not a known source directory"
                % (locale, ", ".join(sorted(unknown))),
            ))
    return findings


def stale_translations(collections_map):
    """Translations whose base-locale entry has changed since import.

    Always empty on a first import by construction -- the baseline is stamped
    from the current en-us content. It becomes meaningful once editing starts.
    """
    findings = []
    for name in ("monsters", "spells"):
        stale = [
            d for d in collections_map[name]
            if d["locale"] != mf.BASE_LOCALE and d.get("translated_from_rev") is None
        ]
        if stale:
            by_locale = collections.Counter(d["locale"] for d in stale)
            for locale, count in sorted(by_locale.items()):
                findings.append(Finding(
                    "untracked-translation", "info",
                    "%s/%s: %d entries have no %s counterpart to track drift "
                    "against" % (name, locale, count, mf.BASE_LOCALE),
                ))
    return findings


def format_fidelity(file_meta):
    findings = []
    for meta in file_meta:
        if not meta.get("format_exact", True):
            findings.append(Finding(
                "format-not-reproducible", "error",
                "%s: formatting could not be reproduced; exporting it would "
                "reformat the file" % meta["_id"],
            ))
    return findings


ALL_CHECKS = [
    duplicate_keys,
    acronym_consistency,
    missing_translations,
    declared_vs_actual,
    config_coverage,
    stale_translations,
]


def run(collections_map, file_meta=None):
    findings = []
    for check in ALL_CHECKS:
        findings.extend(check(collections_map))
    if file_meta is not None:
        findings.extend(format_fidelity(file_meta))
    return findings


def render(findings):
    if not findings:
        return "Integrity report: no findings.\n"
    order = {"error": 0, "warning": 1, "info": 2}
    findings = sorted(findings, key=lambda f: (order[f.severity], f.kind, f.message))
    counts = collections.Counter(f.severity for f in findings)
    lines = ["", "Integrity report: %s" % ", ".join(
        "%d %s%s" % (counts[s], s, "" if counts[s] == 1 else "s")
        for s in ("error", "warning", "info") if counts[s]
    ), ""]
    current = None
    for finding in findings:
        if finding.kind != current:
            current = finding.kind
            lines.append("  %s" % current)
        lines.append("    %-8s %s" % (finding.severity, finding.message))
    lines.append("")
    lines.append("  These are pre-existing conditions in the content tree, not")
    lines.append("  import failures. Nothing was modified.")
    lines.append("")
    return "\n".join(lines)


def error_count(findings):
    return sum(1 for f in findings if f.severity == "error")
