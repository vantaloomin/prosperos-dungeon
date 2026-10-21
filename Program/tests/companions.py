"""Helpers for tests that need more than one companion in the workspace."""
import re

from dungeon.characters import insert_version
from dungeon.database import identifier
from dungeon.models import CharacterDefinition
from dungeon.providers.chat import Chunk


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def companion_named(client, name: str, personality='Easygoing.') -> str:
    """Another companion in the workspace, stepped back, as a switch leaves them."""
    database = client.app.state.database
    with database.connect(write=True) as connection:
        companion_id, timeline_id, now = identifier(), identifier(), database.now()
        connection.execute('INSERT INTO companions (id, slot, stepped_back_at, created_at) VALUES (?, NULL, ?, ?)',
                           (companion_id, now, now))
        version_id = insert_version(connection, companion_id, 1, CharacterDefinition(
            name=name, personality=personality, timezone='America/New_York'), '', now)
        connection.execute("INSERT INTO timelines (id, companion_id, status, created_at) VALUES (?, ?, 'active', ?)",
                           (timeline_id, companion_id, now))
        connection.execute('UPDATE companions SET active_version_id=?, active_timeline_id=? WHERE id=?',
                           (version_id, timeline_id, companion_id))
    return companion_id


def speaker(messages) -> str | None:
    found = re.search(r"Write (.+?)'s next message", messages[-1]['content'])
    return found and found[1]


def by_speaker(system, messages):
    """Each speaker says who they are, so a test can tell the replies apart (a 1:1 reply just says hello)."""
    return [Chunk(f'{speaker(messages)} here.' if speaker(messages) else 'Hello again.'), Chunk('', 'stop')]
