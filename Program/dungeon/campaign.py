"""Campaign start (docs/story.md "Campaign start"): who the player is when a story begins.

A city may ship premade characters (`world/data/premades/<city>.json`), each with a few lines about them and their
MARVEL stats. Or the player makes their own: a name, a few lines, and stats bought from a pool of points. Either
way the persona of this world takes them on, the story clock starts (dungeon/story_clock.py), and the story opens
with the player arriving where the scene is.
"""
import json
from pathlib import Path

from dungeon import inventory, quests, sheet, story, story_clock, timeline, worlds
from dungeon.database import one
from dungeon.errors import require
from dungeon.models import PersonaInput
from dungeon.rules import marvel

PREMADES = Path(__file__).parent / 'world' / 'data' / 'premades'
# Point-buy at the start: the six stats share POINTS, each from START_RANGE, so the default sheet (all 10) fits.
POINTS = 60
START_RANGE = (4, 18)


def premades(city_id: str) -> list[dict]:
    path = PREMADES / f'{city_id}.json'
    return json.loads(path.read_text(encoding='utf-8'))['premades'] if path.exists() else []


def view(database) -> dict:
    with database.connect() as connection:
        city_id = story.scene_row(connection)['city_id']
    return {'premades': premades(city_id), 'points': POINTS, 'range': list(START_RANGE),
            'stat_names': list(marvel.STATS), 'meanings': marvel.MEANINGS}


def bought(stats: dict[str, int]) -> dict[str, int]:
    """The stats of a made character: every stat, each in START_RANGE, spending no more than POINTS."""
    low, high = START_RANGE
    require(set(stats) == set(marvel.STATS), f"Give all six stats: {', '.join(marvel.STATS)}.", 422)
    require(all(isinstance(value, int) and low <= value <= high for value in stats.values()),
            f'Each stat starts from {low} to {high}.', 422)
    require(sum(stats.values()) <= POINTS, f'The stats can share {POINTS} points at most.', 422)
    return stats


def begin(database, premade_id: str | None = None, persona: PersonaInput | None = None,
          stats: dict[str, int] | None = None) -> dict:
    """Start the story as a premade character or one the player made; only a story with nothing in it yet."""
    with database.connect() as connection:
        where, values = timeline.visible(connection)
        require(one(connection, f'SELECT COUNT(*) AS n FROM story_messages WHERE {where}', values)['n'] == 0,
                'The story has already begun. Start a new story to choose someone else.', 409)
        city_id = story.scene_row(connection)['city_id']
    if premade_id:
        chosen = next((item for item in premades(city_id) if item['id'] == premade_id), None)
        require(chosen is not None, 'That character is not in this town.', 404)
        persona = PersonaInput(name=chosen['name'], gender=chosen['gender'], age=chosen['age'], about=chosen['about'])
        stats = chosen['stats']
    else:
        require(persona is not None and bool((persona.name or '').strip()), 'Give your character a name.', 422)
        stats = bought(stats or {})
    data = worlds.registry(database)
    active = worlds.found(data['worlds'], data['active'], 'world')
    worlds.update_persona(database, active['persona_id'], persona)
    with database.connect(write=True) as connection:
        sheet.set_stats(connection, stats, database.now())
        story_clock.start(connection, database.clock.now())
        quests.start(connection, city_id, database.clock.now())
        inventory.give_kit(connection, city_id, premade_id)
        story.arrive(connection, database.now())
    return story.story(database)
