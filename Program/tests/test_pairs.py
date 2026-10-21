"""Closeness between people: two-way stages worked out from shared history (dungeon/memory/pairs.py)."""
import json
from datetime import timedelta

import pytest
from companions import by_speaker, companion_named, ok
from test_cast import met_someone

from dungeon.characters import by_id, insert_version
from dungeon.database import identifier
from dungeon.life import body, encounters
from dungeon.memory import closeness as own
from dungeon.memory import pairs
from dungeon.models import CharacterDefinition


@pytest.fixture(autouse=True)
def unmasked(monkeypatch):
    """Dungeon ids are random, so whether someone's mask keeps a person a step further is too; only the test
    about masks lets it happen."""
    monkeypatch.setattr(pairs, 'MASK_CHANCE', 0)


@pytest.fixture
def cast(client, companion, connected, provider):
    """Mira (the main character), Billy and Sally, with replies that name their speaker."""
    provider.respond = by_speaker
    return {'Mira': companion['id'], 'Billy': companion_named(client, 'Billy Hart'),
            'Sally': companion_named(client, 'Sally Moss')}


@pytest.fixture
def chatty(monkeypatch):
    """Meetings around town happen whenever they can (tests/test_cast.py)."""
    monkeypatch.setattr(body, 'state_on', lambda *_args: None)
    monkeypatch.setattr(encounters, 'ACTIVE', True)
    monkeypatch.setattr(encounters, 'CHANCE', 1)
    monkeypatch.setattr(encounters, 'FAMILIAR_CHANCE', 1)


def key(companion_id: str) -> str:
    return pairs.companion_key(companion_id)


def stage(client, a: str, b: str) -> int | None:
    database = client.app.state.database
    with database.connect() as connection:
        return pairs.closeness(connection, a, b, database.clock.now())


def edit(client, companion_id: str, **changes):
    """A new version of a companion's sheet with these fields changed."""
    database = client.app.state.database
    with database.connect(write=True) as connection:
        found = by_id(connection, companion_id)
        definition = CharacterDefinition.model_validate({**found['version']['definition'], **changes})
        version_id = insert_version(connection, companion_id, found['version']['number'] + 1, definition, '',
                                    database.now())
        connection.execute('UPDATE companions SET active_version_id=? WHERE id=?', (version_id, companion_id))


def test_circle_roles_start_where_people_already_are_with_a_stable_nudge():
    family = [pairs.role_default('sister', f'circle:t:{n}')['level'] for n in range(200)]
    assert min(family) == 2 and max(family) == 4 and family.count(3) > 60
    close = [pairs.role_default('close friend', f'circle:t:{n}')['level'] for n in range(200)]
    assert set(close) == {3, 4} and close.count(4) > close.count(3)
    assert {pairs.role_default('coworker', f'circle:t:{n}')['level'] for n in range(200)} == {2, 3}
    assert pairs.role_default('mom', 'circle:t:7') == pairs.role_default('mom', 'circle:t:7')
    assert pairs.role_default('someone odd', 'circle:t:1')['level'] == 1
    # A grandparent starts with the family, never "Just met".
    for role in ('grandmother', 'grandfather', 'grandparent'):
        assert [pairs.role_default(role, f'circle:t:{n}')['level'] for n in range(200)] == \
            [pairs.role_default('mom', f'circle:t:{n}')['level'] for n in range(200)]


def test_gentle_cooling_follows_the_companions_own_switch(client, cast, clock):
    billy, sally = key(cast['Billy']), key(cast['Sally'])
    database = client.app.state.database
    with database.connect(write=True) as connection:
        pairs.tell(connection, billy, sally, 4, '', database.now())
        own.save(connection, by_id(connection, cast['Sally'])['active_timeline_id'], database.now(),
                 cooling_since=database.now())
    clock.instant = clock.now() + timedelta(days=30)
    assert stage(client, sally, billy) == 3 and stage(client, billy, sally) == 4
    clock.instant = clock.now() + timedelta(days=60)
    assert stage(client, sally, billy) == 2  # Two steps at most, and never below the second stage.


def test_a_mask_makes_at_most_one_step_of_difference(client, companion, monkeypatch):
    monkeypatch.setattr(pairs, 'MASK_CHANCE', 1)
    ids = [companion_named(client, f'Person {n}') for n in range(12)]
    # Whose temperament is a mask is drawn from their random id; make sure one of them has one.
    drawn = pairs.perception.for_companion

    def lines(companion_id, definition):
        found = drawn(companion_id, definition)
        if companion_id != ids[0]:
            return found
        return {**found, 'gaps': {**found['gaps'], 'temperament': 'mask'},
                'written': {**found['written'], 'sees_self': []}}
    monkeypatch.setattr(pairs.perception, 'for_companion', lines)
    database = client.app.state.database
    with database.connect(write=True) as connection:
        for index, a in enumerate(ids):
            for b in ids[index + 1:]:
                assert pairs.tell(connection, key(a), key(b), 3, '', database.now())
        found = [(pairs.closeness(connection, key(a), key(b), database.clock.now()),
                  pairs.closeness(connection, key(b), key(a), database.clock.now()))
                 for index, a in enumerate(ids) for b in ids[index + 1:]]
    assert all(abs(mine - theirs) <= 1 and {mine, theirs} <= {2, 3} for mine, theirs in found)
    assert any(mine != theirs for mine, theirs in found)


def test_circle_people_show_their_stage_and_storylines_move_it(client):
    response = client.post('/api/companion', json={'name': 'Mira', 'timezone': 'America/New_York',
                                                     'location': 'Fells Point, Baltimore'})
    mira = ok(response)
    people = ok(client.get('/api/life/circle'))
    assert people and all(person['stage'] and person['stage']['level'] >= 2 for person in people
                          if person['role'] in ('mom', 'dad', 'sister', 'brother', 'close friend'))
    friend = next(person for person in people if person['role'] == 'close friend')
    start_level = friend['stage']['level']
    database = client.app.state.database
    today = database.clock.now().date()
    stages = [{'on': (today - timedelta(days=2)).isoformat(), 'text': 'fight', 'share': '', 'tone': 'bad'},
              {'on': (today + timedelta(days=3)).isoformat(), 'text': 'made up', 'share': '', 'tone': 'good'}]
    with database.connect(write=True) as connection:
        connection.execute("INSERT INTO storylines (id, timeline_id, story, level, cast_ids, stages, started_on, "
                           "status, created_at) VALUES (?, ?, 'friend_fight', 2, ?, ?, ?, 'running', ?)",
                           (identifier(), mira['active_timeline_id'], json.dumps([friend['id']]), json.dumps(stages),
                            stages[0]['on'], database.now()))
    fallen = next(person for person in ok(client.get('/api/life/circle')) if person['id'] == friend['id'])
    assert fallen['stage']['level'] == max(start_level - 1, 1)
    with database.connect(write=True) as connection:
        stages[1]['on'] = (today - timedelta(days=1)).isoformat()
        connection.execute('UPDATE storylines SET stages=?', (json.dumps(stages),))
    made_up = next(person for person in ok(client.get('/api/life/circle')) if person['id'] == friend['id'])
    assert made_up['stage']['level'] == start_level
    with database.connect() as connection:
        assert pairs.closeness(connection, friend['key'], key(mira['id']), database.clock.now()) == start_level


def test_a_new_companion_starts_at_their_meetings_and_the_form_can_tell_it_once(client, clock, chatty):
    mira, person = met_someone(client, clock)
    drafted = ok(client.get('/api/companion/cast/draft', params={'key': person['key']}))
    tie = drafted['ties'][0]
    assert tie['companion_id'] == mira['id'] and tie['meetings'] == person['times']
    assert tie['level'] == pairs.meeting_stage(person['times'])
    new = ok(client.post('/api/companion/cast/switch', json={
        'key': person['key'], 'definition': drafted['definition'],
        'ties': [{'companion_id': mira['id'], 'level': 4, 'how': 'Regulars at the same bar.'}]}))
    ties = ok(client.get('/api/companion/ties'))['ties']
    assert [(item['name'], item['feels']['level'], item['how']) for item in ties] == \
        [('Mira', 4, 'Regulars at the same bar.')]
    assert stage(client, key(new['id']), key(mira['id'])) == 4


def test_a_mask_never_leaves_their_own_mom_at_just_met(client, monkeypatch):
    monkeypatch.setattr(pairs, 'MASK_CHANCE', 1)
    monkeypatch.setattr(pairs, 'masked', lambda _me, _them: True)
    # A mom nudged a step down from the usual, then a step further by a mask, used to read "Just met".
    monkeypatch.setattr(pairs, 'role_default', lambda _role, _seed: {'level': 2, 'default': 3, 'nudge': -1})
    ok(client.post('/api/companion', json={'name': 'Mira', 'timezone': 'America/New_York',
                                           'location': 'Fells Point, Baltimore'}))
    people = ok(client.get('/api/life/circle'))
    family = [person for person in people if person['role'] in ('mom', 'dad', 'sister', 'brother')]
    assert family and all(person['stage']['level'] >= 2 for person in family)
