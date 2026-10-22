"""One turn's rolls (docs/requirements.md "Turn loop"): the Referee splits the player's intent into actions, code
rolls each uncertain one on the persona's stats, and the narrator is handed the results to write. A message is
rolled once; retelling it keeps the dice."""
import random

from dungeon import quests, sheet
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
            'bonus, shift, total, band, threat, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (identifier(), message_id, position, sheet.PERSONA, action['action'], int(bool(action.get('said'))),
             action['stat'],
             action['difficulty'], result['die'], result['natural'], result['bonus'], result['shift'],
             result['total'], result['band'], action.get('threat'), now))
    return saved(connection, message_id)


def outcomes(rolls: list[dict]) -> list[dict]:
    """What the narrator is told: who tried what and how it landed. Keyword actions are the player's own words; a
    danger's threat comes true when its roll fails (dungeon/quests.py)."""
    return [{'actor': ACTOR_NAME.get(row['actor'], row['actor']), 'action': row['action'], 'band': row['band'],
             'said': bool(row['said'])}
            | ({'detail': row['threat']} if row.get('threat') and row['band'] in quests.BITES else {})
            for row in rolls]


def shown(row: dict) -> dict:
    """A roll as the screen shows it while the dice are on."""
    return {key: row[key] for key in ('action', 'stat', 'difficulty', 'die', 'natural', 'bonus', 'shift', 'total',
                                      'band')} | {'label': ladder.LABELS[row['band']]}


def hidden(row: dict) -> dict:
    """A roll as the screen shows it while the dice are hidden: what was tried and with which stat, never the odds."""
    return {'action': row['action'], 'stat': row['stat']}


def announced(rolls: list[dict], dice_shown: bool) -> list[dict]:
    """The actions a turn rolls for, as the turn stream names them before the results (dungeon/story_routes.py)."""
    return [{'action': row['action'], 'stat': row['stat']} | ({'difficulty': row['difficulty']} if dice_shown else {})
            for row in rolls]


def bands() -> list[dict]:
    """The ruleset's bands by total, worst first, for the screen's band strip; the top band has no ceiling. (A natural
    roll of CRITICAL_NATURAL or less is a critical failure whatever the total.)"""
    return [{'band': band, 'label': ladder.LABELS[band], 'ceiling': ceiling} for ceiling, band in marvel.CEILINGS] + [
        {'band': 'critical_success', 'label': ladder.LABELS['critical_success'], 'ceiling': None}]

