# MongoDB import

Loads the JSON content tree into MongoDB so a backend API and a web editor can
work against it. The app keeps consuming the JSON files, so **the files remain
the delivery mechanism** — the database is the editing source of truth, and
`export.py` regenerates the tree.

Everything here is built around one property: **the round trip is byte-exact.**
`export.py` reproduces all 57 files exactly as they are on disk. Without that,
publishing an edit would also reformat unrelated content.

## Setup

```bash
python3 -m pip install --user pymongo
cp .env.example .env
docker compose up -d mongo
python3 scripts/mongo/import.py
```

## Commands

| Command | Purpose |
|---|---|
| `python3 scripts/mongo/verify.py` | Round trip + validator fit + integrity report. **No database needed.** |
| `python3 scripts/mongo/import.py` | Load everything. Idempotent. |
| `python3 scripts/mongo/import.py --dry-run` | Read and check, write nothing. No database needed. |
| `python3 scripts/mongo/import.py --drop` | Rebuild from scratch. |
| `python3 scripts/mongo/import.py --strict` | Also exit non-zero on content integrity errors. |
| `python3 scripts/mongo/export.py --check` | Confirm the database still reproduces `json/` exactly. |
| `python3 scripts/mongo/export.py --in-place` | Write the database back over `json/` — the future `/publish`. |

## Collections

| Collection | Docs | `_id` |
|---|---|---|
| `monsters` | 4,207 | `<locale>:<source_acronym>:<index>` |
| `spells` | 2,196 | `<locale>:<source_acronym>:<index>` |
| `conditions` | 45 | `<locale>:<index>` |
| `sources` | 41 | `<locale>:<catalog>:<acronym>` |
| `_file_meta` | 57 | repo-relative path |

`index` alone is **not** unique: 113 monster indexes appear in more than one
source (`bugbear-chief` is in `MM`, `MM-LEGACY` and `SRD2024`). The composite
key is the reason the import can be idempotent.

`_file_meta` records per-file indent width and trailing newline. The tree is not
formatted consistently — the 2024-era sources use `indent=2`, everything older
uses `indent=4` — so this is measured on import rather than assumed. **Export
cannot reproduce the files without it.**

### Derived fields

Added by the import, stripped on export:

- `locale`, `source_acronym` — flattened from the file's position in the tree.
- `lineage` / `edition` / `role` — `MM`, `MM2024` and `MM-LEGACY` are three
  sources in one family. The `*-LEGACY` sources are *deltas*: `MM-LEGACY` holds
  exactly the 7 entries dropped from the 2024 edition, not a 2014 catalog.
  `role` is `full` or `legacy-remainder`.
- `translated_from_rev` — hash of the `en-us` entry a translation was made
  from. Missing translations are a set difference; *stale* ones are invisible
  without this, and that is what ships wrong content.

The virtual `SRD` source covers `json/<locale>/monsters.json` and
`spells.json`, which have no source directory but are referenced as `SRD` by
the configs.

## What is deliberately not normalised

The corpus is inconsistent in two ways that are **preserved, not fixed**:

- `desc` vs `description` — `special_abilities` uses `desc` 1,677 times and
  `description` 550 times; `reactions` 67 vs 57. The app falls back between
  them. Normalising requires checking the app's parser first.
- `damage_dices` vs `damage_dices_v2` — 31 actions carry both, a half-finished
  migration.

The validators accept either. Verified: all 4,207 monsters pass.

## Source configs

Imported from `content-sources.json` (catalog `full`) and
`content-sources-basic.json` (catalog `basic`). The older
`default-sources.json` / `alternative-sources.json` /
`alternative-sources-basic.json` trio is **superseded** and not imported —
`content-sources.json` is their union plus the 2024 entries. Note `CLAUDE.md`
still documents the old pair.

`totalMonsters` / `totalSpells` are imported as `declared_total_monsters` /
`declared_total_spells`, so nothing in the database looks authoritative when it
is not. The real count is an aggregation over `monsters`; `import.py` reports
where the two disagree.

## Integrity report

Every run ends with findings about the content tree. These are **pre-existing
conditions, not import failures** — nothing is repaired automatically. Current
baseline: 1 error, 9 warnings.

The error is `json/pt-br/sources/psb3/monsters.json` carrying `source.acronym:
"BEJ3"` on one entry — a translation leaked into an identifier field.

`import.py` exits non-zero only when the **import** fails (duplicate keys inside
a file, a validator that could not be applied). Integrity findings describe the
content tree, not the run, so they do not fail it — otherwise every run would
report failure until unrelated content is edited. Pass `--strict` in a pipeline
that should block on them.

## Not yet imported

Lore (~6,000 entries; lore sources are a separate taxonomy of 38 adventure
books, and lore covers 703 monster indexes with no stat block), images
(`json/monster-images.json`, 1,023 entries, locale-independent), and the legacy
root files `json/monsters.json` / `json/spells.json` (last touched 2023 and
2022, strict subsets of the locale files).
