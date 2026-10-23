"""Art on request (dungeon/art.py): portraits, places and passages, routed to the image backends."""
import pytest
from conftest import Chunk, tell
from fastapi.testclient import TestClient
from test_images import FakeAdapter, local_comfy, ok, png

from dungeon import art, combat, record
from dungeon.identity import CLIENT_HEADER
from dungeon.images.adapters.base import AdapterError
from dungeon.main import create_app
from dungeon.providers.vault import MemoryVault


@pytest.fixture
def adapters():
    return {'comfyui': FakeAdapter(), 'codex': FakeAdapter(), 'hosted': FakeAdapter()}


@pytest.fixture
def app(tmp_path, clock, provider, adapters):
    return create_app(tmp_path / 'workspace' / 'dungeon.sqlite3', clock=clock, vault=MemoryVault(),
                      provider=provider, background=False, image_adapters=adapters)


@pytest.fixture
def client(app):
    with TestClient(app, headers={CLIENT_HEADER: 'workspace'}) as test_client:
        ok(test_client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'pell-provisions'}))
        ok(test_client.delete('/api/story'))
        ok(test_client.post('/api/story/start', json={'premade_id': 'agna-holt'}))
        yield test_client


def ask(client, kind, subject=''):
    return ok(client.post('/api/story/art', json={'kind': kind, 'subject': subject}))


def made(answer):
    return next(item for item in answer['art'] if item['id'] == answer['asked'])


def test_a_portrait_of_the_character_is_built_from_what_the_game_tracks_and_becomes_their_reference(client, adapters):
    local_comfy(client)
    first = made(ask(client, 'portrait', 'player'))
    assert first['status'] == 'done' and first['reference'] and first['kind'] == 'portrait'
    sent = adapters['comfyui'].requests[0]
    assert 'Portrait of Agna Holt' in sent.prompt and 'They are unhurt.' in sent.prompt
    assert sent.width < sent.height  # a portrait is tall
    assert client.get(first['url']).content == png()
    second = made(ask(client, 'portrait', 'player'))
    assert second['status'] == 'done' and not second['reference']
    with client.app.state.database.connect() as connection:
        assert art.reference_of(connection, client.app.state.database, 'portrait', 'player') == png()


def test_a_picture_goes_out_of_date_when_what_it_shows_changes(client):
    local_comfy(client)
    ask(client, 'portrait', 'player')
    assert not ok(client.get('/api/story/art'))['art'][0]['stale']
    with client.app.state.database.connect(write=True) as connection:
        combat.set_condition(connection, 3)
    assert ok(client.get('/api/story/art'))['art'][0]['stale']


def test_a_failed_backend_passes_the_picture_on_and_with_none_it_is_refused(client, adapters):
    refused = made(ask(client, 'place'))
    assert refused['status'] == 'refused' and 'No image backend' in refused['error']
    local_comfy(client)
    ok(client.post('/api/images/backends', json={'kind': 'comfyui', 'base_url': 'http://127.0.0.1:8189',
                                                 'accept_disclosure': True}))
    adapters['comfyui'].outcomes = [AdapterError('timeout', 'It took too long.'), png(96, 64)]
    place = made(ask(client, 'place'))
    assert place['status'] == 'done' and (place['width'], place['height']) == (96, 64)
    assert len(adapters['comfyui'].requests) == 2 and 'Pell' in adapters['comfyui'].requests[0].prompt


def test_a_passage_is_pictured_from_its_own_words_and_nsfw_stays_off_safe_only_backends(client, adapters):
    ok(client.post('/api/images/backends', json={'kind': 'codex', 'accept_disclosure': True}))
    with client.app.state.database.connect(write=True) as connection:
        connection.execute("INSERT INTO story_messages (id, seq, role, text, city_id, place_id, created_at) VALUES "
                           "('m-1', 900, 'narrator', 'The reeve counts coins by candlelight.', 'kingswood', "
                           "'pell-provisions', 'x'), ('m-2', 901, 'narrator', 'She stands nude in the rain.', "
                           "'kingswood', 'pell-provisions', 'x')")
    passage = made(ask(client, 'passage', 'm-1'))
    assert passage['status'] == 'done' and 'counts coins by candlelight' in adapters['codex'].requests[0].prompt
    nude = made(ask(client, 'passage', 'm-2'))
    assert nude['status'] == 'refused' and 'NSFW' in nude['error'] and len(adapters['codex'].requests) == 1
    assert client.post('/api/story/art', json={'kind': 'passage', 'subject': 'nope'}).status_code == 404


def test_someone_met_is_pictured_as_the_town_knows_them_with_their_feelings_on_their_face(client, adapters):
    local_comfy(client)
    with client.app.state.database.connect(write=True) as connection:
        connection.execute("INSERT INTO story_people (key, city_id, name, first_met_at, last_met_at, last_day, notes, "
                           "fear) VALUES ('town:kingswood:the-green:0', 'kingswood', 'Fenwick Cutter', 'x', 'x', 'x', "
                           "'[\"Fenwick wipes honey from his beard.\"]', 3)")
    portrait = made(ask(client, 'portrait', 'town:kingswood:the-green:0'))
    sent = adapters['comfyui'].requests[0].prompt
    assert portrait['status'] == 'done' and 'Portrait of Fenwick Cutter (he/him, 49 years old, hawker)' in sent
    assert 'wipes honey from his beard' in sent and 'a frightened, wary look' in sent
    assert client.post('/api/story/art', json={'kind': 'portrait', 'subject': 'stranger'}).status_code == 404


def test_passive_art_pictures_the_place_after_a_turn_once_and_stops_at_the_cap(client, adapters, provider, monkeypatch):
    client.put('/api/connection', json={'base_url': 'http://127.0.0.1:1234/v1', 'model': 'local-model', 'api_key': 'k'})
    provider.respond = lambda system, messages: ([Chunk('{"facts": []}'), Chunk('', 'stop')] if system.startswith(record.EXTRACT)
                                                 else [Chunk('Pell looks up.'), Chunk('', 'stop')])
    local_comfy(client)
    tell(client, 'I look around.', 'art-0001')
    assert ok(client.get('/api/story/art'))['art'] == []  # off by default
    ok(client.put('/api/settings', json={'passive_art': True}))
    tell(client, 'I look around again.', 'art-0002')
    pictured = ok(client.get('/api/story/art'))['art']
    assert [(item['kind'], item['status']) for item in pictured] == [('place', 'done')]
    tell(client, 'I wait.', 'art-0003')
    assert len(ok(client.get('/api/story/art'))['art']) == 1  # the place has its picture
    monkeypatch.setattr(art, 'PASSIVE_CAP', 0)
    with client.app.state.database.connect(write=True) as connection:
        connection.execute('DELETE FROM story_art')
    tell(client, 'I wait some more.', 'art-0004')
    assert ok(client.get('/api/story/art'))['art'] == []


def test_someone_here_in_the_scene_can_be_pictured_before_the_record_has_met_them(client, adapters):
    # Playtest m6a: the first person in the scene was refused as not met.
    from dungeon import story, story_clock
    local_comfy(client)
    with client.app.state.database.connect() as connection:
        view = story.scene(connection, story_clock.now(connection, client.app.state.database.clock))
    here = view['people'][0]['sheet']
    portrait = made(ask(client, 'portrait', here['key']))
    assert portrait['status'] == 'done' and f"Portrait of {here['name']}" in adapters['comfyui'].requests[0].prompt


def test_the_stage_shows_the_places_picture_and_portraits_of_who_is_here(client, adapters):
    from dungeon import story, story_clock
    local_comfy(client)
    assert ok(client.get('/api/story/art/stage')) == {'background': None, 'portraits': []}
    with client.app.state.database.connect(write=True) as connection:
        view = story.scene(connection, story_clock.now(connection, client.app.state.database.clock))
        here = view['people'][0]['sheet']
        connection.execute("INSERT INTO story_people (key, city_id, name, first_met_at, last_met_at, last_day, notes) "
                           "VALUES (?, 'kingswood', ?, 'x', 'x', 'x', '[]')", (here['key'], here['name']))
    ask(client, 'place')
    ask(client, 'portrait', here['key'])
    staged = ok(client.get('/api/story/art/stage'))
    assert staged['background']['url'].endswith('/file')
    assert [(item['key'], item['name']) for item in staged['portraits']] == [(here['key'], here['name'])]
    # Live-state portraits: once their feelings change, passive art makes them again.
    with client.app.state.database.connect(write=True) as connection:
        assert not art.stale_portrait(connection, client.app.state.database, here['key'])
        connection.execute('UPDATE story_people SET fear=4 WHERE key=?', (here['key'],))
        assert art.stale_portrait(connection, client.app.state.database, here['key'])
        assert art.wanted(connection, client.app.state.database, [here['key']]) == ('portrait', here['key'])
