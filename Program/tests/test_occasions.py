"""Birthdays and anniversaries: from the calendar and what the user said, never guessed."""
import re
from datetime import date, timedelta

import pytest
from conftest import reconcile, send, set_life

from dungeon.clock import zone
from dungeon.database import decode
from dungeon.life import body, circle, composer, occasions


def test_a_birthday_is_heard_only_when_said_plainly():
    today = date(2026, 10, 5)
    assert occasions.said_birthday('my birthday is March 3rd, by the way', today) == '03-03'
    assert occasions.said_birthday("My bday's on the 14th of Feb", today) == '02-14'
    assert occasions.said_birthday("it's my birthday today!", today) == '10-05'
    assert occasions.said_birthday('my birthday is tomorrow', today) == '10-06'
    assert occasions.said_birthday('When is your birthday?', today) is None
    assert occasions.said_birthday('if my birthday is in June we should party', today) is None
    assert occasions.said_birthday('my birthday is February 30', today) is None


def test_milestones_count_from_the_first_conversation():
    first = date(2026, 1, 31)
    assert occasions.milestone(first, date(2026, 2, 28)) == 'a month'
    assert occasions.milestone(first, date(2026, 4, 30)) == 'three months'
    assert occasions.milestone(first, first + timedelta(days=100)) == '100 days'
    assert occasions.milestone(first, date(2027, 1, 31)) == 'a year'
    assert occasions.milestone(first, date(2028, 1, 31)) == '2 years'
    assert occasions.milestone(first, date(2026, 3, 31)) is None
    assert occasions.on(date(2027, 2, 28), '02-29') and not occasions.on(date(2028, 2, 28), '02-29')


def test_a_bad_birthday_is_refused(client, companion):
    assert client.put('/api/life/settings', json={'user_birthday': '13-01'}).status_code == 422


def test_the_companions_birthday_is_a_celebration(client, monkeypatch, clock):
    monkeypatch.setattr(body, 'state_on', lambda *_args: None)
    monkeypatch.setattr(composer, 'QUIET_SHARE', 0)
    tomorrow = (clock.now() + timedelta(days=1)).strftime('%m-%d')
    response = client.post('/api/companion', json={'name': 'Mira', 'timezone': 'UTC', 'birthday': tomorrow})
    assert response.status_code == 200, response.text
    set_life(client, automatic_events=True)
    system = client.get('/api/context/preview').json()['system']
    # Their seeded age can make it a milestone ("your 30th birthday, a big one").
    assert re.search(r'- Tomorrow is your (\d+\w\w )?birthday', system), system
    reconcile(client)
    with client.app.state.database.connect() as connection:
        entries = [decode(row['entry']) for row in connection.execute(
            "SELECT entry FROM life_agenda WHERE subject='companion' AND local_date=? AND entry IS NOT NULL "
            'ORDER BY starts_at', ((clock.now() + timedelta(days=1)).date().isoformat(),))]
    birthday = [entry for entry in entries if entry['activity'] == 'own-birthday']
    # A milestone reads "Mira marked turning 30 with a party."
    assert len(birthday) == 1 and re.search(r'birthday|turning \d+', birthday[0]['summary']), birthday
    assert client.post('/api/companion', json={'name': 'Ana', 'birthday': '7-4'}).status_code == 422


@pytest.mark.parametrize('relationship, words', [('friendship', 'since you and the user first talked'),
                                                 ('romance', 'your anniversary')])
def test_talking_milestones_reach_the_context(client, connected, clock, relationship, words):
    version = client.get('/api/companion').json()['companion']['version']
    revised = client.post('/api/companion/versions', json={
        'definition': {**version['definition'], 'relationship': relationship}, 'expected_version_id': version['id']})
    assert revised.status_code == 200, revised.text
    send(client, 'Hi there', 'client-anniv-01')
    clock.advance(timedelta(days=100))
    system = client.get('/api/context/preview').json()['system']
    assert words in system and '100 days' in system


def test_in_1895_a_birthday_is_their_mothers_on_today_and_in_the_context(client, clock, monkeypatch):
    response = client.post('/api/companion', json={
        'name': 'Ada Hartley', 'timezone': 'Europe/London', 'home_city': 'london-1895', 'location': 'Marylebone, London',
        'identity': '29. She/her. Her mother Edith lives nearby.', 'relationship': 'friendship'})
    assert response.status_code == 200, response.text
    edith = next(person for person in client.get('/api/life/circle').json() if person['name'] == 'Edith')
    tomorrow = clock.now().astimezone(zone('Europe/London')).date() + timedelta(days=1)
    monkeypatch.setattr(occasions, 'SEEDED', True)
    monkeypatch.setattr(occasions, 'own_birthday', lambda _companion: None)
    monkeypatch.setattr(circle, 'birthday', lambda person_id: tomorrow.strftime('%m-%d') if person_id == edith['id']
                        else (tomorrow + timedelta(days=60)).strftime('%m-%d'))
    assert "- Tomorrow is your mother Edith's birthday." in client.get('/api/context/preview').json()['system']
    found = [item for item in client.get('/api/today').json()['occasions'] if item['kind'] == 'circle_birthday']
    assert [(item['person'], item['relation']) for item in found] == [('Edith', 'mother')]
