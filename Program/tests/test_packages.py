"""World packages (dungeon/packages.py): one SQLite file per world, and the folder of Markdown and JSON it round-trips
with."""
import json
import shutil

import pytest
from test_travel import ok

from dungeon import packages
from dungeon.errors import DomainError


@pytest.fixture
def folder(tmp_path):
    """A small world folder."""
    root = tmp_path / 'ashmoor'
    (root / 'canon').mkdir(parents=True)
    (root / 'assets' / 'maps').mkdir(parents=True)
    packages.dump(root / 'world.json', {'id': 'ashmoor', 'name': 'Ashmoor', 'currency': 'marks'})
    packages.dump(root / 'regions.json', {'schema_version': 1, 'regions': [{'id': 'fen', 'name': 'The Fen'}]})
    packages.dump(root / 'settlements.json', {'schema_version': 1, 'settlements': [
        {'id': 'reedby', 'name': 'Reedby', 'region': 'fen'}]})
    packages.dump(root / 'cast.json', {'schema_version': 1, 'fields': {'secret': 'hidden'}, 'cast': [
        {'id': 'old-tam', 'name': 'Old Tam', 'settlement': 'reedby', 'secret': 'He drowned the miller.'},
        {'id': 'jess', 'name': 'Jess', 'settlement': 'reedby'}]})
    (root / 'canon' / 'overview.md').write_text('# Ashmoor\n\nA wet country.\n', encoding='utf-8')
    (root / 'assets' / 'maps' / 'fen.png').write_bytes(b'\x89PNG fake')
    return root


def test_a_world_folder_round_trips_through_its_package(folder, tmp_path):
    contents = packages.folder_contents(folder)
    path = packages.write(contents, tmp_path / 'ashmoor.sqlite')
    summary = packages.summary(path)
    assert summary['sections']['cast'] == {'entries': 2, 'hidden': 1} and summary['assets'] == 1
    out = packages.export(path, tmp_path / 'out')
    assert json.loads((out / 'cast.json').read_text()) == json.loads((folder / 'cast.json').read_text())
    assert (out / 'canon' / 'overview.md').read_text() == '# Ashmoor\n\nA wet country.\n'
    assert packages.fingerprint(packages.folder_contents(out)) == packages.fingerprint(contents)


@pytest.mark.parametrize(('change', 'detail'), [
    (lambda data: data['cast'].append({'id': 'jess', 'name': 'Jess again'}), 'two entries with the id jess'),
    (lambda data: data['cast'].append({'id': 'Bad Id'}), 'lowercase kebab-case id'),
    (lambda data: data['cast'].append({'id': 'wren', 'settlement': 'nowhere'}), 'settlement nowhere is not in settlements'),
])
def test_the_validator_refuses_a_folder_with_problems(folder, change, detail):
    data = json.loads((folder / 'cast.json').read_text())
    change(data)
    packages.dump(folder / 'cast.json', data)
    with pytest.raises(DomainError, match=detail):
        packages.folder_contents(folder)


def test_a_broken_json_file_is_named(folder):
    (folder / 'regions.json').write_text('{oops', encoding='utf-8')
    with pytest.raises(DomainError, match='regions.json is not valid JSON'):
        packages.folder_contents(folder)


def test_vallarith_builds_with_its_engine_data_and_rebuilds_when_its_sources_change(tmp_path, monkeypatch):
    path = packages.installed(tmp_path, 'vallarith')
    summary = packages.summary(path)
    assert summary['name'] == 'Vallarith' and summary['sections']['hidden-truths']['hidden'] > 0
    contents = packages.read(path)
    assert ('travel', 'vallarith') in contents['engine'] and ('adventures', 'kingswood') in contents['engine']
    built = path.stat().st_mtime_ns
    assert packages.installed(tmp_path, 'vallarith').stat().st_mtime_ns == built
    # A changed source makes it build again.
    shipped = tmp_path / 'shipped'
    shutil.copytree(packages.BUILTIN, shipped)
    monkeypatch.setattr(packages, 'BUILTIN', shipped)
    (shipped / 'vallarith' / 'canon' / 'overview.md').write_text('Changed.', encoding='utf-8')
    assert packages.read(packages.installed(tmp_path, 'vallarith'))['documents']['canon/overview.md'] == 'Changed.'


def test_packages_over_the_api(client, folder, app):
    listed = ok(client.get('/api/packages'))['packages']
    assert [item['id'] for item in listed] == ['vallarith'] and listed[0]['builtin']
    imported = ok(client.post('/api/packages/import', json={'folder': str(folder)}))
    assert imported['id'] == 'ashmoor'
    assert [item['id'] for item in ok(client.get('/api/packages'))['packages']] == ['vallarith', 'ashmoor']
    exported = ok(client.post('/api/packages/ashmoor/export'))['folder']
    assert json.loads((packages.Path(exported) / 'world.json').read_text())['name'] == 'Ashmoor'
    downloaded = client.get('/api/packages/ashmoor/file')
    assert downloaded.status_code == 200 and downloaded.content.startswith(b'SQLite format 3')
    # A folder may not take a built-in world's id.
    packages.dump(folder / 'world.json', {'id': 'vallarith', 'name': 'Not Vallarith'})
    refused = client.post('/api/packages/import', json={'folder': str(folder)})
    assert refused.status_code == 409
    assert client.get('/api/packages/nowhere/file').status_code == 404
