"""Voice notes: rules decide when and which voice, an engine only reads the words aloud (docs/voice-notes.md)."""
import base64
import hashlib
import io
import json
import tarfile
import wave
from types import SimpleNamespace

import httpx
import pytest

from dungeon.voice import hosted, kokoro, notes, voices


def wav_bytes(seconds=2.0, rate=24000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(b'\0\0' * int(seconds * rate))
    return buffer.getvalue()


class FakeKokoro:
    """Stands in for sherpa-onnx-offline-tts: writes a WAV where it is told to, or fails."""

    def __init__(self):
        self.calls = []
        self.fail = False

    def __call__(self, arguments):
        self.calls.append(arguments)
        if self.fail:
            return SimpleNamespace(returncode=1, stderr=b'Error in generating audio.')
        output = next(argument.split('=', 1)[1] for argument in arguments if argument.startswith('--output-filename='))
        with open(output, 'wb') as file:
            file.write(wav_bytes())
        return SimpleNamespace(returncode=0, stderr=b'')


@pytest.fixture
def speaker(app, tmp_path, monkeypatch):
    model = tmp_path / 'kokoro'
    (model / 'espeak-ng-data').mkdir(parents=True)
    for name in ('model.onnx', 'voices.bin', 'tokens.txt'):
        (model / name).write_bytes(b'x')
    monkeypatch.setenv(kokoro.PROGRAM_ENV, str(tmp_path / 'sherpa-onnx-offline-tts'))
    monkeypatch.setenv(kokoro.MODEL_ENV, str(model))
    fake = FakeKokoro()
    app.state.voice.kokoro.runner = fake
    return fake


@pytest.fixture
def always(monkeypatch):
    monkeypatch.setattr(notes, 'CHANCE', 1.0)


def test_the_app_picks_a_voice_that_suits_them():
    assert voices.gender({'identity': 'He runs a bakery; his sister helps him.'}) == 'male'
    assert voices.gender({'identity': 'A nurse who loves her cat.'}) == 'female'
    assert voices.gender({}) == 'female'
    assert voices.accent('United Kingdom', 'UTC') == 'gb'
    assert voices.accent('United States', 'Europe/London') == 'us'
    assert voices.accent('', 'Europe/London') == 'gb'
    assert voices.accent('', 'America/New_York') == 'us'
    wanted = {'gender': 'male', 'accent': 'gb'}
    picked = voices.pick('companion-1', voices.kokoro_voices(), wanted)
    assert picked['gender'] == 'male' and picked['accent'] == 'gb'
    assert voices.pick('companion-1', voices.kokoro_voices(), wanted) == picked
    # No voice of the right accent: her gender still decides.
    assert voices.pick('x', voices.openai_voices(), {'gender': 'female', 'accent': 'gb'})['gender'] == 'female'
    assert not any('santa' in voice['name'].lower() for voice in voices.kokoro_voices())


def test_only_the_words_are_read_aloud():
    assert notes.spoken('Done with work 😅 *stretches* look https://example.com/x  ok') == 'Done with work look ok'


def test_british_voices_read_with_british_pronunciation(tmp_path):
    british = kokoro.command('tts', tmp_path, 21, tmp_path / 'a.wav', 'Hello')
    american = kokoro.command('tts', tmp_path, 3, tmp_path / 'a.wav', 'Hello')
    assert '--kokoro-lang=en' in british and '--kokoro-lang=en-us' in american
    assert british[-1] == 'Hello' and '--sid=21' in british


def test_a_call_is_read_aloud_only_while_voice_notes_are_on(app, client, companion, speaker):
    service = app.state.voice
    assert service.for_call() == 'builtin'
    client.put('/api/voice', json={'voice_notes': False})
    assert service.for_call() is None
    assert not service.fits('Look at this https://example.com') and not service.fits('x' * 400)
    assert service.fits('How did it go?')


def test_keys_are_saved_in_the_vault_and_never_returned(app, client, companion, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('ELEVENLABS_API_KEY', raising=False)
    client.put('/api/voice', json={'engine': 'elevenlabs'})
    assert client.get('/api/voice').json()['keys']['elevenlabs'] is None
    view = client.put('/api/voice/key', json={'engine': 'elevenlabs', 'api_key': 'el-secret'}).json()
    assert view['keys']['elevenlabs'] == 'saved' and view['ready'] is True
    assert 'el-secret' not in json.dumps(view)
    assert app.state.vault.get('voice-elevenlabs') == 'el-secret'
    assert client.put('/api/voice/key', json={'engine': 'elevenlabs', 'api_key': ''}).json()['keys']['elevenlabs'] is None


def test_an_openai_text_model_key_is_used_for_openai_voices(app, client, companion, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    response = client.post('/api/models/profiles', json={'name': 'OpenAI', 'config': {
        'provider': 'openai', 'model': 'gpt-5-mini', 'base_url': 'https://api.openai.com/v1'}, 'api_key': 'sk-text'})
    assert response.status_code == 201, response.text
    assert app.state.voice.key('openai') == ('sk-text', 'profile')


def test_each_companion_gets_a_voice_the_user_can_change(client, companion, speaker):
    listed = client.get('/api/voice/companions').json()
    [mira] = listed['companions']
    assert mira['chosen_by'] == 'app' and any(voice['id'] == mira['voice'] for voice in listed['voices'])
    client.put(f"/api/voice/companions/{mira['id']}", json={'engine': 'builtin', 'voice': '22'})
    assert client.get('/api/voice/companions').json()['companions'][0] == {**mira, 'voice': '22', 'chosen_by': 'user'}
    client.put(f"/api/voice/companions/{mira['id']}", json={'engine': 'builtin', 'voice': ''})
    assert client.get('/api/voice/companions').json()['companions'][0] == mira
    preview = client.post('/api/voice/preview', json={'companion_id': mira['id'], 'voice': '22'})
    assert preview.status_code == 200 and preview.content[:4] == b'RIFF'
    assert '--sid=22' in speaker.calls[-1] and 'Mira' in speaker.calls[-1][-1]


def test_hosted_engines_get_only_the_words(app):
    seen = []

    def handle(request):
        seen.append(request)
        if 'texttospeech' in request.url.host:
            return httpx.Response(200, json={'audioContent': base64.b64encode(b'mp3').decode()})
        return httpx.Response(200, content=b'mp3')

    transport = httpx.MockTransport(handle)
    import asyncio
    assert asyncio.run(hosted.speak('openai', 'k1', 'marin', 'Hi there', transport)) == b'mp3'
    assert asyncio.run(hosted.speak('elevenlabs', 'k2', 'voice123', 'Hi there', transport)) == b'mp3'
    assert asyncio.run(hosted.speak('google', 'k3', 'en-GB-Chirp3-HD-Aoede', 'Hi there', transport)) == b'mp3'
    openai, eleven, google = seen
    assert openai.headers['authorization'] == 'Bearer k1'
    assert json.loads(openai.content) | {'instructions': ''} == {'model': hosted.OPENAI_MODEL, 'voice': 'marin',
                                                                 'input': 'Hi there', 'instructions': '',
                                                                 'response_format': 'mp3'}
    assert eleven.url.path == '/v1/text-to-speech/voice123' and eleven.headers['xi-api-key'] == 'k2'
    assert json.loads(eleven.content) == {'text': 'Hi there', 'model_id': hosted.ELEVENLABS_MODEL}
    assert google.headers['x-goog-api-key'] == 'k3'
    assert json.loads(google.content)['voice'] == {'languageCode': 'en-GB', 'name': 'en-GB-Chirp3-HD-Aoede'}


def test_a_refused_key_says_so():
    import asyncio
    transport = httpx.MockTransport(lambda request: httpx.Response(401))
    with pytest.raises(Exception, match='did not accept the voice key'):
        asyncio.run(hosted.speak('openai', 'bad', 'marin', 'Hi', transport))


def test_hosted_voice_lists_are_labelled():
    import asyncio

    def handle(request):
        if 'elevenlabs' in request.url.host:
            return httpx.Response(200, json={'voices': [{'voice_id': 'v1', 'name': 'Alice', 'labels': {
                'gender': 'female', 'accent': 'british', 'age': 'middle_aged'}}]})
        language = request.url.params['languageCode']
        return httpx.Response(200, json={'voices': [
            {'name': f'{language}-Standard-A', 'ssmlGender': 'FEMALE'},
            {'name': f'{language}-Chirp3-HD-Charon', 'ssmlGender': 'MALE'}]})

    transport = httpx.MockTransport(handle)
    [alice] = asyncio.run(hosted.elevenlabs_voices('k', transport))
    assert alice['gender'] == 'female' and alice['accent'] == 'gb'
    google = asyncio.run(hosted.google_voices('k', transport))
    assert [voice['id'] for voice in google][:2] == ['en-GB-Chirp3-HD-Charon', 'en-US-Chirp3-HD-Charon']
    assert {voice['accent'] for voice in google} == {'us', 'gb'}


def archive(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:bz2') as bundle:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), 0o755
            bundle.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def test_the_built_in_voice_installs_only_what_matches_its_checksum(tmp_path, monkeypatch):
    import asyncio
    monkeypatch.delenv(kokoro.PROGRAM_ENV, raising=False)
    monkeypatch.delenv(kokoro.MODEL_ENV, raising=False)
    runtime = archive({f'sherpa/bin/{kokoro.program_name()}': b'program'})
    model = archive({f'{kokoro.MODEL_NAME}/{name}': b'x' for name in ('model.onnx', 'voices.bin', 'tokens.txt')}
                    | {f'{kokoro.MODEL_NAME}/espeak-ng-data/phontab': b'x'})
    monkeypatch.setattr(kokoro, 'platform_key', lambda: 'test')
    monkeypatch.setitem(kokoro.RUNTIMES, 'test', ('v1/runtime.tar.bz2', len(runtime), hashlib.sha256(runtime).hexdigest()))
    monkeypatch.setattr(kokoro, 'MODEL', ('models/kokoro.tar.bz2', len(model), 'wrong'))
    served = {'/v1/runtime.tar.bz2': runtime, '/models/kokoro.tar.bz2': model}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=served[
        request.url.path.removeprefix('/k2-fsa/sherpa-onnx/releases/download')]))
    voice = kokoro.Kokoro(tmp_path, transport)
    assert voice.status()['ready'] is False
    with pytest.raises(Exception, match='checksum'):
        asyncio.run(voice.install())
    assert voice.program() is not None and voice.model() is None and voice.status()['error']
    monkeypatch.setattr(kokoro, 'MODEL', ('models/kokoro.tar.bz2', len(model), hashlib.sha256(model).hexdigest()))
    assert asyncio.run(voice.install())['ready'] is True
    assert not any((tmp_path / 'downloads').iterdir())


def test_the_built_in_voice_waits_for_a_press_to_download(app, monkeypatch):
    """Big downloads happen only after a press: starting with background activity on downloads nothing."""
    from fastapi.testclient import TestClient

    from dungeon import auto_backup
    from dungeon.identity import CLIENT_HEADER

    async def idle(*_args, **_kwargs):
        return None

    for worker in (app.state.life, app.state.images):
        monkeypatch.setattr(worker, 'run_forever', idle)
    monkeypatch.setattr(auto_backup, 'run_forever', idle)
    monkeypatch.setattr(app.state.launcher, 'launch_all', idle)
    monkeypatch.setattr(app.state.builtin_recall, 'kick', lambda: None)
    monkeypatch.setattr(app.state.ready, 'recover', lambda: None)
    pressed = []
    monkeypatch.setattr(app.state.voice.kokoro, 'install', lambda: pressed.append(True) or idle())
    app.state.life_tasks = True
    with TestClient(app, headers={CLIENT_HEADER: 'workspace'}) as client:
        view = client.get('/api/voice').json()
        assert view['voice_notes'] and view['engine'] == 'builtin' and not view['builtin']['downloading']
        assert pressed == []
        client.post('/api/voice/builtin/download', json={})
    assert pressed == [True]
