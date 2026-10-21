"""Secrets in the companion's life: storylines that are secrets, and how people are named when news travels.

A storyline that is a secret (`STORY_SECRETS`) never travels as news (dungeon/news.py) and stays out of what is on
their mind (dungeon/life/thoughts.py). A gossip is someone whose flaw is gossip (`gossips`), which makes news
likelier to pass on.
"""
from dungeon.characters import by_id
from dungeon.database import optional
from dungeon.world import perception

# Storylines that are secrets. `statement` is filled like a storyline beat; `subjects` are template fields;
# `knowers` the cast who know from the start besides the companion; `ends` a beat that makes it public.
STORY_SECRETS = {
    'secret_couple': {
        'statement': '{a} and {b} have been secretly seeing each other',
        'subjects': ('a', 'b'), 'knowers': ('a', 'b'), 'ends': 'made it official',
        'keys': ('seeing each other', 'secretly seeing', 'dating', 'hooking up', 'hooked up', 'sleeping together',
                 'sleeping with', 'slept', 'affair', 'sneaking around', 'a thing', 'a couple', 'kissed', 'in love',
                 'secret'),
    },
    'family_secret': {
        'statement': '{name} has a half-sibling they never knew about',
        'subjects': ('name',), 'knowers': ('a',), 'ends': None,
        'keys': ('half-sibling', 'half sibling', 'half-brother', 'half brother', 'half-sister', 'half sister',
                 'secret sibling', 'another sibling'),
    },
}


def person_name(connection, key: str | None) -> str | None:
    """A person key's current name: companions by their active version, circle people as named now."""
    if not key:
        return None
    kind, _, value = key.partition(':')
    if kind == 'companion':
        found = by_id(connection, value)
        return found['version']['name'] if found else None
    if kind == 'circle':
        row = optional(connection, 'SELECT name FROM circle_people WHERE seed=?', (key,))
        return row['name'] if row else None
    return None


def first_name(name: str) -> str:
    return name.split()[0] if name.split() else name


def gossips(connection, key: str) -> bool:
    """Whether this person's flaw is gossip: only companions have a sheet to read it from."""
    if not key.startswith('companion:'):
        return False
    found = by_id(connection, key.split(':', 1)[1])
    return bool(found) and perception.for_companion(found['id'], found['version']['definition'])['picks'].get(
        'flaw') == 'gossip'
