"""How a wedding goes where it is held: the customs, what the couple wear and where it takes place.

Weddings in the companion's circle and town, and a friend's own wedding (dungeon/life/big_days.py), follow the city's
calendar (dungeon/world/catalog.calendar_id), else its era group (dungeon/life/admin.era_group), from the customs in
world/data/wedding.json. Rules and seeds only, no model.
"""
import json
import re
from datetime import date
from functools import cache

from dungeon.life import admin, outings
from dungeon.world import catalog, generators

# Places nobody marries at, whatever their kind (a concert or music hall is a "hall" by name only).
NOT_VENUES = re.compile(r'\b(?:station|hospital|clinic|campus|transit|airport|stadium|arena|gym|fitness|library|'
                        r'prison|jail|court|police|school|office|parking|mall|outlet|pizza|burger|pancake|sandwich|'
                        r'taco|hot dog|diner|deli|food hall|murals?|street|avenue|paseo|surgical|music hall|symphony|concert|'
                        r'festival hall|cemetery|graveyard|churchyard|necropolis|crematorium)\b', re.IGNORECASE)
# Words in a place's description that mark it as somewhere people marry ("Victorian glass houses", "a 1926 ballroom").
WEDDING_WORDS = re.compile(r'\b(?:chapel|church|cathedral|garden|conservatory|ballroom|mansion|manor|estate|winery|'
                           r'pavilion|terrace|lighthouse|temple|shrine|great hall|opera hall|castle|palace|glass ?houses?)',
                           re.IGNORECASE)
# Restaurants and taverns host a wedding only now and then, whatever their name says ("Crab House").
EATERIES = {'restaurant', 'tavern'}
# How likely each kind of place is when nothing in its words says weddings: a park or a garden often, a restaurant or
# a music club hardly ever.
VENUE_KINDS = {'garden': 1.0, 'park': 0.8, 'landmark': 0.8, 'temple': 1.0, 'inn': 0.8, 'museum': 0.5, 'beach': 0.4,
               'restaurant': 0.08, 'venue': 0.08, 'tavern': 0.3}
# Outdoor places, kept out of a wedding in a month whose typical high is below COLD_F (a park in a Chicago February).
OUTDOOR = {'garden', 'park', 'beach'}
OUTDOOR_NAMES = re.compile(r'\b(?:gate|lighthouse|fountain|statue|bridge|plaza|square|pier|monument|beach|park|'
                           r'gardens?|lawn|meadow|trail|lakefront|waterfront|promenade|fort|harbou?r)\b', re.IGNORECASE)
COLD_F = 55
VENUE = '~venue'


@cache
def bank() -> dict:
    return json.loads((catalog.DATA / 'wedding.json').read_text(encoding='utf-8'))


def culture_of(data: dict | None) -> str:
    """The customs a wedding follows: the city's calendar (us, uk, japan ...), else its era group."""
    found = bank()['customs']
    key = catalog.calendar_id(data) if data else None
    return key if key in found else admin.era_group(data)


def customs(culture: str) -> dict:
    found = bank()['customs']
    return found.get(culture) or found['modern']


def pronoun_key(definition: dict) -> str:
    from dungeon.world import looks
    return {'she/her': 'she', 'he/him': 'he'}.get(looks.pronouns_of(definition), 'they')


def attire(definition: dict, culture: str) -> str:
    """What they wear on the day, for the wedding photo: 'a white wedding dress'."""
    return customs(culture)['attire'][pronoun_key(definition)]


def cold(data: dict | None, day: date | None) -> bool:
    """Whether the day falls in a month too cold for an outdoor wedding there, by the city's climate."""
    climate = (data or {}).get('climate')
    return bool(day and climate) and climate['months'][day.month - 1]['high_f'] < COLD_F


def venue_for(data: dict | None, rules: dict, size: str, seed: str, without: tuple = (), day: date | None = None) -> dict:
    """A venue in their city that fits the customs, the size and the budget; words like chapel or garden count most,
    and nowhere outdoors in a cold month. Somewhere unnamed when the city isn't known."""
    if not data:
        return {'id': VENUE, 'name': 'the wedding venue', 'kind': 'venue', 'neighborhood': '', 'summary': '', 'cost': '',
                'cuisine': '', 'city': '', 'city_id': '', 'spots': []}
    words = re.compile(rf"\b(?:{rules['venues']['words']})", re.IGNORECASE)
    options = []
    for kinds in (rules['venues']['kinds'], rules['venues'].get('else', ())):  # A church service is in a church.
        options = options or [item for item in data['places'] if item['kind'] in kinds and item['id'] not in without
                              and not NOT_VENUES.search(item['name'])]
    if not options:
        options = [item for item in data['places'] if item['id'] not in without] or data['places']
    if cold(data, day):
        options = [item for item in options if item['kind'] not in OUTDOOR and not OUTDOOR_NAMES.search(item['name'])
                   ] or options
    dear = {'small': {'free', '', '$', '$$'}, 'proper': {'$$', '$$$'}, 'big': {'$$$', '$$$$'}}[size]

    def weight(item: dict) -> float:
        if item['kind'] in EATERIES:
            named = 1.0 if words.search(item['name']) or WEDDING_WORDS.search(item.get('summary', '')) else 0.08
        elif words.search(item['name']) or WEDDING_WORDS.search(item['name']):
            named = 8.0
        elif WEDDING_WORDS.search(item.get('summary', '')):
            named = 4.0
        else:
            named = VENUE_KINDS.get(item['kind'], 0.3)
        return named * (1.5 if item.get('cost', '') in dear else 1.0) * (1.3 if 'date' in item.get('good_for', ()) else 1.0)
    item = generators.pick(seed, 'venue', options, [weight(item) for item in options])
    return outings.place_view(item, data)
