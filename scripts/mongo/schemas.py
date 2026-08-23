"""MongoDB $jsonSchema validators.

The enums are taken from the corpus itself rather than from CLAUDE.md, because
the two disagree in places. Anything the corpus actually contains must pass --
a validator that rejects existing content would block the editor from saving a
document it had just loaded.
"""

MONSTER_TYPES = [
    "ABERRATION", "BEAST", "CELESTIAL", "CONSTRUCT", "DRAGON", "ELEMENTAL",
    "FEY", "FIEND", "GIANT", "HUMANOID", "MONSTROSITY", "OOZE", "PLANT",
    "UNDEAD",
]
SIZES = ["Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"]
SPEED_TYPES = ["WALK", "BURROW", "CLIMB", "FLY", "SWIM"]
ABILITY_TYPES = [
    "STRENGTH", "DEXTERITY", "CONSTITUTION", "INTELLIGENCE", "WISDOM",
    "CHARISMA",
]
# METER is documented and supported by the app but unused: every speed in all
# three locales is FEET. Kept in the enum so a future metric locale is not
# blocked by the validator.
MEASUREMENT_UNITS = ["FEET", "METER"]
DAMAGE_TYPES = [
    "ACID", "BLUDGEONING", "COLD", "FIRE", "FORCE", "LIGHTNING", "NECROTIC",
    "PIERCING", "POISON", "PSYCHIC", "RADIANT", "SLASHING", "THUNDER",
]
SPELLCASTING_TYPES = ["INNATE", "SPELLCASTER"]
SPELL_SCHOOLS = [
    "ABJURATION", "CONJURATION", "DIVINATION", "ENCHANTMENT", "EVOCATION",
    "ILLUSION", "NECROMANCY", "TRANSMUTATION",
]
LOCALES = ["en-us", "pt-br", "es"]

_STR_OR_NULL = {"bsonType": ["string", "null"]}
_NUM = {"bsonType": ["double", "int", "long"]}


def _damage_dice_array():
    return {
        "bsonType": "array",
        "items": {
            "bsonType": "object",
            "properties": {
                "dice": {"bsonType": "string"},
                "damage": {
                    "bsonType": "object",
                    "properties": {"type": {"enum": DAMAGE_TYPES}},
                },
            },
        },
    }


def _ability_block():
    """Named abilities, actions, reactions and so on.

    Deliberately permissive about the description key: the corpus splits between
    `desc` and `description` (special_abilities uses desc 1677 times and
    description 550 times) and the app falls back between them. Requiring either
    one would reject roughly a quarter of the existing content. Likewise
    damage_dices and damage_dices_v2 coexist on 31 actions -- a half-finished
    migration -- so both are allowed.
    """
    return {
        "bsonType": "array",
        "items": {
            "bsonType": "object",
            "required": ["name"],
            "properties": {
                "name": {"bsonType": "string"},
                "desc": _STR_OR_NULL,
                "description": _STR_OR_NULL,
                "attack_bonus": {"bsonType": ["int", "long", "null"]},
                "damage_dices": _damage_dice_array(),
                "damage_dices_v2": _damage_dice_array(),
            },
        },
    }


MONSTER_SCHEMA = {
    "bsonType": "object",
    "required": [
        "_id", "index", "locale", "source_acronym", "name", "type", "size",
        "ability_scores", "speed",
    ],
    "properties": {
        "_id": {"bsonType": "string"},
        "index": {"bsonType": "string"},
        "locale": {"enum": LOCALES},
        "source_acronym": {"bsonType": "string"},
        "name": {"bsonType": "string"},
        "type": {"enum": MONSTER_TYPES},
        "size": {"enum": SIZES},
        "subtype": _STR_OR_NULL,
        "group": _STR_OR_NULL,
        "challenge_rating": _NUM,
        "armor_class": {"bsonType": ["int", "long", "null"]},
        "hit_points": {"bsonType": ["int", "long", "null"]},
        "ability_scores": {
            "bsonType": "array",
            "minItems": 6,
            "maxItems": 6,
            "items": {
                "bsonType": "object",
                "required": ["type", "value", "modifier"],
                "properties": {
                    "type": {"enum": ABILITY_TYPES},
                    "value": {"bsonType": ["int", "long"]},
                    "modifier": {"bsonType": ["int", "long"]},
                },
            },
        },
        "speed": {
            "bsonType": "object",
            "required": ["value"],
            "properties": {
                "hover": {"bsonType": ["bool", "null"]},
                "value": {
                    "bsonType": "array",
                    "minItems": 1,
                    "items": {
                        "bsonType": "object",
                        "required": ["type", "measurement_unit", "value"],
                        "properties": {
                            "type": {"enum": SPEED_TYPES},
                            "measurement_unit": {"enum": MEASUREMENT_UNITS},
                            "value": _NUM,
                        },
                    },
                },
            },
        },
        "special_abilities": _ability_block(),
        "actions": _ability_block(),
        "legendary_actions": _ability_block(),
        "bonus_actions": _ability_block(),
        "reactions": _ability_block(),
        "spellcasting": {
            "bsonType": "array",
            "items": {
                "bsonType": "object",
                "properties": {"type": {"enum": SPELLCASTING_TYPES}},
            },
        },
        "source": {
            "bsonType": "object",
            "required": ["name", "acronym"],
            "properties": {
                "name": {"bsonType": "string"},
                "acronym": {"bsonType": "string"},
            },
        },
    },
}

SPELL_SCHEMA = {
    "bsonType": "object",
    "required": ["_id", "index", "locale", "source_acronym", "name", "level", "school"],
    "properties": {
        "_id": {"bsonType": "string"},
        "index": {"bsonType": "string"},
        "locale": {"enum": LOCALES},
        "source_acronym": {"bsonType": "string"},
        "name": {"bsonType": "string"},
        "level": {"bsonType": ["int", "long"], "minimum": 0, "maximum": 9},
        "school": {"enum": SPELL_SCHOOLS},
        "ritual": {"bsonType": "bool"},
        "concentration": {"bsonType": "bool"},
        "saving_throw_type": _STR_OR_NULL,
        "damage_type": _STR_OR_NULL,
        "higher_level": _STR_OR_NULL,
        "description": {"bsonType": "string"},
    },
}

CONDITION_SCHEMA = {
    "bsonType": "object",
    "required": ["_id", "index", "locale", "name", "description"],
    "properties": {
        "_id": {"bsonType": "string"},
        "index": {"bsonType": "string"},
        "locale": {"enum": LOCALES},
        "type": {"bsonType": "string"},
        "name": {"bsonType": "string"},
        "description": {"bsonType": "string"},
    },
}

SOURCE_SCHEMA = {
    "bsonType": "object",
    "required": ["_id", "locale", "catalog", "acronym", "source", "isEnabled"],
    "properties": {
        "_id": {"bsonType": "string"},
        "locale": {"enum": LOCALES},
        "catalog": {"enum": ["full", "basic"]},
        "acronym": {"bsonType": "string"},
        "source": {
            "bsonType": "object",
            "required": ["name", "acronym"],
            "properties": {
                "name": {"bsonType": "string"},
                "acronym": {"bsonType": "string"},
                "originalAcronym": {"bsonType": "string"},
            },
        },
        "declared_total_monsters": {"bsonType": ["int", "long"]},
        "declared_total_spells": {"bsonType": ["int", "long"]},
        "isEnabled": {"bsonType": "bool"},
        "isLoreEnabled": {"bsonType": "bool"},
        "isDefault": {"bsonType": "bool"},
        "contentVersion": {"bsonType": ["int", "long"]},
        "coverImageUrl": {"bsonType": "string"},
        "summary": {"bsonType": "string"},
    },
}

LORE_SCHEMA = {
    "bsonType": "object",
    "required": ["_id", "index", "locale", "lore_source", "entries"],
    "properties": {
        "_id": {"bsonType": "string"},
        "index": {"bsonType": "string"},
        "locale": {"enum": LOCALES},
        "lore_source": {"bsonType": "string"},
        "entries": {
            "bsonType": "array",
            "minItems": 1,
            "items": {
                "bsonType": "object",
                # description is the body of a lore paragraph and is always
                # present; title is optional, marking a sub-heading.
                "required": ["description"],
                "properties": {
                    "description": {"bsonType": "string"},
                    "title": {"bsonType": "string"},
                },
            },
        },
        "translated_from_rev": {"bsonType": ["string", "null"]},
    },
}

# Images are global: no locale field, and keyed by monster_index alone rather
# than by the (locale, source, index) triple monsters use. One image serves the
# same monster across every locale and every source that reprints it.
IMAGE_SCHEMA = {
    "bsonType": "object",
    "required": ["_id", "monster_index", "catalog", "background_color", "image_url"],
    "properties": {
        "_id": {"bsonType": "string"},
        "monster_index": {"bsonType": "string"},
        "catalog": {"enum": ["default", "srd"]},
        "background_color": {
            "bsonType": "object",
            "required": ["light", "dark"],
            "properties": {
                "light": {"bsonType": "string"},
                "dark": {"bsonType": "string"},
            },
        },
        "image_url": {"bsonType": "string"},
        "is_horizontal_image": {"bsonType": "bool"},
        # Absent on 26 of the 322 SRD entries, so it cannot be required.
        "content_scale": {"enum": ["Crop", "Fit"]},
    },
}

VALIDATORS = {
    "monsters": MONSTER_SCHEMA,
    "spells": SPELL_SCHEMA,
    "conditions": CONDITION_SCHEMA,
    "sources": SOURCE_SCHEMA,
    "monster_lore": LORE_SCHEMA,
    "monster_images": IMAGE_SCHEMA,
}

INDEXES = {
    "monsters": [
        (["locale", "source_acronym", "index"], {"unique": True, "name": "uq_locale_source_index"}),
        (["locale", "source_acronym"], {"name": "ix_locale_source"}),
        (["locale", "type"], {"name": "ix_locale_type"}),
        (["locale", "challenge_rating"], {"name": "ix_locale_cr"}),
        (["locale", "index"], {"name": "ix_locale_index"}),
        (["lineage", "edition"], {"name": "ix_lineage_edition"}),
    ],
    "spells": [
        (["locale", "source_acronym", "index"], {"unique": True, "name": "uq_locale_source_index"}),
        (["locale", "source_acronym"], {"name": "ix_locale_source"}),
        (["locale", "level"], {"name": "ix_locale_level"}),
        (["locale", "school"], {"name": "ix_locale_school"}),
    ],
    "conditions": [
        (["locale", "index"], {"unique": True, "name": "uq_locale_index"}),
    ],
    "sources": [
        (["locale", "catalog", "acronym"], {"unique": True, "name": "uq_locale_catalog_acronym"}),
    ],
    "monster_lore": [
        (["locale", "lore_source", "index"], {"unique": True, "name": "uq_locale_book_index"}),
        # "all lore for this monster" spans books: 333 indexes appear in more
        # than one, so this is the query the editor actually needs.
        (["locale", "index"], {"name": "ix_locale_index"}),
        (["locale", "lore_source"], {"name": "ix_locale_book"}),
    ],
    "monster_images": [
        (["catalog", "monster_index"], {"unique": True, "name": "uq_catalog_monster"}),
        (["monster_index"], {"name": "ix_monster_index"}),
    ],
}

# Text indexes are declared separately: a collection may only have one, and it
# needs a language override because the default "language" field lookup would
# collide with nothing here but the locale mix makes stemming unhelpful anyway.
TEXT_INDEXES = {
    "monsters": ("name", "tx_name"),
    "spells": ("name", "tx_name"),
}
