"""Life Cards in play (dungeon/happenings.py): a day in town, a journey and a rest draw from the world's deck."""
import re
from datetime import date

import pytest
from conftest import tell
from test_inventory import begin
from test_rest import out_in_the_badlands
from test_travel import Road, ok, reply

from dungeon import happenings, inventory
from dungeon.life import cards


@pytest.fixture
def dealt(monkeypatch):
    """Life Cards on, with every draw the card named in `dealt.next` (None for nothing), and each call kept."""
    monkeypatch.setattr(happenings, 'ACTIVE', True)

    class Dealer:
        next, calls = None, []

        def draw(self, world, scene, seed, level, intensity, has, recent, region=None, veils=frozenset(), forced=False):
            self.calls.append({'scene': scene, 'level': level, 'region': region, 'recent': recent,
                               'intensity': intensity})
            found = cards.card(world, self.next)
            return {'card': found, 'odds': 0.5, 'veiled': False}

    dealer = Dealer()
    dealer.calls = []
    monkeypatch.setattr(cards, 'draw', dealer.draw)
    return dealer


def test_a_day_in_town_draws_once_and_plays_the_card(client, connected, provider, app, dealt):
    begin(client)
    dealt.next = 'early-tithe'
    with app.state.database.connect() as connection:
        before = inventory.purse(connection)
    reply(provider, 'Soldiers at the doors.')
    tell(client, 'I look out of the window.', 'story-0001')
    narrator = provider.requests[-1]['system']
    assert '## What the world brings' in narrator and 'war tithe, a month early' in narrator
    assert 'It puts a choice to the player: A widow on your street' in narrator
    # Two of a logger's day wages (1.50 cr. each).
    assert 'It costs the character 3.00 cr.' in narrator
    with app.state.database.connect() as connection:
        assert inventory.purse(connection) == max(0, before - 300)
        facts = {row['truth']: row['text'] for row in connection.execute(
            "SELECT truth, text FROM record_entries WHERE subject='The tithe comes early'").fetchall()}
    assert 'lost at cards' in facts['world'] and 'door to door' in facts['belief']
    assert dealt.calls[0]['scene'] == 'town' and dealt.calls[0]['region'] == 'cyrel'
    assert dealt.calls[0]['level'] == cards.DRAMA.index('eventful')
    # The same day draws no more.
    reply(provider, 'Still raining.')
    tell(client, 'I sit down again.', 'story-0002')
    assert len(dealt.calls) == 1 and '## What the world brings' not in provider.requests[-1]['system']


def test_the_drama_setting_and_intensity_decide_what_can_turn_up(client, connected, provider, dealt):
    begin(client)
    ok(client.put('/api/settings', json={'drama': 'quiet', 'intensity': 'restrained'}))
    assert ok(client.get('/api/story'))['intensity']['drama'] == 'quiet'
    reply(provider, 'Quiet.')
    tell(client, 'I wait.', 'story-0001')
    call = dealt.calls[0]
    assert call['level'] == 0 and call['intensity'] == cards.PRESETS['restrained']
    # Cards that need someone the game cannot name yet never come up.
    assert happenings.unnamed('vallarith', faction=True) <= call['recent']


def test_a_road_card_can_bring_a_fight(client, connected, provider, app, dealt):
    begin(client)
    dealt.next = 'hungry-deserters'
    app.state.dice = Road(99)
    reply(provider, 'The road goes on.')
    tell(client, 'I set out for Eriane.', 'story-0001')
    story = ok(client.get('/api/story'))
    assert story['scene']['place']['id'] == 'eriane' and story['fight']['fight']['foes'][0]['name'] == 'deserter 1'
    assert dealt.calls[-1]['scene'] == 'road' and 'It comes to a fight: deserters close in.' in \
        provider.requests[-1]['system']


def test_a_rest_card_with_foes_ends_the_rest(client, connected, provider, app, dealt):
    out_in_the_badlands(client)
    dealt.next = 'wolves'
    app.state.dice = Road(99)
    reply(provider, 'Eyes in the dark.')
    tell(client, 'I make camp and keep watch.', 'story-0001')
    narrator = provider.requests[-1]['system'].split('## The rest')[1]
    assert 'starving wolves close in' in narrator and 'The rest ends here' in narrator
    assert [call['scene'] for call in dealt.calls] == ['rest']


def test_every_card_the_game_can_draw_has_every_name_filled(app):
    """Real draws: whatever turns up in town, on the road or at rest, the text leaves no placeholder behind."""
    names = {'pc': 'Agna', 'npc': 'Corin Ashby', 'town': 'Kingswood'}
    with app.state.database.connect() as connection:
        for n in range(150):
            for scene, place in (('town', ('kingswood', 'felled-oak')), ('road', ('vallarith-road', 'eriane')),
                                 ('rest', ('vallarith-road', 'adlmyr'))):
                drawn = happenings.draw(connection, scene, f'seed-{n}', *place, {'intensity': {'drama': 'merciless'}},
                                        {'levels': cards.PRESETS['unflinching'], 'veils': []}, date(1290, 5, 1))
                if drawn:
                    for field in ('title', 'truth', 'seen', 'pressure'):
                        assert not re.search(r'\{\w+\}', happenings.fill(drawn['card'][field] or '', names))
