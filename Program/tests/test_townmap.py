"""Town maps (dungeon/townmap.py): a street map laid out from the town's data and the campaign's seed."""
import math

import pytest

from dungeon import townmap
from dungeon.world import catalog

TOWNS = ('kingswood', 'haven', 'hollin', 'the-concourse', 'the-gilded-bazaar', 'haddon-harbor')


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def test_the_same_town_and_seed_give_the_same_map_and_another_seed_another():
    data = catalog.city('kingswood')
    one, again = townmap.build(data, 'one'), townmap.build(data, 'one')
    assert one == again
    other = townmap.build(data, 'two')
    assert [lot['polygon'] for lot in other['lots']] != [lot['polygon'] for lot in one['lots']]
    # The neighborhoods are the town's own whatever the seed.
    assert {district['id'] for district in other['districts']} == {district['id'] for district in one['districts']}


def test_the_era_picks_the_look_unless_the_town_says():
    assert townmap.style(catalog.city('kingswood')) == 'ink'
    assert townmap.style(catalog.city('haven')) == 'street'
    assert townmap.style(catalog.city('kingswood') | {'town_map': {'style': 'floor'}}) == 'floor'


def test_a_worlds_roads_and_wilds_have_no_town_map():
    for city_id in ('vallarith-road', 'havenbrooke-road', 'babel-floors'):
        assert not townmap.has_map(catalog.city(city_id))
    assert all(townmap.has_map(catalog.city(city_id)) for city_id in TOWNS)


@pytest.mark.parametrize('city_id', TOWNS)
def test_every_place_in_town_is_on_the_map_in_its_own_neighborhood(city_id):
    data = catalog.city(city_id)
    board = townmap.build(data, 'seed')
    away = {found['id'] for found in board['exits']}
    on_lots = {lot['place']['id']: lot for lot in board['lots'] if lot['place']}
    on_ground = {patch['place']['id'] for patch in board['patches'] if patch['place']}
    for place in data['places']:
        if place['neighborhood'] in away:
            continue
        if place['kind'] in townmap.OPEN:
            continue  # a square, park or trail takes a patch when its neighborhood has one to spare
        lot = on_lots[place['id']]
        assert lot['neighborhood'] == place['neighborhood'], place['id']
    # No place is on two lots, and no lot holds two places.
    assert len(on_lots) == sum(1 for lot in board['lots'] if lot['place'])
    assert not on_ground & set(on_lots)
    # Each employer has a building of its own, or shares the place of the same name.
    names = {place['name'].casefold() for place in data['places']}
    for employer in data['employers']:
        if employer['neighborhood'] not in away and employer['name'].casefold() not in names:
            assert on_lots[employer['id']]['neighborhood'] == employer['neighborhood']


def test_no_lot_stands_in_the_river():
    board = townmap.build(catalog.city('kingswood'), 'seed')
    river = board['water'][0]
    for lot in board['lots']:
        for point in lot['polygon']:
            assert townmap.to_line(tuple(point), [tuple(p) for p in river['points']]) > river['width'] / 2


def test_a_neighborhood_far_out_of_town_is_a_road_off_the_map():
    board = townmap.build(catalog.city('hollin'), 'seed')
    assert {found['id'] for found in board['exits']} == {'the-valley-road', 'the-reachwall'}
    assert all(found['at'] and math.hypot(*found['at']) > townmap.TOWN for found in board['exits'])
    assert 'the-reachwall' not in {district['id'] for district in board['districts']}


def test_main_roads_start_at_the_square_and_reach_the_edge():
    board = townmap.build(catalog.city('kingswood'), 'seed')
    square = next(patch for patch in board['patches'] if patch['id'] == board['square'])
    corners = {tuple(point) for point in square['polygon']}
    assert len(board['roads']) >= 3
    for road in board['roads']:
        assert tuple(road[0]) in corners
        assert math.hypot(*road[-1]) > townmap.EDGE


def test_the_story_shows_the_map_of_the_town_it_is_in(client):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
    town = ok(client.get('/api/story/town'))['town']
    assert town['town'] == 'kingswood' and town['name'] == 'Kingswood'
    here = town['here']['place']
    assert any(lot['place'] and lot['place']['id'] == here for lot in town['lots']) or \
        any(patch['place'] and patch['place']['id'] == here for patch in town['patches'])
    assert town['here'] == {'place': 'pell-provisions', 'neighborhood': 'the-crossroads'}
    # The seed is the campaign's, so the map is the same next time.
    assert ok(client.get('/api/story/town'))['town'] == town
    # Out on the road there is no town to map.
    ok(client.put('/api/story/scene', json={'city_id': 'vallarith-road'}))
    assert ok(client.get('/api/story/town'))['town'] is None
