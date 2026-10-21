"""Gear and the shop (dungeon/inventory.py): the purse, the pack, carry slots and Pell's Provisions."""
from datetime import timedelta

from conftest import Chunk, tell

from dungeon import inventory
from dungeon.world import catalog


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def begin(client, premade='agna-holt', place='pell-provisions'):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': place}))
    ok(client.delete('/api/story'))
    return ok(client.post('/api/story/start', json={'premade_id': premade}))


def begin_when(client, clock, open_now=True, premade='agna-holt'):
    """Start the story at Pell's at an hour when the shop is open (or shut), moving the app clock an hour at a time."""
    for _ in range(24 * 7):
        begin(client, premade)
        if ok(client.get('/api/story/gear'))['shop']['open'] == open_now:
            return
        clock.instant = clock.now() + timedelta(hours=1)
    raise AssertionError("Pell's never opens or never shuts.")


def test_every_item_file_prices_from_its_catalog_and_kits_fit():
    for path in inventory.ITEMS.glob('*.json'):
        data = inventory.catalog(path.stem)
        ids = {entry['id'] for entry in data['items']}
        city = catalog.city(path.stem)
        places = {place['id'] for place in city['places']}
        for shop in data['shops']:
            assert shop['place'] in places and set(shop['stock']) <= ids and 0 < shop['sell_rate'] < 1
        for kit in data['kits'].values():
            assert set(kit['items']) <= ids and kit['coins'] >= 0
        # Ordinary things stay within ordinary means: no shop item costs more than a month of a logger's wage.
        wage = next(price['high'] for price in city['prices'] if price['id'] == 'day-wage')
        for shop in data['shops']:
            for item_id in shop['stock']:
                assert inventory.item(path.stem, item_id)['price'] <= wage * 30, item_id


def test_a_premade_starts_with_their_kit_and_the_narrator_knows_it(client, connected, provider):
    begin(client)
    gear = ok(client.get('/api/story/gear'))
    assert gear['coins'] == 340 and gear['currency']['symbol'] == 'cr.'
    assert {item['item_id'] for item in gear['items']} == {'sword', 'knife', 'blanket', 'boots', 'whetstone'}
    assert gear['slots']['max'] == 5 + 16 / 2 and gear['slots']['used'] == 1 + 0.25 + 1 + 1 + 0.1
    provider.replies = [[Chunk('The bell over the door rings.'), Chunk('', 'stop')]]
    tell(client, 'I look at the shelves.', 'story-0001')
    narrator = provider.requests[-1]['system']
    assert 'Carrying (kept by the game' in narrator and 'Plain sword' in narrator and 'Purse: 3.40 cr.' in narrator
    assert '## The shop here' in narrator


def test_buying_and_selling_at_the_counter(client, connected, clock, app):
    begin_when(client, clock)
    shop = ok(client.get('/api/story/gear'))['shop']
    assert shop['open'] and shop['keeper'].startswith('the ')
    rope = next(row for row in shop['stock'] if row['item_id'] == 'rope')
    assert (rope['price'], rope['qty']) == (75, 5)

    bought = ok(client.post('/api/story/shop/buy', json={'item_id': 'rope', 'qty': 2}))
    assert bought['coins'] == 340 - 150
    assert next(row for row in bought['shop']['stock'] if row['item_id'] == 'rope')['qty'] == 3
    assert ok(client.get('/api/story'))['messages'][-1]['text'] == 'You buy 2 × Rope, fifty feet for 1.50 cr.'

    # Too dear, too heavy, or not stocked: refused, and nothing changes.
    assert client.post('/api/story/shop/buy', json={'item_id': 'lantern', 'qty': 2}).status_code == 409
    assert client.post('/api/story/shop/buy', json={'item_id': 'felling-axe'}).status_code == 404
    assert client.post('/api/story/shop/buy', json={'item_id': 'rope', 'qty': 4}).status_code == 409

    # Pell's buys what it deals in at half price; it doesn't buy swords.
    gear = ok(client.get('/api/story/gear'))
    boots = next(row for row in gear['items'] if row['item_id'] == 'boots')
    sword = next(row for row in gear['items'] if row['item_id'] == 'sword')
    assert gear['shop']['offers'][boots['id']] == 200 and sword['id'] not in gear['shop']['offers']
    sold = ok(client.post('/api/story/shop/sell', json={'inventory_id': boots['id']}))
    assert sold['coins'] == 190 + 200 and 'boots' not in {row['item_id'] for row in sold['items']}
    assert next(row for row in sold['shop']['stock'] if row['item_id'] == 'boots')['qty'] == 3
    assert client.post('/api/story/shop/sell', json={'inventory_id': sword['id']}).status_code == 409
    with app.state.database.connect() as connection:
        assert [row['kind'] for row in connection.execute('SELECT kind FROM story_trades ORDER BY rowid')] == \
            ['buy', 'sell']


def test_a_full_pack_refuses_more(client, connected, clock, app):
    begin_when(client, clock, premade='tobin-pell')
    with app.state.database.connect(write=True) as connection:
        connection.execute("UPDATE character_stats SET value=2 WHERE stat='Vitality'")
        inventory.set_purse(connection, 10000)
    assert ok(client.get('/api/story/gear'))['slots']['max'] == 6
    response = client.post('/api/story/shop/buy', json={'item_id': 'blanket', 'qty': 3})
    assert response.status_code == 200
    response = client.post('/api/story/shop/buy', json={'item_id': 'cloak', 'qty': 2})
    assert response.status_code == 409 and 'carry' in response.json()['detail']


def test_a_closed_shop_sells_nothing_and_elsewhere_there_is_no_shop(client, connected, clock):
    begin_when(client, clock, open_now=False)
    assert not ok(client.get('/api/story/gear'))['shop']['open']
    assert client.post('/api/story/shop/buy', json={'item_id': 'rope'}).status_code == 409
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'felled-oak'}))
    assert ok(client.get('/api/story/gear'))['shop'] is None
    assert client.post('/api/story/shop/buy', json={'item_id': 'rope'}).status_code == 404


def test_going_back_puts_the_purse_back(client, connected, clock, provider):
    begin_when(client, clock)
    provider.replies = [[Chunk('Fine.'), Chunk('', 'stop')]] * 2
    first = tell(client, 'I nod to the storekeeper.', 'story-0001')
    ok(client.post('/api/story/shop/buy', json={'item_id': 'bread'}))
    tell(client, 'I eat the bread.', 'story-0002')
    assert ok(client.get('/api/story/gear'))['coins'] == 330
    ok(client.post('/api/story/back', json={'message_id': first['message']['id']}))
    assert ok(client.get('/api/story/gear'))['coins'] == 340


def test_a_made_character_gets_the_default_kit(client, connected):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood'}))
    ok(client.delete('/api/story'))
    stats = {'Mind': 10, 'Allure': 10, 'Resolve': 10, 'Vitality': 10, 'Essence': 10, 'Luck': 10}
    ok(client.post('/api/story/start', json={'persona': {'name': 'Wat Fenn'}, 'stats': stats}))
    gear = ok(client.get('/api/story/gear'))
    assert gear['coins'] == 500 and {item['item_id'] for item in gear['items']} == {'knife', 'bread', 'waterskin', 'cloak'}
