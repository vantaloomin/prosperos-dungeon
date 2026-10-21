"""Big days in the circle (dungeon/life/big_days.py): where big days come from, the invitation, saying no, the day
itself and what it changes, the gift and a friend's own wedding."""
import re
import string
from datetime import date, datetime, timedelta

import pytest

from dungeon.characters import current
from dungeon.database import decode, encode, one, optional
from dungeon.life import ages, big_days, circle, money, outings
from dungeon.memory import context
from dungeon.providers.chat import Chunk

ROLES = ['mom', 'brother', 'close friend', 'friend', 'cousin']


@pytest.fixture(autouse=True)
def on(monkeypatch):
    monkeypatch.setattr(big_days, 'ACTIVE', True)


def make(client, relationship='romance', **values):
    response = client.post('/api/companion', json={'name': 'Mira Costa', 'timezone': 'UTC', 'home_city': 'Baltimore',
                                                     'relationship': relationship, **values})
    assert response.status_code == 200, response.text
    client.put('/api/connection', json={'base_url': 'http://127.0.0.1:1234/v1', 'model': 'local-model',
                                        'api_key': 'secret-key'})
    assert client.get('/api/life/circle').status_code == 200
    with client.app.state.database.connect(write=True) as connection:
        rows = circle.people(connection, current(connection)['active_timeline_id'])
        for row, role in zip(rows, ROLES, strict=False):
            details = {**decode(row['details']), 'local': True}
            connection.execute('UPDATE circle_people SET role=?, details=? WHERE id=?', (role, encode(details), row['id']))
        for row in rows[len(ROLES):]:
            connection.execute("UPDATE circle_people SET status='removed' WHERE id=?", (row['id'],))


def person(client, role):
    with client.app.state.database.connect() as connection:
        return next(row for row in circle.people(connection, current(connection)['active_timeline_id'])
                    if row['role'] == role)


def set_details(client, person_id, **values):
    with client.app.state.database.connect(write=True) as connection:
        row = one(connection, 'SELECT details FROM circle_people WHERE id=?', (person_id,))
        connection.execute('UPDATE circle_people SET details=? WHERE id=?',
                           (encode({**decode(row['details']), **values}), person_id))


def guests(client, level):
    with client.app.state.database.connect(write=True) as connection:
        connection.execute('UPDATE life_settings SET guests_realism=? WHERE id=1', (level,))


def add(client, clock, kind='wedding', role='brother', days=30, source='test:1', **details):
    with client.app.state.database.connect(write=True) as connection:
        companion = current(connection)
        row = person(client, role) if role else None
        day = clock.now().date() + timedelta(days=days)
        found = big_days.candidate(kind, source, row, day, **details)
        return big_days.add(connection, companion, found, clock.now())


def advance(client, clock):
    with client.app.state.database.connect(write=True) as connection:
        big_days.advance(connection, current(connection), clock.now())


def row_of(client, row_id):
    with client.app.state.database.connect() as connection:
        return big_days.get(connection, row_id)


def lines(client, clock):
    with client.app.state.database.connect() as connection:
        return [text for _key, text in big_days.context_lines(connection, current(connection), clock.now())]


def at(clock, day: str, hour_minute: str):
    hours, minutes = map(int, hour_minute.split(':'))
    target = datetime.combine(date.fromisoformat(day), datetime.min.time(), clock.now().tzinfo)
    clock.advance(target + timedelta(hours=hours, minutes=minutes) - clock.now())


def prompt(provider):
    request = provider.requests[-1]
    return request['prompt'] + ''.join(message['content'] for message in request.get('messages', ()))


def says(provider, text='Okay!'):
    provider.replies.append([Chunk(text), Chunk('', 'stop')])


def test_the_banks_have_enough_lines_with_their_places():
    bank = big_days.bank()
    for kind in ('wedding', 'birthday', 'retirement', 'graduation', 'wedding_modern', 'birthday_modern'):
        gifts = bank['gifts'][kind]
        assert len(gifts) >= 100 and len(set(gifts)) == len(gifts)
        assert all(gift[:1].islower() and not gift.endswith('.') for gift in gifts), kind
    wanted = {'invite': {'event', 'day', 'time', 'place'}, 'stand_up': {'partner', 'day', 'place'},
              'buzz_before': {'event', 'host'}, 'buzz_after': {'event', 'host'}, 'captions': set()}
    for key, names in wanted.items():
        found = bank[key]
        assert len(found) >= 100 and len(set(found)) == len(found), key
        for line in found:
            assert {name for _text, name, _spec, _conv in string.Formatter().parse(line) if name} == names, line
            assert not re.search(r'\b(?:he|she|him|her|his|hers)\b', line, re.IGNORECASE), line
    assert all(kind.gift is None or kind.gift in bank['gifts'] for kind in big_days.KINDS.values())


def test_a_big_day_gets_a_place_a_gift_an_outfit_and_the_engine_decides_whether_you_come(client, clock):
    make(client)
    guests(client, 3)
    row = add(client, clock)
    assert row['kind'] == 'wedding' and row['status'] == 'planned' and row['details']['role'] == 'brother'
    assert row['place']['name'] and not row['place']['id'].startswith('~')
    assert row['gift'] in big_days.bank()['gifts']['wedding_modern'] and row['gift_cost'] > 0
    assert row['gift_on'] == (date.fromisoformat(row['local_date']) - timedelta(days=7)).isoformat()
    assert row['invite'] in (0, 1) and row['consequence_id']  # The engine's roll.
    assert date.fromisoformat(row['invite_on']) <= date.fromisoformat(row['local_date']) - timedelta(days=14)
    assert add(client, clock) is None  # Once per source.
    with client.app.state.database.connect() as connection:
        outcome = optional(connection, 'SELECT * FROM consequences WHERE id=?', (row['consequence_id'],))
    assert outcome['choice'] == big_days.INVITE and 'often' in outcome['options']
    [line] = lines(client, clock)
    assert "your brother" in line.lower() and "wedding is on" in line and "You're bringing" in line


def test_the_gift_is_paid_from_their_money(client, clock):
    make(client)
    client.get('/api/life/home')
    row = add(client, clock)
    with client.app.state.database.connect() as connection:
        companion = current(connection)
        day = date.fromisoformat(row['gift_on'])
        bought = big_days.purchases(connection, companion['active_timeline_id'], day - timedelta(days=1), day)
        home = money.household(connection, companion['active_timeline_id'], companion['version']['definition'], day)
    assert bought == [{'text': f"bought {row['gift']} as a gift", 'date': row['gift_on'], 'spend': '',
                       'cost': row['gift_cost'], 'for': 'gift'}]
    assert any(item['for'] == 'gift' for item in home['purchases'])


def test_a_person_who_leaves_the_circle_calls_it_off(client, clock):
    make(client)
    row = add(client, clock)
    with client.app.state.database.connect(write=True) as connection:
        connection.execute("UPDATE circle_people SET status='removed' WHERE id=?", (row['person_id'],))
    advance(client, clock)
    assert row_of(client, row['id'])['status'] == 'called_off'


def test_a_siblings_engagement_storyline_becomes_a_wedding_next_year(client, clock):
    make(client)
    brother = person(client, 'brother')
    today = clock.now().date()
    stages = [{'on': (today - timedelta(days=20)).isoformat(), 'text': 'engaged', 'share': '', 'tone': 'good'},
              {'on': (today - timedelta(days=5)).isoformat(), 'text': 'a date', 'share': '', 'tone': 'good'}]
    with client.app.state.database.connect(write=True) as connection:
        companion = current(connection)
        connection.execute("INSERT INTO storylines (id, timeline_id, story, level, cast_ids, stages, started_on, status, "
                           "created_at) VALUES ('story-1', ?, 'sibling_engaged', 0, ?, ?, ?, 'ended', ?)",
                           (companion['active_timeline_id'], encode([brother['id']]), encode(stages), stages[0]['on'],
                            clock.now().isoformat()))
        people = {row['id']: row for row in circle.people(connection, companion['active_timeline_id'])}
        [found] = big_days.sibling_weddings(connection, companion, today, people, clock.now())
    assert found['kind'] == 'wedding' and found['person_id'] == brother['id']
    assert found['day'].year == today.year + 1 and found['day'].weekday() == 5 and 4 <= found['day'].month <= 9


def test_milestone_birthdays_retirements_and_graduations_come_from_the_circle(client, clock):
    make(client)
    today = clock.now().date()
    mom, cousin, friend = person(client, 'mom'), person(client, 'cousin'), person(client, 'friend')
    set_details(client, mom['id'], career='Nurse')
    set_details(client, friend['id'], career='College student')
    with client.app.state.database.connect(write=True) as connection:
        for row, age in ((mom, 70), (cousin, 40), (friend, 23)):
            birthday = big_days.next_birthday(row['id'], today)
            connection.execute("INSERT INTO birth_dates (kind, person_key, born_on, birthday, from_age, anchored_on, "
                               "created_at, updated_at) VALUES ('circle', ?, ?, ?, 18, ?, ?, ?)",
                               (row['id'], ages.birthday_in(birthday.year - age, circle.birthday(row['id'])).isoformat(),
                                circle.birthday(row['id']), today.isoformat(), clock.now().isoformat(),
                                clock.now().isoformat()))
        companion = current(connection)
        people = {row['id']: row for row in circle.people(connection, companion['active_timeline_id'])}
        birthdays = big_days.milestone_birthdays(connection, companion, today, people, clock.now())
        retiring = big_days.retirements(connection, companion, today, people, clock.now())
        graduating = big_days.graduations(connection, companion, today, people, clock.now())
    by_person = {found['person_id']: found for found in birthdays}
    assert by_person[mom['id']]['details']['age'] == 70 and by_person[cousin['id']]['details']['age'] == 40
    assert by_person[cousin['id']]['day'].weekday() >= 4
    # The rest of the circle is seeded at random, so only the people set up here are checked.
    retired = {found['person_id']: found for found in retiring}
    assert mom['id'] in retired and retired[mom['id']]['day'].weekday() == 4
    graduate = {found['person_id']: found for found in graduating}
    assert friend['id'] in graduate and mom['id'] not in graduate
    assert graduate[friend['id']]['day'].month in (5, 6) and graduate[friend['id']]['day'].weekday() == 5


def test_friends_marry_by_their_love_life(client, clock, monkeypatch):
    make(client)
    friend = person(client, 'close friend')
    set_details(client, friend['id'], age=30)
    monkeypatch.setattr(big_days, 'FRIEND_RATE', (0.0, 1.0, 1.0, 1.0))
    with client.app.state.database.connect(write=True) as connection:
        companion = current(connection)
        people = {row['id']: row for row in circle.people(connection, companion['active_timeline_id'])}
        found = big_days.friend_weddings(connection, companion, clock.now().date(), people, clock.now())
        connection.execute('UPDATE life_settings SET love_life=0 WHERE id=1')
        none = big_days.friend_weddings(connection, companion, clock.now().date(), people, clock.now())
    mine = [item for item in found if item['person_id'] == friend['id']]
    assert mine and all(item['details']['engaged_on'] <= clock.now().date().isoformat() for item in mine)
    assert none == []


def test_the_users_romance_never_has_a_big_day_wedding_of_their_own(client, clock):
    make(client)
    with client.app.state.database.connect(write=True) as connection:
        companion = current(connection)
        assert not big_days.own_wedding(connection, companion, {'id': 'x', 'name': 'Sam'}, clock.now().date(),
                                        clock.now())


def test_buzz_comes_the_week_before_and_the_section_is_offered(client, clock):
    make(client)
    row = add(client, clock, days=10)
    clock.advance(timedelta(days=5))
    found = lines(client, clock)
    assert any(line.startswith('- Group chat buzz you could pass on:') and 'wedding' in line for line in found)
    with client.app.state.database.connect() as connection:
        assert 'big_days' in context.HEADINGS
        assert big_days.dressed(connection, row['timeline_id'], row['local_date']) == row['outfit']


def test_their_own_graduation_and_retirement_party_come_from_their_life_chapters(client, clock):
    make(client)
    guests(client, 3)
    today = clock.now().date()
    with client.app.state.database.connect(write=True) as connection:
        companion = current(connection)
        for chapter_id, kind, details in (('ch-school', 'school', {'ends_on': (today + timedelta(days=20)).isoformat()}),
                                          ('ch-retire', 'retire', {'last_day': (today + timedelta(days=30)).isoformat()})):
            connection.execute("INSERT INTO life_chapters (id, timeline_id, kind, started_on, title, told, share, details, "
                               "created_at) VALUES (?, ?, ?, ?, 'A chapter', '', '', ?, ?)",
                               (chapter_id, companion['active_timeline_id'], kind, today.isoformat(), encode(details),
                                clock.now().isoformat()))
    advance(client, clock)
    with client.app.state.database.connect() as connection:
        found = {row['kind']: row for row in big_days.rows(connection, current(connection)['active_timeline_id'],
                                                           ('planned',))}
    assert {'own_graduation', 'own_retirement'} <= set(found)  # The circle's own big days may be found too.
    graduation = found['own_graduation']
    assert graduation['source'] == 'chapter:ch-school' and graduation['gift'] == '' and graduation['at_time'] == '10:00'
    assert big_days.title(graduation, 'Mira Costa') == "Mira's graduation"
    assert big_days.said(found['own_retirement']) == 'your retirement party'
    assert not any('buzz' in line and 'graduation' in line for line in lines(client, clock))
    graduation['invite'] = 1
    assert 'there with you' in big_days.reason_for(graduation, date.fromisoformat(graduation['local_date']))


def test_a_big_day_held_after_the_fork_is_still_to_come_on_the_copy():
    row = {'status': 'done', 'local_date': '2027-05-01', 'message_id': None, 'answered_at': None}
    assert big_days.copied_status(row, {}, '2027-04-20T10:00:00+00:00') == ('planned', None)
    assert big_days.copied_status(row, {}, '2027-05-02T10:00:00+00:00') == ('done', None)
    asked = {**row, 'message_id': 'm', 'answered_at': '2027-04-25T10:00:00+00:00'}
    assert big_days.copied_status(asked, {'m': 'm2'}, '2027-04-20T10:00:00+00:00') == ('invited', 'm2')
    assert big_days.copied_status(asked, {'m': 'm2'}, '2027-04-26T10:00:00+00:00') == ('declined', 'm2')


def agenda_at(client, clock):
    from dungeon.life import agenda
    with client.app.state.database.connect(write=True) as connection:
        companion = current(connection)
        agenda.extend(connection, companion, client.app.state.life.world, clock.now())
        found = optional(connection, "SELECT block, entry FROM life_agenda WHERE timeline_id=? AND subject='companion' "
                         'AND starts_at<=? AND ends_at>?', (companion['active_timeline_id'], clock.now().isoformat(),
                                                           clock.now().isoformat()))
    return decode(found['block']), decode(found['entry']) if found['entry'] else None


def test_going_on_their_own_is_in_their_day(client, clock):
    make(client)
    guests(client, 0)
    row = add(client, clock)
    at(clock, row['local_date'], '16:00')
    _block, entry = agenda_at(client, clock)
    assert entry['activity'] == big_days.ACTIVITY and entry['big_day']['id'] == row['id']
    assert f"went to {big_days.title(row)} at {row['place']['name']}" in entry['summary']


WORK = [{'key': 'work', 'label': 'Work', 'kind': 'work', 'start': '09:00', 'end': '17:00', 'days': [0, 1, 2, 3, 4, 5, 6]},
        {'key': 'evening', 'label': 'Evening', 'kind': 'leisure', 'start': '17:00', 'end': '23:00'},
        {'key': 'night', 'label': 'Asleep', 'kind': 'sleep', 'start': '23:00', 'end': '07:00'},
        {'key': 'morning', 'label': 'Morning', 'kind': 'leisure', 'start': '07:00', 'end': '09:00'}]


def test_in_an_old_city_the_invitation_and_caption_have_no_cars_texts_or_photos(client, clock):
    client.post('/api/companion', json={'name': 'Elayne', 'timezone': 'Europe/London', 'home_city': 'Camelot'})
    client.get('/api/life/circle')
    row = add(client, clock, role=None, source='test:camelot', name='Cynan Ap Rhys')
    assert row['place']['modern'] is False
    for number in range(200):
        found = {**row, 'id': f'seed-{number}'}
        for kind in ('wedding', 'own_wedding', 'funeral'):
            text = big_days.invitation({**found, 'kind': kind}, 'Saturday', '3')
            assert not big_days.MODERN_ONLY.search(text), text
        assert not big_days.MODERN_ONLY.search(big_days.caption({'id': f'o-{number}', 'place': row['place']}))
    modern = {**row['place'], 'modern': True}
    assert any(big_days.MODERN_ONLY.search(big_days.caption({'id': f'o-{number}', 'place': modern}))
               for number in range(400))


def test_a_party_is_somewhere_open_at_its_hour(client, clock):
    make(client)
    with client.app.state.database.connect() as connection:
        companion = current(connection)
        data = outings.city_data(connection, companion['version']['definition'])
        day = clock.now().date() + timedelta(days=30)
        for key, part in (('birthday', 'evening'), ('retirement', 'evening'), ('graduation', 'morning')):
            for number in range(60):
                found = big_days.place_for(connection, companion, big_days.KINDS[key], day, f'seed-{number}', {})
                place = next(item for item in data['places'] if item['id'] == found['id'])
                assert part in place['day_parts'], (key, place['name'], place['day_parts'])


def test_the_invitation_names_a_day_weeks_off_by_its_date():
    tuesday = date(2026, 10, 20)
    assert big_days.when_text(date(2026, 10, 24), tuesday) == 'Saturday'
    assert big_days.when_text(date(2026, 10, 31), tuesday) == 'next Saturday'
    assert big_days.when_text(date(2026, 11, 14), tuesday) == 'Saturday, November 14'


def test_next_saturday_starting_a_sentence_has_a_capital():
    for kind in ('birthday', 'own_wedding'):
        for number in range(100):
            row = {'id': f'row-{number}', 'kind': kind, 'place': {'name': 'Ouzo Bay', 'modern': True},
                   'details': {'name': 'James Hill', 'role': 'dad', 'age': 60}, 'title': "James's 60th birthday party"}
            line = big_days.invitation(row, 'next Saturday', '7')
            assert not re.search(r'(^|[.?!] )next Saturday', line), line


def test_in_1895_a_parent_is_mother_or_father(client, clock):
    client.post('/api/companion', json={'name': 'Ada Lowe', 'timezone': 'Europe/London', 'home_city': 'london-1895'})
    client.get('/api/life/circle')
    with client.app.state.database.connect(write=True) as connection:
        row = circle.people(connection, current(connection)['active_timeline_id'])[0]
        connection.execute("UPDATE circle_people SET role='mom' WHERE id=?", (row['id'],))
    found = add(client, clock, kind='birthday', role='mom', age=60)
    assert found['details']['role'] == 'mother' and 'your mother' in big_days.said(found)


def test_a_parent_is_mom_or_dad_on_the_day_like_everyone_else(client, clock):
    make(client)
    with client.app.state.database.connect(write=True) as connection:
        row = circle.people(connection, current(connection)['active_timeline_id'])[0]
        details = decode(row['details']) or {}
        connection.execute("UPDATE circle_people SET role='parent', details=? WHERE id=?",
                           (encode({**details, 'pronouns': 'she/her'}), row['id']))
    found = add(client, clock, kind='birthday', role='parent', age=60)
    assert found['details']['role'] == 'mom' and 'your mom' in big_days.said(found)
    assert big_days.host(found)['role'] == 'mom'  # Today's "With Tracy (mom)".


def test_before_asking_their_own_day_is_never_a_plus_one():
    row = {'kind': 'own_wedding', 'status': 'planned', 'invite': 1, 'local_date': '2027-02-20', 'at_time': '15:00',
           'place': {'name': 'Royal Observatory'}, 'details': {'name': 'Sam Okafor'}, 'gift': '', 'outfit': ''}
    assert 'to stand up with you at your wedding' in big_days.coming_line(row, date(2027, 2, 1))
    for kind in ('own_graduation', 'own_retirement', 'funeral'):
        assert 'plus-one' not in big_days.coming_line({**row, 'kind': kind}, date(2027, 2, 1))
    assert 'as your plus-one' in big_days.coming_line({**row, 'kind': 'wedding', 'details': {'name': 'Leo'}},
                                                       date(2027, 2, 1))


def test_a_no_to_one_big_day_lets_the_next_one_close_by_be_asked(client, clock, monkeypatch):
    # Only these two days: a seeded milestone birthday in the circle that the engine asks the user to (about 1 run in
    # 75) would hold the second back on its own, which is a different rule.
    monkeypatch.setattr(big_days, 'SOURCES', [])
    make(client)
    guests(client, 3)
    first = add(client, clock, days=30)
    with client.app.state.database.connect(write=True) as connection:
        connection.execute('UPDATE big_days SET invite=1 WHERE id=?', (first['id'],))
    second = add(client, clock, kind='birthday', role='mom', days=36, source='test:2', age=60)
    assert second['invite'] == 0 and second['consequence_id'] is None  # Held back by the first, still to be asked.
    advance(client, clock)
    assert row_of(client, second['id'])['consequence_id'] is None
    with client.app.state.database.connect(write=True) as connection:
        connection.execute("UPDATE big_days SET status='declined' WHERE id=?", (first['id'],))
    advance(client, clock)
    assert row_of(client, second['id'])['consequence_id']  # The no doesn't hide it: the engine decides now.


def test_a_day_the_user_went_to_still_holds_the_next_back_but_not_a_funeral_in_the_family(client, clock):
    make(client)
    first = add(client, clock, days=30)
    with client.app.state.database.connect(write=True) as connection:
        connection.execute("UPDATE big_days SET invite=1, status='done', with_user=1 WHERE id=?", (first['id'],))
        near = {'id': 'near', 'timeline_id': first['timeline_id'], 'kind': 'birthday', 'details': {},
                'local_date': (date.fromisoformat(first['local_date']) + timedelta(days=5)).isoformat()}
        assert big_days.crowded(connection, near)
        assert not big_days.crowded(connection, {**near, 'kind': 'funeral', 'details': {'family': True}})
        connection.execute("UPDATE big_days SET with_user=0 WHERE id=?", (first['id'],))
        assert not big_days.crowded(connection, near)


def test_an_out_of_town_relatives_wedding_is_a_trip_you_can_come_along_to(client, clock, monkeypatch):
    make(client)
    client.get('/api/life/home')
    set_details(client, person(client, 'brother')['id'], local=False, city='')
    row = add(client, clock)
    details = row['details']
    assert details['city'] and details['city_id'] and row['place']['name'] == f"a venue in {details['city']}"
    with client.app.state.database.connect() as connection:
        companion = current(connection)
        assert big_days.invitable(connection, companion, row)
        set_off = date.fromisoformat(row['local_date']) - timedelta(days=1)
        fares = [item for item in big_days.purchases(connection, companion['active_timeline_id'], set_off, set_off)
                 if item['for'] == 'trip']
        assert details['fare'] > 0 and fares == [{'text': f"travelled to {details['city']} for {big_days.title(row)}",
                                                  'date': set_off.isoformat(), 'spend': '', 'cost': details['fare'],
                                                  'for': 'trip'}]
        monkeypatch.setattr('dungeon.life.where.far', lambda *_args: object())
        assert not big_days.invitable(connection, companion, row)  # The user lives elsewhere: they go on their own.
    line = next(text for text in lines(client, clock) if 'wedding is on' in text)
    assert f"It's out of town, in {details['city']}: you travel there for it." in line
    assert "It's out of town" in big_days.coming_line({**row, 'status': 'invited'}, clock.now().date())
    assert 'the two of you together' in big_days.coming_line({**row, 'status': 'invited'}, clock.now().date())


def test_camelot_has_its_own_gifts_and_1895_keeps_the_timeless_ones(client, clock):
    gifts = big_days.bank()['gifts']
    for kind in ('wedding', 'birthday', 'first_birthday'):
        found = gifts[f'{kind}_old']
        assert len(found) >= 25 and len(set(found)) == len(found)
        assert not any(re.search(r'\b(?:tea|teacup|sparkling|champagne|whisky|printed|framed)\b', gift) for gift in found)
    client.post('/api/companion', json={'name': 'Elayne', 'timezone': 'Europe/London', 'home_city': 'Camelot'})
    client.get('/api/life/circle')
    row = add(client, clock, role=None, source='test:camelot', name='Cynan Ap Rhys')
    assert row['gift'] in gifts['wedding_old']
    with client.app.state.database.connect() as connection:
        companion = current(connection)
        for number in range(40):
            gift, _cost = big_days.gift_for(connection, companion, big_days.KINDS['birthday'], f'seed-{number}')
            assert gift in gifts['birthday_old'], gift
        definition = {**companion['version']['definition'], 'home_city': 'london-1895'}
        victorian = {**companion, 'version': {**companion['version'], 'definition': definition}}
        assert {big_days.gift_for(connection, victorian, big_days.KINDS['birthday'], f'seed-{number}')[0]
                for number in range(40)} <= set(gifts['birthday'])


def test_a_friends_own_wedding_photo_has_them_in_wedding_clothes():
    from dungeon.images import prompts
    line = prompts.doing({'activity': big_days.PICTURED, 'summary': 'Priya got married.', 'place': 'Royal Observatory'},
                         'Priya', 'her', 'she')
    assert line == 'Priya is smiling in wedding clothes at her own wedding at Royal Observatory.'


def test_the_feed_rephrase_keeps_the_user_on_a_day_together():
    from dungeon.life import synthesis
    assert 'when the facts say "with you", keep "with you"' in synthesis.RULES
    assert 'Never add the user' in synthesis.RULES
