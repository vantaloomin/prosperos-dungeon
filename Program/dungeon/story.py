"""Story mode: free-form roleplay with a narrator around the cities (docs/story.md).

The story has its own scene (`story_scene`: the city and place the user is at) and its own history
(`story_messages`).

The app decides the scene from the city data and the townsfolk rules: the place, the local time and
weather, and who is there at that hour. The narrator model only voices it. Moving somewhere else is the
user's choice in the place picker, not the model's.
"""
import asyncio
import logging
import time
from datetime import datetime

from dungeon import (
    authors_note,
    beats,
    chapters,
    combat,
    director,
    factions,
    feelings,
    finds,
    growth,
    happenings,
    in_character,
    injuries,
    inventory,
    jobs,
    pace,
    passages,
    prompt_library,
    quests,
    record,
    referee,
    remembering,
    rest,
    safety,
    story_clock,
    story_people,
    stress,
    tiers,
    timeline,
    travel,
    turn,
)
from dungeon.authors_note import NOTE_CLOSE
from dungeon.clock import zone
from dungeon.database import decode, encode, identifier, many, one, optional, settings
from dungeon.errors import DomainError, require
from dungeon.life import ages
from dungeon.narration import prompt as narration_prompt
from dungeon.narration import prose
from dungeon.providers.chat import INCOMPLETE
from dungeon.providers.scheduling import CONVERSATION
from dungeon.rules import marvel
from dungeon.sheet import stats as sheet_stats
from dungeon.text_models import config_for, default_name, key_for
from dungeon.world import catalog, changes, custom, generators, inside, life_details, townsfolk

JOB = 'story'
log = logging.getLogger(__name__)
DEFAULT_CITY = 'kingswood'
HISTORY_LIMIT = 200
CHARS_PER_TOKEN = 4
# The kinds a story starts at when nothing else is chosen: somewhere people sit and talk.
OPENING_KINDS = ('cafe', 'tavern', 'bar', 'restaurant', 'market', 'park')

# Story mode's player has no persona yet, so the narrator speaks to them as "you", as Story mode always has.
NARRATION = narration_prompt.Format(pov='second', tense='present', length='short')


def intensity(connection, data: dict) -> dict:
    """How far the story goes on the page: the player's preset, or the world's (requirements "Intensity and tone").
    v0 has one preset for every category; per-category sliders and veils come later."""
    world = data.get('intensity') or {}
    chosen = settings(connection)['intensity']
    world_preset = world.get('preset') or narration_prompt.DEFAULT_PRESET
    drama, world_drama = settings(connection)['drama'], world.get('drama') or happenings.DEFAULT_DRAMA
    return {'preset': world_preset if chosen == 'world' else chosen, 'chosen': chosen, 'world': world_preset,
            'voice': world.get('voice') or '', 'drama': world_drama if drama == 'world' else drama,
            'drama_chosen': drama, 'drama_world': world_drama, 'cutaways': bool(settings(connection)['cutaways'])}


def no_model() -> DomainError:
    return DomainError('Add a text model in Settings > Models to tell the story.', 409, 'no_connection')


# The scene ----------------------------------------------------------------------------------------

def city_data(connection, city_id: str) -> dict:
    """The city as the story has it, in this world's town."""
    return city_for(connection, city_id, town_seed(connection))


def town_seed(connection) -> str:
    """The seed of this world's town (dungeon/worlds.py build): '' in the first world, so each world has its own people."""
    row = optional(connection, 'SELECT town_seed FROM persona WHERE id=1')
    return row['town_seed'] or '' if row else ''


def city_for(connection, city_id: str, town: str) -> dict:
    """The city with the town `town` seeds (`data['town']`, dungeon/world/townsfolk.py): another town makes another
    person of the same key. `you` is the townsperson the user became there, who is no longer one of its people."""
    data = changes.resolve(city_id, custom.all_cities(connection))
    if data is None:
        raise DomainError(f'No world data for city {city_id!r}.', 404, 'unknown_city')
    return data | {'kin': [], 'town': town, 'you': you(connection, town), 'kept': ()}


def you(connection, town: str) -> str:
    """The townsperson the user became in this world (dungeon/worlds.py, Become a townsperson), when this town is
    theirs."""
    row = optional(connection, 'SELECT townsfolk_key, town_seed FROM persona WHERE id=1')
    return row['townsfolk_key'] if row and row['townsfolk_key'] and row['town_seed'] == town else ''


def opening_place(data: dict) -> dict:
    for kind in OPENING_KINDS:
        if found := catalog.places(data, kind=kind):
            return found[0]
    return data['places'][0]


def scene_row(connection) -> dict:
    """Where the story is; a new story starts in Kingswood, the slice town, at its tavern or another opening place. A place or city that
    has since gone falls back the same way."""
    row = optional(connection, 'SELECT city_id, place_id FROM story_scene WHERE id=1')
    known = row and changes.resolve(row['city_id'], custom.all_cities(connection))
    data = city_data(connection, row['city_id'] if known else DEFAULT_CITY)
    if known and catalog.find(data, row['place_id']) in data['places']:
        return {'city_id': row['city_id'], 'place_id': row['place_id']}
    return {'city_id': data['id'], 'place_id': opening_place(data)['id']}


def local_moment(data: dict, now: datetime) -> datetime:
    return now.astimezone(zone(data['timezone'])).replace(tzinfo=None)


def present(connection, data: dict, place_id: str, moment: datetime) -> list[dict]:
    """Who the townsfolk rules put at the place now: the people seeded there and residents whose rules bring them."""
    day = moment.date()
    seeded = [] if place_id.startswith('~') else townsfolk.at_place(data, place_id, day)
    # The dead, taken, missing and conscripted are not about (dungeon/beats.py).
    people, seen = [], beats.gone(connection)
    for sheet in [*seeded, *townsfolk.reaching(data, place_id, day)]:
        if sheet['key'] in seen:
            continue
        seen.add(sheet['key'])
        found = townsfolk.whereabouts(sheet, data, moment)
        if found['place'] and found['place']['id'] == place_id:
            # How old they are now (dungeon/life/ages.py).
            people.append({'sheet': {**sheet, 'age': ages.town_age(connection, sheet, day)}, **found})
    return people


def who(sheet: dict, place: dict, data: dict, doing: str = '') -> str:
    """'the barista there', 'a regular at Daily Grind', 'a local from Canton waiting for the bus'."""
    if sheet['kind'] == 'resident':
        local = f"a local from {townsfolk.neighborhood_name(data, sheet['home'])}"
        return f'{local} {doing}' if doing.startswith('waiting for') else local
    if sheet['place']['id'] == place.get('id'):
        return "a regular there" if not sheet['staff'] else f"the {sheet['role']} there"
    return f"a regular at {sheet['place']['name']}" if not sheet['staff'] else \
        f"the {sheet['role']} from {sheet['place']['name']}"


def weather_text(conditions: dict) -> str:
    text = f"High {conditions['high_f']}°F, low {conditions['low_f']}°F, "
    text += 'with rain.' if conditions['rain'] else 'dry.'
    # The month's note can describe sunshine, so it is left out on a rainy day.
    return text if conditions['rain'] else f"{text} {conditions['note']}"


def scene(connection, now: datetime) -> dict:
    row = scene_row(connection)
    data = city_data(connection, row['city_id'])
    place = catalog.find(data, row['place_id'])
    moment = local_moment(data, now)
    weather = generators.conditions(data, moment.date())
    hood = townsfolk.neighborhood_name(data, place['neighborhood'])
    return {'city': {'id': data['id'], 'name': data['name'], 'era': data.get('era', 'modern')},
            'place': {'id': place['id'], 'name': place['name'], 'kind': place['kind'], 'summary': place.get('summary', ''),
                      'neighborhood': hood, 'spots': inside.names(inside.for_place(place, data.get('era')))},
            'local_time': moment.isoformat(timespec='minutes'), 'weather': weather_text(weather) if weather else '',
            'people': present(connection, data, place['id'], moment), 'data': data, 'now': now,
            'known': story_people.known(connection)}


def initiative(sheet: dict, data: dict, moment: datetime | None) -> str:
    """A named person's own business: who they are and what they are after, for them to act on unprompted."""
    if not sheet.get('notable'):
        return ''
    wants = sheet.get('wants') or (townsfolk.story(sheet, data, moment.date())['goal']['text'] if moment else '')
    return (f" {sheet['about']}" + (f' Right now they are after this: {wants}.' if wants else '') +
            ' They pursue their own ends in the scene without waiting to be asked.')


def person_line(person: dict, place: dict, data: dict, known: dict | None = None,
                moment: datetime | None = None) -> str:
    sheet = person['sheet']
    seen = who(sheet, place, data, person['doing'])
    pronouns = f", {sheet['pronouns']}" if sheet.get('pronouns') else ''
    job = sheet.get('occupation') or sheet['role']
    # "working as the owner" already says the job: no "working as the owner, owner."
    job = '' if f' {job}' in f" {person['doing']}" else f', {job}'
    return (f"- {seen[0].upper()}{seen[1:]}: {sheet['full']}{pronouns}, {sheet['age']}, {person['doing']}{job}. "
            f"{townsfolk.first_impression(sheet).capitalize()}; "
            f"{sheet['quirk']}.{life_text(data, sheet)}{initiative(sheet, data, moment)} Mood: {person['mood']}."
            f"{story_people.remembered(known)}"
            f"{person.get('note', '')}")


def life_text(data: dict, sheet: dict) -> str:
    """Where they come from, a taste and a story they might tell, for the model to use or leave."""
    found = life_details.for_sheet(data, sheet)
    if not found:
        return ''
    story = f" Might tell the story of the time they {found['stories'][0]}." if found['stories'] else ''
    return f" {found['origin'][:1].upper()}{found['origin'][1:]}; {found['likes'][0]}.{story}"


def scene_text(view: dict) -> str:
    data, place = view['data'], view['place']
    moment = datetime.fromisoformat(view['local_time'])
    when = f"{moment:%A} {moment.day} {moment:%B}" + (f", {moment.year}" if data.get('era', 'modern') == 'modern' else '')
    lines = [f"Place: {place['name']}, a {place['kind']} in {place['neighborhood']}, {data['name']}. {place['summary']}",
             f"City: {data['summary']}" + ('' if townsfolk.modern(data) else f" The era is {data['era']}."),
             f"Local time: {when}, {moment.strftime('%H:%M')} ({townsfolk.part_of_day(moment.hour * 60 + moment.minute)})."]
    if place.get('spots'):
        lines.append(f"Spots here, for detail only (nobody moves between them): {', '.join(place['spots'])}.")
    if view['weather']:
        lines.append(f"Weather: {view['weather']}")
    lines.append('Who is here (their names are for you; the user knows only the names of people they have met):')
    lines += [person_line(person, {'id': place['id']}, data, view['known'].get(person['sheet']['key']), moment)
              for person in view['people']] or \
        ['- Nobody the story knows; only passers-by.']
    return '## Scene\n' + '\n'.join(lines)


def scene_view(view: dict) -> dict:
    """The scene for the screen: what the user can see, never the names of people they have not met."""
    data = view['data']
    return {key: view[key] for key in ('city', 'place', 'local_time', 'weather')} | {
        'places': [{'id': item['id'], 'name': item['name'], 'kind': item['kind'],
                    'neighborhood': townsfolk.neighborhood_name(data, item['neighborhood'])} for item in data['places']],
        'around': [seen(person, view) for person in view['people']]}


def seen(person: dict, view: dict) -> str:
    """'the barista', or 'Dana, the barista' once the user has met her."""
    sheet = person['sheet']
    said = who(sheet, {'id': view['place']['id']}, view['data'], person['doing']).removesuffix(' there')
    return f"{sheet['name']}, {said}" if sheet['key'] in view['known'] else said


# The player's character ---------------------------------------------------------------------------

STRONG, WEAK = 14, 7


def persona_text(connection) -> tuple[str, str | None]:
    """Who the player is, for the narrator: what they wrote about themselves and, in words, what their stats make
    them good and bad at. Never the numbers. ('', None) when they have not said who they are."""
    row = optional(connection, 'SELECT name, gender, age, about FROM persona WHERE id=1')
    if not row or not row['name']:
        return '', None
    details = ', '.join(str(item) for item in (row['gender'], row['age']) if item)
    lines = [f"{row['name']}" + (f' ({details})' if details else '') + '.']
    if row['about']:
        lines.append(row['about'].strip())
    stats = sheet_stats(connection)
    if strong := [marvel.MEANINGS[stat] for stat, value in stats.items() if value >= STRONG]:
        lines.append(f"Good at: {'; '.join(strong)}.")
    if weak := [marvel.MEANINGS[stat] for stat, value in stats.items() if value <= WEAK]:
        lines.append(f"Poor at: {'; '.join(weak)}.")
    lines.append('Write their actions and words in their own voice, from what is here; invent nothing about their '
                 'past.')
    return '\n'.join(lines), row['name']


# Gear and the shop --------------------------------------------------------------------------------

def shop_view(connection, view: dict) -> dict | None:
    """The shop where the story is, if it is one: open while one of its staff is at work."""
    shop = inventory.shop_at(view['city']['id'], view['place']['id'])
    if shop is None:
        return None
    staff = [person['sheet'] for person in view['people'] if person['sheet'].get('staff')
             and person['sheet']['place']['id'] == view['place']['id']]
    keeper = f"the {staff[0].get('occupation') or staff[0]['role']}" if staff else ''
    return inventory.window(connection, view['city']['id'], shop, bool(staff), keeper, story_day(view)) | {
        'keeper_key': staff[0]['key'] if staff else ''}


def story_day(view: dict) -> str:
    return view['local_time'][:10]


def gear(database) -> dict:
    """The character's purse and pack, and the shop window where the story is."""
    with database.connect(write=True) as connection:
        view = scene(connection, story_clock.now(connection, database.clock))
        city = view['city']['id']
        rows = inventory.carried(connection, city)
        return {'coins': inventory.purse(connection), 'currency': view['data']['currency'],
                'slots': {'used': inventory.used(rows), 'max': inventory.capacity(connection)},
                'items': [{key: row[key] for key in ('id', 'item_id', 'name', 'category', 'qty', 'slots')}
                          for row in rows],
                'shop': shop_view(connection, view)}


def trade(database, kind: str, key: str, qty: int) -> dict:
    """Buy an item from the shop here, or sell it one of the character's; the story gets a line about it."""
    with database.connect(write=True) as connection:
        view = scene(connection, story_clock.now(connection, database.clock))
        city = view['city']['id']
        shop = inventory.shop_at(city, view['place']['id'])
        require(shop is not None, 'There is no shop here.', 404)
        require(shop_view(connection, view)['open'], 'The shop is closed; nobody is behind the counter.', 409)
        done = (inventory.buy(connection, city, shop, key, qty, database.now(), story_day(view)) if kind == 'buy'
                else inventory.sell(connection, city, shop, key, qty, database.now()))
        what = done['name'] if done['qty'] == 1 else f"{done['qty']} × {done['name']}"
        verb = 'buy' if kind == 'buy' else 'sell'
        price = inventory.money_text(done['amount'], view['data']['currency'])
        add(connection, database.now(), 'scene', f"You {verb} {what} for {price}" + ('' if price.endswith('.') else '.'),
            scene_row(connection))
    return gear(database)


# History ------------------------------------------------------------------------------------------

def next_seq(connection) -> int:
    return one(connection, 'SELECT COALESCE(MAX(seq), 0) + 1 AS seq FROM story_messages')['seq']


def add(connection, now: str, role: str, text: str, where: dict, **extra) -> dict:
    message_id = identifier()
    connection.execute(
        'INSERT INTO story_messages (id, seq, role, text, client_id, reply_to, status, error, city_id, place_id, '
        'created_at, branch_id, flags) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (message_id, next_seq(connection), role, text, extra.get('client_id'), extra.get('reply_to'),
         extra.get('status', 'complete'), extra.get('error'), where['city_id'], where['place_id'], now,
         timeline.active(connection), encode(extra.get('flags', []))))
    return one(connection, 'SELECT * FROM story_messages WHERE id=?', (message_id,))


def messages(connection, limit: int = HISTORY_LIMIT) -> list[dict]:
    where, values = timeline.visible(connection)
    rows = many(connection, 'SELECT id, seq, role, text, reply_to, status, error, city_id, place_id, created_at, '
                f'flags, previous FROM story_messages WHERE {where} ORDER BY seq DESC LIMIT ?', (*values, limit))
    # The app's crisis note under a user's line that sounds like self-harm (dungeon/safety.py), and a narration's
    # flagged passages, and whether it can switch back to its wording before a rewrite (dungeon/passages.py).
    return [{**row, 'crisis_help': row['role'] == 'user' and safety.crisis(row['text']),
             'flags': passages.shown(decode(row['flags'])), 'previous': row['previous'] is not None}
            for row in reversed(rows)]


def dice_shown(connection) -> bool:
    """Roll visibility (Settings > World > Hidden values): hidden unless the player shows them."""
    return bool(settings(connection)['show_odds'])


def with_rolls(connection, rows: list[dict]) -> list[dict]:
    """The rolls under each of the player's lines, and how long its turn took (dungeon/pace.py), only while the dice
    are shown; hidden dice never leave the app."""
    if not dice_shown(connection):
        return rows
    return [{**row, 'rolls': [turn.shown(roll) for roll in turn.saved(connection, row['id'])],
             'pace': decode(pace.saved(connection, row['id']) or 'null')}
            if row['role'] == 'user' else row for row in rows]


def story(database) -> dict:
    with database.connect() as connection:
        view = scene(connection, story_clock.now(connection, database.clock))
        return {'scene': scene_view(view), 'messages': with_rolls(connection, messages(connection)),
                'people': people(connection, view), 'ready': config_for(connection, JOB) is not None,
                'dice_shown': dice_shown(connection), 'bands': turn.bands() if dice_shown(connection) else None,
                'branches': timeline.branches(connection),
                'campaign': chapters.view(connection),
                'fight': combat.view(connection, dice_shown(connection)) | {
                    'injuries': injuries.view(connection, view['now']),
                    'stress': stress.view(connection, dice_shown(connection))},
                'injury_persistence': injuries.persistence(connection),
                'intensity': intensity(connection, view['data']),
                'map': travel.view(connection, view['city']['id'], view['place']['id']),
                'factions': powers(connection, view), 'tier': standing(connection, view)}


def standing(connection, view: dict) -> dict | None:
    """The character's tier and its track (dungeon/tiers.py), for the screen."""
    world = tiers.world_of(view['city']['id'])
    return tiers.view(connection, world, dice_shown(connection)) if world else None


def powers(connection, view: dict) -> list[dict]:
    """The factions the character knows of (dungeon/factions.py), for the screen."""
    found = happenings.where(view['city']['id'], view['place']['id'])
    if found is None:
        return []
    visited = {row['node_id'] for row in many(connection, 'SELECT node_id FROM story_map WHERE visited=1')}
    return factions.view(connection, found['world'], visited | {found['node']}, dice_shown(connection))


def ending(connection) -> str:
    """How the branch being left ended, when the character died or was lost there (dungeon/chapters.py tree)."""
    return 'death' if combat.condition(connection)['dead'] else 'lost' if growth.lost(connection) else ''


def back(database, message_id: str) -> dict:
    """Go back to before one of the player's lines; the line comes back as a draft to send again, with new dice."""
    with database.connect(write=True) as connection:
        chapters.no_going_back(connection)
        line = timeline.back(connection, message_id, database.now(), ending(connection))
    return story(database) | {'draft': line['text']}


def switch_branch(database, branch_id: str) -> dict:
    with database.connect(write=True) as connection:
        if branch_id != timeline.active(connection):
            chapters.no_going_back(connection)
        timeline.switch(connection, branch_id, database.now(), ending(connection))
    return story(database)


def chapter_back(database, chapter_id: str) -> dict:
    """Play on from the start of a chapter in the tree: in its branch, back to before its first line."""
    with database.connect(write=True) as connection:
        chapters.no_going_back(connection)
        row = optional(connection, 'SELECT branch_id, seq FROM story_chapters WHERE id=?', (chapter_id,))
        require(row is not None, 'That chapter is not in this story.', 404)
        if row['branch_id'] != timeline.active(connection):
            timeline.switch(connection, row['branch_id'], database.now(), ending(connection))
        line = optional(connection, "SELECT id FROM story_messages WHERE branch_id=? AND seq=? AND role='user'",
                        (row['branch_id'], row['seq']))
        require(line is not None, 'That chapter has no line to go back to.', 409)
    return back(database, line['id'])


def bookmark_go(database, bookmark_id: str) -> dict:
    """Play on in the branch a bookmark's line was told in; the screen then shows the line."""
    with database.connect() as connection:
        marked = chapters.marked_branch(connection, bookmark_id)
        where, values = timeline.visible(connection)
        here = optional(connection, f'SELECT 1 FROM story_messages WHERE id=? AND {where}',
                        (marked['message_id'], *values))
    result = story(database) if here else switch_branch(database, marked['branch_id'])
    return result | {'message_id': marked['message_id']}


def people(connection, view: dict) -> list[dict]:
    """Everyone the user has met in the story, most recent first, with where their rules put them now; with the
    dice shown, how they feel about the character too."""
    result, cities, shown = [], {}, dice_shown(connection)
    for row in view['known'].values():
        if row['city_id'] not in cities:
            try:
                cities[row['city_id']] = city_data(connection, row['city_id'])
            except DomainError:
                cities[row['city_id']] = None
        data = cities[row['city_id']]
        sheet = townsfolk.find(data, row['key']) if data else None
        if sheet is None:
            continue  # Their city is gone, or its townsfolk were seeded anew.
        now = townsfolk.whereabouts(sheet, data, local_moment(data, view['now']))
        result.append({'key': row['key'], 'name': row['name'], 'role': sheet.get('occupation') or sheet['role'],
                       'city': data['name'], 'meetings': row['meetings'], 'last_met_at': row['last_met_at'],
                       'notes': row['notes'], 'doing': now['doing'],
                       'feelings': feelings.shown(row) if shown else '',
                       'place': now['place'] and {'id': now['place']['id'], 'name': now['place']['name'],
                                                  'city_id': data['id']}})
    return result


def find(database, key: str) -> dict:
    """Go to where someone the user has met is right now."""
    with database.connect() as connection:
        view = scene(connection, story_clock.now(connection, database.clock))
        person = next((item for item in people(connection, view) if item['key'] == key), None)
    require(person is not None, "You haven't met them in your story.", 404)
    place = person['place']
    require(place is not None and not place['id'].startswith('~'),
            f"{person['name'].split()[0]} isn't anywhere you can go right now ({person['doing']}).", 409)
    return move(database, place['city_id'], place['id'])


def move(database, city_id: str, place_id: str | None) -> dict:
    """Go somewhere else: another place in this city, or another city (its opening place unless one is named)."""
    with database.connect(write=True) as connection:
        data = city_data(connection, city_id)
        place = catalog.find(data, place_id) if place_id else opening_place(data)
        require(place is not None and place in data['places'], 'No such place in this city.', 404)
        require(combat.fight(connection) is None, "You're in a fight. Get away first.", 409)
        moving_from = scene_row(connection)['city_id']
        if scene_row(connection) != {'city_id': data['id'], 'place_id': place['id']}:
            place_scene(connection, data['id'], place['id'], database.now())
            pass_time(database, connection, story_clock.ACROSS_TOWN_MINUTES if moving_from == data['id'] else
                      story_clock.ANOTHER_CITY_MINUTES)
            arrive(connection, database.now())
    return story(database)


def place_scene(connection, city_id: str, place_id: str, now: str):
    connection.execute('INSERT INTO story_scene (id, city_id, place_id, updated_at) VALUES (1, ?, ?, ?) ON CONFLICT(id) '
                       'DO UPDATE SET city_id=excluded.city_id, place_id=excluded.place_id, '
                       'updated_at=excluded.updated_at', (city_id, place_id, now))


def pass_time(database, connection, minutes: int):
    """The story clock moves on: any deadline it passes lands (dungeon/quests.py), and the factions' clocks run
    (dungeon/factions.py)."""
    before = story_clock.now(connection, database.clock)
    story_clock.advance(connection, minutes)
    after = story_clock.now(connection, database.clock)
    quests.check(connection, after, database.now())
    row = optional(connection, 'SELECT city_id, place_id FROM story_scene WHERE id=1')
    if row and (found := happenings.where(row['city_id'], row['place_id'])):
        factions.advance(connection, found['world'], before, after, database.now())
        # And the director's arcs, on their own clocks (dungeon/director.py).
        director.advance(connection, found['world'], before, after, database.now())


def arrive(connection, now: str) -> dict:
    """The line that opens a scene: "You arrive at …", where the scene is now."""
    row = scene_row(connection)
    data = city_data(connection, row['city_id'])
    place = catalog.find(data, row['place_id'])
    hood = townsfolk.neighborhood_name(data, place['neighborhood'])
    return add(connection, now, 'scene', f"You arrive at {place['name']}, {hood}, {data['name']}.", row)


def clear(database) -> dict:
    """A new story: the history, the people met and the record go, the scene stays where it is."""
    with database.connect(write=True) as connection:
        connection.execute('DELETE FROM story_messages')
        connection.execute('DELETE FROM story_people')
        for table in ('record_entries', 'record_corrections', 'story_summary', 'story_clock', 'story_quests',
                      'story_inventory', 'story_purse', 'story_stock', 'story_trades', 'story_wounds', 'story_fight',
                      'story_haggles', 'story_counter', 'story_turn_steps', 'story_finds', 'story_looks',
                      'story_rounds', 'story_map', 'story_journeys', 'story_rests', 'story_injuries', 'story_treatments', 'story_stress',
                      'story_cards', 'story_clocks', 'story_reputation', 'story_fates', 'story_beats', 'story_word',
                      'story_offpage', 'story_tier', 'story_marks', 'story_dark',
                      'story_director', 'story_arcs', 'story_threads', 'story_nemeses'):
            connection.execute(f'DELETE FROM {table}')
        timeline.clear(connection)
        chapters.clear(connection)
    return story(database)


# The narrator -------------------------------------------------------------------------------------

def model_messages(rows: list[dict], budget_chars: int) -> list[dict]:
    """The story so far as chat turns, newest kept when it does not all fit. A move is a note on the user's side."""
    chat, used = [], 0
    for row in reversed(rows):
        if row['role'] == 'narrator' and row['status'] != 'complete':
            continue
        text = f"[{row['text']}]" if row['role'] == 'scene' else row['text']
        used += len(text)
        if used > budget_chars and chat:
            break
        role = 'assistant' if row['role'] == 'narrator' else 'user'
        if chat and chat[0]['role'] == role:
            chat[0] = {'role': role, 'content': text + '\n\n' + chat[0]['content']}
        else:
            chat.insert(0, {'role': role, 'content': text})
    return chat


def steered(chat: list[dict], steer: str) -> list[dict]:
    """The story's author's note (dungeon/authors_note.py) right before the user's latest words."""
    if not steer or not chat or chat[-1]['role'] != 'user':
        return chat
    return [*chat[:-1], {'role': 'user', 'content': f"{steer}\n{NOTE_CLOSE}\n{chat[-1]['content']}"}]


def prompt(connection, now: datetime, config: dict, latest: dict, outcomes: list[dict] | None = None,
           fought: list[str] | None = None, traded: list[str] | None = None,
           looked: list[str] | None = None, travelled: list[str] | None = None,
           rested: list[str] | None = None, tended: list[str] | None = None,
           carded: list[str] | None = None, meanwhile: list[str] | None = None,
           noted: list[str] | None = None) -> dict:
    view = scene(connection, now)
    craft = narration_prompt.craft_for(config.get('context_tokens'), prompt_library.text(connection, 'narrator-craft'))
    who_text, name = persona_text(connection)
    for extra in (combat.condition_text(connection), stress.prompt_text(connection), growth.prompt_text(connection),
                  injuries.prompt_text(connection, now),
                  inventory.prompt_text(connection, view['city']['id'], view['data']['currency'])):
        if extra:
            who_text = f'{who_text}\n{extra}' if who_text else extra
    shop, level = shop_view(connection, view), intensity(connection, view['data'])
    found = happenings.where(view['city']['id'], view['place']['id'])
    after = record.summary(connection)['through_seq']
    rows = [row for row in messages(connection) if after < row['seq'] <= latest['seq']]
    # What the scene is about, for the facts recalled by relevance (dungeon/remembering.py).
    focus = ' '.join([latest['text'], view['place']['name'], *(person['sheet']['name'] for person in view['people']),
                      *(row['text'] for row in rows[-2:])])
    place_text = scene_text(view) + (f"\n\n{inventory.shop_prompt(shop, view['data']['currency'])}" if shop else '')
    window = remembering.room(connection, config)
    # The summary gives way first, then the record's facts, so the recent turns keep at least half the window.
    for summary_kept, facts in ((True, record.IN_PROMPT), (False, record.IN_PROMPT), (False, record.IN_PROMPT // 4)):
        memory = '\n\n'.join(part for part in (summary_kept and record.summary_text(connection),
                                                 record.prompt_text(connection, focus, facts),
                                                 quests.prompt_text(connection, now), beats.prompt_text(connection),
                                                 found and factions.prompt_text(connection, found['world'],
                                                                                found['node']),
                                                 found and tiers.prompt_text(connection, found))
                             if part)
        system = narration_prompt.system(prompt_library.text(connection, 'story-narrator'), craft, scene=place_text,
                                         persona=who_text, persona_name=name, memory=memory, narration=NARRATION,
                                         intensity=narration_prompt.Intensity.preset(level['preset'], level['voice']),
                                         outcomes=outcomes, rolls_shown=dice_shown(connection))
        if len(system) <= (window - config['max_output_tokens']) * CHARS_PER_TOKEN // 2:
            break
    for extra in (travel.prompt_text(travelled or []), rest.prompt_text(rested or []),
                  injuries.treatment_text(tended or []), happenings.prompt_text(carded or []),
                  beats.cutaway_text(meanwhile or []), *(noted or []), combat.prompt_text(fought or [], connection),
                  counter_text(traded or []), finds.prompt_text(looked or [])):
        if extra:
            system += '\n\n' + extra
    if in_character.out_of_character(latest['text']):
        system += '\n\n' + in_character.OUT_OF_CHARACTER_NOTE.format(name='the narrator', model=default_name(config))
    budget = (window - config['max_output_tokens']) * CHARS_PER_TOKEN - len(system)
    # Older messages are in the summary; the narrator reads the rest word for word.
    chat = model_messages(rows, max(budget, 2000))
    if not in_character.out_of_character(latest['text']):
        chat = steered(chat, authors_note.prompt_text(connection, 'story'))
    return {'system': system, 'messages': chat, 'people': view['people'],
            'city_id': view['city']['id'], 'day': datetime.fromisoformat(view['local_time']).date()}


async def narrate(state, packet: dict, config: dict, active: bool, on_text=None) -> tuple[str, str | None]:
    """The narrator's reply as it is written; `on_text(piece)` gets each piece as it comes, for the stream."""
    guard, text, error = in_character.Guard(active), [], None
    async with state.scheduler.reserve(config, CONVERSATION):
        async for chunk in state.provider.stream(config, key_for(state.vault, config), packet['system'],
                                                        packet['messages']):
            piece = guard.feed(chunk.text)
            text.append(piece)
            if piece and on_text is not None:
                await on_text(piece)
            if chunk.finish_reason == 'content_filter':
                error = INCOMPLETE[chunk.finish_reason]
    text.append(tail := guard.flush())
    if tail and on_text is not None:
        await on_text(tail)
    return ''.join(text).strip(), error


async def complete(state, config: dict, system: str, messages: list[dict]) -> str:
    """One whole reply from the story's model, for the narration's rewrite pass."""
    async with state.scheduler.reserve(config, CONVERSATION):
        return ''.join([chunk.text async for chunk in state.provider.stream(
            config, key_for(state.vault, config), system, messages)])


def counter_turn(state, user: dict, rolls: list[dict]) -> list[str]:
    """The shop's part of the turn (dungeon/inventory.py), decided once: a haggle settled by the player's Allure roll,
    then anything the line buys, at today's price."""
    database = state.database
    with database.connect(write=True) as connection:
        if (kept := optional(connection, 'SELECT lines FROM story_counter WHERE message_id=?', (user['id'],))):
            return decode(kept['lines'])
        view = scene(connection, story_clock.now(connection, database.clock))
        found = shop_view(connection, view)
        if not found or not found['open']:
            return []
        city, shop, day = view['city']['id'], inventory.shop_at(view['city']['id'], view['place']['id']), story_day(view)
        lines = haggle_lines(connection, city, shop, day, rolls, found['keeper_key'])
        stock_rows = inventory.window(connection, city, shop, True, '', day)['stock']
        lines += inventory.buy_in_story(connection, city, shop, user['text'], stock_rows, day, database.now(),
                                        view['data']['currency'])
        connection.execute('INSERT INTO story_counter (message_id, lines) VALUES (?, ?)', (user['id'], encode(lines)))
        return lines


def haggle_lines(connection, city: str, shop: dict, day: str, rolls: list[dict], keeper_key: str) -> list[str]:
    roll = next((roll for roll in rolls if roll['stat'] == 'Allure' and inventory.HAGGLE.search(roll['action'])), None)
    if roll is None:
        return []
    percent = inventory.haggle(connection, city, shop, roll['band'], day)
    if percent is None:
        return ['The shopkeeper has already haggled with the character today and will not move on price again.']
    if roll['band'] == 'success_cost' and keeper_key:
        feelings.change(connection, keeper_key, {'affection': -1}, 'Beat me down on price.')
    return [f"The haggle settles today's prices: {inventory.haggle_text(percent) or 'no change'}."]


def scene_break(connection, user: dict, travelled: list[str], rested: list[str], fought: list[str]) -> str | None:
    """Why the line ends a chapter, if it does: a new place, time passing on the road or in rest, a fight over."""
    now = scene_row(connection)
    if (now['city_id'], now['place_id']) != (user['city_id'], user['place_id']):
        return 'place'
    if travelled or rested:
        return 'time'
    if fought and not combat.fight(connection):
        return 'fight'
    return None


def recall_turn(state, rolls: list[dict]) -> list[str]:
    """A faded detail the line tried to recall (dungeon/remembering.py), brought back to mind on a success."""
    with state.database.connect(write=True) as connection:
        lines = remembering.recalled(connection, rolls)
    return ['## What the character remembers\n' + '\n'.join(lines)] if lines else []


def look_turn(state, user: dict, rolls: list[dict]) -> list[str]:
    """What the line looks into and takes (dungeon/finds.py), decided once, before the narrator describes it."""
    database = state.database
    with database.connect(write=True) as connection:
        if (kept := optional(connection, 'SELECT lines FROM story_looks WHERE message_id=?', (user['id'],))):
            return decode(kept['lines'])
        view = scene(connection, story_clock.now(connection, database.clock))
        city = view['city'] | {'currency': view['data']['currency']}
        lines = finds.look(connection, city, view['place'], user['text'], rolls, getattr(state, 'dice', None),
                           database.now())
        lines += finds.take(connection, city, view['place'], user['text'], database.now())
        connection.execute('INSERT INTO story_looks (message_id, lines) VALUES (?, ?)', (user['id'], encode(lines)))
        return lines


def travel_turn(state, user: dict, rolls: list[dict]) -> list[str]:
    """The journey a line sets out on (dungeon/travel.py), walked once: the roads, the time, the food, where it ends."""
    database = state.database
    with database.connect(write=True) as connection:
        planned = travel.journey(connection, user['id'])
        if planned is None:
            return []
        if planned['lines'] is None:
            planned['lines'] = walk(database, connection, planned, rolls, user['id'])
            connection.execute('UPDATE story_journeys SET lines=? WHERE message_id=?',
                               (encode(planned['lines']), user['id']))
        return planned['lines']


def rest_turn(state, user: dict, rolls: list[dict]) -> list[str]:
    """The rest a line takes (dungeon/rest.py), slept once: the nights, what one turned up, the food, the mending."""
    database = state.database
    with database.connect(write=True) as connection:
        resting = rest.kept(connection, user['id'])
        if resting is None:
            return []
        if resting['lines'] is None:
            resting['lines'] = slept(database, connection, resting, rolls, user['id'], getattr(state, 'dice', None))
            connection.execute('UPDATE story_rests SET lines=? WHERE message_id=?',
                               (encode(resting['lines']), user['id']))
        return resting['lines']


def slept(database, connection, resting: dict, rolls: list[dict], message_id: str, rng=None) -> list[str]:
    if resting.get('fighting'):
        return ["The player's character cannot rest with a fight on their hands."]
    nights, lost, cut_short, happened = rest.night(resting, rolls)
    if resting.get('outside') and not cut_short:
        drawn, _ = life_card(database, connection, 'rest', message_id)
        happened += drawn
        if combat.fight(connection) is not None:
            nights, lost, cut_short = 0, 0, True
            happened.append('The rest ends here, in the dark, with a fight on its hands.')
    hungry = 0
    if resting.get('outside') and nights > 1:
        _, hungry = travel.eat(connection, resting['food'], nights - 1)
    pass_time(database, connection, rest.minutes(nights, cut_short))
    lines = [rest.opening(resting), *happened]
    if hungry:
        lines.append(f"The pack runs out of food: {hungry} hungry day{'s' if hungry > 1 else ''}, and no mending on them.")
    # A night's sleep turns what the character used into growth (dungeon/growth.py).
    grown = growth.grow(connection, database.now(), rng) if nights - lost > 0 else []
    return (lines + combat.mend(connection, nights - lost - hungry) + stress.ease(connection, nights - lost - hungry)
            + grown)


def treat_turn(state, user: dict, rolls: list[dict]) -> list[str]:
    """The treatment a line asks for (dungeon/injuries.py), decided once: a healer's, for a fee, or the character's own."""
    database = state.database
    with database.connect(write=True) as connection:
        if (kept := optional(connection, 'SELECT lines FROM story_treatments WHERE message_id=?', (user['id'],))):
            return decode(kept['lines'])
        view = scene(connection, story_clock.now(connection, database.clock))
        lines = injuries.treat(connection, user['text'], view['people'], rolls, view['data']['currency'],
                               getattr(state, 'dice', None))
        if lines:
            connection.execute('INSERT INTO story_treatments (message_id, lines) VALUES (?, ?)',
                               (user['id'], encode(lines)))
        return lines


def walk(database, connection, planned: dict, rolls: list[dict], message_id: str) -> list[str]:
    travel_map, start = travel.find(planned['from'])
    if planned.get('unknown'):
        return [f"The player's character does not know the way to {travel.nodes(travel_map)[planned['to']]['name']}: "
                'it is on no road they know of, and nobody has told them how to get there.']
    legs, happened = travel.travelled(planned, rolls)
    spent, nights, days = travel.minutes(legs, travel_map['hours_a_day'])
    eaten, hungry = travel.eat(connection, travel_map['food'], days)
    pass_time(database, connection, spent)
    for leg in legs:
        travel.visit(connection, travel_map, leg['from'])
        travel.visit(connection, travel_map, leg['to'])
    end = travel.nodes(travel_map)[legs[-1]['to']]
    place_scene(connection, end['city'], end['place'], database.now())
    add(connection, database.now(), 'scene', f"You arrive at {end['name']}.", scene_row(connection))
    # Signs warn when the road ends somewhere above the character (dungeon/tiers.py).
    found = happenings.where(end['city'], end['place'])
    happened += [warned] if found and (warned := tiers.warning(connection, found)) else []
    if not any(travel.STOPPED in line for line in happened):
        drawn, minutes = life_card(database, connection, 'road', message_id)
        happened += drawn
        pass_time(database, connection, minutes)
    return travel.lines_for(travel_map, legs, nights, eaten, hungry) + happened


def life_card(database, connection, kind: str, message_id: str) -> tuple[list[str], int]:
    """A Life Card draw for the line where the scene is now (dungeon/happenings.py), kept with it; what the
    narrator is told and the minutes it costs."""
    view = scene(connection, story_clock.now(connection, database.clock))
    data, day = view['data'], datetime.fromisoformat(view['local_time']).date()
    drawn = happenings.draw(connection, kind, f'{message_id}:{kind}', view['city']['id'], view['place']['id'], data,
                            intensity(connection, data)['preset'], day)
    persona = optional(connection, 'SELECT name FROM persona WHERE id=1')
    lines, minutes = happenings.play(connection, drawn, {
        'people': view['people'], 'name': persona and persona['name'], 'data': data, 'map': drawn['map'],
        'now': story_clock.now(connection, database.clock), 'logged': database.now(),
        'rng': None, 'preset': intensity(connection, data)['preset']}) if drawn else ([], 0)
    happenings.keep(connection, message_id, kind, day, drawn and drawn['card']['id'], lines)
    return lines, minutes


def town_turn(state, user: dict) -> list[str]:
    """A day in town draws a Life Card once, on the first line of the story day there."""
    database = state.database
    with database.connect(write=True) as connection:
        kept = many(connection, "SELECT lines FROM story_cards WHERE message_id=? AND scene IN ('news', 'town') "
                                "ORDER BY scene", (user['id'],))
        if kept:
            return [line for row in kept for line in decode(row['lines'])]
        view = scene(connection, story_clock.now(connection, database.clock))
        found = happenings.where(view['city']['id'], view['place']['id'])
        day = datetime.fromisoformat(view['local_time']).date()
        if not found or not found['town'] or combat.fight(connection):
            return []
        # The news among the powers since the character was last in a town (dungeon/factions.py).
        # And the word about the people they know (dungeon/beats.py).
        lines = factions.news(connection, found['world'], database.now()) + beats.heard(
            connection, story_clock.now(connection, database.clock), database.now())
        if lines:
            happenings.keep(connection, user['id'], 'news', day, None, lines)
        if not happenings.drawn_today(connection, 'town', day):
            drawn, minutes = life_card(database, connection, 'town', user['id'])
            # A faction holding the town may need something done (dungeon/jobs.py).
            work = jobs.offer(connection, found['world'], found['node'], view['city']['id'],
                              happenings.wage(view['data']), view['data']['currency'],
                              story_clock.now(connection, database.clock), getattr(state, 'dice', None),
                              looking=jobs.seeking(user['text']))
            if work:
                happenings.keep(connection, user['id'], 'news', day, None, lines + work)
            lines += drawn + work
            pass_time(database, connection, minutes)
        elif jobs.seeking(user['text']):
            # Going looking for work finds it at the character's tier or below, any line (dungeon/jobs.py).
            work = jobs.offer(connection, found['world'], found['node'], view['city']['id'],
                              happenings.wage(view['data']), view['data']['currency'],
                              story_clock.now(connection, database.clock), getattr(state, 'dice', None), looking=True)
            if work:
                happenings.keep(connection, user['id'], 'news', day, None, lines + work)
            lines += work
        return lines


def director_turn(state, user: dict) -> list[str]:
    """The director's hidden note for the line (dungeon/director.py), written once and kept with it."""
    database = state.database
    with database.connect(write=True) as connection:
        kept = optional(connection, "SELECT lines FROM story_cards WHERE message_id=? AND scene='director'",
                        (user['id'],))
        if kept:
            return decode(kept['lines'])
        now = story_clock.now(connection, database.clock)
        view = scene(connection, now)
        found = happenings.where(view['city']['id'], view['place']['id'])
        text = director.note(connection, found['world'], found['node'], view['people'],
                             happenings.drama(connection, view['data']), now) if found else ''
        happenings.keep(connection, user['id'], 'director', datetime.fromisoformat(view['local_time']).date(), None,
                        [text] if text else [])
        return [text] if text else []


def beats_turn(state, user: dict) -> list[str]:
    """The lives going on off the page (dungeon/beats.py), once for each line; the cutaways the narrator may show."""
    database = state.database
    with database.connect(write=True) as connection:
        kept = beats.saved(connection, user['id'])
        if kept is not None:
            return kept
        now = story_clock.now(connection, database.clock)
        view = scene(connection, now)
        lines = beats.fire(connection, user['id'], view, intensity(connection, view['data'])['preset'], now,
                           database.now(), getattr(state, 'dice', None))
        beats.keep(connection, user['id'], datetime.fromisoformat(view['local_time']).date(), lines)
        return lines


def counter_text(lines: list[str]) -> str:
    return '## At the counter (decided by the game)\n' + '\n'.join(f'- {line}' for line in lines) if lines else ''


def fight_round(state, user: dict, rolls: list[dict]) -> list[str]:
    """The fight's part of the turn (dungeon/combat.py): a fight the player starts or a danger brings, one round."""
    database = state.database
    with database.connect(write=True) as connection:
        view = scene(connection, story_clock.now(connection, database.clock))
        bitten = next((roll for roll in rolls if roll.get('threat') and roll['band'] in quests.BITES), None)
        foe = quests.foe_for(user['city_id'], user['place_id'], bitten['threat']) if bitten else None
        sent = ''
        if bitten and foe is None and (foe := travel.foe_for(bitten['threat'])):
            # A road's foes are at its region's tier, or sent by an enemy above it (dungeon/tiers.py).
            found = happenings.where(view['city']['id'], view['place']['id'])
            foe, sent = tiers.foe(connection, found, foe, found['tier']) if found else (foe, '')
        moment = story_clock.now(connection, database.clock)
        def aftermath(events):
            # What the fight did to the character, and what it left between them and a foe (dungeon/director.py).
            director.history(connection, events, moment, database.now(), getattr(state, 'dice', None))
            return stress.aftermath(connection, moment, events, getattr(state, 'dice', None), database.now())

        fought = combat.turn(connection, user['id'], view['people'], rolls, foe,
                             inventory.carried(connection, view['city']['id']), getattr(state, 'dice', None),
                             database.now(), aftermath)
        return ([sent] if sent else []) + fought


class After:
    """What a turn still does once its reply is on screen (dungeon/pace.py): fact extraction and the summary. It runs
    once, after the response or, if the next turn comes first, at the start of that turn."""

    def __init__(self, work):
        self.work, self.started, self.done = work, False, None

    async def run(self):
        if self.started:
            if self.done is not None:
                await self.done.wait()
            return
        self.started, self.done = True, asyncio.Event()
        try:
            await self.work()
        finally:
            self.done.set()


async def settled(state):
    """The last turn's after-work, finished before a new turn starts."""
    if (after := getattr(state, 'after_turn', None)) is not None:
        await after.run()


async def rolled(state, user: dict, steps: pace.Steps) -> list[dict]:
    """The turn's rolls: kept from an earlier telling, or decided now (obvious lines skip the Referee's model)."""
    database = state.database
    with database.connect() as connection:
        rolls, judge = turn.saved(connection, user['id']), referee.own_model(connection)
    if rolls:
        return rolls
    since = steps.clock()
    actions = await referee.decide(state, user['text'], None if pace.obvious(user['text']) else judge)
    steps.timed('referee', since)
    if hazard := quests.danger_action(user['city_id'], user['place_id'], getattr(state, 'dice', None)):
        actions = [*actions, hazard]
    with database.connect(write=True) as connection:
        if road := travel.decide(connection, user['id'], user['city_id'], user['place_id'], user['text'],
                                 getattr(state, 'dice', None)):
            actions = [*actions, road]
        if camp := rest.decide(connection, user['id'], user['city_id'], user['place_id'], user['text'],
                               getattr(state, 'dice', None)):
            actions = [*actions, camp]
        moment = story_clock.now(connection, database.clock)
        if mend := injuries.decide(connection, user['text'], scene(connection, moment)['people']):
            actions = [*actions, mend]
        if memory := remembering.recall_action(connection, user['text']):
            # The recall roll is the line's Mind roll; the Referee's own is dropped for it.
            actions = [*(action for action in actions if action['stat'] != 'Mind'), memory]
        actions = injuries.adjust(connection, combat.adjust(connection, feelings.adjust(connection, actions)), moment)
        return turn.saved(connection, user['id']) or turn.store(connection, user['id'], actions, database.now(),
                                                                getattr(state, 'dice', None))


async def told(state, packet: dict, config: dict, in_story: bool, steps: pace.Steps,
               on_text) -> tuple[str, str | None, list[dict]]:
    """The narration, then (time allowing) the prose rewrite and, only when it names the dead, the contradiction check;
    with what the checks left in it, flagged for the player to rewrite (dungeon/passages.py)."""
    since = steps.clock()
    try:
        text, error = await narrate(state, packet, config, in_story, on_text)
    except DomainError as failure:
        text, error = '', failure.message
    steps.timed('narrator', since)
    if not text or error or not in_story:
        return text, error, []
    rewrite = lambda system, messages: complete(state, config, system, messages)  # noqa: E731
    since, timely = steps.clock(), steps.has_time()
    text, _ = await prose.polish(text, rewrite if timely else None)
    if timely:
        steps.timed('rewrite', since)
    else:
        steps.skip('rewrite')
    with state.database.connect() as connection:
        names = pace.named_dead(record.dead(connection), text)
        checking = bool(settings(connection)['contradiction_check'])
    unchecked = []
    if names and checking and steps.has_time():
        since = steps.clock()
        text = await pace.contradiction(text, names, rewrite)
        steps.timed('contradiction', since)
    elif names:
        # Skipped for time, or by the player's setting: the passage is flagged for them to rewrite instead.
        steps.skip('contradiction')
        unchecked = names
    with state.database.connect() as connection:
        return text, None, passages.flags(text, passages.dead_reasons(connection, unchecked))


async def afterwards(state, user: dict, reply: dict, packet: dict, steps: pace.Steps):
    """Fact extraction and the summary, once the reply is on screen; a failure here never loses the turn."""
    database = state.database
    try:
        since = steps.clock()
        with database.connect() as connection:
            there = [{'key': row['key'], 'name': row['name']} for row in feelings.met(connection)
                     if row['key'] in {person['sheet']['key'] for person in packet['people']}]
            ask = (quests.ending_ask(connection) + quests.oath_ask() + feelings.feelings_ask(there)
                   + growth.dark_ask())
            extra = (quests.ending_schema(connection) | quests.OATH_SCHEMA | feelings.feelings_schema(there)
                     | growth.dark_schema())
        answered = await record.extract(state, user['text'], reply, ask, extra)
        with database.connect(write=True) as connection:
            for item in quests.endings(answered):
                quests.end(connection, item['id'], item['status'], item['outcome'], database.now())
                chapters.mark(connection, 'quest')
            # What the character did that feeds a dark track (dungeon/growth.py).
            for track in growth.darkened(answered):
                view = scene(connection, story_clock.now(connection, database.clock))
                growth.darken(connection, track, 1, intensity(connection, view['data'])['preset'], database.now(),
                              getattr(state, 'dice', None))
            # An oath the character swore is an obligation, with its deadline (dungeon/quests.py).
            for oath in quests.oaths(answered):
                quests.swear(connection, user['city_id'], oath, story_clock.now(connection, database.clock))
            feelings.from_answer(connection, answered, {person['key'] for person in there})
        steps.timed('extraction', since)
        since = steps.clock()
        with database.connect() as connection:
            rows = messages(connection)
        await record.fold(state, rows)
        await chapters.summarize(state)
        steps.timed('summary', since)
        with database.connect(write=True) as connection:
            if optional(connection, 'SELECT 1 FROM story_messages WHERE id=?', (user['id'],)):
                pace.save(connection, user['id'], steps)
    except Exception:  # noqa: BLE001 - facts missed are better than a story that stops
        log.exception('After the turn')


async def no_event(_event: dict):
    pass


async def answer(state, user: dict, on_text=None, on_event=None) -> dict:
    """The narrator's reply to the user's message, saved complete or failed with the reason. Fact extraction and the
    summary are left for `state.after_turn`, run once the reply is on screen (dungeon/pace.py). `on_event(event)` hears
    the turn's stages as they happen, for the stream: reading the line, the actions and each roll, then writing; with
    the dice hidden, only what was tried and with which stat (dungeon/turn.py)."""
    emit = on_event or no_event
    database = state.database
    in_story = not in_character.out_of_character(user['text'])
    # No model fails the turn before it says it has begun.
    with database.connect() as connection:
        if config_for(connection, JOB) is None:
            raise no_model()
    if in_story:
        await emit({'stage': 'reading'})
    await settled(state)
    with database.connect() as connection:
        config = config_for(connection, JOB)
        if config is None:
            raise no_model()
        steps = pace.Steps(pace.budget_for(connection, config), getattr(state, 'pace_clock', None) or time.monotonic)
    rolls = await rolled(state, user, steps) if in_story else []
    if rolls:
        with database.connect() as connection:
            shown = dice_shown(connection)
        await emit({'actions': turn.announced(rolls, shown)} | ({'bands': turn.bands()} if shown else {}))
        for roll in rolls:
            await emit({'roll': turn.shown(roll) if shown else turn.hidden(roll)})
    travelled = travel_turn(state, user, rolls) if in_story else []
    rested = rest_turn(state, user, rolls) if in_story else []
    carded = town_turn(state, user) if in_story else []
    meanwhile = beats_turn(state, user) if in_story else []
    noted = director_turn(state, user) + recall_turn(state, rolls) if in_story else []
    fought = fight_round(state, user, rolls) if in_story else []
    traded = counter_turn(state, user, rolls) if in_story else []
    tended = treat_turn(state, user, rolls) if in_story else []
    looked = look_turn(state, user, rolls) if in_story else []
    with database.connect() as connection:
        packet = prompt(connection, story_clock.now(connection, database.clock), config, user,
                        turn.outcomes(rolls) if in_story else None, fought, traded, looked, travelled, rested, tended, carded,
                        meanwhile, noted)
    await emit({'stage': 'writing'})
    text, error, flagged = await told(state, packet, config, in_story, steps, on_text)
    status = 'complete' if text and not error else 'failed'
    error = None if status == 'complete' else error or 'The model returned no story text.'
    with database.connect(write=True) as connection:
        connection.execute("DELETE FROM story_messages WHERE reply_to=? AND status='failed'", (user['id'],))
        if status == 'complete' and in_story:
            story_people.note_exchange(connection, packet['people'], packet['city_id'], user['text'], text,
                                       database.now(), packet['day'])
            feelings.from_rolls(connection, rolls)
            growth.mark(connection, rolls, user['id'])
            remembering.refresh(connection, f"{user['text']}\n{text}")
            if reason := scene_break(connection, user, travelled, rested, fought):
                chapters.mark(connection, reason)
            # What the line touched in the GM's notebook, and the scene's kind (dungeon/director.py).
            if found := happenings.where(packet['city_id'], scene_row(connection)['place_id']):
                director.touch(connection, found['world'], f"{user['text']}\n{text}",
                               director.scene_kind(rolls, fought, packet['people']), user['id'], database.now())
        reply = add(connection, database.now(), 'narrator', text, scene_row(connection), reply_to=user['id'],
                    status=status, error=error,
                    flags=flagged)
        pace.save(connection, user['id'], steps)
    if status == 'complete' and in_story:
        state.after_turn = After(lambda: afterwards(state, user, reply, packet, steps))
    return reply


def received(database, text: str, client_id: str) -> tuple[dict, dict | None]:
    """The user's message, saved once whatever retries come; with the narrator's reply if it already has one."""
    with database.connect(write=True) as connection:
        user = optional(connection, 'SELECT * FROM story_messages WHERE client_id=?', (client_id,))
        if user is None:
            after = ' In Ironman, that is final: start a new story.' if chapters.ironman(connection) else \
                ' Go back to an earlier line to play on.'
            require(not combat.condition(connection)['dead'], 'Your character is dead.' + after, 409)
            require(not growth.lost(connection), f'Your character is lost to {growth.lost(connection)}.' + after, 409)
            user = add(connection, database.now(), 'user', text, scene_row(connection), client_id=client_id)
            timeline.save(connection, user['id'])
            # A break left pending by the last line opens a new chapter with this one (dungeon/chapters.py).
            chapters.arrive(connection, user, database.now())
            # The time the line takes passes as it is sent: the narrator writes the scene after it.
            if not in_character.out_of_character(text):
                # A rest passes its own nights (dungeon/rest.py).
                pass_time(database, connection, 0 if rest.resting(text) else
                          story_clock.minutes_for(text, bool(referee.by_keywords(text))))
        reply = optional(connection, "SELECT * FROM story_messages WHERE reply_to=? AND status='complete'",
                         (user['id'],))
        return user, reply


async def send(state, text: str, client_id: str, on_text=None, on_event=None) -> dict:
    user, reply = received(state.database, text, client_id)
    return {'message': user, 'reply': reply or await answer(state, user, on_text, on_event)}


async def retry(state, on_text=None, on_event=None) -> dict:
    """Tell the last part again: a new reply to the user's latest message, replacing the one there."""
    await settled(state)
    with state.database.connect(write=True) as connection:
        where, values = timeline.visible(connection)
        user = optional(connection, f"SELECT * FROM story_messages WHERE role='user' AND {where} ORDER BY seq DESC "
                                    'LIMIT 1', values)
        # A line from before going back is shared with the branch it came from; its reply stays as it was told.
        require(user is not None and user['branch_id'] == timeline.active(connection),
                'There is nothing to retell yet.', 409)
        # The facts the old reply brought in go with it.
        connection.execute('DELETE FROM record_entries WHERE message_id IN (SELECT id FROM story_messages WHERE '
                           'reply_to=?)', (user['id'],))
        connection.execute('DELETE FROM story_messages WHERE reply_to=?', (user['id'],))
        # So are the meetings and feelings it moved; the kept rolls move them again.
        timeline.restore_at(connection, user['id'], ('story_people',))
    return {'message': user, 'reply': await answer(state, user, on_text, on_event)}


# Rewrite -----------------------------------------------------------------------------------------

def narration(connection, message_id: str) -> dict:
    """A narration the player may reword: told in the branch being played, so no other branch shares it."""
    where, values = timeline.visible(connection)
    row = optional(connection, f"SELECT * FROM story_messages WHERE id=? AND role='narrator' AND status='complete' "
                               f'AND {where}', (message_id, *values))
    require(row is not None, 'That part of the story is not there to rewrite.', 404)
    require(row['branch_id'] == timeline.active(connection),
            'That part comes from before you went back, and another branch shares it, so it stays as it was.', 409)
    return row


def reworded(state, connection, row: dict, text: str, flagged: list[dict], previous: dict | None):
    """The narration's new wording saved, and its facts taken again from it once the reply is back (the facts the
    old wording brought in go with it)."""
    connection.execute('UPDATE story_messages SET text=?, flags=?, previous=? WHERE id=?',
                       (text, encode(flagged), encode(previous) if previous else None, row['id']))
    connection.execute("DELETE FROM record_entries WHERE message_id=? AND source='narrator'", (row['id'],))
    user = optional(connection, 'SELECT * FROM story_messages WHERE id=?', (row['reply_to'],))
    if user is not None:
        state.after_turn = After(lambda: record.extract(state, user['text'], {'id': row['id'], 'text': text}))


async def rewritten(state, message_id: str, passage: str, note: str = '') -> dict:
    """A passage of a narration in new words (dungeon/passages.py): the dice and the record's facts stay."""
    await settled(state)
    database = state.database
    with database.connect() as connection:
        row, config = narration(connection, message_id), config_for(connection, JOB)
        if config is None:
            raise no_model()
        where = passages.span(row['text'], passage)
        require(where is not None, 'Select a passage of this part of the story to rewrite.', 422)
        system = '\n\n'.join(part for part in (passages.SYSTEM, record.prompt_text(connection)) if part)
    before, flagged = row['text'][where[0]:where[1]], decode(row['flags'])
    revised = prose.without_dashes((await complete(
        state, config, system, passages.request(row['text'], before, flagged, note))).strip())
    require(prose.acceptable(before, revised), 'The rewrite came back too different, so the passage stays as it was. '
                                               'Try again.', 502)
    text = row['text'][:where[0]] + revised + row['text'][where[1]:]
    with database.connect(write=True) as connection:
        dead, kept = passages.still_dead(flagged, text)
        reworded(state, connection, row, text, passages.flags(text, dead, kept),
                 {'text': row['text'], 'flags': flagged})
    return story(database)


async def switched(state, message_id: str) -> dict:
    """A rewritten narration back to its wording before the rewrite; switching again brings the rewrite back."""
    await settled(state)
    database = state.database
    with database.connect(write=True) as connection:
        row = narration(connection, message_id)
        require(row['previous'] is not None, 'That part has not been rewritten.', 409)
        previous = decode(row['previous'])
        reworded(state, connection, row, previous['text'], previous['flags'],
                 {'text': row['text'], 'flags': decode(row['flags'])})
    return story(database)
