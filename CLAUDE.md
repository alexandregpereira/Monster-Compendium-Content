# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a **content-only repository** (no build system or tests) that provides JSON data consumed by the [Monster Compendium Android App](https://github.com/alexandregpereira/monster-compendium). All work here involves editing or validating JSON files.

Validate JSON manually with:
```bash
python3 -m json.tool json/en-us/monsters.json > /dev/null
```

## Directory Structure

```
json/
├── monsters.json           # Legacy root-level monsters (SRD-only, ~244 entries)
├── spells.json             # Legacy root-level spells
├── monster-images.json     # Image URLs + background colors per monster index
├── monster-lore-sources.json  # Index of all lore sources
├── remote-config.json      # App remote config (e.g. sessionTimeLimitInMillis)
├── en-us/
│   ├── monsters.json       # SRD monsters in English (~322 entries)
│   ├── spells.json         # SRD spells in English
│   ├── monster-lore.json   # Lore entries for non-source-specific monsters
│   ├── default-sources.json    # SRD source config (enabled by default)
│   ├── alternative-sources.json # Non-SRD sources config (MTF, VGM, GGR, etc.)
│   ├── sources/
│   │   └── <acronym>/
│   │       └── monsters.json   # Monster stat blocks per source (e.g. mtf, vgm, ggr)
│   └── lore/
│       └── <acronym>/
│           └── monster-lore.json  # Lore entries per source
└── pt-br/
    └── (mirrors en-us structure for Portuguese translations)
```

## Key Schemas

### Monster entry (`sources/<acronym>/monsters.json` or `monsters.json`)
- `index`: kebab-case unique identifier (e.g. `"aboleth"`, `"abyssal-wretch"`)
- `type`: one of `ABERRATION | BEAST | CELESTIAL | CONSTRUCT | DRAGON | ELEMENTAL | FEY | FIEND | GIANT | HUMANOID | MONSTROSITY | OOZE | PLANT | UNDEAD`
- `source.acronym`: uppercase acronym matching the source directory name (e.g. `"MTF"`)
- `ability_scores`: always 6 entries in order: STRENGTH, DEXTERITY, CONSTITUTION, INTELLIGENCE, WISDOM, CHARISMA
- `speed.value`: at least one entry; `type` is `BURROW | CLIMB | FLY | WALK | SWIM`
- `measurement_unit`: `FEET` or `METER`

### Source config (`default-sources.json` / `alternative-sources.json`)
- `isEnabled`: whether source appears active in the app by default
- `isLoreEnabled`: whether lore entries are shown for this source
- `totalMonsters`: must match the actual count in `sources/<acronym>/monsters.json`

### Lore entry (`monster-lore.json`)
- `index`: matches the monster's `index` field
- `entries`: array of `{ "description": String }` or `{ "title": String, "description": String }`

### Monster images (`monster-images.json`)
- `monster_index`: matches the monster's `index` field
- `background_color.light` / `background_color.dark`: hex color strings
- `image_url`: raw GitHub URL pointing to `images/` directory

## Important Conventions

- Monster `index` values are **lowercase kebab-case** (e.g. `"young-red-dragon"`)
- Source acronyms in directory names are **lowercase** (e.g. `sources/mtf/`) but **uppercase** in the `source.acronym` JSON field (e.g. `"MTF"`)
- Both `en-us` and `pt-br` directories mirror the same structure; when adding monsters, update both locales
- `totalMonsters` in source config files must be kept in sync with the actual array length in the corresponding `monsters.json`
- The `covers/` directory contains cover images referenced by `coverImageUrl` in `alternative-sources.json`
