"""The canon ledger and the story so far (docs/story.md "The ledger"; requirements "Memory and context").

The ledger is the source of truth: facts as structured entries (deaths, items, wounds, promises, locations,
secrets, relationships, other facts), each marked as world truth, the character's belief, or both. Code records
the facts it decides; after each narration the Continuity model, when one is chosen for that job, lists the new
facts the narrator brought in, and code keeps those that do not contradict the ledger. The narrator is given the
ledger every turn and never contradicts it.

The player sees and corrects what their character knows (truth 'belief' or 'both'); every correction is logged.
Hidden truth ('world') stays out of their view.

The story so far: the narrator reads the most recent messages word for word and, before them, one rolling summary.
When enough older messages pile up, they are folded into the summary by the Continuity model (or the Default one).

Both are game state, kept per branch (dungeon/timeline.py SAVED).
"""
import json
import re

from dungeon.database import identifier, many, one, optional
from dungeon.errors import require
from dungeon.providers.scheduling import CONVERSATION
from dungeon.text_models import config_for, key_for, routes

JOB = 'continuity'
KINDS = ('death', 'item', 'wound', 'promise', 'location', 'secret', 'relationship', 'fact')
TRUTHS = ('world', 'belief', 'both')
MOST_FACTS = 6
# Entries the narrator is given each turn: every death and promise, then the newest of the rest.
IN_PROMPT = 40
# Messages the narrator reads word for word; older ones are folded into the summary FOLD at a time.
RECENT = 30
FOLD = 20
SUMMARY_WORDS = 400

EXTRACT = f"""You keep the continuity of a tabletop roleplaying game. You never write story. Read the latest turn \
and list the new, lasting facts it established: someone died or was hurt, an item was gained, lost or given, a \
promise or debt was made, a place was learned of, a secret came out, a relationship changed, or a name, scar or \
rumour worth remembering. Leave out moods, weather and anything that will not matter later. At most {MOST_FACTS}.

For each fact give its kind ({', '.join(KINDS)}), its subject (the person, item or place it is about, in a few \
words), the fact in one short sentence, and its truth: "both" when the player's character saw or knows it, \
"world" when it is true but hidden from them, "belief" when the character believes it but it may not be true.

Answer with JSON only, in this shape:
{{"facts": [{{"kind": "wound", "subject": "the bouncer", "text": "The bouncer's nose is broken.", "truth": "both"}}]}}
Answer {{"facts": []}} when nothing lasting happened."""

SUMMARIZE = f"""You keep the story so far of a tabletop roleplaying game. Rewrite the summary to take in the new \
turns: what happened, in order, who the player's character met and what they did, what is unresolved. Past tense, \
plain prose, at most {SUMMARY_WORDS} words. Keep everything that still matters; drop what no longer does. Answer \
with the summary only."""


# The ledger --------------------------------------------------------------------------------------

def dead(connection) -> set[str]:
    return {row['subject'].lower() for row in many(connection, "SELECT subject FROM ledger_entries WHERE kind='death' "
                                                                'AND removed=0')}


def record(connection, kind: str, subject: str, text: str, now: str, source: str = 'code', truth: str = 'both',
           message_id: str | None = None) -> dict | None:
    """A new entry, or None when the narrator's fact contradicts the ledger (the dead do nothing more)."""
    require(kind in KINDS, f'{kind} is not a kind of fact.', 422)
    require(truth in TRUTHS, f'{truth} is not a kind of truth.', 422)
    subject, text = subject.strip()[:120], text.strip()[:500]
    require(bool(subject and text), 'A fact needs a subject and its text.', 422)
    if source == 'narrator' and kind != 'death' and subject.lower() in dead(connection):
        return None
    entry_id = identifier()
    connection.execute('INSERT INTO ledger_entries (id, kind, subject, text, truth, source, message_id, created_at) '
                       'VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (entry_id, kind, subject, text, truth, source, message_id, now))
    return one(connection, 'SELECT * FROM ledger_entries WHERE id=?', (entry_id,))


def entries(connection, known_only: bool = True) -> list[dict]:
    """The ledger, newest first; only what the character knows unless asked for everything."""
    hidden = "AND truth != 'world'" if known_only else ''
    return many(connection, f'SELECT id, kind, subject, text, truth, source, created_at FROM ledger_entries '
                            f'WHERE removed=0 {hidden} ORDER BY created_at DESC, rowid DESC')


def correct(connection, entry_id: str, now: str, text: str | None = None) -> None:
    """The player changes (text) or removes (None) what their character knows; the change is logged."""
    row = optional(connection, "SELECT * FROM ledger_entries WHERE id=? AND removed=0 AND truth != 'world'",
                   (entry_id,))
    require(row is not None, 'That fact is not in your journal.', 404)
    if text is None:
        connection.execute('UPDATE ledger_entries SET removed=1 WHERE id=?', (entry_id,))
    else:
        require(bool(text.strip()), 'Write the fact, or remove it.', 422)
        connection.execute("UPDATE ledger_entries SET text=?, source='player' WHERE id=?", (text.strip()[:500], entry_id))
    connection.execute('INSERT INTO ledger_corrections (id, entry_id, before, after, created_at) VALUES (?, ?, ?, ?, ?)',
                       (identifier(), entry_id, row['text'], text, now))


def prompt_text(connection) -> str:
    """The ledger for the narrator: what is true, including what the player's character does not know."""
    rows = many(connection, 'SELECT kind, subject, text, truth FROM ledger_entries WHERE removed=0 '
                            "ORDER BY kind IN ('death', 'promise') DESC, created_at DESC, rowid DESC LIMIT ?",
                (IN_PROMPT,))
    if not rows:
        return ''
    lines = [f"- {row['kind']}, {row['subject']}: {row['text']}"
             + {'world': " (hidden: the player's character does not know)",
                'belief': " (the player's character believes this; it may be wrong)", 'both': ''}[row['truth']]
             for row in rows]
    return '## The record (kept by the game; never contradict it)\n' + '\n'.join(lines)


def checked(answer: str) -> list[dict] | None:
    """The model's facts, keeping only well-formed ones; None when nothing in the answer can be read."""
    match = re.search(r'\{.*\}', answer, re.S)
    try:
        data = json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        return None
    items = data.get('facts') if isinstance(data, dict) else None
    if not isinstance(items, list):
        return None
    return [{'kind': item['kind'], 'subject': str(item['subject']), 'text': str(item['text']),
             'truth': item.get('truth') if item.get('truth') in TRUTHS else 'both'}
            for item in items[:MOST_FACTS]
            if isinstance(item, dict) and item.get('kind') in KINDS and str(item.get('subject') or '').strip()
            and str(item.get('text') or '').strip()]


async def ask(state, config: dict, system: str, text: str) -> str:
    async with state.scheduler.reserve(config, CONVERSATION):
        return ''.join([chunk.text async for chunk in state.provider.stream(
            config, key_for(state.vault, config), system, [{'role': 'user', 'content': text}])])


async def extract(state, user_text: str, reply: dict):
    """The new facts of a turn, from the Continuity model only when the player chose one for it."""
    database = state.database
    with database.connect() as connection:
        config = config_for(connection, JOB) if routes(connection).get(JOB) else None
    if config is None:
        return
    try:
        facts = checked(await ask(state, config, EXTRACT, f"The player: {user_text}\n\nThe narrator: {reply['text']}"))
    except Exception:  # noqa: BLE001 - a fact missed is better than a turn lost.
        return
    with database.connect(write=True) as connection:
        for fact in facts or []:
            record(connection, fact['kind'], fact['subject'], fact['text'], database.now(), 'narrator', fact['truth'],
                   reply['id'])


# The story so far --------------------------------------------------------------------------------

def summary(connection) -> dict:
    row = optional(connection, 'SELECT text, through_seq FROM story_summary WHERE id=1')
    return row or {'text': '', 'through_seq': 0}


def summary_text(connection) -> str:
    text = summary(connection)['text']
    return f'## The story so far (older turns, summarized)\n{text}' if text else ''


def to_fold(rows: list[dict], through_seq: int) -> list[dict]:
    """The oldest messages past the summary, once RECENT + FOLD of them wait; else nothing."""
    waiting = [row for row in rows if row['seq'] > through_seq]
    return waiting[:FOLD] if len(waiting) >= RECENT + FOLD else []


def transcript(rows: list[dict]) -> str:
    names = {'user': 'The player', 'narrator': 'The narrator', 'scene': 'Scene'}
    return '\n\n'.join(f"{names[row['role']]}: {row['text']}" for row in rows
                       if row['role'] != 'narrator' or row['status'] == 'complete')


async def fold(state, rows: list[dict]):
    """Fold the oldest waiting messages into the summary, when enough have piled up."""
    database = state.database
    with database.connect() as connection:
        before = summary(connection)
        config = config_for(connection, JOB)
    chunk = to_fold(rows, before['through_seq'])
    if not chunk or config is None:
        return
    try:
        text = (await ask(state, config, SUMMARIZE, f"The summary so far:\n{before['text'] or '(none yet)'}\n\n"
                                                    f'The new turns:\n{transcript(chunk)}')).strip()
    except Exception:  # noqa: BLE001 - the turns stay word for word until the next try.
        return
    if text:
        with database.connect(write=True) as connection:
            connection.execute('INSERT INTO story_summary (id, text, through_seq, updated_at) VALUES (1, ?, ?, ?) '
                               'ON CONFLICT(id) DO UPDATE SET text=excluded.text, through_seq=excluded.through_seq, '
                               'updated_at=excluded.updated_at', (text, chunk[-1]['seq'], database.now()))
