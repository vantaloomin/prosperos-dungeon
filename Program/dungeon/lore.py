"""Lore from imported lorebooks (dungeon/imports/lore_routes.py): what the world knows as fact.

A book belongs to the world (a lorebook file imported on its own), or to a city (a world map's notes). Each entry is
plain text with keywords: always-on, or matched only while one of its keywords is in the last few messages, as a
whole word in any letter case, like Prospero's Study's literal keyword matching (server/lore/matching.py at
bbcbde4). No pattern runs and no model picks entries. The story narrator reads it from Milestone 1.
"""
import sqlite3
from pathlib import Path

from dungeon.database import decode, encode, identifier, many, one
from dungeon.errors import require
from dungeon.imports import formats

# The messages a keyword is looked for in, counting the one being answered.
SCAN_MESSAGES = 4
# At most this many keyword entries join one reply, first by book then by their order in it.
MAX_TRIGGERED = 8
MACROS = ('{{char}}', '<BOT>', '{{user}}', '<USER>')
# A Marinara world map's lorebook (dungeon/world/marinara.py) and the source title its city carries.
MAP_FORMAT = 'Marinara world map'
MAP_TITLE = 'Marinara world map: '


def books(connection) -> list[dict]:
    return many(connection, 'SELECT * FROM lore_books ORDER BY created_at')


def entry_view(row: dict) -> dict:
    return {'id': row['id'], 'title': row['title'], 'text': row['text'], 'keywords': decode(row['keywords']),
            'always': bool(row['always']), 'pattern': bool(row['pattern']), 'enabled': bool(row['enabled'])}


def listing(database) -> dict:
    """The world's books, with their entries."""
    with database.connect() as connection:
        found = []
        for book in books(connection):
            entries = many(connection, 'SELECT * FROM lore_entries WHERE book_id=? ORDER BY position', (book['id'],))
            found.append({'id': book['id'], 'name': book['name'], 'description': book['description'],
                          'source_format': book['source_format'], 'source_file': book['source_file'],
                          'city_id': book['city_id'], 'enabled': bool(book['enabled']),
                          'created_at': book['created_at'], 'entries': [entry_view(row) for row in entries]})
        return {'books': found}


def visible_book(connection, book_id: str) -> dict:
    return one(connection, 'SELECT * FROM lore_books WHERE id=?', (book_id,))


def set_book(database, book_id: str, enabled: bool) -> dict:
    with database.connect(write=True) as connection:
        visible_book(connection, book_id)
        connection.execute('UPDATE lore_books SET enabled=? WHERE id=?', (int(enabled), book_id))
    return listing(database)


def set_entry(database, entry_id: str, enabled: bool) -> dict:
    with database.connect(write=True) as connection:
        entry = one(connection, 'SELECT * FROM lore_entries WHERE id=?', (entry_id,))
        visible_book(connection, entry['book_id'])
        require(not (enabled and entry['pattern']), 'This entry finds its moment with a search pattern, which the '
                'Dungeon cannot match, so it stays off. Copy what matters into an entry of your own.', 422)
        connection.execute('UPDATE lore_entries SET enabled=? WHERE id=?', (int(enabled), entry_id))
    return listing(database)


def remove_book(database, book_id: str) -> dict:
    with database.connect(write=True) as connection:
        visible_book(connection, book_id)
        connection.execute('DELETE FROM lore_books WHERE id=?', (book_id,))
    return listing(database)


def add_book(connection, timestamp: str, book: dict, filename: str, city_id: str | None = None) -> dict:
    """A lorebook read by dungeon/imports/formats.py, saved with its entries."""
    book_id = identifier()
    connection.execute('INSERT INTO lore_books (id, name, description, source_format, source_file, created_at, '
                       'city_id) VALUES (?, ?, ?, ?, ?, ?, ?)',
                       (book_id, book['name'], book['description'], book['format'], filename[:260], timestamp, city_id))
    for position, entry in enumerate(book['entries']):
        connection.execute('INSERT INTO lore_entries (id, book_id, position, title, text, keywords, always, pattern, '
                           'enabled) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                           (identifier(), book_id, position, entry['title'], entry['text'], encode(entry['keywords']),
                            int(entry['always']), int(entry['pattern']), int(entry['enabled'])))
    return {'id': book_id, 'name': book['name'], 'entries': len(book['entries']),
            'off': sum(not entry['enabled'] for entry in book['entries'])}


def bring(database, filename: str, encoded: str) -> dict:
    """Import one lorebook file straight away. Character cards wait for the game's own characters."""
    found = formats.read(filename, encoded)
    require(found['character'] is None and found['book'] is not None,
            'Only lorebooks can be imported for now. Character cards come back when the game has characters of its '
            'own.', 422)
    with database.connect(write=True) as connection:
        book = add_book(connection, database.now(), found['book'], filename)
    return {'format': found['format'], 'book': book}


# Lore that belongs to a city ------------------------------------------------------------------------------
# A world map's notes describe its city's places, so they follow the city: a new world in that city gets them too
# (dungeon/worlds.py), and deleting the city deletes them.

def city_book_ids(connection, city: dict, schema: str = 'main') -> list[str]:
    rows = connection.execute(f'SELECT id FROM {schema}.lore_books WHERE city_id=? ORDER BY created_at',
                              (city['id'],)).fetchall()
    return [row[0] for row in rows]


def forget_city(connection, city: dict) -> None:
    for book_id in city_book_ids(connection, city):
        connection.execute('DELETE FROM lore_books WHERE id=?', (book_id,))


def carry_city_lore(target: Path, source: Path, city: dict) -> None:
    """A new world in `city` gets the city's lore from the world it was made from."""
    connection = sqlite3.connect(target, isolation_level=None)
    try:
        connection.execute('ATTACH DATABASE ? AS kept', (str(Path(source).resolve()),))
        connection.execute('BEGIN IMMEDIATE')
        for book_id in [] if city_book_ids(connection, city) else city_book_ids(connection, city, 'kept'):
            new_id = identifier()
            connection.execute(
                'INSERT INTO main.lore_books (id, name, description, source_format, source_file, '
                'enabled, created_at, city_id) SELECT ?, name, description, source_format, source_file, enabled, '
                'created_at, ? FROM kept.lore_books WHERE id=?', (new_id, city['id'], book_id))
            connection.execute(
                'INSERT INTO main.lore_entries (id, book_id, position, title, text, keywords, always, pattern, enabled) '
                'SELECT lower(hex(randomblob(16))), ?, position, title, text, keywords, always, pattern, enabled '
                'FROM kept.lore_entries WHERE book_id=?', (new_id, book_id))
        connection.execute('COMMIT')
    except BaseException:
        if connection.in_transaction:
            connection.execute('ROLLBACK')
        raise
    finally:
        connection.close()


def drop_orphaned(connection) -> None:
    """City lore whose city is gone (deleted in another world, `world_cities` follows the user)."""
    connection.execute('DELETE FROM lore_entries WHERE book_id IN (SELECT id FROM lore_books WHERE city_id IS NOT NULL '
                       'AND city_id NOT IN (SELECT id FROM world_cities))')
    connection.execute('DELETE FROM lore_books WHERE city_id IS NOT NULL AND city_id NOT IN (SELECT id FROM '
                       'world_cities)')
