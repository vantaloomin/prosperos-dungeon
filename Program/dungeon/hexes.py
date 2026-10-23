"""The hex crawl (requirements "### Hex crawl"; docs/story.md "Journeys").

A travel map is a hex crawl unless it says `travel: "roads"` (Havenbrooke's car-or-bus roads, BABEL's Stair). Its
hexes are flat-topped, in axial coordinates (q, r).

- **Authored, then generated.** A world's authored hexes (world/data/hexes/<map>.json, Vallarith's painted from its
  world map by scripts/world/vallarith_hexes.py) are canon. Every hex past them is generated from the campaign's
  seed and its own coordinates alone, so it comes out the same whenever and from wherever it is first seen, and the
  map can grow in any direction without end: smooth noise for land, height and wet, carrying on the authored
  coast and regions near the edge and drifting into the map's frontier regions further out. A map with no authored
  hexes is all generated around its places, set where the travel map's own positions put them.
- **Roads.** The travel map's routes are drawn as roads from place to place; a step along a road takes an hour and
  is as dangerous as its route says. Stepping onto a road from the side costs the land's own hours.
- **Fog of war.** The hexes the character has seen are game state (story_hexes), branched with the story: walking
  into a hex shows it and the ring around it (more from hills and mountains, none past the trees in forest or marsh).
"""
import functools
import hashlib
import heapq
import math
import secrets

from dungeon import world_data
from dungeon.database import many, optional

# Hours to walk across a hex off the road, how many rings around one sees from it, and how it reads to the narrator.
TERRAINS = {
    'water': {'hours': None, 'sight': 1, 'text': 'open water'},
    'plains': {'hours': 2, 'sight': 1, 'text': 'open country'},
    'forest': {'hours': 3, 'sight': 0, 'text': 'the forest'},
    'hills': {'hours': 3, 'sight': 2, 'text': 'the hills'},
    'mountains': {'hours': 5, 'sight': 3, 'text': 'the mountains'},
    'waste': {'hours': 3, 'sight': 1, 'text': 'the waste'},
    'marsh': {'hours': 4, 'sight': 0, 'text': 'the marsh'},
}
ROAD_HOURS = 1
DIRECTIONS = {'north': (0, -1), 'north-east': (1, -1), 'south-east': (1, 0), 'south': (0, 1), 'south-west': (-1, 1),
              'north-west': (-1, 0)}
# How far past the authored hexes the land, coast and regions still carry on from them.
REACH = 6
# Hexes across a map's unit square, for a map with no authored hexes (its places' x and y run from 0 to 1).
SPAN = 100
# How far a way may wander outside the box around its two ends looking for a better path.
MARGIN = 12
FRONTIER = ['wilds']
DANGERS = ('none', 'low', 'medium', 'high')


def is_hex(travel_map: dict) -> bool:
    return travel_map.get('travel', 'hex') == 'hex'


def key(travel_map: dict) -> str:
    return travel_map.get('hexes') or travel_map.get('world') or 'map'


def neighbours(q: int, r: int) -> list[tuple[int, int]]:
    return [(q + dq, r + dr) for dq, dr in DIRECTIONS.values()]


def distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    return (abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[0] + a[1] - b[0] - b[1])) // 2


def ring(centre: tuple[int, int], radius: int) -> list[tuple[int, int]]:
    """Every hex within `radius` of the centre, the centre included."""
    q0, r0 = centre
    return [(q0 + dq, r0 + dr) for dq in range(-radius, radius + 1)
            for dr in range(max(-radius, -dq - radius), min(radius, -dq + radius) + 1)]


def line(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    """The hexes on a straight line from one to the other."""
    steps = distance(start, end)
    cells = []
    for step in range(steps + 1):
        t = step / steps if steps else 0
        q, r = start[0] + (end[0] - start[0]) * t + 1e-6, start[1] + (end[1] - start[1]) * t + 1e-6
        s = -q - r
        rq, rr, rs = round(q), round(r), round(s)
        if abs(rq - q) > abs(rr - r) and abs(rq - q) > abs(rs - s):
            rq = -rr - rs
        elif abs(rr - r) > abs(rs - s):
            rr = -rq - rs
        if not cells or cells[-1] != (rq, rr):
            cells.append((rq, rr))
    return cells


def offset(column: int, row: int) -> tuple[int, int]:
    """An authored file's column and row as an axial hex."""
    return column, row - (column - (column & 1)) // 2


def point(q: int, r: int) -> tuple[float, float]:
    """A hex's centre on the plane, one hex across."""
    return 1.5 * q / math.sqrt(3), r + q / 2


# Seeded noise --------------------------------------------------------------------------------------

def unit(seed: str, *parts) -> float:
    """A number from 0 to 1 that only the seed and the parts decide."""
    digest = hashlib.blake2b(':'.join(map(str, (seed, *parts))).encode(), digest_size=8).digest()
    return int.from_bytes(digest, 'big') / 2 ** 64


def noise(seed: str, field: str, x: float, y: float, scale: float) -> float:
    """Smooth value noise: random at the corners of a lattice `scale` hexes apart, blended between them."""
    x, y = x / scale, y / scale
    x0, y0 = math.floor(x), math.floor(y)
    fx, fy = x - x0, y - y0
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    corner = functools.partial(unit, seed, field)
    top = corner(x0, y0) * (1 - fx) + corner(x0 + 1, y0) * fx
    bottom = corner(x0, y0 + 1) * (1 - fx) + corner(x0 + 1, y0 + 1) * fx
    return top * (1 - fy) + bottom * fy


# The grid ------------------------------------------------------------------------------------------

class Grid:
    """One travel map's hexes for one campaign seed: the authored ones, and any other generated when asked for."""

    def __init__(self, travel_map: dict, seed: str):
        self.map, self.seed = travel_map, seed
        data = world_data.read('hexes', key(travel_map)) or {}
        self.generate = data.get('generate', {})
        self.authored: dict[tuple[int, int], tuple[str, str]] = {}
        legend, regions = data.get('legend', {}), data.get('region_legend', {})
        for row, (terrain_row, region_row) in enumerate(zip(data.get('terrain', []), data.get('regions', []))):
            for column, (terrain, region) in enumerate(zip(terrain_row, region_row)):
                self.authored[offset(column, row)] = (legend[terrain], regions.get(region))
        nodes = {node['id']: node for node in travel_map['nodes']}
        self.places = {node: tuple(at) for node, at in data.get('places', {}).items()}
        for node in nodes.values():
            self.places.setdefault(node['id'], self.placed(node))
        self.at_place = {at: node for node, at in self.places.items()}
        self.roads: dict[tuple[int, int], dict] = {}
        # A road is quick only along it: two roads that pass side by side are not one road.
        self.road_steps: set[frozenset] = set()
        for road in data.get('roads') or [{'name': route['terrain'], 'danger': route['danger'],
                                            'cells': line(self.places[route['from']], self.places[route['to']])}
                                           for route in travel_map['routes']]:
            cells = [tuple(at) for at in road['cells']]
            self.road_steps.update(frozenset(pair) for pair in zip(cells, cells[1:]))
            for at in road['cells']:
                held = self.roads.get(tuple(at))
                if held is None or DANGERS.index(road['danger']) < DANGERS.index(held['danger']):
                    self.roads[tuple(at)] = {'name': road['name'], 'danger': road['danger']}
        self.region_of_place = {self.places[node]: nodes[node]['region'] for node in nodes}
        self.cache: dict[tuple[int, int], dict] = {}

    def placed(self, node: dict) -> tuple[int, int]:
        """Where a place with no authored hex sits: its map position, SPAN hexes to the map's width."""
        span = self.generate.get('span', SPAN)
        q = round(node['map']['x'] * span * math.sqrt(3) / 1.5)
        return q, round(node['map']['y'] * span - q / 2)

    def cell(self, at: tuple[int, int]) -> dict:
        """A hex: its terrain and region, and the road and place on it, if any."""
        if at not in self.cache:
            terrain, region = self.authored.get(at) or self.generated(at)
            if at in self.region_of_place:
                region = self.region_of_place[at]
            if terrain == 'water' and (at in self.roads or at in self.at_place):
                terrain = 'plains'
            self.cache[at] = {'q': at[0], 'r': at[1], 'terrain': terrain, 'region': region,
                              'road': self.roads.get(at), 'place': self.at_place.get(at)}
        return self.cache[at]

    def nearest_authored(self, at: tuple[int, int]) -> tuple[int, bool, str | None] | None:
        """How far the nearest authored hexes are, whether most of them are land, and a region they carry."""
        for radius in range(1, REACH + 1):
            found = [self.authored[other] for other in ring(at, radius)
                     if other in self.authored and distance(at, other) == radius]
            if found:
                land = [region for terrain, region in found if terrain != 'water']
                return radius, len(land) * 2 > len(found), next((region for region in land if region), None)
        return None

    def generated(self, at: tuple[int, int]) -> tuple[str, str]:
        """A hex no one authored, decided by the seed and where it is, carrying on the authored land near it."""
        x, y = point(*at)
        settings = self.generate
        land = noise(self.seed, 'land', x, y, 9) * 0.7 + noise(self.seed, 'land2', x, y, 3) * 0.3
        threshold = settings.get('water', 0.42 if self.authored else 0.3)
        near = self.nearest_authored(at) if self.authored else None
        if near:
            radius, landward, _ = near
            pull = 0.3 * (1 - radius / (REACH + 1))
            threshold += -pull if landward else pull
        if land < threshold:
            return 'water', None
        height, wet = noise(self.seed, 'height', x, y, 7), noise(self.seed, 'wet', x, y, 5)
        if height > 0.72:
            terrain = 'mountains'
        elif height > 0.6:
            terrain = 'hills'
        elif wet > 0.78 and height < 0.35:
            terrain = 'marsh'
        elif wet > 0.58:
            terrain = 'forest'
        elif wet < 0.22:
            terrain = 'waste'
        else:
            terrain = 'plains'
        allowed = settings.get('terrains')
        if allowed and terrain not in allowed:
            terrain = allowed[int(unit(self.seed, 'terrain', *at) * len(allowed))]
        if near and near[2]:
            return terrain, near[2]
        frontier = settings.get('frontier', FRONTIER)
        return terrain, frontier[int(noise(self.seed, 'region', x, y, 20) * len(frontier)) % len(frontier)]

    def on_road(self, here: tuple[int, int], there: tuple[int, int]) -> bool:
        return frozenset((here, there)) in self.road_steps

    def danger(self, cell: dict, road: bool) -> str:
        if road:
            return cell['road']['danger']
        return (self.map['regions'].get(cell['region']) or {}).get('danger', 'high')

    def hours(self, cell: dict, road: bool) -> float | None:
        return ROAD_HOURS if road else TERRAINS[cell['terrain']]['hours']

    def text(self, cell: dict, road: bool) -> str:
        return cell['road']['name'] if road else TERRAINS[cell['terrain']]['text']

    def way(self, start: tuple[int, int], goal: tuple[int, int]) -> list[dict] | None:
        """The quickest way from one hex to another, each step as {from, to, hours, terrain, danger, region}."""
        low_q, high_q = min(start[0], goal[0]) - MARGIN, max(start[0], goal[0]) + MARGIN
        low_r, high_r = min(start[1], goal[1]) - MARGIN, max(start[1], goal[1]) + MARGIN
        queue, best, came = [(0.0, 0.0, start)], {start: 0.0}, {}
        while queue:
            _, spent, at = heapq.heappop(queue)
            if at == goal:
                break
            if spent > best.get(at, math.inf):
                continue
            for other in neighbours(*at):
                if not (low_q <= other[0] <= high_q and low_r <= other[1] <= high_r):
                    continue
                hours = self.hours(self.cell(other), self.on_road(at, other))
                if hours is None:
                    continue
                total = spent + hours
                if total < best.get(other, math.inf):
                    best[other], came[other] = total, at
                    heapq.heappush(queue, (total + distance(other, goal) * ROAD_HOURS, total, other))
        if goal not in best:
            return None
        cells = [goal]
        while cells[-1] != start:
            cells.append(came[cells[-1]])
        cells.reverse()
        return [self.step(here, there) for here, there in zip(cells, cells[1:])]

    def step(self, here: tuple[int, int], there: tuple[int, int]) -> dict:
        cell, road = self.cell(there), self.on_road(here, there)
        leg = {'from': list(here), 'to': list(there), 'hours': self.hours(cell, road), 'terrain': self.text(cell, road),
               'danger': self.danger(cell, road), 'region': cell['region']}
        return leg | ({'place': cell['place']} if cell['place'] else {})

    def sight(self, at: tuple[int, int]) -> list[tuple[int, int]]:
        cell = self.cell(at)
        return ring(at, TERRAINS[cell['terrain']]['sight'] if not cell['road'] else max(
            1, TERRAINS[cell['terrain']]['sight']))


# The campaign's seed and what the character has seen -----------------------------------------------

def seed(connection) -> str:
    """The campaign's world seed, chosen the first time the land past the authored map is needed."""
    row = optional(connection, 'SELECT seed FROM story_campaign WHERE id=1')
    if row and row['seed']:
        return row['seed']
    chosen = secrets.token_hex(8)
    connection.execute('INSERT INTO story_campaign (id, seed) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET seed=?',
                       (chosen, chosen))
    return chosen


def grid(connection, travel_map: dict) -> Grid:
    return _grid(key(travel_map), seed(connection), world_data.version())


@functools.lru_cache(maxsize=4)
def _grid(map_key: str, seed_: str, _version) -> Grid:
    from dungeon import travel
    travel_map = next(found for found in travel.maps() if key(found) == map_key)
    return Grid(travel_map, seed_)


def reveal(connection, board: Grid, cells: list[tuple[int, int]], walked: bool = True):
    """The character walks into these hexes: each is visited, and seen with what can be seen from it."""
    name = key(board.map)
    for at in cells:
        for other in board.sight(at):
            connection.execute('INSERT OR IGNORE INTO story_hexes (map, q, r, visited) VALUES (?, ?, ?, 0)',
                               (name, *other))
        if walked:
            connection.execute('INSERT INTO story_hexes (map, q, r, visited) VALUES (?, ?, ?, 1) '
                               'ON CONFLICT(map, q, r) DO UPDATE SET visited=1', (name, *at))


def seen(connection, board: Grid, here: tuple[int, int] | None = None) -> dict[tuple[int, int], bool]:
    """Every hex the character has seen, and whether they have walked it; where they are, and what they see from
    there, count too."""
    rows = {(row['q'], row['r']): bool(row['visited']) for row in many(
        connection, 'SELECT q, r, visited FROM story_hexes WHERE map=?', (key(board.map),))}
    if here is not None:
        for other in board.sight(here):
            rows.setdefault(other, False)
        rows[here] = True
    return rows


def view(connection, board: Grid, here: tuple[int, int]) -> list[dict]:
    """The hexes the character knows, for the map on screen."""
    return [board.cell(at) | {'visited': visited} for at, visited in sorted(seen(connection, board, here).items())]
