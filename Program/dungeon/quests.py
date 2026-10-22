"""Quests and dangers v0 (requirements "Quests and factions"; docs/story.md "What is happening").

A town's adventure file (world/data/adventures/<city>.json) lists its quests and its dangerous places. When a
story begins there, its quests start: each has a hook the player may know, a truth only the narrator is told, and a
deadline on the story clock. Code keeps the deadline: once the clock passes it with the quest still open, the stakes
land and go in the record. The narrator is told what is happening every turn and lets it press on the scene; it
never ends a quest itself. When a Continuity model is chosen, it says when a turn ended one.

In a dangerous place each turn brings a hidden-cost roll: the character's Luck against the place, and on a failure
one of its threats comes with the turn's outcomes.

Quests are game state, branched with the story (dungeon/timeline.py SAVED).
"""
import json
import random
import re
from datetime import datetime, timedelta
from pathlib import Path

from dungeon import record
from dungeon.database import many

ADVENTURES = Path(__file__).parent / 'world' / 'data' / 'adventures'
STATUSES = ('open', 'done', 'failed', 'missed')
DANGER_STAT = 'Luck'
# The bands where a danger's threat comes true.
BITES = ('critical_failure', 'failure', 'failure_upside')


def adventure(city_id: str) -> dict:
    path = ADVENTURES / f'{city_id}.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'quests': [], 'dangers': []}


def start(connection, city_id: str, at: datetime):
    """The town's quests begin as the story does, each deadline counted from the story clock."""
    connection.execute('DELETE FROM story_quests')
    for quest in adventure(city_id)['quests']:
        due = (at + timedelta(days=quest['days'])).isoformat() if quest.get('days') else None
        connection.execute('INSERT INTO story_quests (id, city_id, status, known, due_at) VALUES (?, ?, ?, ?, ?)',
                           (quest['id'], city_id, 'open', int(bool(quest.get('known'))), due))


def with_text(row: dict) -> dict:
    quest = next((item for item in adventure(row['city_id'])['quests'] if item['id'] == row['id']), None)
    return row | {key: quest[key] for key in ('title', 'hook', 'truth', 'missed')} if quest else row


def rows(connection, status: str | None = None) -> list[dict]:
    where = 'WHERE status=?' if status else ''
    found = many(connection, f'SELECT * FROM story_quests {where} ORDER BY rowid', (status,) if status else ())
    return [quest for quest in map(with_text, found) if 'title' in quest]


def left_text(due_at: str | None, now: datetime) -> str:
    if not due_at:
        return ''
    hours = (datetime.fromisoformat(due_at) - now).total_seconds() / 3600
    if hours <= 0:
        return 'due now'
    if hours < 36:
        return f'{max(1, round(hours))} hours left'
    return f'about {round(hours / 24)} days left'


def check(connection, now: datetime, stamp: str):
    """Deadlines the story clock has passed: the quest is missed and its stakes go in the record."""
    for quest in rows(connection, 'open'):
        if quest['due_at'] and datetime.fromisoformat(quest['due_at']) <= now:
            connection.execute("UPDATE story_quests SET status='missed', known=1, outcome=? WHERE id=?",
                               (quest['missed'], quest['id']))
            if quest['missed']:
                record.add(connection, 'fact', quest['title'], quest['missed'], stamp)


def end(connection, quest_id: str, status: str, outcome: str):
    if status in ('done', 'failed'):
        connection.execute("UPDATE story_quests SET status=?, known=1, outcome=? WHERE id=? AND status='open'",
                           (status, outcome.strip()[:500], quest_id))


def prompt_text(connection, now: datetime) -> str:
    """What is happening, for the narrator: every open quest with its hidden truth, and the ones that just ended."""
    quests = rows(connection)
    if not quests:
        return ''
    lines = []
    for quest in quests:
        if quest['status'] == 'open':
            left = left_text(quest['due_at'], now)
            known = '' if quest['known'] else " (the player's character does not know of this yet)"
            lines.append(f"- {quest['title']}{known}{f' ({left})' if left else ''}: {quest['hook']} "
                         f"Behind it: {quest['truth']}")
        else:
            lines.append(f"- {quest['title']} is over ({quest['status']}): {quest['outcome']}")
    return ('## What is happening (kept by the game; let it press on the scene, never end it yourself)\n'
            + '\n'.join(lines))


def view(connection, now: datetime) -> list[dict]:
    """The quests the player's character knows of, with the time left; hidden truth stays out."""
    return [{'id': quest['id'], 'title': quest['title'], 'hook': quest['hook'], 'status': quest['status'],
             'outcome': quest['outcome'], 'left': left_text(quest['due_at'], now) if quest['status'] == 'open' else ''}
            for quest in rows(connection) if quest['known']]


# Ending a quest, from the Continuity model ---------------------------------------------------------

def ending_ask(connection) -> str:
    """Added to the Continuity model's question while quests are open."""
    quests = rows(connection, 'open')
    if not quests:
        return ''
    listed = '\n'.join(f"- {quest['id']}: {quest['title']}. {quest['hook']}" for quest in quests)
    return ('\n\nThese quests are open:\n' + listed + '\nOnly if this turn settled one for good, add "quests": '
            '[{"id": "...", "status": "done" or "failed", "outcome": "one sentence"}] to your answer.')


def endings(answer: str) -> list[dict]:
    match = re.search(r'\{.*\}', answer, re.S)
    try:
        data = json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        return []
    items = data.get('quests') if isinstance(data, dict) else None
    return [item for item in items or [] if isinstance(item, dict) and isinstance(item.get('id'), str)
            and item.get('status') in ('done', 'failed') and str(item.get('outcome') or '').strip()]


# Dangerous places ----------------------------------------------------------------------------------

def danger(city_id: str, place_id: str) -> dict | None:
    return next((item for item in adventure(city_id)['dangers'] if item['place'] == place_id), None)


def danger_action(city_id: str, place_id: str, rng: random.Random | None = None) -> dict | None:
    """The turn's roll against a dangerous place, with the threat that comes true if it fails."""
    found = danger(city_id, place_id)
    if found is None:
        return None
    threat = (rng or random.SystemRandom()).choice(found['threats'])
    return {'action': found['action'], 'stat': DANGER_STAT, 'difficulty': found['difficulty'],
            'threat': threat_text(threat)}


def threat_text(threat: str | dict) -> str:
    return threat if isinstance(threat, str) else threat['text']


def foe_for(city_id: str, place_id: str, text: str) -> dict | None:
    """The foe a threat brings into a fight (dungeon/combat.py), if it brings one."""
    found = danger(city_id, place_id)
    return next((threat['foe'] for threat in (found or {}).get('threats', [])
                 if isinstance(threat, dict) and threat['text'] == text), None)

