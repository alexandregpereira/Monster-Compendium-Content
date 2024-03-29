# Monster Compendium Content

This repository contains content consumed by the [Monster Compendium Android App](https://github.com/alexandregpereira/monster-compendium). The files [monsters.json](json/monsters.json) and [spells.json](json/spells.json) were formatted from the API https://dnd5eapi.co data.

## Schema

### [monsters.json](json/monsters.json)

```kotlin
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
            "value": RequiredList [
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

### [spells.json](json/spells.json)

```kotlin
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

### [monster-images.json](json/monster-images.json)

```kotlin
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

## Content License

The content of this app are Open-Gaming License (OGL). The content and license can found at the [D&D 5th Systems Reference Document (SRD)](https://dnd.wizards.com/resources/systems-reference-document). Dungeons & Dragons (D&D) is a trademark of Wizards of the Coast company.

## Licence

    Copyright 2022 Alexandre Gomes Pereira
    
    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at
    
           http://www.apache.org/licenses/LICENSE-2.0
    
    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
