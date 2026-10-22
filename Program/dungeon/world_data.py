"""Where the game reads a world's data (docs/packages.md "In play"): from the world packages in the data folder.

Each kind of engine data (a world's travel map, arcs, factions and tiers; a town's adventure, items, finds and
premades) is read from the package whose `engine` part holds it, so an edited or imported world plays as edited. A
built-in world's package is built from the shipped files when the app starts (dungeon/packages.py installed), so
until someone edits it, it holds exactly what `dungeon/world/data` does. With no data folder in use (a script, a
test of one loader) or for data no package holds, the shipped JSON file is read.

Reads are cheap: a package's engine part is read once and again only when the file changes, and each read parses
its own copy, as reading the file did. `memo` caches a loader's work the same way.
"""
import functools
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from dungeon import packages

_root: Path | None = None


def use(root: Path | None):
    """The data folder whose packages the game reads; built-in worlds are built (again) there now."""
    global _root
    _root = Path(root) if root is not None else None
    if _root is not None:
        for world_id in packages.builtin_ids():
            packages.installed(_root, world_id)


def paths() -> list[Path]:
    """The package files in use: the built-in worlds first, then imported ones."""
    if _root is None:
        return []
    folder = _root / packages.FOLDER
    builtin = [folder / f'{world_id}.sqlite' for world_id in packages.builtin_ids()]
    imported = sorted(path for path in folder.glob('*.sqlite') if path not in builtin) if folder.is_dir() else []
    return [path for path in builtin if path.is_file()] + imported


def version() -> tuple:
    """What changes when any package in use changes: their paths and modification times."""
    found = []
    for path in paths():
        try:
            found.append((str(path), os.stat(path).st_mtime_ns))
        except OSError:
            continue
    return tuple(found)


@functools.lru_cache(maxsize=32)
def _engine(path: str, stamp: int) -> dict[tuple[str, str], str]:
    try:
        with closing(packages.connect(Path(path))) as connection:
            return {(row['kind'], row['key']): row['data'] for row in connection.execute('SELECT kind, key, data FROM engine')}
    except sqlite3.Error:
        return {}


def _held(kind: str) -> dict[str, str]:
    """Every package's `kind` data by key; the first package that holds a key wins."""
    found: dict[str, str] = {}
    for path, stamp in version():
        for (held_kind, key), data in _engine(path, stamp).items():
            if held_kind == kind:
                found.setdefault(key, data)
    return found


def read(kind: str, key: str) -> dict | None:
    """One piece of engine data (`kind` is a folder of dungeon/world/data, `key` a world or town id), or None."""
    held = _held(kind).get(key)
    if held is not None:
        return json.loads(held)
    path = packages.DATA / kind / f'{key}.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


def keys(kind: str) -> list[str]:
    """The keys there is `kind` data for, in a package or shipped, sorted."""
    shipped = {path.stem for path in (packages.DATA / kind).glob('*.json')}
    return sorted(shipped | set(_held(kind)))


def memo(function):
    """A loader's cache that empties when a package in use changes."""
    @functools.wraps(function)
    def wrapper(*args):
        token = version()
        if wrapper.token != token:
            cached.cache_clear()
            wrapper.token = token
        return cached(*args)

    cached = functools.cache(function)
    wrapper.token = None
    wrapper.cache_clear = cached.cache_clear
    return wrapper
