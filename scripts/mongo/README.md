# MongoDB import

Loads the JSON content tree into MongoDB so a backend API and a web editor can
work against it. The app keeps consuming the JSON files, so **the files remain
the delivery mechanism** — the database is the editing source of truth, and
`export.py` regenerates the tree.

Everything here is built around one property: **the round trip is byte-exact.**
`export.py` reproduces 175 of the 176 managed files exactly as they are on
disk. Without that, publishing an edit would also reformat unrelated content.

The one exception is `json/en-us/lore/erlw/monster-lore.json`, which has
hand-edited indentation (two array elements at 8 spaces instead of 4) that no
serializer setting emits. It is recorded as `format_exact: false` and will be
reindented on the first publish — a 2-line whitespace-only diff. Both
`verify.py` and `export.py --check` report it as a known normalisation rather
than a failure.

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

| Collection | Docs | `_id` | Locale-scoped |
|---|---|---|---|
| `monsters` | 4,207 | `<locale>:<source_acronym>:<index>` | yes |
| `spells` | 2,196 | `<locale>:<source_acronym>:<index>` | yes |
| `conditions` | 45 | `<locale>:<index>` | yes |
| `sources` | 41 | `<locale>:<catalog>:<acronym>` | yes |
| `monster_lore` | 5,965 | `<locale>:<lore_source>:<index>` | yes |
| `monster_images` | 1,345 | `<catalog>:<monster_index>` | **no** |
| `_file_meta` | 176 | repo-relative path | — |

`index` alone is **not** unique: 113 monster indexes appear in more than one
source (`bugbear-chief` is in `MM`, `MM-LEGACY` and `SRD2024`). The composite
key is the reason the import can be idempotent.

Lore keys need the book for the same reason monsters need the source: **333
lore indexes appear in more than one book** (`azer` has lore in `mtf`,
`mm2024` and `mm`).

`_file_meta` records per-file serialization style, indent width and the exact
trailing whitespace run. The tree is not formatted consistently — the 2024-era
sources use `indent=2`, everything older `indent=4`, the legacy aggregated lore
files are minified, one file ends with a newline plus sixteen spaces, and six
empty lore books are written `[\n]` rather than `[]`. All of it is measured on
import rather than assumed. **Export cannot reproduce the files without it.**

## Lore and images

**Lore books are a separate taxonomy from content sources.** 40 directories,
mostly adventure titles, of which only 8 are also content sources. 698 lore
indexes describe monsters that have no stat block anywhere in the tree, so
lore cannot be modelled as a property of a monster.

**The two image catalogs are not a set and its subset.** `monster-images.json`
(`default`, 1,023) and `monster-images-srd.json` (`srd`, 322) share 322
`monster_index` values and **disagree on the `image_url` for 298 of them** —
`default` points at `srd-v2/`, `srd` at `images/`. They are separate art sets;
merging them would silently drop one.

Images carry **no `locale`** and are keyed by `monster_index` alone: one image
serves a monster across every locale and every source that reprints it.

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

## Deliberately unmanaged

Export never writes these, so app versions pinned to them keep reading exactly
what is there today:

- `json/monsters.json`, `json/spells.json` — superseded by the locale-scoped
  files; last touched 2023 and 2022.
- `json/<locale>/monster-lore.json` — a stale January-2023 aggregate. A list of
  38 lists whose group order matches no config, holding 1,476 of the
  directories' 1,988 entries, missing `erlw`/`mm2024`/`psb3` entirely,
  byte-identical between `en-us` and `pt-br` (never translated), and absent for
  `es`.
- `json/monster-lore-sources.json` — legacy, no longer read by the app. It was
  the only place mapping lore acronyms to book names, so **32 of the 40 lore
  books currently have no display name anywhere** in the repo. Authoring those
  is content work, not migration work.
- `json/alternative-sources.json`, `default-sources.json`,
  `alternative-sources-basic.json` — superseded by `content-sources.json`.
