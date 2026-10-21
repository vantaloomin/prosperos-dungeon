"""Every companion texts first, within one shared allowance, and each chat shows what is unread (dungeon/chats.py,
dungeon/away.py)."""


from dungeon.characters import insert_version
from dungeon.database import identifier
from dungeon.models import CharacterDefinition


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def chats(client):
    return ok(client.get('/api/chats'))


def another(client, name='Sally', **changes):
    """A second companion, out of focus, the way one is after switching away from them."""
    database = client.app.state.database
    mira = ok(client.get('/api/companion'))['companion']
    definition = CharacterDefinition(**{**mira['version']['definition'], 'name': name, **changes})
    timestamp = database.now()
    with database.connect(write=True) as connection:
        companion_id, timeline_id = identifier(), identifier()
        connection.execute('INSERT INTO companions (id, slot, stepped_back_at, created_at) VALUES (?, NULL, ?, ?)',
                           (companion_id, timestamp, timestamp))
        version_id = insert_version(connection, companion_id, 1, definition, '', timestamp)
        connection.execute("INSERT INTO timelines (id, companion_id, status, created_at) VALUES (?, ?, 'active', ?)",
                           (timeline_id, companion_id, timestamp))
        connection.execute('UPDATE companions SET active_version_id=?, active_timeline_id=? WHERE id=?',
                           (version_id, timeline_id, companion_id))
    return companion_id, timeline_id


def focus(client, companion_id):
    return ok(client.post('/api/companion/cast/focus', json={'companion_id': companion_id}))


def test_every_companion_keeps_and_shows_their_own_picture_across_a_switch(client, companion):
    sally, _timeline = another(client)
    with client.app.state.database.connect(write=True) as connection:
        connection.execute('UPDATE companions SET portrait_reference_id=? WHERE id=?', ('mira-picture', companion['id']))
        connection.execute('UPDATE companions SET portrait_reference_id=? WHERE id=?', ('sally-picture', sally))
    for focused in (sally, companion['id'], sally):
        focus(client, focused)
        pictures = {chat['id']: chat['portrait_reference_id'] for chat in chats(client)['chats']}
        assert pictures == {companion['id']: 'mira-picture', sally: 'sally-picture'}


def test_a_companion_out_of_focus_still_shows_their_picture_but_not_their_other_pictures(client, companion):
    """The chats list loads every companion's profile picture by its file address; the rest of an out-of-focus
    companion's reference set stays out of reach until they are in focus again."""
    from dungeon.lora import references

    sally, _timeline = another(client)
    database = client.app.state.database
    folder = references.directory(database)
    folder.mkdir(parents=True, exist_ok=True)
    timestamp = database.now()
    with database.connect(write=True) as connection:
        for reference_id in ('sally-picture', 'sally-other'):
            (folder / f'{reference_id}.png').write_bytes(b'picture')
            connection.execute(
                'INSERT INTO lora_references (id, companion_id, file, media_type, sha256, width, height, bytes, '
                "created_at, updated_at) VALUES (?, ?, ?, 'image/png', ?, 64, 64, 7, ?, ?)",
                (reference_id, sally, f'{reference_id}.png', reference_id, timestamp, timestamp))
        connection.execute('UPDATE companions SET portrait_reference_id=? WHERE id=?', ('sally-picture', sally))
    shown = client.get('/api/lora/references/sally-picture/file')
    assert shown.status_code == 200 and shown.content == b'picture'
    assert client.get('/api/lora/references/sally-other/file').status_code == 404
