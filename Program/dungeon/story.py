"""Story mode: free-form roleplay with a narrator around the cities (docs/story.md).

The story has its own scene (`story_scene`: the city and place the user is at) and its own history
(`story_messages`).

The app decides the scene from the city data and the townsfolk rules: the place, the local time and
weather, and who is there at that hour. The narrator model only voices it. Moving somewhere else is the
user's choice in the place picker, not the model's.
"""
from datetime import datetime

from dungeon import authors_note, in_character, ledger, prompt_library, referee, safety, story_people, timeline, turn
from dungeon.authors_note import NOTE_CLOSE
from dungeon.clock import zone
from dungeon.database import identifier, many, one, optional, settings
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
DEFAULT_CITY = 'haddon-harbor'
HISTORY_LIMIT = 200
CHARS_PER_TOKEN = 4
# The kinds a story starts at when nothing else is chosen: somewhere people sit and talk.
OPENING_KINDS = ('cafe', 'tavern', 'bar', 'restaurant', 'market', 'park')

# Story mode's player has no persona yet, so the narrator speaks to them as "you", as Story mode always has.
NARRATION = narration_prompt.Format(pov='second', tense='present', length='short')


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
    """Where the story is; a new story starts in Haddon Harbor, the shipped city, at a cafe. A place or city that
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
    people, seen = [], set()
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


def person_line(person: dict, place: dict, data: dict, known: dict | None = None) -> str:
    sheet = person['sheet']
    seen = who(sheet, place, data, person['doing'])
    pronouns = f", {sheet['pronouns']}" if sheet.get('pronouns') else ''
    job = sheet.get('occupation') or sheet['role']
    # "working as the owner" already says the job: no "working as the owner, owner."
    job = '' if f' {job}' in f" {person['doing']}" else f', {job}'
    return (f"- {seen[0].upper()}{seen[1:]}: {sheet['full']}{pronouns}, {sheet['age']}, {person['doing']}{job}. "
            f"{townsfolk.first_impression(sheet).capitalize()}; "
            f"{sheet['quirk']}.{life_text(data, sheet)} Mood: {person['mood']}.{story_people.remembered(known)}"
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
    lines += [person_line(person, {'id': place['id']}, data, view['known'].get(person['sheet']['key']))
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


# History ------------------------------------------------------------------------------------------

def next_seq(connection) -> int:
    return one(connection, 'SELECT COALESCE(MAX(seq), 0) + 1 AS seq FROM story_messages')['seq']


def add(connection, now: str, role: str, text: str, where: dict, **extra) -> dict:
    message_id = identifier()
    connection.execute(
        'INSERT INTO story_messages (id, seq, role, text, client_id, reply_to, status, error, city_id, place_id, '
        'created_at, branch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (message_id, next_seq(connection), role, text, extra.get('client_id'), extra.get('reply_to'),
         extra.get('status', 'complete'), extra.get('error'), where['city_id'], where['place_id'], now,
         timeline.active(connection)))
    return one(connection, 'SELECT * FROM story_messages WHERE id=?', (message_id,))


def messages(connection, limit: int = HISTORY_LIMIT) -> list[dict]:
    where, values = timeline.visible(connection)
    rows = many(connection, 'SELECT id, seq, role, text, reply_to, status, error, city_id, place_id, created_at '
                f'FROM story_messages WHERE {where} ORDER BY seq DESC LIMIT ?', (*values, limit))
    # The app's crisis note under a user's line that sounds like self-harm (dungeon/safety.py).
    return [{**row, 'crisis_help': row['role'] == 'user' and safety.crisis(row['text'])} for row in reversed(rows)]


def dice_shown(connection) -> bool:
    """Roll visibility (Settings > World > Hidden values): hidden unless the player shows them."""
    return bool(settings(connection)['show_odds'])


def with_rolls(connection, rows: list[dict]) -> list[dict]:
    """The rolls under each of the player's lines, only while the dice are shown; hidden dice never leave the app."""
    if not dice_shown(connection):
        return rows
    return [{**row, 'rolls': [turn.shown(roll) for roll in turn.saved(connection, row['id'])]}
            if row['role'] == 'user' else row for row in rows]


def story(database) -> dict:
    with database.connect() as connection:
        view = scene(connection, database.clock.now())
        return {'scene': scene_view(view), 'messages': with_rolls(connection, messages(connection)),
                'people': people(connection, view), 'ready': config_for(connection, JOB) is not None,
                'dice_shown': dice_shown(connection), 'branches': timeline.branches(connection)}


def back(database, message_id: str) -> dict:
    """Go back to before one of the player's lines; the line comes back as a draft to send again, with new dice."""
    with database.connect(write=True) as connection:
        line = timeline.back(connection, message_id, database.now())
    return story(database) | {'draft': line['text']}


def switch_branch(database, branch_id: str) -> dict:
    with database.connect(write=True) as connection:
        timeline.switch(connection, branch_id, database.now())
    return story(database)


def people(connection, view: dict) -> list[dict]:
    """Everyone the user has met in the story, most recent first, with where their rules put them now."""
    result, cities = [], {}
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
                       'place': now['place'] and {'id': now['place']['id'], 'name': now['place']['name'],
                                                  'city_id': data['id']}})
    return result


def find(database, key: str) -> dict:
    """Go to where someone the user has met is right now."""
    with database.connect() as connection:
        view = scene(connection, database.clock.now())
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
        if scene_row(connection) != {'city_id': data['id'], 'place_id': place['id']}:
            connection.execute(
                'INSERT INTO story_scene (id, city_id, place_id, updated_at) VALUES (1, ?, ?, ?) ON CONFLICT(id) DO '
                'UPDATE SET city_id=excluded.city_id, place_id=excluded.place_id, updated_at=excluded.updated_at',
                (data['id'], place['id'], database.now()))
            arrive(connection, database.now())
    return story(database)


def arrive(connection, now: str) -> dict:
    """The line that opens a scene: "You arrive at …", where the scene is now."""
    row = scene_row(connection)
    data = city_data(connection, row['city_id'])
    place = catalog.find(data, row['place_id'])
    hood = townsfolk.neighborhood_name(data, place['neighborhood'])
    return add(connection, now, 'scene', f"You arrive at {place['name']}, {hood}, {data['name']}.", row)


def clear(database) -> dict:
    """A new story: the history, the people met and the ledger go, the scene stays where it is."""
    with database.connect(write=True) as connection:
        connection.execute('DELETE FROM story_messages')
        connection.execute('DELETE FROM story_people')
        for table in ('ledger_entries', 'ledger_corrections', 'story_summary'):
            connection.execute(f'DELETE FROM {table}')
        timeline.clear(connection)
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


def prompt(connection, now: datetime, config: dict, latest: dict, outcomes: list[dict] | None = None) -> dict:
    view = scene(connection, now)
    craft = narration_prompt.craft_for(config.get('context_tokens'), prompt_library.text(connection, 'narrator-craft'))
    who_text, name = persona_text(connection)
    memory = '\n\n'.join(part for part in (ledger.summary_text(connection), ledger.prompt_text(connection)) if part)
    system = narration_prompt.system(prompt_library.text(connection, 'story-narrator'), craft, scene=scene_text(view),
                                     persona=who_text, persona_name=name, memory=memory, narration=NARRATION,
                                     outcomes=outcomes, rolls_shown=dice_shown(connection))
    if in_character.out_of_character(latest['text']):
        system += '\n\n' + in_character.OUT_OF_CHARACTER_NOTE.format(name='the narrator', model=default_name(config))
    budget = (config['context_tokens'] - config['max_output_tokens']) * CHARS_PER_TOKEN - len(system)
    # Older messages are in the summary; the narrator reads the rest word for word.
    after = ledger.summary(connection)['through_seq']
    rows = [row for row in messages(connection) if after < row['seq'] <= latest['seq']]
    chat = model_messages(rows, max(budget, 2000))
    if not in_character.out_of_character(latest['text']):
        chat = steered(chat, authors_note.prompt_text(connection, 'story'))
    return {'system': system, 'messages': chat, 'people': view['people'],
            'city_id': view['city']['id'], 'day': datetime.fromisoformat(view['local_time']).date()}


async def narrate(state, packet: dict, config: dict, active: bool) -> tuple[str, str | None]:
    guard, text, error = in_character.Guard(active), [], None
    async with state.scheduler.reserve(config, CONVERSATION):
        async for chunk in state.provider.stream(config, key_for(state.vault, config), packet['system'],
                                                        packet['messages']):
            text.append(guard.feed(chunk.text))
            if chunk.finish_reason == 'content_filter':
                error = INCOMPLETE[chunk.finish_reason]
    text.append(guard.flush())
    return ''.join(text).strip(), error


async def complete(state, config: dict, system: str, messages: list[dict]) -> str:
    """One whole reply from the story's model, for the narration's rewrite pass."""
    async with state.scheduler.reserve(config, CONVERSATION):
        return ''.join([chunk.text async for chunk in state.provider.stream(
            config, key_for(state.vault, config), system, messages)])


async def answer(state, user: dict) -> dict:
    """The narrator's reply to the user's message, saved complete or failed with the reason."""
    database = state.database
    in_story = not in_character.out_of_character(user['text'])
    with database.connect() as connection:
        config = config_for(connection, JOB)
        if config is None:
            raise no_model()
        rolls, judge = turn.saved(connection, user['id']), referee.own_model(connection)
    if in_story and not rolls:
        actions = await referee.decide(state, user['text'], judge)
        with database.connect(write=True) as connection:
            rolls = turn.saved(connection, user['id']) or turn.store(connection, user['id'], actions, database.now(),
                                                                       getattr(state, 'dice', None))
    with database.connect() as connection:
        packet = prompt(connection, database.clock.now(), config, user, turn.outcomes(rolls) if in_story else None)
    try:
        text, error = await narrate(state, packet, config, in_story)
    except DomainError as failure:
        text, error = '', failure.message
    if text and not error and in_story:
        text, _ = await prose.polish(text, lambda system, messages: complete(state, config, system, messages))
    status = 'complete' if text and not error else 'failed'
    error = None if status == 'complete' else error or 'The model returned no story text.'
    with database.connect(write=True) as connection:
        connection.execute("DELETE FROM story_messages WHERE reply_to=? AND status='failed'", (user['id'],))
        if status == 'complete' and not in_character.out_of_character(user['text']):
            story_people.note_exchange(connection, packet['people'], packet['city_id'], user['text'], text,
                                       database.now(), packet['day'])
        reply = add(connection, database.now(), 'narrator', text, user, reply_to=user['id'], status=status, error=error)
    if status == 'complete' and in_story:
        await ledger.extract(state, user['text'], reply)
        with database.connect() as connection:
            rows = messages(connection)
        await ledger.fold(state, rows)
    return reply


def record(database, text: str, client_id: str) -> tuple[dict, dict | None]:
    """The user's message, saved once whatever retries come; with the narrator's reply if it already has one."""
    with database.connect(write=True) as connection:
        user = optional(connection, 'SELECT * FROM story_messages WHERE client_id=?', (client_id,))
        if user is None:
            user = add(connection, database.now(), 'user', text, scene_row(connection), client_id=client_id)
            timeline.save(connection, user['id'])
        reply = optional(connection, "SELECT * FROM story_messages WHERE reply_to=? AND status='complete'",
                         (user['id'],))
        return user, reply


async def send(state, text: str, client_id: str) -> dict:
    user, reply = record(state.database, text, client_id)
    return {'message': user, 'reply': reply or await answer(state, user)}


async def retry(state) -> dict:
    """Tell the last part again: a new reply to the user's latest message, replacing the one there."""
    with state.database.connect(write=True) as connection:
        where, values = timeline.visible(connection)
        user = optional(connection, f"SELECT * FROM story_messages WHERE role='user' AND {where} ORDER BY seq DESC "
                                    'LIMIT 1', values)
        # A line from before going back is shared with the branch it came from; its reply stays as it was told.
        require(user is not None and user['branch_id'] == timeline.active(connection),
                'There is nothing to retell yet.', 409)
        # The facts the old reply brought in go with it.
        connection.execute('DELETE FROM ledger_entries WHERE message_id IN (SELECT id FROM story_messages WHERE '
                           'reply_to=?)', (user['id'],))
        connection.execute('DELETE FROM story_messages WHERE reply_to=?', (user['id'],))
    return {'message': user, 'reply': await answer(state, user)}
