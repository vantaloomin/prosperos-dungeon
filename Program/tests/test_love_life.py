"""Their own love life (dungeon/life/love_life.py) and townsfolk couples (dungeon/world/couples.py)."""
import re
from datetime import date, timedelta

import pytest
from conftest import reconcile, set_life
from test_chapters import arrange, current, mira  # noqa: F401 - the fixture is used by name
from test_consequences import change

from dungeon import consequences
from dungeon.life import chapters, circle, love_life, steps
from dungeon.world import catalog, couples, paper, townsfolk


def test_the_banks_hold_enough_lines_for_every_step():
    bank = love_life.bank()
    for name in ('met', 'share_new', 'dates', 'splits', 'spotted'):
        assert len(bank[name]) >= 100, name
        assert len(set(bank[name])) == len(bank[name]), name
    assert set(bank['milestones']) == {step.key for step in steps.ROMANCE[1:]}
    assert sum(len(lines) for lines in bank['milestones'].values()) >= 100
    for line in [*bank['share_new'], *bank['dates'], *bank['splits']]:
        assert line.count('{partner}') == 1, line
    for line in bank['spotted']:
        line.format(name='Mira', place='the bakery')



def test_every_bank_line_says_the_partner_with_their_own_pronouns():
    # "It's Maud, and I'm seeing her", not "them" (she/her); a they/them partner keeps "they".
    bank = love_life.bank()
    lines = [*bank['met'], *bank['share_new'], *bank['dates'], *bank['splits'],
             *(line for step in bank['milestones'].values() for line in step)]
    wrong = re.compile(r"\b(?:she|he) (?:are|were|have|do|know|love|need|want|like)\b|\bthey (?:is|was|has|does)\b|"
                       r"\bthey's\b", re.IGNORECASE)
    for pronouns in ('she/her', 'he/him', 'they/them'):
        for template in lines:
            text = love_life.line(template, 'Maud', pronouns)
            assert '{' not in text and '}' not in text, text
            assert not wrong.search(text), text
    found = {'name': 'Maud Pike', 'details': {'pronouns': 'she/her'}}
    assert love_life.told("It's {partner}, and I'm seeing {them}. {They're} lovely.", found) == \
        "It's Maud, and I'm seeing her. She's lovely."
    assert love_life.line('{They} know{s} the stars; {they} {have} opinions.', 'Tom', 'he/him') == \
        'He knows the stars; he has opinions.'
    assert love_life.line('{They} know{s} the stars; {they} {were} kind.', 'Sam', 'they/them') == \
        'They know the stars; they were kind.'
    # With no pronouns known, the partner is "they".
    assert love_life.line('I like {them}.', 'Sam', None) == 'I like them.'
    # A partner who is she or he is never "they" in their own lines.
    for template in lines:
        for pronouns, word in (('she/her', 'she'), ('he/him', 'he')):
            text = love_life.line(template, 'Maud', pronouns)
            assert not re.search(r"\b(?:they|them|their|theirs|themselves)\b", text, re.IGNORECASE) or \
                template in THEY_ABOUT_OTHERS, (word, text)



# Lines where "they" or "them" is someone else (friends, jars, keys, a saying), not the partner.
THEY_ABOUT_OTHERS = {
    "Supper with {partner}'s friends tonight. They're loud and lovely.",
    "Met {partner}'s friends at the dance. They already knew all about me.",
    'Off the market, as they say. {partner} and me.',
    'Introduced {partner} to my friends. They like {them} more than me now.',
    'when you knocked a row of jars off a shelf and {they} caught two of them',
    'Picked wildflowers with {partner} and pressed them in a book.',
    "Two keys on my ring now. One of them opens {partner}'s door.",
}


def test_the_odds_tables_say_what_moved_them():
    names = {'name': 'Mira', 'partner': 'Sam', 'a': 'Sam', 'b': '', 'step': 'being exclusive'}
    for choice in (love_life.NEXT, love_life.SECRET):
        for option in consequences.tables()[choice]['options']:
            option['label'].format(**names)
            for rule in option['rules']:
                rule['why'].format(**names)
    quiet = consequences.odds(love_life.NEXT, {'love_life': 1, 'drama': 0, 'step': 2, 'can_up': 1}, names)
    stormy = consequences.odds(love_life.NEXT, {'love_life': 3, 'drama': 3, 'step': 0, 'can_up': 1}, names)
    assert stormy[2]['odds'] > quiet[2]['odds'] and 'the drama level is high' in stormy[2]['reasons']
    married = consequences.odds(love_life.NEXT, {'love_life': 2, 'drama': 1, 'step': 7, 'can_up': 0}, names)
    assert married[0]['odds'] == 0


def test_who_has_a_love_life_of_their_own(client, mira):  # noqa: F811
    with client.app.state.database.connect() as connection:
        companion = current(client)
        assert love_life.mode(connection, companion) == 'free'
        romance = {**companion, 'version': {**companion['version'], 'definition': {
            **companion['version']['definition'], 'relationship': 'romance'}}}
        assert love_life.mode(connection, romance) is None
        open_one = {**romance, 'version': {**romance['version'], 'definition': {
            **romance['version']['definition'], 'interests': ['an open relationship', 'jazz']}}}
        assert love_life.mode(connection, open_one) == 'open'
    assert love_life.is_open({'identity': 'Happily polyamorous.'}) and not love_life.is_open({'identity': 'Shy.'})


def partner_row(client):
    with client.app.state.database.connect() as connection:
        return love_life.partners(connection, current(client)['active_timeline_id'], active=False)


def force(monkeypatch, picked: int):
    """Every love:* roll lands on `picked`; anything else takes its likeliest option."""
    real = consequences.roll

    def roll(seed, found):
        if ':love:' in seed:
            return picked
        return real(seed, found)
    monkeypatch.setattr(consequences, 'roll', roll)


def begin_partner(client, clock):
    companion = current(client)
    world = client.app.state.life.world
    with client.app.state.database.connect(write=True) as connection:
        day = steps.local_today(companion, clock.now())
        found = love_life.plan(connection, companion, world, day, 'test-seed')
        love_life.begin(connection, companion, world, day, found, clock.now())
    return partner_row(client)[0]


def test_the_user_can_make_it_go_another_way(client, mira, clock, monkeypatch):  # noqa: F811
    found = begin_partner(client, clock)
    force(monkeypatch, 2)
    clock.advance(timedelta(days=40))
    with client.app.state.database.connect(write=True) as connection:
        love_life.advance(connection, current(client), client.app.state.life.world, clock.now())
        outcome = consequences.recorded(connection, f"love:{found['id']}:exclusive:1", love_life.NEXT)
    assert partner_row(client)[0]['ended_how'] == 'split'
    # Every reason says which way it pushed ("More likely because…").
    assert all(len(item['moves']) == len(item['reasons']) for item in outcome['options'])
    changed = change(client, outcome['id'], 0)
    assert changed['picked'] == 0
    [after] = partner_row(client)
    assert after['ended_on'] is None
    with client.app.state.database.connect() as connection:
        reached = [row['step'] for row in steps.reached(connection, found['timeline_id'], 'romance',
                                                        love_life.key_of(found))]
        assert circle.person(connection, found['person_id'])['status'] == 'active'
    assert reached == ['dating', 'exclusive']


def test_nothing_new_leaves_them_where_they_are(client, mira, clock, monkeypatch):  # noqa: F811
    set_life(client, love_life=0)
    with client.app.state.database.connect() as connection:
        companion = current(client)
        assert love_life.plan(connection, companion, client.app.state.life.world,
                              steps.local_today(companion, clock.now()), 'seed') is None


@pytest.fixture
def romance(client, clock, monkeypatch):
    from dungeon.life import body
    monkeypatch.setattr(body, 'state_on', lambda *_args: None)
    response = client.post('/api/companion', json={'name': 'Rae Okafor', 'timezone': 'UTC', 'relationship': 'romance',
                                                     'location': 'Fells Point, Baltimore'})
    assert response.status_code == 200, response.text
    client.put('/api/life/steps', json={'step': 'exclusive'})
    return response.json()


def test_on_drama_a_secret_starts_in_about_one_month_in_fifty():
    # Vanta (2026-10-17): about 2% a month on Drama, not 55 to 80% of years. Below soap opera there is no roll at all
    # (love_life.mode); the love life slider, the Life deck's card and their description still move it.
    names = {'name': 'Rae', 'a': 'someone', 'b': ''}

    def starts(**facts):
        found = consequences.odds(love_life.SECRET, {'love_life': 2, 'drama': 3, 'card': 0, 'closeness': 3,
                                                     'mood': 0, 'sheet': set()} | facts, names)
        return found[1]

    plain = starts()
    assert plain['odds'] == 0.02
    assert plain['reasons'] == ['the drama level is soap opera, and you two are exclusive']
    assert plain['moves'] == ['possible']
    assert starts(love_life=1)['odds'] == 0.01 and starts(love_life=3)['odds'] == 0.03
    assert 0.05 < starts(card=1)['odds'] < 0.06 and "someone caught Rae's eye lately" in starts(card=1)['reasons']
    assert starts(closeness=5)['odds'] < plain['odds'] < starts(sheet={'restless'})['odds']
    # Over a year of monthly rolls, about one in five on true to life (it was over half).
    assert 0.18 < 1 - (1 - plain['odds']) ** 12 < 0.25


def test_townsfolk_couples_move_on_week_by_week():
    data = catalog.city('baltimore') if hasattr(catalog, 'city') else next(iter(catalog.cities().values()))
    hood = data['neighborhoods'][0]['id']
    found = []
    for sheet in townsfolk.residents(data, hood)[:60]:
        state = couples.couple(sheet, data, date(2027, 6, 1))
        if state:
            found.append((sheet, state))
    assert found, 'some residents have partners'
    for sheet, state in found:
        assert state == couples.couple(sheet, data, date(2027, 6, 1))  # The same every time.
        assert state['status'] in ('seeing someone', 'engaged', 'married', 'single')
        if state['partner']:
            assert state['partner']['age'] >= 18 and couples.text(state)
    # Over a few years, someone gets engaged or married, and the paper reports it that week.
    events = [(sheet, item) for sheet in townsfolk.residents(data, hood)[:60]
              for item in couples.events(sheet, data, (date(2026, 1, 5), date(2030, 1, 5)))]
    assert events
    sheet, item = events[0]
    week = (item['day'] - timedelta(days=item['day'].weekday() + 1) + timedelta(days=1), item['day'] + timedelta(days=1))
    assert any(item['partner']['full'] in entry['text'] for entry in paper.couples_news(
        {**data, 'neighborhoods': [data['neighborhoods'][0]]}, week)) or len(events) > paper.MOST_COUPLES


def test_a_new_partner_never_shares_a_first_name_with_someone_already_in_their_life(client, clock):
    client.post('/api/companion', json={'name': 'Sarah Wells', 'timezone': 'UTC', 'home_city': 'baltimore'})
    world = client.app.state.life.world
    with client.app.state.database.connect(write=True) as connection:
        companion = current(client)
        circle.ensure(connection, companion, world, clock.now())
        people = [row['name'] for row in circle.people(connection, companion['active_timeline_id'])]
        assert 'Sarah' not in people  # Nor in the circle: someone called Sarah there goes by their full name.
        used = {name.split()[0] for name in people} | {'Sarah'}
        found = [love_life.new_person(connection, companion, world, f'seed:{n}')['name'] for n in range(150)]
    assert not [name for name in found if name.split()[0] in used]


def test_a_fork_keeps_how_their_rolls_went_before_it(client, mira, clock, monkeypatch, provider):  # noqa: F811
    from conftest import send
    client.put('/api/connection', json={'base_url': 'http://127.0.0.1:1234/v1', 'model': 'local-model',
                                        'api_key': 'secret-key'})
    found = begin_partner(client, clock)
    force(monkeypatch, 1)  # Not yet: exclusive is rolled again some weeks later.
    clock.advance(timedelta(days=40))
    with client.app.state.database.connect(write=True) as connection:
        love_life.advance(connection, current(client), client.app.state.life.world, clock.now())
    sent = send(client, 'How are things with them?', 'client-love-01')['message']
    fork = client.post('/api/timelines', json={'message_id': sent['id'], 'text': 'How are you two?'}).json()['id']
    assert client.post(f'/api/timelines/{fork}/activate').status_code == 200
    force(monkeypatch, 2)  # Any roll made again on the fork would split them up, in the past.
    with client.app.state.database.connect(write=True) as connection:
        companion = current(client)
        assert companion['active_timeline_id'] == fork
        love_life.advance(connection, companion, client.app.state.life.world, clock.now())
        [copied] = love_life.partners(connection, fork, active=False)
        assert copied['ended_on'] is None
        assert consequences.recorded(connection, f"love:{copied['id']}:exclusive:1", love_life.NEXT)['picked'] == 1
    assert found['name'] == copied['name']


def test_undoing_the_chapter_on_a_fork_takes_back_only_its_own_partner(client, mira, clock, monkeypatch, provider):  # noqa: F811
    from conftest import send
    client.put('/api/connection', json={'base_url': 'http://127.0.0.1:1234/v1', 'model': 'local-model',
                                        'api_key': 'secret-key'})
    arrange(client, monkeypatch, clock, 'relationship')
    reconcile(client)
    parent = current(client)['active_timeline_id']
    sent = send(client, 'Tell me about them.', 'client-love-02')['message']
    fork = client.post('/api/timelines', json={'message_id': sent['id']}).json()['id']
    assert client.post(f'/api/timelines/{fork}/activate').status_code == 200
    [chapter] = client.get('/api/life/chapters').json()
    assert client.post(f"/api/life/chapters/{chapter['id']}/undo").status_code == 200
    with client.app.state.database.connect() as connection:
        [kept] = love_life.partners(connection, parent, active=False)
        [taken] = love_life.partners(connection, fork, active=False)
    assert kept['ended_how'] is None and taken['ended_how'] == 'undone'


def test_after_a_split_they_wait_about_two_months_before_someone_new(client, mira, clock, monkeypatch):  # noqa: F811
    # A friend had a new partner 15 days after splitting up (v0.13 run). No one new for REBOUND days.
    found = begin_partner(client, clock)
    world = client.app.state.life.world
    with client.app.state.database.connect(write=True) as connection:
        love_life.end(connection, found, 'split', steps.local_today(current(client), clock.now()))
    for days, planned in ((15, False), (love_life.REBOUND - 1, False), (love_life.REBOUND, True)):
        with client.app.state.database.connect() as connection:
            companion = current(client)
            day = steps.local_today(companion, clock.now()) + timedelta(days=days)
            assert bool(love_life.plan(connection, companion, world, day, f'seed:{days}')) is planned, days
    # The chapter's odds say why it could not happen.
    labels = [rule['why'] for option in consequences.tables()[chapters.CHOICE]['options'] for rule in option['rules']
              if rule['reader'] == 'can_relationship']
    assert labels == ['{name} is already seeing someone, split up lately, or has no love life of their own here']


def open_romance(client):
    response = client.post('/api/companion', json={'name': 'Haru Sato', 'timezone': 'UTC', 'relationship': 'romance',
                                                     'location': 'Fells Point, Baltimore',
                                                     'interests': ['an open relationship', 'jazz'],
                                                     'emotional_traits': [{'name': 'Jealous', 'intensity': 'moderate'}]})
    assert response.status_code == 200, response.text
    client.put('/api/life/steps', json={'step': 'exclusive'})


def test_an_open_relationship_partner_never_becomes_exclusive(client, clock, monkeypatch):
    from dungeon.life import body
    monkeypatch.setattr(body, 'state_on', lambda *_args: None)
    open_romance(client)
    found = begin_partner(client, clock)
    force(monkeypatch, 0)
    clock.advance(timedelta(days=200))
    with client.app.state.database.connect(write=True) as connection:
        love_life.advance(connection, current(client), client.app.state.life.world, clock.now())
        reached = [row['step'] for row in steps.reached(connection, found['timeline_id'], 'romance',
                                                        love_life.key_of(found))]
        lines = dict(love_life.context_lines(connection, current(client), clock.now()))
    assert reached[:2] == ['dating', 'love'] and 'exclusive' not in reached
    people = {person['id']: person for person in client.get('/api/life/circle').json()}
    assert people[found['person_id']]['love'].endswith(', open')
    # The partner line says it is open, once, with no doubled brackets, and the jealousy points the right way.
    text = lines[f"love:{found['id']}"]
    assert 'open relationship: you both see other people' in text and ')' + ' (' not in text
    assert re.search(r'\(\d+, [^()]*\), together', text), text
    assert 'say plainly that it is an open relationship' in text
    assert 'a pang when the user mentions seeing someone else' in text and 'jealousy about the user' not in text
    # Where things stand with the user never says "you only see each other" (no other romance of the user's here).
    prompt = client.get('/api/context/preview').json()['prompt']
    assert steps.OPEN_ALONE in prompt and 'only see each other' not in prompt


def test_an_open_romance_keeps_their_partner(client, clock, monkeypatch):
    from dungeon.life import body
    monkeypatch.setattr(body, 'state_on', lambda *_args: None)
    open_romance(client)
    begin_partner(client, clock)
    with client.app.state.database.connect(write=True) as connection:
        love_life.advance(connection, current(client), client.app.state.life.world, clock.now())
    [after] = partner_row(client)
    assert after['ended_on'] is None


def test_the_banks_keep_to_the_citys_time_and_the_season():
    bank, cities = love_life.bank(), catalog.cities()
    every = {*bank['met'], *bank['share_new'], *bank['dates'], *bank['splits'],
             *(line for lines in bank['milestones'].values() for line in lines)}
    assert set(bank['tags']) == {'older', 'modern', 'cold', 'warm'}
    assert set(love_life.tags()) <= every
    june, january = date(2027, 6, 12), date(2027, 1, 12)
    baltimore, london = cities['baltimore'], cities['london-1895']
    modern_june = love_life.fitting(bank['met'] + bank['dates'], baltimore, june)
    assert 'outside the theatre in the rain, sharing a cloak' not in modern_june
    assert 'Played in the snow with {partner}. Lost the snowball fight badly.' not in modern_june
    assert 'Played in the snow with {partner}. Lost the snowball fight badly.' in love_life.fitting(
        bank['dates'], baltimore, january)
    assert 'Picnic in the park with {partner}. The ants came too.' not in love_life.fitting(
        bank['dates'], baltimore, january)
    older = love_life.fitting(bank['splits'], london, june)
    assert '{partner} ended it in a letter. A letter! After all that time.' not in older
    assert 'outside the theatre in the rain, sharing a cloak' in love_life.fitting(bank['met'], london, june)
    # Miami never freezes; a city the app doesn't know reads as today's, in a northern year.
    assert not set(bank['tags']['cold']) & set(love_life.fitting(bank['dates'], cities['miami'], january))
    assert love_life.fitting(bank['met'], None, june) == love_life.fitting(bank['met'], baltimore, june)
    # No "met" line puts the partner behind a counter (a data analyst became "the guy from the tailor's shop").
    assert not [line for line in bank['met'] if re.search(r'came out with an invitation|of \{their\} honey', line)]


def test_the_paper_says_were_wed_in_older_eras(monkeypatch):
    from dungeon.world import couples as couples_module
    data = catalog.cities()['london-1895']
    sheet = townsfolk.residents(data, data['neighborhoods'][0]['id'])[0]
    item = {'what': 'married', 'day': date(1895, 6, 12), 'partner': {'name': 'George', 'full': 'George Hale'}}
    monkeypatch.setattr(paper, 'sample', lambda *_args: [sheet])
    monkeypatch.setattr(couples_module, 'events', lambda *_args: [item])
    [found] = paper.couples_news(data, (date(1895, 6, 10), date(1895, 6, 16)))
    assert found['headline'] == f"{sheet['name']} and George were wed." and ' wed on ' in found['text']
    [modern] = paper.couples_news(catalog.cities()['baltimore'], (date(2027, 6, 10), date(2027, 6, 16)))
    assert modern['headline'].endswith('got married.')


def test_with_breakups_off_as_on_an_easy_life_their_couple_never_splits(client, mira, clock, monkeypatch):  # noqa: F811
    names = {'name': 'Mira', 'partner': 'Sam', 'a': 'Sam', 'b': '', 'step': 'being exclusive'}
    off = consequences.odds(love_life.NEXT, {'love_life': 1, 'drama': 0, 'step': 7, 'can_up': 0, 'breakups': 0}, names)
    assert off[2]['odds'] == 0 and 'breakups are off (an easy life has none)' in off[2]['reasons']
    assert client.put('/api/life/settings', json={'breakups': False}).status_code == 200
    found = begin_partner(client, clock)
    real = consequences.roll

    def roll(seed, options):  # A split whenever the odds leave any room for one.
        if ':love:' in seed:
            return 2 if options[2]['odds'] > 0 else 0
        return real(seed, options)
    monkeypatch.setattr(consequences, 'roll', roll)
    clock.advance(timedelta(days=1500))
    with client.app.state.database.connect(write=True) as connection:
        love_life.advance(connection, current(client), client.app.state.life.world, clock.now())
    [after] = partner_row(client)
    assert after['id'] == found['id'] and after['ended_on'] is None
