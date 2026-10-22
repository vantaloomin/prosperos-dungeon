"""Combat v0 (dungeon/combat.py): rounds, wounds, morale, the defeat table and healing."""
from conftest import Chunk, tell

from dungeon import combat


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def reply(text):
    return [Chunk(text), Chunk('', 'stop')]


class Dice:
    """A d100 that always shows `natural`; every other die rolls `other` ('high' or 'low')."""

    def __init__(self, natural, other='high'):
        self.natural, self.other = natural, other

    def randint(self, low, high):
        return self.natural if high == 100 else (high if self.other == 'high' else low)

    def choice(self, items):
        return next((item for item in items if isinstance(item, dict) and 'boar' in item['text']), items[0])


def foe(**values):
    return {'id': 'f', 'name': 'the bandit', 'vitality': 10, 'resolve': 10, 'weapon': 0, 'wound': 0,
            'zone': 'engaged', 'broken': False} | values


def roll(action, band, stat='Vitality'):
    return {'action': action, 'band': band, 'stat': stat}


def test_a_round_hits_breaks_and_wins(app):
    with app.state.database.connect(write=True) as connection:
        state = {'round': 0, 'wants': 'rob', 'foes': [foe(), foe(id='g', name='the lookout', zone='near')]}
        state, lines, ending = combat.play_round(connection, state, [roll('I stab the bandit', 'success')],
                                                 [{'item_id': 'knife'}], Dice(20))
        # Two levels for a success with a knife; Hurt isn't enough to shake the lookout, who closes in.
        assert state['foes'][0]['wound'] == 2 and ending == ''
        assert lines[0] == "The player's character hits the bandit: now hurt." and 'The lookout closes in.' in lines
        state, lines, ending = combat.play_round(connection, state, [roll('I stab the bandit', 'critical_success')],
                                                 [{'item_id': 'sword'}], Dice(20))
        # Down, and the lookout fails its morale and breaks: the fight is won.
        assert state['foes'][0]['wound'] == combat.DYING and state['foes'][1]['broken'] and ending == 'won'


def test_foes_hit_back_and_a_guard_or_flight_helps(app):
    with app.state.database.connect(write=True) as connection:
        state = {'round': 0, 'wants': 'kill', 'foes': [foe(weapon=1)]}
        _, lines, _ = combat.play_round(connection, state, [], [], Dice(80))
        assert combat.condition(connection)['level'] == 3 and lines == [
            "The bandit hits the player's character: now wounded."]
        # Wounded makes physical actions a step harder; Maimed makes everything harder too.
        assert [action['difficulty'] for action in combat.adjust(connection, [
            {'action': 'run', 'stat': 'Vitality', 'difficulty': 'normal'},
            {'action': 'lie', 'stat': 'Allure', 'difficulty': 'normal'}])] == ['hard', 'normal']
        _, lines, _ = combat.play_round(connection, state, [roll('I parry', 'success')], [], Dice(40))
        assert lines == ['The bandit attacks and misses.']
        _, lines, ending = combat.play_round(connection, state, [roll('I run away', 'success')], [], Dice(80))
        assert ending == 'escaped' and lines == ["The player's character gets away."]


def test_the_defeat_table_follows_what_the_winners_want(app):
    with app.state.database.connect(write=True) as connection:
        connection.execute('INSERT INTO story_purse (id, coins) VALUES (1, 500)')
        outcome, _ = combat.defeat(connection, {'wants': 'kill', 'foes': [foe()]}, Dice(20, 'low'), '2026-10-21')
        assert outcome == 'death' and combat.condition(connection) == {'level': 5, 'dead': True, 'rested': 0}
        # Clinging on rules death out; robbers mostly rob.
        outcome, _ = combat.defeat(connection, {'wants': 'rob', 'foes': [foe()]}, Dice(95, 'low'), '2026-10-21')
        assert outcome == 'robbed' and combat.condition(connection) == {'level': 4, 'dead': False, 'rested': 0}
        assert connection.execute('SELECT coins FROM story_purse').fetchone()[0] == 0
        outcome, _ = combat.defeat(connection, {'wants': 'drive_off', 'foes': [foe()]}, Dice(20, 'low'), '')
        assert outcome == 'thrown_out'


def kingswood(client, place):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': place}))
    ok(client.delete('/api/story'))
    return ok(client.post('/api/story/start', json={'premade_id': 'agna-holt'}))


def test_attacking_someone_starts_a_brawl_the_narrator_writes(client, connected, provider, app):
    story = kingswood(client, 'felled-oak')
    with app.state.database.connect() as connection:
        from dungeon import story as story_module
        view = story_module.scene(connection, story_module.story_clock.now(connection, app.state.database.clock))
    # Someone not yet named is aimed at by their work.
    target = view['people'][0]['sheet']
    name = target['full'] or f"the {target.get('occupation') or target['role']}"
    assert story['fight']['fight'] is None and story['fight']['condition'] == 'unhurt'
    app.state.dice = Dice(95)
    provider.replies = [reply('Teeth on the floorboards.')]
    tell(client, f"I punch {name} in the mouth.", 'story-0001')
    narrator = provider.requests[-1]['system']
    assert '## The fight (decided by the game' in narrator and f"hits {name}" in narrator
    assert 'the fight is won' in narrator and ok(client.get('/api/story'))['fight']['fight'] is None

    # Telling it again keeps the round.
    provider.replies = [reply('Teeth again.')]
    ok(client.post('/api/story/retry'))
    assert provider.requests[-1]['system'].count('## The fight') == 1 and f"hits {name}" in \
        provider.requests[-1]['system']


def test_a_danger_brings_a_foe_and_a_dead_character_plays_no_more(client, connected, provider, app):
    kingswood(client, 'the-heartwood')
    app.state.dice = Dice(20, 'low')
    provider.replies = [reply('Something heavy in the brush.')]
    first = tell(client, 'I look around.', 'story-0001')
    fight = ok(client.get('/api/story'))['fight']['fight']
    assert fight['foes'][0]['name'] == 'ley-mad boar' and fight['foes'][0]['state'] == 'unhurt'
    assert fight['foes'][0]['wound'] is None  # Numbers only with the dice shown.
    assert client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'felled-oak'}).status_code == 409

    with app.state.database.connect(write=True) as connection:
        combat.set_condition(connection, 5, dead=True)
    response = client.post('/api/story/messages', json={'text': 'I get up.', 'client_id': 'story-0002'})
    assert response.status_code == 409 and 'dead' in response.json()['detail']
    # Going back brings them back.
    ok(client.post('/api/story/back', json={'message_id': first['message']['id']}))
    assert ok(client.get('/api/story'))['fight']['dead'] is False


def test_wounds_mend_with_nights_of_rest(client, connected, provider, app):
    kingswood(client, 'felled-oak')
    with app.state.database.connect(write=True) as connection:
        combat.set_condition(connection, 3)
    provider.replies = [reply('Morning.'), reply('Three mornings.')]
    # Gritty MARVEL healing: Wounded takes four nights to mend to Hurt.
    tell(client, 'I go to bed and sleep.', 'story-0001')
    assert ok(client.get('/api/story'))['fight']['condition'] == 'wounded'
    assert 'still wounded: 3 more nights of rest to mend' in provider.requests[-1]['system']
    tell(client, 'I rest for three days.', 'story-0002')
    assert ok(client.get('/api/story'))['fight']['condition'] == 'hurt'
    assert "is hurt (kept by the game" in provider.requests[-1]['system']
    # A new wound starts the count again.
    with app.state.database.connect(write=True) as connection:
        combat.set_condition(connection, 1)
        assert combat.mend(connection, 0) == [] and combat.condition(connection)['rested'] == 0
