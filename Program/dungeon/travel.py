"""Journeys on the travel map (requirements "Time and travel"; docs/story.md "Journeys").

Each world has a travel map (world/data/travel/<world>.json): places joined by roads, each road with its hours on
foot, its terrain and its danger, and each region with its road encounters. A place is a whole town (its city and
the place one arrives at) or a place on the Road (world/data/cities/vallarith-road.json) for one not yet built out.

- **Fog of war.** The character knows the places they have been, the places next to those, and the famous ones
  everybody has heard of (a capital). The rest stay hidden until found.
- **A journey is decided before the narrator writes it.** "I set out for Eriane" plans the way by the shortest
  roads and rolls each road against its danger. A road that turns up an encounter draws one from the region's
  table: a sight or a meeting the narrator weaves in, or a danger to get past (a Luck roll, like a dangerous place
  in town); one that brings foes starts a fight where it happens, and the journey stops there.
- **Every road costs time and food.** Walking takes the road's hours, nights on the road pass in camp, and each day
  eats one food from the pack (bread, dried meat, cheese); without it the character goes hungry. A modern world's map
  says how people get about instead (`by`: "car or bus", Havenbrooke's), and with no `food` a trip eats nothing.

The places known are game state, branched with the story (dungeon/timeline.py SAVED); each line's journey is kept
with it, so telling the turn again changes nothing.
"""
import heapq
import math
import random
import re
from pathlib import Path

from dungeon import inventory, sworn, world_data
from dungeon.database import decode, encode, many, optional

MAPS = Path(__file__).parent / 'world' / 'data' / 'travel'
STAT = 'Luck'
BITES = ('critical_failure', 'failure', 'failure_upside')
NIGHT_HOURS = 14
STOPPED = 'The journey stops here'
GOING = re.compile(r'\b(travel\w*|set(s|ting)? (out|off)|head\w*|ride|rides|riding|walk\w*|journey\w*|march\w*|'
                   r'make (my|our|their) way|go|goes|going|leave|leaves|leaving|return\w*)\b', re.I)


@world_data.memo
def maps() -> tuple[dict, ...]:
    return tuple(world_data.read('travel', key) for key in world_data.keys('travel'))


def nodes(travel_map: dict) -> dict[str, dict]:
    return {node['id']: node for node in travel_map['nodes']}


def node_at(city_id: str, place_id: str) -> tuple[dict, dict] | None:
    """The travel map and the place on it where the scene is: the place itself on the Road, or the whole town."""
    for travel_map in maps():
        found = next((node for node in travel_map['nodes'] if node['city'] == city_id and node['place'] == place_id),
                     None) or next((node for node in travel_map['nodes'] if node['city'] == city_id
                                    and node['city'] != 'vallarith-road'), None)
        if found:
            return travel_map, found
    return None


def neighbours(travel_map: dict, node_id: str) -> list[tuple[str, dict]]:
    return [(route['to'] if route['from'] == node_id else route['from'], route) for route in travel_map['routes']
            if node_id in (route['from'], route['to'])]


def visit(connection, travel_map: dict, node_id: str):
    """The character has been here, and has heard of every place one road away."""
    connection.execute('INSERT INTO story_map (node_id, visited) VALUES (?, 1) ON CONFLICT(node_id) DO UPDATE SET '
                       'visited=1', (node_id,))
    for other, _ in neighbours(travel_map, node_id):
        connection.execute('INSERT OR IGNORE INTO story_map (node_id, visited) VALUES (?, 0)', (other,))


def known(connection, travel_map: dict, here: str) -> dict[str, bool]:
    """Each place the character knows of, and whether they have been there; where they are counts as visited."""
    rows = {row['node_id']: bool(row['visited']) for row in many(connection, 'SELECT * FROM story_map')}
    rows[here] = True
    for other, _ in neighbours(travel_map, here):
        rows.setdefault(other, False)
    return {node['id']: rows.get(node['id'], False) for node in travel_map['nodes']
            if node['id'] in rows or node.get('famous')}


def find(node_id: str) -> tuple[dict, dict]:
    return next((travel_map, node) for travel_map in maps() for node in travel_map['nodes'] if node['id'] == node_id)


def bare(name: str) -> str:
    return re.sub(r'^the\s+', '', name, flags=re.I)


def destination(travel_map: dict, here: str, text: str) -> dict | None:
    """The place a line sets out for ("I set out for Eriane"), if it names one."""
    going = GOING.search(text)
    if not going:
        return None
    after = text[going.end():]
    found = [(match.start(), node) for node in travel_map['nodes'] if node['id'] != here
             if (match := re.search(rf'(?<![\w-]){re.escape(bare(node["name"]))}(?![\w-])', after, re.I))]
    return min(found, key=lambda pair: pair[0])[1] if found else None


def way(travel_map: dict, start: str, goal: str) -> list[dict] | None:
    """The roads from one place to another, shortest in hours, each as {from, to, hours, terrain, danger}."""
    queue, best = [(0, start, [])], {start: 0}
    while queue:
        hours, node, legs = heapq.heappop(queue)
        if node == goal:
            return legs
        for other, route in neighbours(travel_map, node):
            total = hours + route['hours']
            if total < best.get(other, math.inf):
                best[other] = total
                heapq.heappush(queue, (total, other, [*legs, route | {'from': node, 'to': other}]))
    return None


def pick(entries: list[dict], rng) -> dict:
    roll, at = rng.randint(1, sum(entry['weight'] for entry in entries)), 0
    for entry in entries:
        at += entry['weight']
        if roll <= at:
            return entry
    return entries[-1]


def threat_text(threat: str | dict) -> str:
    return threat if isinstance(threat, str) else threat['text']


def plan(connection, city_id: str, place_id: str, text: str, rng=None) -> dict | None:
    """The journey a line sets out on, its roads rolled for encounters: None when it goes nowhere on the map, or the
    character is held prisoner (dungeon/combat.py captors)."""
    held = optional(connection, 'SELECT captors FROM story_wounds WHERE id=1')
    if held and held['captors']:
        return None
    found = node_at(city_id, place_id)
    if found is None:
        return None
    travel_map, here = found
    goal = destination(travel_map, here['id'], text)
    if goal is None:
        return None
    legs = way(travel_map, here['id'], goal['id']) if goal['id'] in known(connection, travel_map, here['id']) else None
    if legs is None:
        return {'from': here['id'], 'to': goal['id'], 'unknown': True}
    rng = rng or random.SystemRandom()
    encounter = None
    for index, leg in enumerate(legs):
        if rng.randint(1, 100) <= travel_map['odds'][leg['danger']]:
            region = nodes(travel_map)[leg['to']]['region']
            encounter = {'leg': index, 'entry': pick(travel_map['encounters'][region], rng)}
            break
    return {'from': here['id'], 'to': goal['id'], 'legs': legs, 'encounter': encounter}


def decide(connection, message_id: str, city_id: str, place_id: str, text: str, rng=None) -> dict | None:
    """The line's journey, planned once, and the roll its danger calls for, if any (for the turn's rolls)."""
    row = optional(connection, 'SELECT plan FROM story_journeys WHERE message_id=?', (message_id,))
    journey = decode(row['plan']) if row else plan(connection, city_id, place_id, text, rng)
    if journey is None:
        return None
    if row is None:
        connection.execute('INSERT INTO story_journeys (message_id, plan) VALUES (?, ?)', (message_id, encode(journey)))
    entry = (journey.get('encounter') or {}).get('entry') or {}
    if 'action' not in entry:
        return None
    return {'action': entry['action'], 'stat': STAT, 'difficulty': entry['difficulty'],
            'threat': threat_text(entry['threat'])}


def journey(connection, message_id: str) -> dict | None:
    row = optional(connection, 'SELECT plan, lines FROM story_journeys WHERE message_id=?', (message_id,))
    return row and decode(row['plan']) | {'lines': decode(row['lines']) if row['lines'] else None}


def foe_for(text: str) -> dict | None:
    """The foe a road or camp threat brings into a fight (dungeon/combat.py), if it brings one."""
    for travel_map in maps():
        for entries in (*travel_map['encounters'].values(), *travel_map.get('camp', {}).values()):
            for entry in entries:
                threat = entry.get('threat')
                if isinstance(threat, dict) and threat['text'] == text and threat.get('foe'):
                    return threat['foe']
    return None


def bitten(rolls: list[dict], entry: dict) -> bool:
    return any(roll.get('threat') == threat_text(entry['threat']) and roll['band'] in BITES for roll in rolls)


def travelled(plan_: dict, rolls: list[dict]) -> tuple[list[dict], list[str]]:
    """The roads actually walked (a fight on the road ends the journey where it happens), and what happened on them."""
    legs, encounter = plan_['legs'], plan_.get('encounter')
    if not encounter:
        return legs, []
    entry, where = encounter['entry'], legs[encounter['leg']]
    if 'action' not in entry:
        return legs, [f"On {where['terrain']}: {entry['text']}"]
    if not bitten(rolls, entry):
        return legs, [f"On {where['terrain']} the character manages to {entry['action']}, and goes on."]
    lines = [f"On {where['terrain']}: {threat_text(entry['threat'])}"]
    if isinstance(entry['threat'], dict) and entry['threat'].get('foe'):
        return legs[:encounter['leg'] + 1], lines + [f'{STOPPED}, on the road, with a fight on its hands.']
    return legs, lines


def minutes(legs: list[dict], hours_a_day: int) -> tuple[int, int, int]:
    """The journey's hours on foot, its nights camped on the road, and its days, in minutes, nights and days."""
    hours = sum(leg['hours'] for leg in legs)
    days = max(1, math.ceil(hours / hours_a_day))
    nights = days - 1
    return round((hours + nights * NIGHT_HOURS) * 60), nights, days


def eat(connection, food: list[str], days: int) -> tuple[list[str], int]:
    """A food from the pack for each day on the road, in the map's order; the days left without. Under Ironsworn a
    day costs a point of supply instead (dungeon/sworn.py)."""
    if (supplied := sworn.spend_supply(connection, days)) is not None:
        spent, left = supplied
        return ([f'{spent} supply ({left} left)'] if spent else []), days - spent
    if not food:
        return [], 0
    eaten = []
    for _ in range(days):
        row = next((found for item_id in food if (found := optional(
            connection, 'SELECT id, city_id, item_id FROM story_inventory WHERE item_id=? AND qty > 0 LIMIT 1',
            (item_id,)))), None)
        if row is None:
            break
        connection.execute('UPDATE story_inventory SET qty=qty-1 WHERE id=?', (row['id'],))
        entry = inventory.item(row['city_id'], row['item_id'])
        eaten.append(entry['name'] if entry else row['item_id'])
    return eaten, days - len(eaten)


def duration(hours: float) -> str:
    """'40 minutes', 'an hour', '4.5 hours'."""
    if hours < 1:
        return f'{round(hours * 60)} minutes'
    return 'an hour' if hours == 1 else f"{hours:g} hours"


def lines_for(travel_map: dict, legs: list[dict], nights: int, eaten: list[str], hungry: int) -> list[str]:
    places = nodes(travel_map)
    roads = ', then '.join(dict.fromkeys(leg['terrain'] for leg in legs))
    hours = sum(leg['hours'] for leg in legs)
    way = (f"by {travel_map['by']} on {roads}: {duration(hours)} on the road" if travel_map.get('by') else
           f'on foot by {roads}: {hours} hours of walking')
    lines = [f"The player's character travels from {places[legs[0]['from']]['name']} to "
             f"{places[legs[-1]['to']]['name']} {way}"
             + (f", {nights} night{'s' if nights > 1 else ''} camped on the road." if nights else '.')]
    if eaten:
        lines.append(f"They eat from their pack on the way: {', '.join(eaten)}.")
    if hungry:
        lines.append(f"They have nothing to eat for {hungry} day{'s' if hungry > 1 else ''} of it and go hungry.")
    return lines


def view(connection, city_id: str, place_id: str) -> dict | None:
    """The travel map as far as the character knows it, for the screen: places, the roads between them, here."""
    found = node_at(city_id, place_id)
    if found is None:
        return None
    travel_map, here = found
    seen = known(connection, travel_map, here['id'])
    places = [{'id': node['id'], 'name': node['name'], 'x': node['map']['x'], 'y': node['map']['y'],
               'visited': seen[node['id']], 'here': node['id'] == here['id']}
              for node in travel_map['nodes'] if node['id'] in seen]
    roads = [{'from': route['from'], 'to': route['to'], 'hours': route['hours'], 'danger': route['danger'],
              'terrain': route['terrain']} for route in travel_map['routes']
             if route['from'] in seen and route['to'] in seen]
    return {'places': places, 'roads': roads}


def prompt_text(lines: list[str]) -> str:
    return '## The journey (decided by the game; write it as it went)\n' + '\n'.join(
        f'- {line}' for line in lines) if lines else ''
