"""Intensity v0 (dungeon/story.py intensity): the world's preset, or the player's, shapes the narrator's prompt."""
from conftest import Chunk, tell


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def narrator_after(client, provider, client_id):
    provider.replies = [[Chunk('Rain on the shingles.'), Chunk('', 'stop')]]
    tell(client, 'I listen.', client_id)
    return provider.requests[-1]['system']


def test_kingswood_is_grim_and_unflinching_until_the_player_turns_it_down(client, connected, provider):
    ok(client.put('/api/story/scene', json={'city_id': 'kingswood', 'place_id': 'felled-oak'}))
    ok(client.delete('/api/story'))
    ok(client.post('/api/story/start', json={'premade_id': 'agna-holt'}))
    assert ok(client.get('/api/story'))['intensity'] | {'voice': ''} == \
        {'preset': 'unflinching', 'chosen': 'world', 'world': 'unflinching', 'voice': '', 'drama': 'eventful',
         'drama_chosen': 'world', 'drama_world': 'eventful', 'cutaways': False,
         'defeat': 'as_written', 'ruleset': 'marvel'}
    narrator = narrator_after(client, provider, 'story-0001')
    assert '- Violence: unflinching: explicit' in narrator and 'Voice: grim and earthy' in narrator

    # Mid-story, the next line follows the new preset; the world's voice stays.
    settings = ok(client.put('/api/settings', json={'intensity': 'restrained'}))
    assert settings['intensity'] == 'restrained'
    assert ok(client.get('/api/story'))['intensity']['preset'] == 'restrained'
    narrator = narrator_after(client, provider, 'story-0002')
    assert '- Sex: restrained: implied' in narrator and 'unflinching' not in narrator
    assert 'Voice: grim and earthy' in narrator
    assert client.put('/api/settings', json={'intensity': 'gory'}).status_code == 422


def test_a_world_without_its_own_preset_is_unflinching_with_no_voice(client, connected, provider):
    ok(client.put('/api/story/scene', json={'city_id': 'baltimore'}))
    narrator = narrator_after(client, provider, 'story-0001')
    assert '- Horror: unflinching' in narrator and 'Voice:' not in narrator
