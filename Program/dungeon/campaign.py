"""Campaign start (docs/story.md "Campaign start"): who the player is when a story begins.

A city may ship premade characters (`world/data/premades/<city>.json`), each with a few lines about them and their
MARVEL stats. Or the player makes their own: a name, a few lines, and stats bought from a pool of points. Either
way the persona of this world takes them on, the story clock starts (dungeon/story_clock.py), and the story opens
with the player arriving where the scene is.
"""
import json
from pathlib import Path

from dungeon import (
    chapters,
    director,
    inventory,
    legacy,
    quests,
    sheet,
    story,
    story_clock,
    table,
    tiers,
    timeline,
    worlds,
)
from dungeon.database import one
from dungeon.errors import require
from dungeon.models import PersonaInput
from dungeon.rules import marvel, srd52

PREMADES = Path(__file__).parent / 'world' / 'data' / 'premades'
# Point-buy at the start: the six stats share POINTS, each from START_RANGE, so the default sheet (all 10) fits.
POINTS = 60
START_RANGE = (4, 18)
# A premade with no 5E build of its own takes one from its strongest MARVEL stat.
CLASS_BY_STAT = {'Vitality': ('fighter', 'soldier'), 'Mind': ('wizard', 'sage'), 'Allure': ('bard', 'criminal'),
                 'Resolve': ('paladin', 'soldier'), 'Essence': ('cleric', 'acolyte'), 'Luck': ('rogue', 'criminal')}


def premades(city_id: str) -> list[dict]:
    path = PREMADES / f'{city_id}.json'
    return json.loads(path.read_text(encoding='utf-8'))['premades'] if path.exists() else []


def view(database) -> dict:
    with database.connect() as connection:
        city_id = story.scene_row(connection)['city_id']
        rules = table.rules(connection)
    world = tiers.world_of(city_id)
    return {'premades': premades(city_id), 'points': POINTS, 'range': list(START_RANGE),
            'stat_names': list(marvel.STATS), 'meanings': marvel.MEANINGS,
            # The rulesets a campaign can be played in, the world's own first (dungeon/sheet.py).
            'rulesets': [{'id': key, 'name': name} for key, name in sheet.RULESETS.items()],
            'ruleset': sheet.default_for(world), 'srd52': srd52_choices(),
            'arc': world and {'arc': tiers.track(world)['arc'], 'pace': tiers.track(world)['pace'],
                              'hand': director.DEFAULT_HAND},
            # Session zero (dungeon/table.py): the presets, and the rules as a new campaign would start.
            'presets': table.PRESETS, 'table': rules,
            # Other worlds' stories, to bring in as history (dungeon/legacy.py).
            'legacy': legacy.candidates(database)}


def srd52_choices() -> dict:
    """What a 5E character is built from: the pack's classes, species and backgrounds, and the standard array."""
    return {'classes': [{'id': item['id'], 'name': item['name'], 'hit_die': item['hit_die'],
                         'primary': item['primary_ability'], 'skills': item['skill_choices']}
                        for item in srd52.pack('classes')],
            'species': [{'id': item['id'], 'name': item['name']} for item in srd52.pack('species')],
            'backgrounds': [{'id': item['id'], 'name': item['name'], 'skills': item['skill_proficiencies'],
                             'abilities': item['ability_scores']} for item in srd52.pack('backgrounds')],
            'abilities': [{'id': ability, 'name': name} for ability, name in srd52.ABILITY_NAMES.items()],
            'skills': [{'id': skill['id'], 'name': skill['name'], 'ability': skill['ability']}
                       for skill in srd52.pack('rules')['skills']],
            'array': list(srd52.STANDARD_ARRAY), 'attribution': srd52.attribution()}


def premade_build(chosen: dict) -> dict:
    """A premade's 5E character: its own class, species and background, with the quick build's scores and skills."""
    own = chosen.get('srd52')
    if not own:
        top = max(marvel.STATS, key=lambda stat: chosen['stats'].get(stat, 0))
        class_id, background = CLASS_BY_STAT[top]
        own = {'class': class_id, 'species': 'human', 'background': background}
    quick = srd52.suggested(own['class'], own['background'])
    return srd52.build(own['class'], own['species'], own['background'], quick['scores'], quick['picks'])


def bought(stats: dict[str, int]) -> dict[str, int]:
    """The stats of a made character: every stat, each in START_RANGE, spending no more than POINTS."""
    low, high = START_RANGE
    require(set(stats) == set(marvel.STATS), f"Give all six stats: {', '.join(marvel.STATS)}.", 422)
    require(all(isinstance(value, int) and low <= value <= high for value in stats.values()),
            f'Each stat starts from {low} to {high}.', 422)
    require(sum(stats.values()) <= POINTS, f'The stats can share {POINTS} points at most.', 422)
    return stats


def begin(database, premade_id: str | None = None, persona: PersonaInput | None = None,
          stats: dict[str, int] | None = None, arc: str | None = None, pace: str | None = None,
          hand: str | None = None, ironman: bool = False, legacy_of: dict | None = None,
          ruleset: str | None = None, build: dict | None = None, rules: dict | None = None) -> dict:
    """Start the story as a premade character or one the player made; only a story with nothing in it yet. The
    ruleset (the world's own by default) is chosen now and locked; under 5E a made character is `build` (class,
    species, background, the standard array placed, the class's skills). `rules` are session zero's (dungeon/table.py)."""
    with database.connect() as connection:
        where, values = timeline.visible(connection)
        require(one(connection, f'SELECT COUNT(*) AS n FROM story_messages WHERE {where}', values)['n'] == 0,
                'The story has already begun. Start a new story to choose someone else.', 409)
        city_id = story.scene_row(connection)['city_id']
    ruleset = ruleset or sheet.default_for(tiers.world_of(city_id))
    require(ruleset in sheet.RULESETS, 'That ruleset is not built in.', 422)
    native = None
    if premade_id:
        chosen = next((item for item in premades(city_id) if item['id'] == premade_id), None)
        require(chosen is not None, 'That character is not in this town.', 404)
        persona = PersonaInput(name=chosen['name'], gender=chosen['gender'], age=chosen['age'], about=chosen['about'])
        stats = chosen['stats']
        native = premade_build(chosen) if ruleset == srd52.ID else None
    else:
        require(persona is not None and bool((persona.name or '').strip()), 'Give your character a name.', 422)
        if ruleset == srd52.ID:
            require(build is not None, 'Choose a class, species and background, and place the standard array.', 422)
            native = srd52.build(build['class_id'], build['species_id'], build['background_id'], build['scores'],
                                 build['skills'])
            stats = {stat: marvel.DEFAULT_STAT for stat in marvel.STATS}
        else:
            stats = bought(stats or {})
    earlier = legacy_of and legacy.chosen(database, legacy_of['world_id'], legacy_of['role'])
    data = worlds.registry(database)
    active = worlds.found(data['worlds'], data['active'], 'world')
    worlds.update_persona(database, active['persona_id'], persona)
    with database.connect(write=True) as connection:
        sheet.set_stats(connection, stats, database.now())
        # The ruleset (dungeon/sheet.py): chosen now, for the whole campaign, with its own sheet.
        sheet.set_ruleset(connection, ruleset)
        if native:
            sheet.set_native(connection, native, database.now())
        # Ironman (dungeon/chapters.py): chosen now, for the whole campaign.
        chapters.set_ironman(connection, ironman)
        # The Table (dungeon/table.py): session zero's rules, the rest from the world's tone and the player's last taste.
        table.choose(connection, rules or {}, database.now())
        table.begin(connection)
        story_clock.start(connection, database.clock.now())
        quests.start(connection, city_id, database.clock.now())
        inventory.give_kit(connection, city_id, premade_id)
        # How far and how fast the character can rise (dungeon/tiers.py).
        if world := tiers.world_of(city_id):
            tiers.begin(connection, world, arc, pace)
            # The director's arcs and threads, and how hard its hand pushes (dungeon/director.py).
            director.begin(connection, world, hand, database.now())
        # An earlier campaign's character as this world's history (dungeon/legacy.py).
        if earlier:
            legacy.bring(connection, earlier, legacy_of['role'], database.clock.now())
        story.arrive(connection, database.now())
    return story.story(database)
