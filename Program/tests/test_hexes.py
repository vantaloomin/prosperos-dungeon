"""The hex crawl (dungeon/hexes.py): authored hexes, land generated past them from the seed, roads, fog of war."""
from conftest import Chunk, tell
from test_inventory import begin
from test_travel import Road

from dungeon import hexes, travel


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def vallarith() -> dict:
    return next(found for found in travel.maps() if found.get('world') == 'vallarith')


def test_worlds_crawl_hexes_unless_their_map_opts_out():
    assert hexes.is_hex(vallarith())
    # Havenbrooke goes by car or bus, and BABEL climbs the Stair: both keep their roads.
    assert {found['world'] for found in travel.maps() if not hexes.is_hex(found)} >= {'havenbrooke'}
    babel = next(found for found in travel.maps() if any(node['id'] == 'the-concourse' for node in found['nodes']))
    assert not hexes.is_hex(babel)


def test_the_authored_map_is_canon_and_its_places_sit_on_land():
    board = hexes.Grid(vallarith(), 'one')
    other = hexes.Grid(vallarith(), 'two')
    for node in vallarith()['nodes']:
        at = board.places[node['id']]
        assert board.cell(at)['terrain'] != 'water' and board.cell(at)['place'] == node['id']
        assert board.cell(at)['region'] == node['region']
    # Inside the authored map the seed changes nothing.
    assert all(board.cell((q, 60)) == other.cell((q, 60)) for q in range(20, 80))


def test_land_past_the_map_comes_from_the_seed_alone_whatever_order_it_is_seen_in():
    far = [(200 + q, r) for q in range(12) for r in range(-30, -18)]
    forward, backward = hexes.Grid(vallarith(), 'seed'), hexes.Grid(vallarith(), 'seed')
    ahead = [forward.cell(at) for at in far]
    behind = [backward.cell(at) for at in reversed(far)][::-1]
    assert ahead == behind
    elsewhere = [hexes.Grid(vallarith(), 'another seed').cell(at) for at in far]
    assert elsewhere != ahead
    # Out there it is the wilds, and the land is of more than one kind.
    land = [cell for cell in ahead if cell['terrain'] != 'water']
    assert land and {cell['region'] for cell in land} == {'wilds'}
    assert len({cell['terrain'] for cell in ahead}) > 1


def test_a_map_without_authored_hexes_is_generated_around_its_places():
    travel_map = {'world': 'nowhere', 'nodes': [
        {'id': 'a', 'name': 'A', 'region': 'r', 'city': 'c', 'place': 'p', 'safe': True, 'map': {'x': 0.1, 'y': 0.1}},
        {'id': 'b', 'name': 'B', 'region': 'r', 'city': 'c', 'place': 'q', 'safe': True, 'map': {'x': 0.2, 'y': 0.1}}],
        'routes': [{'from': 'a', 'to': 'b', 'hours': 5, 'terrain': 'the old road', 'danger': 'low'}],
        'regions': {'r': {'danger': 'low'}}}
    board = hexes.Grid(travel_map, 'seed')
    legs = board.way(board.places['a'], board.places['b'])
    assert legs and legs[-1]['place'] == 'b'
    assert {leg['terrain'] for leg in legs} == {'the old road'}
    assert sum(leg['hours'] for leg in legs) == hexes.distance(board.places['a'], board.places['b'])


def test_two_roads_side_by_side_are_not_one_road():
    travel_map = vallarith()
    board = hexes.Grid(travel_map, 'seed')
    eriane = board.places['eriane']
    for leg in board.way(board.places['kingswood'], eriane):
        assert leg['terrain'] == 'the Cyrel road' and leg['hours'] == hexes.ROAD_HOURS


def test_a_fight_out_in_the_wild_ends_the_journey_at_the_next_place():
    entry = next(entry for entry in vallarith()['encounters']['kingdom-of-cyrel'] if 'Bandits' in str(entry))
    legs = [{'from': [0, 0], 'to': [1, 0], 'hours': 1, 'terrain': 'the Cyrel road', 'danger': 'low'},
            {'from': [1, 0], 'to': [2, 0], 'hours': 1, 'terrain': 'the Cyrel road', 'danger': 'low'},
            {'from': [2, 0], 'to': [3, 0], 'hours': 1, 'terrain': 'the Cyrel road', 'danger': 'low', 'place': 'eriane'},
            {'from': [3, 0], 'to': [4, 0], 'hours': 1, 'terrain': 'the Cyrel road', 'danger': 'low', 'place': 'cyrel'}]
    rolls = [{'threat': entry['threat']['text'], 'band': 'failure'}]
    walked, lines = travel.travelled({'mode': 'hex', 'legs': legs, 'encounter': {'leg': 0, 'entry': entry}}, rolls)
    assert walked == legs[:3] and travel.end_of({'mode': 'hex'}, walked) == 'eriane'
    assert travel.STOPPED in lines[-1]


def test_a_journey_shows_the_hexes_it_crosses(client, connected, provider, app):
    begin(client)
    before = ok(client.get('/api/story'))['map']
    assert before['hexes'] and any(cell['place'] == 'kingswood' and cell['visited'] for cell in before['hexes'])
    app.state.dice = Road(99)
    provider.replies = [[Chunk('The road goes on.'), Chunk('', 'stop')]]
    tell(client, 'I set out for Eriane.', 'story-0001')
    after = ok(client.get('/api/story'))['map']
    walked = {(cell['q'], cell['r']) for cell in after['hexes'] if cell['visited']}
    board = hexes.Grid(vallarith(), 'any')
    assert {board.places['kingswood'], board.places['eriane']} <= walked
    assert len(after['hexes']) > len(before['hexes'])
    with app.state.database.connect() as connection:
        seed = connection.execute('SELECT seed FROM story_campaign WHERE id=1').fetchone()[0]
    assert seed
