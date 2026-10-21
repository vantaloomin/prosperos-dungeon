"""Replacing the active workspace with a backup keeps later deletions (PRD M5, persistence section)."""
from pathlib import Path

import pytest

from dungeon import backup, restore
from dungeon.errors import DomainError


def remember(client, subject, value):
    response = client.post('/api/memories', json={'layer': 'user_fact', 'subject': subject, 'value': value})
    assert response.status_code == 200, response.text
    return response.json()


def test_a_refused_restore_leaves_the_current_workspace_in_place(client, app, companion, tmp_path, clock):
    remember(client, 'Pet', 'Biscuit')
    damaged = tmp_path / 'damaged.zip'
    damaged.write_bytes(b'not a backup')
    path = app.state.database.path
    before = sorted(item.name for item in path.parent.iterdir())
    with pytest.raises(DomainError):
        restore.replace_workspace(damaged, path, clock)
    assert sorted(item.name for item in path.parent.iterdir()) == before


def test_a_failed_restore_moves_the_workspace_back(client, app, companion, clock, monkeypatch):
    remember(client, 'Pet', 'Biscuit')
    archive = Path(client.post('/api/backups').json()['path'])
    path = app.state.database.path
    client.close()

    def broken(*args, **kwargs):
        raise DomainError('boom', 500)

    monkeypatch.setattr(backup, 'restore', broken)
    with pytest.raises(DomainError):
        restore.replace_workspace(archive, path, clock)
    assert path.exists() and not list(path.parent.glob('replaced-*'))
    with app.state.database.connect() as connection:
        assert connection.execute('SELECT value FROM memories').fetchone()[0] == 'Biscuit'


def test_the_launcher_restores_a_backup_and_exits(client, app, companion, monkeypatch, capsys, tmp_path):
    import socket

    from dungeon import launch
    remember(client, 'Pet', 'Biscuit')
    archive = Path(client.post('/api/backups').json()['path'])
    path = app.state.database.path
    client.close()
    monkeypatch.setenv('DUNGEON_DATA_DIR', str(path.parent))
    monkeypatch.delenv('DUNGEON_DB', raising=False)
    monkeypatch.chdir(tmp_path)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    assert launch.main(['--restore', str(archive.relative_to(tmp_path)), '--port', str(port)]) == 0
    output = capsys.readouterr().out
    assert 'Restored' in output and 'moved to' in output
    assert list(path.parent.glob('replaced-*/dungeon.sqlite3'))


def test_a_restore_chosen_in_settings_runs_on_the_next_start(client, app, companion, clock):
    remember(client, 'Pet', 'Biscuit')
    name = Path(client.post('/api/backups').json()['path']).name
    remember(client, 'Car', 'A green van')
    listed = client.get('/api/backups').json()
    assert [item['name'] for item in listed['backups']] == [name] and listed['pending'] is None
    assert listed['backups'][0]['readable'] and listed['backups'][0]['kind'] == 'backup'
    with pytest.raises(DomainError):
        restore.archive_path(app.state.database.path.parent, '../escape.zip')
    assert client.post('/api/backups/..%2Fescape.zip/restore').status_code in (404, 405)
    assert client.post('/api/backups/missing.zip/restore').status_code == 404
    scheduled = client.post(f'/api/backups/{name}/restore').json()
    assert scheduled['pending']['name'] == name
    assert client.delete('/api/backups/restore').json()['pending'] is None
    client.post(f'/api/backups/{name}/restore')
    path = app.state.database.path
    client.close()

    chosen = restore.apply_pending(path)

    assert chosen[0] == name and chosen[1]['previous']
    assert restore.apply_pending(path) is None  # Consumed: never repeated on later starts.
    restored = app.state.database.__class__(path, clock)
    with restored.connect() as connection:
        values = {row[0] for row in connection.execute('SELECT value FROM memories')}
    assert values == {'Biscuit'}


def test_a_damaged_backup_cannot_be_chosen(client, app, companion):
    folder = app.state.database.path.parent / 'backups'
    folder.mkdir(exist_ok=True)
    (folder / 'broken.zip').write_bytes(b'not a zip')
    assert client.get('/api/backups').json()['backups'][0]['readable'] is False
    assert client.post('/api/backups/broken.zip/restore').status_code == 422
    assert client.get('/api/backups').json()['pending'] is None


def test_the_launcher_restores_the_world_you_are_in(client, app, companion, monkeypatch, capsys, tmp_path):
    import socket

    from dungeon import launch
    made = client.post('/api/worlds', json={}).json()
    assert client.post(f"/api/worlds/{made['id']}/switch").status_code == 200
    archive = Path(client.post('/api/backups').json()['path'])
    first = app.state.database.home
    client.close()
    monkeypatch.setenv('DUNGEON_DATA_DIR', str(first.parent))
    monkeypatch.delenv('DUNGEON_DB', raising=False)
    monkeypatch.chdir(tmp_path)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    assert launch.main(['--restore', str(archive), '--port', str(port)]) == 0
    assert list((first.parent / made['folder']).glob('replaced-*/dungeon.sqlite3'))
    assert not list(first.parent.glob('replaced-*'))
