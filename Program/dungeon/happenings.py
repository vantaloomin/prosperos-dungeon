"""Life Cards in play (requirements "Intensity and tone": drama; "Time and travel"; docs/life-cards.md;
docs/story.md "Life Cards").

The world's deck (dungeon/life/cards.py) is drawn into the story by code, with the same seeded dice:
- **A day in town** draws once, on the first line of each story day spent in a town on the travel map.
- **A journey** draws once, for the road it ends on, unless a road encounter already stopped it.
- **A rest out in the open** draws once; a card that brings foes ends the rest like a bad night.

How often a scene draws anything, and which cards can turn up, follow the **drama** level (the world's own, or the
player's: quiet, uneasy, eventful, merciless); the intensity preset leaves out cards it does not allow. Drama never
touches roll odds.

A drawn card's hidden truth goes in the record as the world's (and what the character sees, as their belief when
it is not the whole truth); the narrator gets what the character sees and any choice it puts to them. Code applies
the effects the game can keep so far: stress, a wound, coin in an unskilled day's wages, food gained or lost, time,
someone's feelings, and a fight. Market, rumor, quest, faction, fate and pursuer effects wait for their systems
(factions, off-page beats, word gets around); their truth is kept in the record meanwhile.

Draws are game state (story_cards), branched with the story; each line's draw is kept with it, so telling the turn
again draws nothing new.
"""
import re
from datetime import date, timedelta

from dungeon import combat, factions, feelings, injuries, inventory, record, stress, travel
from dungeon.database import encode, many, settings
from dungeon.life import cards

DEFAULT_DRAMA = 'uneasy'
# Off only for tests that are about something else (tests/conftest.py).
ACTIVE = True
# Cards that need someone the game cannot name yet: a bonded companion, a beat's absent character; and a faction,
# where no faction has a hand.
UNNAMED = re.compile(r'\{(bond|them)\}')
FACTION = re.compile(r'\{faction\}')
WAGE_ID = 'day-wage'
DEFAULT_WAGE = 100
# Who a card's fight brings (a level-one tier until "Scaling and tiers"): the name of one, of them all, how many,
# Vitality, Resolve, weapon and what they want; the dreadful ones are horror (dungeon/stress.py).
FOE_FIELDS = ('name', 'group', 'count', 'vitality', 'resolve', 'weapon', 'wants')
HORRORS = ('undead', 'fiend', 'fey')
FOES = {kind: dict(zip(FOE_FIELDS, row)) | ({'horror': True} if kind in HORRORS else {}) for kind, row in {
    'bandits': ('bandit', 'bandits', 2, 10, 8, 0, 'rob'),
    'deserters': ('deserter', 'deserters', 2, 11, 7, 1, 'rob'),
    'gnolls': ('gnoll', 'gnolls', 2, 12, 10, 1, 'kill'),
    'orcs': ('orc raider', 'orc raiders', 2, 13, 12, 1, 'kill'),
    'beasts': ('starving wolf', 'starving wolves', 2, 11, 8, 0, 'kill'),
    'undead': ('restless dead', 'one of the restless dead', 1, 14, 20, 1, 'kill'),
    'corsairs': ('corsair', 'corsairs', 2, 11, 10, 1, 'capture'),
    'hunters': ('bounty hunter', 'bounty hunters', 2, 12, 12, 1, 'capture'),
    'fiend': ('fiend', 'a fiend', 1, 16, 20, 1, 'kill'),
    'cultists': ('cultist', 'cultists', 3, 9, 14, 0, 'capture'),
    'watch': ('watchman', 'the watch', 2, 11, 10, 0, 'capture'),
    'fey': ('fey hunter', 'a fey hunter', 1, 13, 16, 1, 'capture'),
}.items()}


# What to draw from --------------------------------------------------------------------------------

def where(city_id: str, place_id: str) -> dict | None:
    """The deck and region a place draws from, and whether it is a town, from the travel map."""
    found = travel.node_at(city_id, place_id)
    if found is None or not found[0].get('world'):
        return None
    travel_map, node = found
    return {'world': travel_map['world'], 'region': travel_map['regions'][node['region']].get('cards'),
            'town': node['safe'] and node['city'] != 'vallarith-road', 'map': travel_map, 'node': node['id']}


def drama(connection, data: dict) -> str:
    chosen = settings(connection)['drama']
    return (data.get('intensity') or {}).get('drama') or DEFAULT_DRAMA if chosen == 'world' else chosen


def unnamed(world: str, faction: bool = False) -> set[str]:
    """The cards that name someone the game cannot fill in here."""
    return {item['id'] for item in cards.cards(world) if any(
        UNNAMED.search(item.get(field) or '') or (not faction and FACTION.search(item.get(field) or ''))
        for field in ('title', *cards.TEXT)) or (not faction and any(
            effect['kind'] in ('clock', 'reputation') for effect in item['effects']))}


def recent(connection, world: str, day: date) -> set[str]:
    since = (day - timedelta(days=cards.deck(world).get('repeat_days', 0))).isoformat()
    return {row['card_id'] for row in many(connection, 'SELECT card_id FROM story_cards WHERE day >= ? AND card_id '
                                                       'IS NOT NULL', (since,))}


def draw(connection, scene: str, seed: str, city_id: str, place_id: str, data: dict, preset: str,
         day: date) -> dict | None:
    """One draw for a scene at a place: {'card', 'veiled', 'map'}, or None when nothing happens."""
    found = where(city_id, place_id)
    if found is None or not ACTIVE:
        return None
    world = found['world']
    has = {'injured'} if combat.condition(connection)['level'] else set()
    powers = factions.local(world, found['node'])
    drawn = cards.draw(world, scene, seed, cards.DRAMA.index(drama(connection, data)), cards.PRESETS[preset], has,
                       recent(connection, world, day) | unnamed(world, bool(powers)), found['region'])
    if not drawn['card']:
        return None
    faction = powers[sum(map(ord, seed)) % len(powers)] if powers else None
    return drawn | {'map': found['map'], 'world': world, 'faction': faction}


def keep(connection, message_id: str, scene: str, day: date, card_id: str | None, lines: list[str]):
    connection.execute('INSERT OR REPLACE INTO story_cards (message_id, scene, day, card_id, lines) VALUES '
                       '(?, ?, ?, ?, ?)', (message_id, scene, day.isoformat(), card_id, encode(lines)))


def drawn_today(connection, scene: str, day: date) -> bool:
    return bool(many(connection, 'SELECT 1 FROM story_cards WHERE scene=? AND day=?', (scene, day.isoformat())))


# Playing a card -------------------------------------------------------------------------------------

def fill(text: str, names: dict[str, str]) -> str:
    return re.sub(r'\{(pc|npc|town|faction)\}', lambda match: names[match.group(1)], text)


def npc(people: list[dict]) -> dict | None:
    return people[0]['sheet'] if people else None


def wage(data: dict) -> int:
    found = next((price for price in data.get('prices', []) if price['id'] == WAGE_ID), None)
    return inventory.cents((found['low'] + found['high']) / 2) if found else DEFAULT_WAGE


def food_city(travel_map: dict, food: str) -> str | None:
    return next((node['city'] for node in travel_map['nodes'] if inventory.item(node['city'], food)), None)


def coin(connection, effect: dict, context: dict) -> list[str]:
    amount = effect['wages'] * wage(context['data'])
    before = inventory.purse(connection)
    inventory.set_purse(connection, max(0, before + amount))
    moved = inventory.money_text(abs(inventory.purse(connection) - before), context['data']['currency'])
    return [f"The character gains {moved}." if amount > 0 else f"It costs the character {moved}."] if moved else []


def supply(connection, effect: dict, context: dict) -> list[str]:
    travel_map, food = context['map'], context['map']['food']
    if effect['shift'] > 0:
        city = food_city(travel_map, food[0])
        if city is None:
            return []
        inventory.add_item(connection, city, food[0], effect['shift'])
        return [f"Food for the pack: {effect['shift']} more of {inventory.item(city, food[0])['name']}."]
    lost, _ = travel.eat(connection, food, -effect['shift'])
    return [f"Food lost from the pack: {', '.join(lost)}."] if lost else []


def wound(connection, effect: dict, context: dict) -> list[str]:
    level = min(combat.DOWN, cards.WOUNDS.index(effect['level']) + 1)
    if level <= combat.condition(connection)['level']:
        return []
    combat.set_condition(connection, level)
    lines = [f"The character is hurt in it: now {combat.LEVELS[level]}."]
    if level >= combat.DOWN and (left := injuries.roll(connection, context['now'], context['title'], context['rng'],
                                                         context['logged'])):
        lines.append(left)
    return lines


def feeling(connection, effect: dict, context: dict) -> list[str]:
    person = context['npc']
    if effect['who'] != 'npc' or person is None:
        return []
    feelings.change(connection, person['key'], {effect['axis']: effect['shift']}, context['title'])
    return []


def fight(connection, effect: dict, context: dict) -> list[str]:
    if combat.fight(connection) is not None:
        return []
    spec = FOES[effect['foes']]
    combat.save_fight(connection, {'round': 0, 'wants': spec['wants'], 'foes': combat.foes_from(spec)})
    return [f"It comes to a fight: {spec['group']} {'close' if spec['count'] > 1 else 'closes'} in."]


def clocked(connection, effect: dict, context: dict) -> list[str]:
    faction = context['faction']
    clock = faction and factions.first_open(connection, faction)
    if clock:
        factions.tick(connection, context['world'], faction, clock, effect['shift'], context['now'], context['logged'])
    return []


def reputed(connection, effect: dict, context: dict) -> list[str]:
    return [factions.shift(connection, context['faction'], effect['shift'])] if context['faction'] else []


def feared(connection, effect: dict, context: dict) -> list[str]:
    return stress.add(connection, 'card', '', context['now'], context['rng'], context['logged'],
                      amount=effect['amount'], cause='what just happened')


APPLY = {'coin': coin, 'supply': supply, 'wound': wound, 'feeling': feeling, 'fight': fight, 'stress': feared,
         'clock': clocked, 'reputation': reputed}


def play(connection, drawn: dict, context: dict) -> tuple[list[str], int]:
    """A drawn card in play: the record keeps its truth, the narrator gets what the character sees, and code applies
    what it can. Returns the lines for the narrator and the minutes it costs."""
    card = drawn['card']
    person = npc(context['people'])
    names = {'pc': context['name'] or 'the character', 'town': context['data']['name'],
             'faction': drawn['faction']['name'] if drawn.get('faction') else 'the powers here',
             'npc': (person.get('full') or f"the {person.get('occupation') or person['role']}") if person
             else 'a stranger'}
    context = context | {'npc': person, 'title': fill(card['title'], names).lower(), 'faction': drawn.get('faction'),
                         'world': drawn.get('world')}
    truth, seen = fill(card['truth'], names), fill(card['seen'], names)
    record.add(connection, 'fact', fill(card['title'], names), truth, context['logged'], truth='world')
    if card['accuracy'] != 'true':
        record.add(connection, 'fact', fill(card['title'], names), seen, context['logged'], truth='belief')
    lines = [seen[:1].upper() + seen[1:]]
    if card.get('pressure'):
        lines.append(f"It puts a choice to the player: {fill(card['pressure'], names)}")
    if drawn['veiled']:
        lines.append('Veiled: whatever it holds that the player veiled happens off the page; fade to black.')
    minutes = 0
    for effect in card['effects']:
        if effect['kind'] == 'time':
            minutes += effect['hours'] * 60
        elif effect['kind'] in APPLY:
            lines += APPLY[effect['kind']](connection, effect, context)
    return lines, minutes


def prompt_text(lines: list[str]) -> str:
    return ('## What the world brings (a Life Card, decided by the game; weave it in)\n'
            + '\n'.join(f'- {line}' for line in lines)) if lines else ''
