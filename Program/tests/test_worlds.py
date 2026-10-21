"""Worlds and personas (dungeon/worlds.py): more than one life for the user, each in its own world."""
import json

from dungeon import worlds


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def listing(client):
    return ok(client.get('/api/worlds'))


def test_a_damaged_registry_is_not_trusted(tmp_path):
    (tmp_path / worlds.REGISTRY).write_text('{not json', encoding='utf-8')
    assert worlds.load(tmp_path) is None
    (tmp_path / worlds.REGISTRY).write_text(json.dumps({'worlds': []}), encoding='utf-8')
    assert worlds.load(tmp_path) is None
