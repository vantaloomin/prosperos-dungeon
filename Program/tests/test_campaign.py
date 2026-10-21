"""Campaign start (dungeon/campaign.py): a premade character or one the player made, then the story opens."""
from conftest import Chunk


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def test_starting_as_a_premade_character(client, provider):
    assert ok(client.get('/api/story/start'))['premades'] == []  # The test world starts in Baltimore, with none.
    ok(client.put('/api/story/scene', json={'city_id': 'haddon-harbor'}))
    ok(client.delete('/api/story'))
    choices = ok(client.get('/api/story/start'))
    assert choices['points'] == 60 and choices['range'] == [4, 18]
    nell = next(item for item in choices['premades'] if item['id'] == 'nell-coombs')
    assert all(sum(item['stats'].values()) <= 60 for item in choices['premades'])

    started = ok(client.post('/api/story/start', json={'premade_id': 'nell-coombs'}))
    assert [message['role'] for message in started['messages']] == ['scene']
    assert started['messages'][0]['text'].startswith('You arrive at')
    assert ok(client.get('/api/story/sheet'))['stats'] == nell['stats']
    assert ok(client.get('/api/worlds'))['persona']['name'] == 'Nell Coombs'
    # Once begun, the story keeps its character until a new story.
    again = client.post('/api/story/start', json={'premade_id': 'theo-marsh'})
    assert again.status_code == 409
    assert client.post('/api/story/start', json={'premade_id': 'nobody'}).status_code == 409
    ok(client.delete('/api/story'))
    assert client.post('/api/story/start', json={'premade_id': 'nobody'}).status_code == 404

    # The narrator is told who the player is, in words, never the numbers.
    ok(client.post('/api/story/start', json={'premade_id': 'nell-coombs'}))
    ok(client.put('/api/connection', json={'base_url': 'http://127.0.0.1:1234/v1', 'model': 'local-model'}))
    provider.replies = [[Chunk('The fog sits on the harbor.'), Chunk('', 'stop')]]
    ok(client.post('/api/story/messages', json={'text': 'I look at the boats.', 'client_id': 'story-0001'}))
    system = provider.requests[-1]['system']
    assert "## The player's character\nNell Coombs (woman, 41)." in system and "lobsterman's widow" in system
    character = system.split("## The player's character")[1].split('##')[0]
    assert 'Good at: will, nerve, intimidation, resisting pain or influence; strength, speed' in character
    assert 'Poor at: charm, persuasion, deception, performance; magic, faith, the uncanny.' in character
    assert not any(stat in character for stat in ('Resolve', 'Vitality', '14'))


def test_making_your_own_character(client):
    stats = {'Mind': 12, 'Allure': 12, 'Resolve': 10, 'Vitality': 10, 'Essence': 8, 'Luck': 8}
    person = {'name': 'Ash Ward', 'gender': 'nonbinary', 'age': 30, 'about': 'New in town, and broke.'}
    refused = client.post('/api/story/start', json={'persona': person, 'stats': {**stats, 'Mind': 18}})
    assert refused.status_code == 422 and '60 points' in refused.json()['detail']
    assert client.post('/api/story/start', json={'persona': person, 'stats': {**stats, 'Luck': 2}}).status_code == 422
    assert client.post('/api/story/start', json={'persona': {'name': ' '}, 'stats': stats}).status_code == 422
    assert client.post('/api/story/start', json={'persona': person, 'stats': {'Mind': 10}}).status_code == 422

    started = ok(client.post('/api/story/start', json={'persona': person, 'stats': stats}))
    assert len(started['messages']) == 1
    assert ok(client.get('/api/story/sheet'))['stats'] == stats
    persona = ok(client.get('/api/worlds'))['persona']
    assert (persona['name'], persona['about']) == ('Ash Ward', 'New in town, and broke.')
