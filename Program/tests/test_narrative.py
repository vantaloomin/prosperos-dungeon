"""Narrative Only (dungeon/rules/narrative.py, dungeon/judge.py): no stats and no dice; a judge's verdict per action."""
import json

from conftest import Chunk, tell
from test_rulesets import start
from test_travel import ok

from dungeon import judge, turn
from dungeon.rules import narrative


def judging(provider, verdicts):
    """The judge answers with `verdicts`; everyone else gets a line of story."""
    def respond(system, messages):
        text = json.dumps({'verdicts': verdicts}) if system == judge.SYSTEM else 'The bar goes quiet.'
        return [Chunk(text), Chunk('', 'stop')]
    provider.respond = respond


def player(client, **extra):
    persona = {'name': 'Dale', 'about': 'Thirty-four, overweight, has not left his room in a year.'}
    ok(start(client, persona=persona, ruleset='narrative',
             narrative={'good_at': ['old games'], 'bad_at': ['talking to women']}, **extra))


def test_the_judge_decides_each_action_from_who_the_character_is(client, connected, provider, app):
    player(client)
    view = ok(client.get('/api/story/sheet'))
    assert (view['ruleset'], view['ruleset_name'], view['good_at'], view['bad_at']) == \
        ('narrative', 'Narrative', ['old games'], ['talking to women'])
    judging(provider, [{'verdict': 'no_but', 'reason': 'he opens with her looks; she does laugh at the joke'}])
    tell(client, 'I try to seduce the shopkeeper with my best line.', 'story-0001')
    asked = next(request for request in provider.requests if request['system'] == judge.SYSTEM)
    told = asked['messages'][-1]['content']
    assert 'overweight' in told and 'bad at talking to women' in told and 'seduce the shopkeeper' in told
    assert '## Scene' in told
    with app.state.database.connect() as connection:
        row = connection.execute('SELECT band, die, natural, ruleset, skill FROM story_rolls').fetchone()
    assert tuple(row) == ('failure_upside', 0, 0, 'narrative',
                          'No, but: he opens with her looks; she does laugh at the joke')
    narrator = [request for request in provider.requests if request['system'] != judge.SYSTEM][-1]['system']
    assert 'fails, but something useful comes out of the attempt. Why: he opens with her looks' in narrator


def test_no_roll_card_is_ever_shown_but_the_gm_view_sees_the_verdicts(client, connected, provider):
    player(client, table={'show_odds': True})
    judging(provider, [{'verdict': 'yes', 'reason': 'an easy ask'}])
    tell(client, 'I try to convince the shopkeeper to let me sleep in the back room.', 'story-0001')
    lines = [row for row in ok(client.get('/api/story'))['messages'] if row['role'] == 'user']
    assert 'rolls' not in lines[0] and not ok(client.get('/api/story'))['dice_shown']
    ok(client.put('/api/story/table', json={'gm_view': True}))
    lines = [row for row in ok(client.get('/api/story'))['messages'] if row['role'] == 'user']
    assert lines[0]['rolls'] and lines[0]['rolls'][0]['skill'].startswith('Yes')


def test_with_no_readable_verdict_the_difficulty_decides_without_dice():
    assert narrative.result(None, '', 'hard')['band'] == 'failure_upside'
    assert narrative.result('maybe', '', 'easy')['band'] == 'success'
    assert narrative.result('no', 'locked tight', 'easy')['skill'] == 'No: locked tight'
    assert judge.verdicts('{"verdicts": [{"verdict": "yes", "reason": "fine"}]}', 2) is None
    assert judge.verdicts('{"verdicts": [{"verdict": "sure"}]}', 1) == [{'verdict': None, 'reason': ''}]
    assert turn.judged_why({'ruleset': 'narrative', 'skill': 'Yes, but: costs him'}) == 'costs him'
    assert turn.judged_why({'ruleset': 'marvel', 'skill': 'x: y'}) == ''
