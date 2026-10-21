"""What the character carries and what the town sells, v0 (requirements "Inventory and equipment", "Shops and
economy"; docs/story.md "Gear and the shop").

Code owns every item and every coin: the narrator is told what the character carries, what is in their purse and,
in a shop, its stock and prices, and it never adds, removes or prices anything. A town's item file
(world/data/items/<city>.json) lists its items with base prices in the city's currency, its shops with their
starting stock, and the kit each premade starts with.

- Money is kept in hundredths of the currency, so sums never drift.
- Carrying is counted in slots: a knife takes a quarter, a sword one. The character carries 5 plus half their
  Vitality.
- A shop is open while one of its staff is at work (the townsfolk rules). Its stock is finite: what the player
  buys is gone. It buys what it deals in at its sell rate (half the base price).
- Buying and selling happen on the shop window; each trade is logged and adds a line to the story.

All of it is game state, branched with the story (dungeon/timeline.py SAVED).
"""
import json
from pathlib import Path

from dungeon.database import identifier, many, optional
from dungeon.errors import require
from dungeon.sheet import stats as sheet_stats

ITEMS = Path(__file__).parent / 'world' / 'data' / 'items'
BASE_SLOTS = 5


def catalog(city_id: str) -> dict:
    path = ITEMS / f'{city_id}.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'items': [], 'shops': [], 'kits': {}}


def item(city_id: str, item_id: str) -> dict | None:
    return next((entry for entry in catalog(city_id)['items'] if entry['id'] == item_id), None)


def cents(amount: float) -> int:
    return round(amount * 100)


def money_text(hundredths: int, currency: dict) -> str:
    """'3.40 cr.', or the currency's name when it has no symbol."""
    amount = f'{hundredths / 100:.2f}'
    return f"{amount} {currency.get('symbol') or currency.get('name') or ''}".strip()


# The purse and the pack --------------------------------------------------------------------------

def purse(connection) -> int:
    row = optional(connection, 'SELECT coins FROM story_purse WHERE id=1')
    return row['coins'] if row else 0


def set_purse(connection, coins: int):
    connection.execute('INSERT INTO story_purse (id, coins) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET '
                       'coins=excluded.coins', (coins,))


def carried(connection, city_id: str) -> list[dict]:
    rows = many(connection, 'SELECT * FROM story_inventory WHERE qty > 0 ORDER BY rowid')
    result = []
    for row in rows:
        entry = item(row['city_id'], row['item_id']) or item(city_id, row['item_id'])
        if entry:
            result.append(row | {'name': entry['name'], 'category': entry['category'], 'slots': entry['slots'],
                                 'price': entry['price']})
    return result


def capacity(connection) -> float:
    return BASE_SLOTS + sheet_stats(connection).get('Vitality', 10) / 2


def used(rows: list[dict]) -> float:
    return sum(row['slots'] * row['qty'] for row in rows)


def add_item(connection, city_id: str, item_id: str, qty: int = 1):
    row = optional(connection, 'SELECT id FROM story_inventory WHERE item_id=? AND city_id=?', (item_id, city_id))
    if row:
        connection.execute('UPDATE story_inventory SET qty=qty+? WHERE id=?', (qty, row['id']))
    else:
        connection.execute('INSERT INTO story_inventory (id, city_id, item_id, qty) VALUES (?, ?, ?, ?)',
                           (identifier(), city_id, item_id, qty))


def give_kit(connection, city_id: str, premade_id: str | None):
    """The starting purse and pack: the premade's own kit, or the town's default one."""
    kits = catalog(city_id)['kits']
    kit = kits.get(premade_id or '') or kits.get('default')
    connection.execute('DELETE FROM story_inventory')
    set_purse(connection, cents(kit['coins']) if kit else 0)
    for item_id, qty in (kit or {}).get('items', {}).items():
        add_item(connection, city_id, item_id, qty)


def prompt_text(connection, city_id: str, currency: dict) -> str:
    """What the character carries and has in their purse, for the narrator."""
    rows = carried(connection, city_id)
    if not rows and not purse(connection):
        return ''
    things = ', '.join(f"{row['name']}" + (f" (x{row['qty']})" if row['qty'] > 1 else '') for row in rows)
    return (f"Carrying (kept by the game; nothing else, and nothing appears or goes without the game): "
            f"{things or 'nothing'}. Purse: {money_text(purse(connection), currency)}.")


# The shop ----------------------------------------------------------------------------------------

def shop_at(city_id: str, place_id: str) -> dict | None:
    return next((shop for shop in catalog(city_id)['shops'] if shop['place'] == place_id), None)


def stock(connection, city_id: str, shop: dict) -> dict[str, int]:
    """The shop's stock, seeded from its file the first time anyone looks."""
    rows = many(connection, 'SELECT item_id, qty FROM story_stock WHERE city_id=? AND place_id=?',
                (city_id, shop['place']))
    if not rows:
        for item_id, qty in shop['stock'].items():
            connection.execute('INSERT INTO story_stock (city_id, place_id, item_id, qty) VALUES (?, ?, ?, ?)',
                               (city_id, shop['place'], item_id, qty))
        return dict(shop['stock'])
    return {row['item_id']: row['qty'] for row in rows}


def offer(shop: dict, entry: dict) -> int | None:
    """What the shop pays for one of an item, in hundredths; None if it does not deal in it."""
    if entry['category'] not in shop['buys'] or not entry.get('legal', True):
        return None
    return max(1, cents(entry['price'] * shop['sell_rate']))


def window(connection, city_id: str, shop: dict, open_now: bool, keeper: str) -> dict:
    found = stock(connection, city_id, shop)
    order = [entry['id'] for entry in catalog(city_id)['items']]
    items = [(item(city_id, item_id), found[item_id])
             for item_id in sorted(found, key=lambda key: order.index(key) if key in order else len(order))]
    pack = carried(connection, city_id)
    return {'place_id': shop['place'], 'open': open_now, 'keeper': keeper,
            'stock': [{'item_id': entry['id'], 'name': entry['name'], 'category': entry['category'],
                       'price': cents(entry['price']), 'qty': qty, 'slots': entry['slots']}
                      for entry, qty in items if entry and qty > 0],
            'offers': {row['id']: price for row in pack if (price := offer(shop, row)) is not None}}


def shop_prompt(view: dict, currency: dict) -> str:
    if not view['open']:
        return '## The shop here\nIt is closed now; nobody is behind the counter.'
    lines = [f"- {row['name']}: {money_text(row['price'], currency)} ({row['qty']} left)" for row in view['stock']]
    return ('## The shop here (stock and prices kept by the game; quote them exactly, invent nothing)\n'
            f"{view['keeper'] or 'The shopkeeper'} sells:\n" + '\n'.join(lines) +
            '\nSales happen at the counter (the shop window): the shopkeeper can name what is there and its price, '
            'but nothing changes hands until the game says so.')


def log(connection, now: str, kind: str, city_id: str, item_id: str, qty: int, amount: int):
    connection.execute('INSERT INTO story_trades (id, kind, city_id, item_id, qty, amount, created_at) '
                       'VALUES (?, ?, ?, ?, ?, ?, ?)', (identifier(), kind, city_id, item_id, qty, amount, now))


def buy(connection, city_id: str, shop: dict, item_id: str, qty: int, now: str) -> dict:
    entry = item(city_id, item_id)
    have = stock(connection, city_id, shop).get(item_id, 0)
    require(entry is not None and have > 0, 'The shop has none of that.', 404)
    require(qty <= have, f'The shop has only {have}.', 409)
    cost = cents(entry['price']) * qty
    require(cost <= purse(connection), "You can't afford that.", 409)
    pack = carried(connection, city_id)
    require(used(pack) + entry['slots'] * qty <= capacity(connection), "You can't carry that much more.", 409)
    connection.execute('UPDATE story_stock SET qty=qty-? WHERE city_id=? AND place_id=? AND item_id=?',
                       (qty, city_id, shop['place'], item_id))
    set_purse(connection, purse(connection) - cost)
    add_item(connection, city_id, item_id, qty)
    log(connection, now, 'buy', city_id, item_id, qty, cost)
    return {'name': entry['name'], 'qty': qty, 'amount': cost}


def sell(connection, city_id: str, shop: dict, inventory_id: str, qty: int, now: str) -> dict:
    row = optional(connection, 'SELECT * FROM story_inventory WHERE id=? AND qty > 0', (inventory_id,))
    require(row is not None, "You don't have that.", 404)
    require(qty <= row['qty'], f"You have only {row['qty']}.", 409)
    entry = item(row['city_id'], row['item_id'])
    price = offer(shop, entry) if entry else None
    require(price is not None, "This shop doesn't buy that.", 409)
    stock(connection, city_id, shop)
    connection.execute('UPDATE story_inventory SET qty=qty-? WHERE id=?', (qty, inventory_id))
    connection.execute('INSERT INTO story_stock (city_id, place_id, item_id, qty) VALUES (?, ?, ?, ?) '
                       'ON CONFLICT(city_id, place_id, item_id) DO UPDATE SET qty=qty+excluded.qty',
                       (city_id, shop['place'], row['item_id'], qty))
    set_purse(connection, purse(connection) + price * qty)
    log(connection, now, 'sell', city_id, row['item_id'], qty, price * qty)
    return {'name': entry['name'], 'qty': qty, 'amount': price * qty}

