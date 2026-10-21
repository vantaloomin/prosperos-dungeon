"""Together or apart (dungeon/life/together.py): visits asked for in the chat, knocks at the door, and the state."""
from datetime import timedelta

import pytest
from conftest import reconcile, send, set_life

from dungeon.characters import current
from dungeon.life import body, composer, outings, together
from dungeon.providers.chat import Chunk

EVENINGS = [{'key': 'work', 'label': 'Work', 'kind': 'work', 'start': '09:00', 'end': '17:00', 'days': [0, 1, 2, 3, 4]},
            {'key': 'evening', 'label': 'Evening', 'kind': 'leisure', 'start': '17:00', 'end': '23:00'},
            {'key': 'night', 'label': 'Asleep', 'kind': 'sleep', 'start': '23:00', 'end': '07:00'}]


def test_visits_are_read_from_the_message():
    assert together.asked('wanna come over?') == 'visit-yours'
    assert together.asked('Come over tonight, I miss you') == 'visit-yours'
    assert together.asked('Can you come round tonight?') == 'visit-yours'
    assert together.asked("Come to mine for dinner Friday? I'll cook") == 'dinner-yours'
    assert together.asked('Can I come over?') == 'visit-in'
    assert together.asked('could i come to yours later?') == 'visit-in'
    assert together.asked("I'm outside your door, let me in") == 'door'
    for text in ('Dana came over yesterday', "I don't want you to come over", 'how was work?'):
        assert together.asked(text) is None, text


def test_more_ways_to_ask_for_a_visit():
    assert together.asked('dinner at mine tonight?') == 'dinner-yours'
    assert together.asked('want to come to mine for dinner?') == 'dinner-yours'
    assert together.asked('Do you want me to come over?') == 'visit-in'
    assert together.asked('Can I stop by?') == 'visit-in'
    assert together.asked('mind if I drop by later?') == 'visit-in'
    # Going to theirs for dinner is a visit, never a restaurant (dungeon/life/outings.py).
    from datetime import date
    assert outings.proposal("want to come to mine for dinner? I'll cook", date(2026, 10, 5), {}, None) is None


def mira(client, monkeypatch, **values):
    monkeypatch.setattr(body, 'state_on', lambda *_args: None)
    for name in ('QUIET_SHARE', 'PLAN_SHARE', 'THREAD_SHARE'):
        monkeypatch.setattr(composer, name, 0)
    response = client.post('/api/companion', json={'name': 'Mira', 'timezone': 'UTC', 'schedule': EVENINGS,
                                                    'home_city': 'Baltimore', **values})
    assert response.status_code == 200, response.text
    client.put('/api/connection', json={'base_url': 'http://127.0.0.1:1234/v1', 'model': 'local-model',
                                        'api_key': 'secret-key'})
    set_life(client, automatic_events=True, phrase_with_model=False, catch_up_max_events=6,
             catch_up_lookback_hours=168)


@pytest.fixture
def nearby(client, monkeypatch):
    mira(client, monkeypatch)


def says(provider, text='Okay!'):
    provider.replies.append([Chunk(text), Chunk('', 'stop')])


def where(client):
    response = client.get('/api/life/where')
    assert response.status_code == 200, response.text
    return response.json()


def notes(provider):
    return provider.requests[-1]['prompt']


def test_a_visit_on_a_day_is_planned_like_an_outing(client, nearby, provider):
    reconcile(client)
    says(provider)
    send(client, 'come over Friday?', 'client-together-6')
    [visit] = client.get('/api/life/outings').json()['outings']
    assert (visit['activity'], visit['local_date'], visit['at_time']) == ('visit-yours', '2026-10-09', '19:00')
    assert "You agreed: a visit to the user's place" in notes(provider)
    reconcile(client)
    with client.app.state.database.connect() as connection:
        entry = connection.execute("SELECT entry FROM life_agenda WHERE slot_key='evening@2026-10-09'").fetchone()
    assert '"came over to your place' in entry['entry'] or 'came over to your place' in entry['entry']


def test_the_user_at_their_door_comes_in_when_they_are_home(client, nearby, provider, clock):
    clock.advance(timedelta(hours=7))  # 19:00.
    says(provider)
    send(client, "I'm outside your door!", 'client-together-7')
    [visit] = client.get('/api/life/outings').json()['outings']
    assert visit['activity'] == 'visit-in' and visit['place']['name'] == "Mira's place"
    assert where(client)['text'] == "At Mira's place"
    says(provider)
    send(client, 'hi!!', 'client-together-8')
    assert 'Right now the user is over at your place, in person' in notes(provider)


def test_long_distance_they_cannot_just_come_over(client, monkeypatch, provider, clock):
    mira(client, monkeypatch, home_city='Chicago')
    world = client.get('/api/worlds').json()['world']
    assert client.put(f"/api/worlds/{world['id']}/home", json={'city_id': 'baltimore'}).status_code == 200
    clock.advance(timedelta(hours=7))
    says(provider)
    send(client, 'come over?', 'client-together-9')
    assert client.get('/api/life/outings').json()['outings'] == []
    assert "you live in Chicago" in notes(provider) and "so you can't just come over" in notes(provider)
    assert where(client)['kind'] == 'long-distance' and where(client)['text'].startswith('Long distance, Chicago')


def test_a_visit_ends_before_bed_and_early_on_a_work_night():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    monday = datetime(2026, 10, 5, 21, 0, tzinfo=ZoneInfo('UTC'))
    assert together.end_of_visit({'name': 'Mira', 'schedule': EVENINGS}, monday, 3.0) == '22:30'
    friday = datetime(2026, 10, 9, 21, 0, tzinfo=ZoneInfo('UTC'))
    assert together.end_of_visit({'name': 'Mira', 'schedule': EVENINGS}, friday, 3.0) == '23:00'
    assert outings.ACTIVITIES['visit-yours'][3] == 3.0


def test_tonight_asked_at_work_is_a_visit_this_evening_and_sometime_settles_nothing(client, nearby, provider):
    says(provider)
    send(client, 'come over tonight?', 'client-together-20')  # Monday 12:00, at work until 17:00.
    [visit] = client.get('/api/life/outings').json()['outings']
    assert (visit['activity'], visit['local_date'], visit['at_time'], visit['state']) == (
        'visit-yours', '2026-10-05', '19:00', 'planned')
    assert "You can't" not in notes(provider) and where(client)['state'] == 'apart'
    says(provider)
    send(client, 'can I come over sometime next week?', 'client-together-21')
    assert len(client.get('/api/life/outings').json()['outings']) == 1
    assert 'The user asked' not in notes(provider)


def test_sometime_in_the_evening_is_not_a_visit_from_now(client, nearby, provider, clock):
    clock.advance(timedelta(hours=7))  # 19:00, free.
    says(provider)
    send(client, 'come over sometime next week?', 'client-together-22')
    assert client.get('/api/life/outings').json()['outings'] == [] and where(client)['state'] == 'apart'
    says(provider)
    send(client, 'come over later?', 'client-together-23')  # In the evening, later is now.
    assert where(client)['state'] == 'together'


def test_their_texting_style_stays_out_of_the_prompt_while_together(client, monkeypatch, provider, clock):
    mira(client, monkeypatch, texting={'bursts': True, 'lowercase': True, 'typos': True})
    says(provider)
    send(client, 'hi', 'client-together-24')
    assert 'How you text:' in provider.requests[-1]['system']
    clock.advance(timedelta(hours=7))
    says(provider)
    send(client, 'come over?', 'client-together-25')
    assert where(client)['state'] == 'together'
    says(provider)
    send(client, 'nice to see you', 'client-together-26')
    assert 'How you text:' not in provider.requests[-1]['system']


def another_companion(client, name):
    """A second companion in Baltimore, stepped back (a switch of focus brings them in)."""
    from dungeon.characters import insert_version
    from dungeon.database import identifier
    from dungeon.models import CharacterDefinition
    database = client.app.state.database
    with database.connect(write=True) as connection:
        companion_id, timeline_id, now = identifier(), identifier(), database.now()
        connection.execute('INSERT INTO companions (id, slot, stepped_back_at, created_at) VALUES (?, NULL, ?, ?)',
                           (companion_id, now, now))
        version_id = insert_version(connection, companion_id, 1, CharacterDefinition(
            name=name, timezone='UTC', home_city='Baltimore', schedule=EVENINGS), '', now)
        connection.execute("INSERT INTO timelines (id, companion_id, status, created_at) VALUES (?, ?, 'active', ?)",
                           (timeline_id, companion_id, now))
        connection.execute('UPDATE companions SET active_version_id=?, active_timeline_id=? WHERE id=?',
                           (version_id, timeline_id, companion_id))
    return companion_id


def test_two_companions_at_your_place_know_the_other_is_there(client, nearby, provider, clock):
    from dungeon import cast
    database = client.app.state.database
    with database.connect() as connection:
        mira_id = current(connection)['id']
    sally_id = another_companion(client, 'Sally')
    clock.advance(timedelta(hours=6))  # 18:00, both free.
    says(provider)
    send(client, 'wanna come over now?', 'client-together-28')
    assert "Right now you are over at the user's place" in notes(provider)
    assert 'also visiting the user' not in notes(provider)  # Nobody else there yet.
    cast.focus_on(database, sally_id)
    says(provider)
    send(client, 'wanna come over now?', 'client-together-29')
    says(provider)
    send(client, 'so what do you two want to do?', 'client-together-30')
    assert 'Mira, also visiting the user, is here too, in person.' in notes(provider)
    cast.focus_on(database, mira_id)
    says(provider)
    send(client, 'so what do you two want to do?', 'client-together-31')
    assert 'Sally, also visiting the user, is here too, in person.' in notes(provider)
    # Once Mira heads home, Sally's prompt no longer names her.
    says(provider)
    send(client, "it's late, you should head home", 'client-together-32')
    cast.focus_on(database, sally_id)
    says(provider)
    send(client, 'nice having you here', 'client-together-33')
    assert 'also visiting the user' not in notes(provider)
