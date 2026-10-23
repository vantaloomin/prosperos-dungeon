"""Havenbrooke in play: the world's own start date, the school a premade starts in, and trips by car or bus."""
from datetime import datetime

from conftest import tell
from test_travel import Road, clock_at, ok, reply

from dungeon import campaign, factions, institutions, packages, tiers, travel
from dungeon.life import cards


def begin(client, premade='michael-reeves', place='nexus-housing'):
    ok(client.put('/api/story/scene', json={'city_id': 'haven', 'place_id': place}))
    ok(client.delete('/api/story'))
    return ok(client.post('/api/story/start', json={'premade_id': premade}))


def test_the_package_and_its_engine_data_hang_together(app):
    """With the data folder in use, as in the app: the school is in the package's own engine data."""
    assert 'havenbrooke' in packages.builtin_ids()
    assert tiers.world_of('haven') == tiers.world_of('havenbrooke-road') == 'havenbrooke'
    school = institutions.find('havenbrooke', 'havenbrooke-university')
    assert factions.find('havenbrooke', school['faction'])
    classes = {item['id'] for item in school['classes']}
    for premade in campaign.premades('haven'):
        assert sum(premade['stats'].values()) <= 60
        assert set(premade['enrolled'][0]['classes']) <= classes
    assert cards.problems(cards.deck('havenbrooke')) == []


def test_a_campaign_starts_in_fall_2009_enrolled_in_the_premades_classes(client, app):
    begin(client)
    assert clock_at(app) == datetime(2009, 8, 31, 8)
    journal = ok(client.get('/api/story/journal'))['institutions']
    assert [item['term'] for item in journal] == ['Fall 2009']
    assert {item['id'] for item in journal[0]['classes']} == {'cs-230', 'cs-215', 'bus-210', 'hum-101'}
    # Michael has no car; the kit says how he gets about, as Austin's says he drives.
    carried = {item['item_id'] for item in ok(client.get('/api/story/gear'))['items']}
    assert 'shuttle-pass' in carried and 'truck-keys' not in carried
    begin(client, 'austin-hallward')
    assert 'truck-keys' in {item['item_id'] for item in ok(client.get('/api/story/gear'))['items']}


def test_a_trip_goes_by_car_or_bus_and_eats_nothing_from_the_pack(client, connected, provider, app):
    begin(client)
    app.state.dice = Road(99)
    before = clock_at(app)
    reply(provider)
    tell(client, 'I head to Ithaca.', 'story-0001')
    story = ok(client.get('/api/story'))
    assert (story['scene']['city']['id'], story['scene']['place']['id']) == ('havenbrooke-road', 'ithaca')
    assert (clock_at(app) - before).total_seconds() >= 42 * 60
    journey = provider.requests[-1]['system'].split('## The journey')[1]
    assert 'from Haven to Ithaca by car or bus on Route 34B along the lake: 42 minutes on the road' in journey
    assert 'hungry' not in journey and 'on foot' not in journey
    assert travel.duration(1) == 'an hour' and travel.duration(4.5) == '4.5 hours'


def test_heading_to_class_goes_to_the_room_so_the_class_is_attended(client, connected, provider, app):
    # Playtest m6a: "I head to my first class" left the lead at home, and the class was missed.
    begin(client)
    first = next(item for item in ok(client.get('/api/story/journal'))['institutions'][0]['today'] if item['place_id'])
    reply(provider)
    tell(client, 'I check my schedule and head to my first class of the day.', 'story-0001')
    assert ok(client.get('/api/story'))['scene']['place']['id'] == first['place_id']
