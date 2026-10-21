"""One turn's rolls (docs/requirements.md "Turn loop"): the Referee splits the player's intent into actions, code
rolls each uncertain one on the persona's stats, and the narrator is handed the results to write. A message is
rolled once; retelling it keeps the dice."""
import random

from dungeon import sheet
from dungeon.database import identifier, many
from dungeon.rules import ladder, marvel

ACTOR_NAME = {sheet.PERSONA: 'The player\'s character'}


def saved(connection, message_id: str) -> list[dict]:
    return many(connection, 'SELECT * FROM story_rolls WHERE message_id=? ORDER BY position', (message_id,))


def store(connection, message_id: str, actions: list[dict], now: str, rng: random.Random | None = None) -> list[dict]:
    values = sheet.stats(connection)
    for position, action in enumerate(actions):
        result = marvel.roll(values.get(action['stat']), action['difficulty'], rng)
        connection.execute(
            'INSERT INTO story_rolls (id, message_id, position, actor, action, said, stat, difficulty, die, natural, '
            'bonus, shift, total, band, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (identifier(), message_id, position, sheet.PERSONA, action['action'], int(bool(action.get('said'))),
             action['stat'],
             action['difficulty'], result['die'], result['natural'], result['bonus'], result['shift'],
             result['total'], result['band'], now))
    return saved(connection, message_id)


def outcomes(rolls: list[dict]) -> list[dict]:
    """What the narrator is told: who tried what and how it landed. Keyword actions are the player's own words."""
    return [{'actor': ACTOR_NAME.get(row['actor'], row['actor']), 'action': row['action'], 'band': row['band'],
             'said': bool(row['said'])} for row in rolls]


def shown(row: dict) -> dict:
    """A roll as the screen shows it while the dice are on."""
    return {key: row[key] for key in ('action', 'stat', 'difficulty', 'die', 'natural', 'bonus', 'shift', 'total',
                                      'band')} | {'label': ladder.LABELS[row['band']]}
