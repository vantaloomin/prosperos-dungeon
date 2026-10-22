"""Character sheets: MARVEL stats per actor (dungeon/rules/marvel.py). The player's character is 'persona'; an actor
with no stats rolls with no die.

The campaign's ruleset is chosen at its start and then locked (story_campaign.ruleset; docs/requirements.md
"Rulesets"). Under MARVEL the persona's sheet is its six stats. Under another ruleset the persona has that ruleset's
own sheet (story_sheet, branched with the story), and `check` rolls the persona's checks its way: the Referee's
approach (a MARVEL stat) and the action's words decide what the ruleset tests. Everyone else keeps MARVEL stats.
"""
import random

from dungeon.database import decode, encode, many, optional
from dungeon.errors import require
from dungeon.rules import marvel, srd52

RULESETS = {marvel.ID: marvel.NAME, srd52.ID: srd52.NAME}
WORLD_RULESETS: dict[str, str] = {}

PERSONA = 'persona'


def stats(connection, actor: str = PERSONA) -> dict[str, int]:
    """Every stat of an actor; the persona's unset ones are the default, anyone else's are left out."""
    rows = {row['stat']: row['value'] for row in many(connection, 'SELECT stat, value FROM character_stats '
                                                                  'WHERE actor=?', (actor,))}
    if actor == PERSONA:
        return {stat: rows.get(stat, marvel.DEFAULT_STAT) for stat in marvel.STATS}
    return rows


def set_stats(connection, values: dict[str, int], now: str, actor: str = PERSONA) -> dict[str, int]:
    low, high = marvel.STAT_RANGE
    for stat, value in values.items():
        require(stat in marvel.STATS, f'{stat} is not a MARVEL stat.', 422)
        require(isinstance(value, int) and low <= value <= high, f'{stat} must be from {low} to {high}.', 422)
    connection.executemany(
        'INSERT INTO character_stats (actor, stat, value, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(actor, stat) '
        'DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at',
        [(actor, stat, value, now) for stat, value in values.items()])
    return stats(connection, actor)


def view(connection) -> dict:
    return {'stats': stats(connection), 'stat_names': list(marvel.STATS), 'range': list(marvel.STAT_RANGE),
            'dice': {stat: marvel.die_for(value) for stat, value in stats(connection).items()}}


# The campaign's ruleset ---------------------------------------------------------------------------

def ruleset(connection) -> str:
    row = optional(connection, 'SELECT ruleset FROM story_campaign WHERE id=1')
    return (row and row['ruleset']) or marvel.ID


def default_for(world: str | None) -> str:
    """The ruleset a world names for its campaigns (every built-in world plays MARVEL for now)."""
    return WORLD_RULESETS.get(world or '', marvel.ID)


def set_ruleset(connection, ruleset_id: str):
    require(ruleset_id in RULESETS, 'That ruleset is not built in.', 422)
    connection.execute('INSERT INTO story_campaign (id, ruleset) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET '
                       'ruleset=excluded.ruleset', (ruleset_id,))


def native(connection) -> dict | None:
    """The persona's sheet under a ruleset other than MARVEL."""
    row = optional(connection, 'SELECT data FROM story_sheet WHERE id=1')
    return decode(row['data']) if row else None


def set_native(connection, data: dict, now: str):
    connection.execute('INSERT INTO story_sheet (id, ruleset, data, updated_at) VALUES (1, ?, ?, ?) ON CONFLICT(id) '
                       'DO UPDATE SET ruleset=excluded.ruleset, data=excluded.data, updated_at=excluded.updated_at',
                       (ruleset(connection), encode(data), now))


def check(connection, approach: str, difficulty: str = 'normal', text: str = '', rng: random.Random | None = None,
          save: bool = False) -> dict:
    """One of the persona's checks in the campaign's ruleset, on the shared ladder. `approach` is a MARVEL stat;
    `save` asks for a saving throw where the ruleset has them (resisting fear, pain, poison)."""
    found = native(connection) if ruleset(connection) == srd52.ID else None
    if found:
        result = srd52.check(found, approach, difficulty, text, rng, save) | {'ruleset': srd52.ID}
        return cast(connection, found, result, rng) if result.get('spell') else result
    return marvel.roll(stats(connection).get(approach), difficulty, rng) | {'ruleset': marvel.ID, 'target': None,
                                                                            'skill': None}


def cast(connection, found: dict, result: dict, rng) -> dict:
    """A 5E spell cast by the turn's check: it spends a slot (none left, it fails); a healing spell always works and
    heals the character."""
    spell = srd52.spells()[result['spell']]
    slot = srd52.spend(found, spell)
    if slot is None:
        return result | {'band': 'failure', 'skill': f"{spell['name']} (no spell slot left)", 'spell': None}
    if dice := srd52.healing_of(spell):
        from dungeon import combat, combat5e
        healed = max(1, combat5e.roll_dice(dice, rng or random.SystemRandom())
                     + srd52.modifier(found['abilities'][found['spell_ability']]))
        found['hp'] = min(found['max_hp'], found['hp'] + healed)
        set_native(connection, found, '')
        combat.set_condition(connection, combat5e.level_for(found['hp'], found['max_hp']))
        return result | {'band': 'success', 'skill': f"{spell['name']} (heals {healed})"}
    set_native(connection, found, '')
    return result


def full_view(connection) -> dict:
    """The sheet the screen shows, in the campaign's ruleset."""
    found = native(connection) if ruleset(connection) == srd52.ID else None
    if found:
        return srd52.view(found)
    return view(connection) | {'ruleset': marvel.ID, 'ruleset_name': marvel.NAME}
