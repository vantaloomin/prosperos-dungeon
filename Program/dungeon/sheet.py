"""Character sheets: MARVEL stats per actor (dungeon/rules/marvel.py). The player's character is 'persona'; an actor
with no stats rolls with no die."""
from dungeon.database import many
from dungeon.errors import require
from dungeon.rules import marvel

PERSONA = 'persona'


def stats(connection, actor: str = PERSONA) -> dict[str, int]:
    """Every stat of an actor; the persona's unset ones are the default, anyone else's are left out."""
    rows = {row['stat']: row['value'] for row in many(connection, 'SELECT stat, value FROM character_stats '
                                                                  'WHERE actor=?', (actor,))}
    if actor == PERSONA:
        return {stat: rows.get(stat, marvel.DEFAULT_STAT) for stat in marvel.STATS}
    return rows


def set_stats(connection, values: dict[str, int], now: str, actor: str = PERSONA) -> dict[str, int]:
    low, high = marvel.STAT_RANGE
    for stat, value in values.items():
        require(stat in marvel.STATS, f'{stat} is not a MARVEL stat.', 422)
        require(isinstance(value, int) and low <= value <= high, f'{stat} must be from {low} to {high}.', 422)
    connection.executemany(
        'INSERT INTO character_stats (actor, stat, value, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(actor, stat) '
        'DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at',
        [(actor, stat, value, now) for stat, value in values.items()])
    return stats(connection, actor)


def view(connection) -> dict:
    return {'stats': stats(connection), 'stat_names': list(marvel.STATS), 'range': list(marvel.STAT_RANGE),
            'dice': {stat: marvel.die_for(value) for stat, value in stats(connection).items()}}
