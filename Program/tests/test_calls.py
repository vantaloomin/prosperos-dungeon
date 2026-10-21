"""On a call (dungeon/life/calls.py): calls started either way, the call in the chat, and how it ends."""
import asyncio
import time
from datetime import timedelta

import pytest
from conftest import send
from test_together import mira, notes, says, where
from test_voice_notes import speaker  # noqa: F401 - the fake built-in voice, used as a fixture.

from dungeon.characters import current
from dungeon.life import calls, pacing


def test_asking_to_call_is_read_from_the_message():
    for text in ('can I call you?', 'call me?', 'wanna facetime?', "I'm calling you", 'give me a ring!',
                 'can you call me right now? I need to hear your voice'):
        assert calls.asked(text), text
    for text in ('call me tonight after work?', 'my mom called me yesterday', "don't call me", 'how was work?',
                 'can I call you tomorrow?'):
        assert not calls.asked(text), text
    assert calls.hanging_up('ok I gotta go, talk later!') and calls.hanging_up('bye!!')
    assert not calls.hanging_up('so how was your day?')


@pytest.fixture
def nearby(client, monkeypatch):
    mira(client, monkeypatch)


def press(client, path=''):
    response = client.post(f'/api/life/calls{path}')
    assert response.status_code == 200, response.text
    return response.json()


def test_the_call_button_and_end_call(client, nearby, provider, clock):
    clock.advance(timedelta(hours=7))  # 19:00, free.
    found = press(client)
    call_id = found['call']['id']
    assert found['state'] == 'call' and found['call']['until_at']
    assert client.post('/api/life/calls').status_code == 409  # One at a time.
    says(provider)
    send(client, 'hiii', 'client-call-5')
    assert 'The user called you at 19:00' in notes(provider)
    ended = press(client, f'/{call_id}/end')
    assert ended['state'] == 'apart' and ended['call']['status'] == 'ended'


def test_a_call_ends_on_its_own_when_the_line_goes_quiet(client, nearby, clock):
    clock.advance(timedelta(hours=7))
    press(client)
    clock.advance(calls.IDLE + timedelta(minutes=1))
    assert where(client)['state'] == 'apart'


def test_a_call_ends_before_they_have_to_sleep(client, nearby, provider, clock, monkeypatch):
    monkeypatch.setattr(calls, 'HOURS', (3.0, 3.0))
    clock.advance(timedelta(hours=10, minutes=20))  # Monday 22:20; up for work tomorrow, so done by 22:30.
    found = press(client)
    assert found['call']['until_at'].startswith('2026-10-05T22:30')
    clock.advance(timedelta(minutes=6))
    says(provider)
    send(client, 'tell me everything', 'client-call-6')
    assert 'You have to go in a few minutes: start wrapping up the call' in notes(provider)


def test_decline_and_no_calls_while_together(client, nearby, clock):
    with client.app.state.database.connect(write=True) as connection:
        found = calls.insert(connection, current(connection), 'them', 'ringing', clock.now())
    assert press(client, f"/{found['id']}/decline")['call']['status'] == 'declined'
    clock.advance(timedelta(hours=7))
    send(client, 'wanna come over now?', 'client-call-8')
    assert where(client)['state'] == 'together'
    assert client.post('/api/life/calls').status_code == 409
    send(client, 'can I call you?', 'client-call-9')  # Beside each other: no call.
    assert where(client)['state'] == 'together'


def test_replies_on_a_call_are_not_held_and_keep_no_texting_habits(client, monkeypatch, provider, clock):
    mira(client, monkeypatch, texting={'bursts': False, 'lowercase': True, 'typos': False})
    monkeypatch.setattr(pacing, 'ACTIVE', True)
    clock.advance(timedelta(hours=7))
    press(client)
    with client.app.state.database.connect() as connection:
        assert pacing.hold(connection, current(connection), clock.now(), 'x')['held_until'] is None
    says(provider, 'Hi! So Good To Hear You.')
    reply = send(client, 'hey', 'client-call-10')['reply']
    assert reply['text'] == 'Hi! So Good To Hear You.'


def test_a_slow_voice_leaves_a_call_reply_as_text(client, nearby, provider, clock, speaker, monkeypatch):  # noqa: F811
    from dungeon import conversation
    from dungeon.voice.notes import VoiceNotes

    async def stuck(*_args, **_kwargs):
        await asyncio.sleep(5)

    monkeypatch.setattr(conversation, 'CALL_VOICE_SECONDS', 0.05)
    monkeypatch.setattr(VoiceNotes, 'record', stuck)
    clock.advance(timedelta(hours=7))
    press(client)
    says(provider, 'Hey, you.')
    started = time.monotonic()
    reply = send(client, 'hey you', 'client-call-slow')['reply']
    assert reply['status'] == 'complete' and not reply['voice'] and time.monotonic() - started < 4


def test_coming_over_during_a_call_ends_it(client, nearby, provider, clock):
    clock.advance(timedelta(hours=7))  # 19:00, free.
    press(client)
    says(provider, 'On my way!')
    send(client, 'wanna come over now?', 'client-call-13')
    found = where(client)
    assert (found['state'], found['kind']) == ('together', 'yours') and found['call'] is None
    assert 'You are on a phone call' not in notes(provider) and 'talked on the phone' not in notes(provider)
    with client.app.state.database.connect() as connection:
        assert calls.latest(connection, current(connection)['active_timeline_id'], clock.now())['status'] == 'ended'


def test_a_clock_moved_back_hides_a_call_not_yet_made(client, nearby, clock):
    clock.advance(timedelta(hours=7))
    press(client)
    clock.advance(timedelta(hours=-1))
    assert where(client)['call'] is None and where(client)['state'] == 'apart'


def test_what_is_not_asking_to_call_or_hanging_up():
    for text in ('you can call me Sam', 'call me crazy but I love it', 'they call me the boss', 'call me old fashioned'):
        assert not calls.asked(text), text
    for text in ('can we talk on the phone?', 'call?', 'free for a call?', "I'll call you in a sec", 'call me rn please',
                 'call me, I miss you'):
        assert calls.asked(text), text
    for text in ('we need to go to that place sometime', 'i have to go to the bathroom brb',
                 'i gotta run to the store later haha but anyway'):
        assert not calls.hanging_up(text), text
    for text in ('I gotta go to bed', 'have to go now babe', 'I should go, it is late', 'gotta go'):
        assert calls.hanging_up(text), text


def test_their_texting_style_stays_out_of_the_prompt_on_a_call(client, monkeypatch, provider, clock):
    mira(client, monkeypatch, texting={'bursts': True, 'lowercase': True, 'typos': True})
    says(provider)
    send(client, 'hi', 'client-call-style-1')
    assert 'How you text:' in provider.requests[-1]['system']
    clock.advance(timedelta(hours=7))
    press(client)
    says(provider, 'Hey.')
    send(client, 'hey you', 'client-call-style-2')
    assert 'How you text:' not in provider.requests[-1]['system']
