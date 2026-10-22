"""Lore from imported lorebooks (dungeon/imports/lore_routes.py): what the world knows as fact.

A book belongs to the world (a lorebook file imported on its own), or to a city (a world map's notes). Each entry is
plain text with keywords: always-on, or matched only while one of its keywords is in the last few messages, as a
whole word in any letter case, like Prospero's Study's literal keyword matching (server/lore/matching.py at
bbcbde4), or while the scene fits its "when" (dungeon/lore_moments.py: rain, night, a holiday, a place...). No
pattern runs and no model picks entries. The story narrator reads it in every turn (`prompt_text`).
"""
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from dungeon import lore_moments as moments
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


def when_of(row: dict, holidays: list[str]) -> tuple[list[str], bool]:
    """(the entry's "when", whether the app read it from its keywords). Always-on entries have none."""
    if row['always']:
        return [], False
    if row.get('moment') is not None:
        return decode(row['moment']), False
    found = moments.guessed(decode(row['keywords']), holidays)
    return found, bool(found)


def entry_view(row: dict, scene: dict) -> dict:
    when, guessed = when_of(row, scene['holidays'])
    return {'id': row['id'], 'title': row['title'], 'text': row['text'], 'keywords': decode(row['keywords']),
            'always': bool(row['always']), 'pattern': bool(row['pattern']), 'enabled': bool(row['enabled']),
            'when': [{'key': key, 'label': moments.label(key, scene['city'])} for key in when],
            'when_guessed': guessed, 'fits_now': bool(row['enabled']) and moments.matches(when, scene['now'])}


def story_scene(connection, now: datetime) -> dict:
    """The story's town, its holidays and what holds in the scene right now, for listing entries."""
    from dungeon import story
    where = story.scene_row(connection)
    city = story.city_data(connection, where['city_id'])
    keys = moments.now_keys(city, where['place_id'], story.local_moment(city, now))
    return {'city': city, 'holidays': moments.holiday_names(city), 'now': keys}


def listing(database) -> dict:
    """The world's books, with their entries, and what the "when" pickers offer in the story's town."""
    with database.connect() as connection:
        from dungeon import story_clock
        scene = story_scene(connection, story_clock.now(connection, database.clock))
        found = []
        for book in books(connection):
            entries = many(connection, 'SELECT * FROM lore_entries WHERE book_id=? ORDER BY position', (book['id'],))
            found.append({'id': book['id'], 'name': book['name'], 'description': book['description'],
                          'source_format': book['source_format'], 'source_file': book['source_file'],
                          'city_id': book['city_id'], 'enabled': bool(book['enabled']),
                          'created_at': book['created_at'], 'entries': [entry_view(row, scene) for row in entries]})
        return {'books': found, 'choices': moments.choices(scene['city'])}


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


def set_when(database, entry_id: str, when: list[str]) -> dict:
    """The player's own "when" for an entry: it replaces the one the app read from its keywords. An empty list
    clears it, so the entry comes only by its keywords."""
    with database.connect(write=True) as connection:
        entry = one(connection, 'SELECT * FROM lore_entries WHERE id=?', (entry_id,))
        visible_book(connection, entry['book_id'])
        require(not entry['always'], 'An always-on entry is part of every turn, so it has no "when".', 422)
        connection.execute('UPDATE lore_entries SET moment=? WHERE id=?', (encode(moments.tidy(when)), entry_id))
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


# For the narrator ---------------------------------------------------------------------------------------------

HEADING = '## Lore (true in this world; use what bears on the scene, in your own words)'


def spelled(text: str, user: str) -> str:
    """A card's {{user}} becomes the player character's name, and {{char}} (the card's own character) "the
    narrator"."""
    for macro in MACROS:
        text = text.replace(macro, user if macro in ('{{user}}', '<USER>') else 'the narrator')
    return text


def mentioned(keyword: str, text: str) -> bool:
    """A keyword as a whole word, in any letter case."""
    keyword = keyword.strip()
    return bool(keyword) and re.search(r'(?<!\w)' + re.escape(keyword.casefold()) + r'(?!\w)', text) is not None


def prompt_text(connection, city: dict, place_id: str, local: datetime, recent: list[str], user: str = '') -> str:
    """The lore for this turn: always-on entries, then entries whose keywords are in the last few messages, then
    those whose "when" fits the scene, at most MAX_TRIGGERED of the last two. '' with no lore switched on."""
    entries = many(connection, 'SELECT e.* FROM lore_entries e JOIN lore_books b ON b.id=e.book_id WHERE e.enabled=1 '
                   'AND b.enabled=1 AND (b.city_id IS NULL OR b.city_id=?) ORDER BY b.created_at, e.position',
                   (city['id'],))
    if not entries:
        return ''
    scanned = '\n'.join(recent[-SCAN_MESSAGES:]).casefold()
    holidays, keys = moments.holiday_names(city), None
    always, mentioned_now, fitting = [], [], []
    for entry in entries:
        line = spelled(f"- {entry['title']}: {entry['text']}" if entry['title'] else f"- {entry['text']}",
                       user or 'the player character')
        when = when_of(entry, holidays)[0]
        if entry['always']:
            always.append(line)
        elif any(mentioned(word, scanned) for word in decode(entry['keywords'])):
            mentioned_now.append(line)
        elif when:
            keys = moments.now_keys(city, place_id, local) if keys is None else keys
            fitting += [line] if moments.matches(when, keys) else []
    lines = [*always, *[*mentioned_now, *fitting][:MAX_TRIGGERED]]
    return f'{HEADING}\n' + '\n'.join(lines) if lines else ''
