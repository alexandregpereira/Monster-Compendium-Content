# Monster Compendium Content

This repository contains data and image content to be used on the [Monster Compendium Android App](https://github.com/alexandregpereira/monster-compendium). The files [monsters.json](json/monsters.json) and [spells.json](json/spells.json) were formatted from the API https://dnd5eapi.co.

## Scheme

### monsters.json

```json
[
    {
        "index": String,
        "type": "ABERRATION" | "BEAST" | "CELESTIAL" | "CONSTRUCT" | "DRAGON" | "ELEMENTAL" | "FEY" | "FIEND" | "GIANT" | "HUMANOID" | "MONSTROSITY" | "OOZE" | "PLANT" | "UNDEAD",
        "subtype": String?,
        "group": String?,
        "challenge_rating": Float,
        "name": String,
        "subtitle": String,
        "size": String,
        "alignment": String,
        "armor_class": Int,
        "hit_points": Int,
        "hit_dice": String,
        "speed": {
            "hover": Boolean,
            "value": [
                {
                    "type": "BURROW" | "CLIMB" | "FLY" | "WALK" | "SWIM",
                    "measurement_unit": "FEET" | "METER",
                    "value": Int,
                    "value_formatted": String
                }
            ]
        },
        "ability_scores": RequiredList [
            {
                "type": "STRENGTH",
                "value": Int,
                "modifier": Int
            },
            {
                "type": "DEXTERITY",
                "value": Int,
                "modifier": Int
            },
            {
                "type": "CONSTITUTION",
                "value": Int,
                "modifier": Int
            },
            {
                "type": "INTELLIGENCE",
                "value": Int,
                "modifier": Int
            },
            {
                "type": "WISDOM",
                "value": Int,
                "modifier": Int
            },
            {
                "type": "CHARISMA",
                "value": Int,
                "modifier": Int
            }
        ],
        "saving_throws": OptionalList [
            {
                "index": String,
                "type": "STRENGTH" | "DEXTERITY" | "CONSTITUTION" | "INTELLIGENCE" | "WISDOM" | "CHARISMA",
                "modifier": Int
            }
        ],
        "skills": OptionalList [
            {
                "index": String,
                "modifier": Int,
                "name": String
            }
        ],
        "damage_vulnerabilities": OptionalList [
            {
                "index": String,
                "type": "ACID" | "BLUDGEONING" | "COLD" | "FIRE" | "BLUDGEONING" | "LIGHTNING" | "NECROTIC" | "PIERCING" | "POISON" | "PSYCHIC" | "RADIANT" | "SLASHING" | "THUNDER" | "OTHER",
                "name": String
            }
        ],
        "damage_resistances": OptionalList [
            {
                "index": String,
                "type": "ACID" | "BLUDGEONING" | "COLD" | "FIRE" | "BLUDGEONING" | "LIGHTNING" | "NECROTIC" | "PIERCING" | "POISON" | "PSYCHIC" | "RADIANT" | "SLASHING" | "THUNDER" | "OTHER",
                "name": String
            }
        ],
        "damage_immunities": OptionalList [
            {
                "index": String,
                "type": "ACID" | "BLUDGEONING" | "COLD" | "FIRE" | "BLUDGEONING" | "LIGHTNING" | "NECROTIC" | "PIERCING" | "POISON" | "PSYCHIC" | "RADIANT" | "SLASHING" | "THUNDER" | "OTHER",
                "name": String
            }
        ],
        "condition_immunities": OptionalList [
            {
                "index": String,
                "type": "BLINDED" | "CHARMED" | "DEAFENED" | "EXHAUSTION" | "FRIGHTENED" | "GRAPPLED" | "PARALYZED" | "PETRIFIED" | "POISONED" | "PRONE" | "RESTRAINED" | "STUNNED" | "UNCONSCIOUS",
                "name": String
            }
        ],
        "senses": OptionalList [String],
        "languages": String,
        "special_abilities": [
            {
                "name": String,
                "desc": String
            }
        ],
        "actions": RequiredList [
            {
                "damage_dices": OptionalList [
                    {
                        "dice": String,
                        "damage": {
                            "index": String,
                            "type": "ACID" | "BLUDGEONING" | "COLD" | "FIRE" | "BLUDGEONING" | "LIGHTNING" | "NECROTIC" | "PIERCING" | "POISON" | "PSYCHIC" | "RADIANT" | "SLASHING" | "THUNDER" | "OTHER",
                            "name": String
                        }
                    }
                ],
                "attack_bonus": Int?,
                "description": String,
                "name": String
            }
        ],
        "reactions": OptionalList [
            {
                "name": String,
                "description": String
            }
        ],
        "spellcasting": OptionalList [
            {
                "desc": String,
                "type": "SPELLCASTER" | "INNATE",
                "spells_by_group": RequiredList [
                    {
                        "group": String,
                        "spells": RequiredList [
                            {
                                "index": String,
                                "name": String,
                                "school": "ABJURATION" | "CONJURATION" | "DIVINATION" | "ENCHANTMENT" | "EVOCATION" | "ILLUSION" | "NECROMANCY" | "TRANSMUTATION",
                                "level": Int
                            }
                        ]
                    }
                ]
            }
        ]
        "source": {
            "name": String,
            "acronym": String
        }
    }
]
```

### spells.json

```json
[
    {
        "index": String,
        "name": String,
        "level": Int,
        "casting_time": String,
        "components": String,
        "duration": String,
        "range": String,
        "ritual": Boolean,
        "concentration": Boolean,
        "saving_throw_type": null | "STRENGTH" | "DEXTERITY" | "CONSTITUTION" | "INTELLIGENCE" | "WISDOM" | "CHARISMA",
        "damage_type": String,
        "school": "ABJURATION" | "CONJURATION" | "DIVINATION" | "ENCHANTMENT" | "EVOCATION" | "ILLUSION" | "NECROMANCY" | "TRANSMUTATION",
        "description": String,
        "higher_level": String?
    }
]
```

### monster-images.json

```json
[
    {
        "monster_index": String,
        "background_color": {
            "light": String,
            "dark": String
        },
        "is_horizontal_image": Boolean,
        "image_url": String
    }
]
```
