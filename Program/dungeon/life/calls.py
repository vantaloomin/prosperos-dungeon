"""On a call (Hit List #59, v0.12 Where you are): talking on the phone, started by the user.

A call is the third state a companion can be in with the user, beside apart and together (dungeon/life/together.py).
Rules start and end it; the model never decides it.

The user calls them: the Call button in the chat header, or words like "can I call you?" and "call me?". They pick up
when they are free (not at work, out, or asleep); otherwise they don't, and the reply to those words says why, or for
the button, it is a missed call.

On a call the same chat is the call: replies are written as spoken words, texting habits stop (no held replies, bursts
or typos) and, when a voice is set up for voice notes (dungeon/voice/notes.py), each reply is also read aloud. It
ends with End call, a goodbye in the chat, ten quiet minutes, or on its own when they have to go (work, class,
bedtime: together.end_of_visit), when they say so first.
"""
import random
import re
from datetime import datetime, timedelta

from dungeon.clock import parse, stamp, zone
from dungeon.database import decode, encode, identifier, many, one, optional
from dungeon.errors import require
from dungeon.life import own_plans, pacing, together

ACTIVE = True
# How long a call rings, how long a quiet line stays open, and the shortest call worth picking up for.
RING = timedelta(minutes=5)
IDLE = timedelta(minutes=10)
SHORTEST = timedelta(minutes=10)
# How long a call lasts at most, rolled per call; it ends sooner at their next work, class or bedtime.
HOURS = (0.5, 1.25)
# When they start to wrap up before having to go, how long the strip shows a call that ended or went unanswered,
# and how long the chat context still mentions it.
WRAP_UP = timedelta(minutes=5)
SHOWN_FOR = timedelta(minutes=2)
TOLD_FOR = timedelta(hours=2)
CLOSE = 3

# Asking to talk on the phone now: "can I call you?", "call me?", "facetime?", "I'm calling you".
ASKS = re.compile(r"\b(?:call me(?:\s+(?:now|rn|right now|back|asap|please|pls|plz))*(?!\s+[a-z'])|"
                  r"(?:can|could|may|should) i (?:call|ring|phone|facetime)(?: you)?|(?:can|could|will) you "
                  r"(?:call|ring|phone|facetime) me|(?:wanna|want to|do you want to) (?:call|talk on the phone|"
                  r"facetime|video ?chat|hop on a call)|(?:can|could|should|shall) we (?:call|talk on the phone|"
                  r"facetime|video ?chat|hop on a call)|(?:i'?ll|i will|gonna|going to|about to) (?:call|ring|facetime) "
                  r"you|free (?:for|to) (?:a )?(?:call|phone call|talk on the phone|facetime)|give (?:me|you) a "
                  r"(?:call|ring|bell)|ring me|phone me|facetime(?: me)?|video ?call|(?:i'?m|i am|im) calling you|"
                  r"calling you now|let'?s (?:call|talk on the phone|facetime|hop on a call))\b", re.IGNORECASE)
# "Call me" before a name or a word is not a call ("you can call me Sam", "call me crazy"); a bare "call?" is.
BARE = re.compile(r'^\s*(?:call|phone|facetime|ring)\s*\?+\s*$', re.IGNORECASE)
# A call for another time is talk, not a call now: "call me tonight after work".
LATER = re.compile(r"\b(?:later|tonight|tomorrow|after (?:work|class|dinner|school)|this (?:evening|weekend)|"
                   r"in (?:a bit|an hour|a few)|when (?:you'?re|you are|i'?m|i am) (?:free|off|home|done|back)|"
                   r"(?:mon|tues|wednes|thurs|fri|satur|sun)day)\b", re.IGNORECASE)
RIGHT_NOW = re.compile(r'\b(?:right now|now|rn)\b', re.IGNORECASE)
# Saying goodbye on the phone ends the call.
# "I have to go" ends it; "we need to go to that place sometime" and "I gotta run to the store later" don't.
HANG_UP = re.compile(r"\b(?:(?:i'?ve |i have |i )?(?:gotta|got to|have to|need to|should) (?:go|run|hang up|get going)"
                     r"(?=\s*(?:$|[.!?,;:)]|now\b|soon\b|sorry\b|though\b|tho\b|anyway\b|bye\b|babe\b|love\b|x+\b|"
                     r"to (?:bed|sleep|work)\b))|"
                     r"talk (?:to you )?(?:later|soon|tomorrow)|bye+|goodbye|good ?night|night night|hanging up|"
                     r"(?:i'?ll|i will) let you go|ttyl)\b", re.IGNORECASE)

ON_CALL = ('This is a voice call, not texting: write only the words you say out loud, the way people talk on the phone, '
           'in short turns. No emoji, no *actions*, no typos. You can hear each other but not see each other.')
WHY = ('you just finished your day and wanted to talk it through', 'you wanted to hear their voice',
       'you were bored and thought of them', 'you had a quiet moment and missed talking to them properly')


# --- Reading the chat -------------------------------------------------------------------------------------------

def asked(text: str) -> bool:
    """Whether a user message asks to talk on the phone now."""
    text = own_plans.QUOTED.sub(' ', own_plans.ACTIONS.sub(' ', text)).replace('’', "'")
    for sentence in re.split(r'(?<=[.!?])\s+|\n+', text):
        if own_plans.PAST.search(sentence) or own_plans.NEGATED.search(sentence) or not (
                ASKS.search(sentence) or BARE.match(sentence)):
            continue
        if LATER.search(sentence) and not RIGHT_NOW.search(sentence):
            continue
        return True
    return False


def hanging_up(text: str) -> bool:
    return bool(HANG_UP.search(text.replace('’', "'")))


# --- The call's state ---------------------------------------------------------------------------------------------

def get(connection, call_id: str) -> dict | None:
    row = optional(connection, 'SELECT * FROM calls WHERE id=?', (call_id,))
    return {**row, 'reason': decode(row['reason'])} if row else None


def latest(connection, timeline_id: str, now: datetime) -> dict | None:
    """The newest call on a chat as of now (a clock moved back hides calls that have not happened yet)."""
    row = optional(connection, 'SELECT * FROM calls WHERE timeline_id=? AND created_at<=? '
                   'ORDER BY created_at DESC, rowid DESC LIMIT 1', (timeline_id, stamp(now)))
    return {**row, 'reason': decode(row['reason'])} if row else None


def last_said(connection, call: dict) -> datetime:
    """The last thing said on the line: the latest message since it was picked up, or the pick-up itself."""
    row = one(connection, 'SELECT MAX(created_at) AS at FROM messages WHERE timeline_id=? AND created_at>=?',
              (call['timeline_id'], call['started_at']))
    return max(parse(call['started_at']), parse(row['at'])) if row['at'] else parse(call['started_at'])


def effective(connection, call: dict | None, now: datetime) -> dict | None:
    """The call as it stands now: a ring nobody answered is missed, and a call ends on its own at its time or after
    IDLE minutes of quiet. Worked out when read, so nothing has to run for a call to end."""
    if call is None:
        return None
    if call['status'] == 'ringing':
        if now - parse(call['created_at']) >= RING:
            return {**call, 'status': 'missed', 'ended_at': stamp(parse(call['created_at']) + RING)}
        return call
    if call['status'] == 'on':
        end = min(parse(call['until_at']), last_said(connection, call) + IDLE)
        if now >= end:
            return {**call, 'status': 'ended', 'ended_at': stamp(end)}
    return call


def as_saved(connection, companion: dict, now: datetime) -> dict | None:
    return effective(connection, latest(connection, companion['active_timeline_id'], now), now)


def now_for(connection, companion: dict, now: datetime) -> dict | None:
    """The newest call on their chat, as it stands now. Once they are together in person (a visit or an outing that
    began during the call) the call is over: nobody stays on the phone with the person beside them."""
    found = as_saved(connection, companion, now)
    if found and found['status'] == 'on' and together.in_person(connection, companion, now):
        return {**found, 'status': 'ended', 'ended_at': stamp(now)}
    return found


def hang_up_others(connection, companion: dict, now: datetime):
    """Calling someone ends a call under way with anyone else, as on a phone."""
    for row in many(connection, "SELECT c.* FROM calls c JOIN companions p ON p.active_timeline_id=c.timeline_id "
                    "WHERE c.status='on' AND c.companion_id<>?", (companion['id'],)):
        if effective(connection, {**row, 'reason': decode(row['reason'])}, now)['status'] == 'on':
            end(connection, row, now)


def on_call(connection, companion: dict, now: datetime) -> dict | None:
    found = now_for(connection, companion, now)
    return found if found and found['status'] == 'on' else None


def ringing(connection, companion: dict, now: datetime) -> dict | None:
    found = now_for(connection, companion, now)
    return found if found and found['status'] == 'ringing' else None


def speaking(connection, companion: dict, now: datetime, message_id: str | None) -> bool:
    """Whether a reply to this message is said on the phone: the call is on, or this message just said goodbye."""
    found = now_for(connection, companion, now)
    return bool(found and (found['status'] == 'on' or (message_id and found['ended_by'] == message_id)))


# --- When they can pick up -----------------------------------------------------------------------------------------

def why_not(connection, companion: dict, now: datetime) -> dict | None:
    """Why they can't talk on the phone right now ({why, ...}), or None when they can. Far away is no reason, and a
    trip is none either: a call is how people keep up from anywhere."""
    found = pacing.block_now(connection, companion, now)
    block = found[0] if found else None
    kind = together.busy_kind(block)
    if kind and kind != 'away':
        until = parse(found[1]).astimezone(zone(companion['version']['timezone'])).strftime('%H:%M')
        return {'why': kind, 'label': (block.get('label') or block['kind']).lower(), 'until': until}
    if until_at(companion, now, 1.0) - now < SHORTEST:
        return {'why': 'late'}
    return None


def until_at(companion: dict, now: datetime, hours: float) -> datetime:
    """When a call picked up now ends on its own (together.end_of_visit: their next work, class or bedtime)."""
    local = now.astimezone(zone(companion['version']['timezone']))
    end = together.end_of_visit(companion['version']['definition'], local, hours)
    found = datetime.combine(local.date(), datetime.strptime(end, '%H:%M').time(), local.tzinfo)
    return max(found, local)


def length(call_id: str) -> float:
    return random.Random(f'call:{call_id}').uniform(*HOURS)


# --- Starting and ending ---------------------------------------------------------------------------------------

def insert(connection, companion: dict, direction: str, status: str, now: datetime, message_id: str | None = None,
           reason: dict | None = None, trigger_key: str | None = None) -> dict:
    call_id = identifier()
    started = stamp(now) if status == 'on' else None
    until = stamp(until_at(companion, now, length(call_id))) if status == 'on' else None
    connection.execute('INSERT INTO calls (id, companion_id, timeline_id, direction, status, message_id, trigger_key, '
                       'reason, started_at, until_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                       (call_id, companion['id'], companion['active_timeline_id'], direction, status, message_id,
                        trigger_key, encode(reason or {}), started, until, stamp(now)))
    return get(connection, call_id)


def blocked(connection, companion: dict, now: datetime) -> str | None:
    """Why no call can start at all: they are together already, or a call is on or ringing."""
    if not ACTIVE:
        return 'off'
    if together.in_person(connection, companion, now):
        return 'together'
    found = now_for(connection, companion, now)
    return found['status'] if found and found['status'] in ('on', 'ringing') else None


def call(connection, companion: dict, now: datetime) -> dict:
    """The user calls them (the Call button): they pick up when free, else it is a missed call."""
    require(blocked(connection, companion, now) is None, 'You are already together or on a call.', 409)
    hang_up_others(connection, companion, now)
    reason = why_not(connection, companion, now)
    if reason:
        return insert(connection, companion, 'you', 'missed', now, reason=reason)
    return insert(connection, companion, 'you', 'on', now)


def answer(connection, found: dict, now: datetime) -> dict:
    from dungeon.characters import by_id
    companion = by_id(connection, found['companion_id'])
    connection.execute("UPDATE calls SET status='on', started_at=?, until_at=? WHERE id=?",
                       (stamp(now), stamp(until_at(companion, now, length(found['id']))), found['id']))
    return get(connection, found['id'])


def end(connection, found: dict, now: datetime, message_id: str | None = None):
    connection.execute("UPDATE calls SET status='ended', ended_at=?, ended_by=? WHERE id=?",
                       (stamp(now), message_id, found['id']))


def act(connection, companion: dict, call_id: str, action: str, now: datetime) -> dict:
    """Answer or Decline a ring, or End call (the strip's buttons)."""
    found = effective(connection, get(connection, call_id), now)
    require(found is not None and found['timeline_id'] == companion['active_timeline_id'], 'That call was not found.',
            404)
    if action == 'end':
        require(found['status'] == 'on', 'That call has already ended.', 409)
        end(connection, found, now)
    else:
        require(found['status'] == 'ringing', 'That call is no longer ringing.', 409)
        if action == 'answer':
            answer(connection, found, now)
        else:
            connection.execute("UPDATE calls SET status='declined', ended_at=? WHERE id=?", (stamp(now), found['id']))
    return together.view(connection, companion, now)


def note(connection, message: dict, companion: dict, timestamp: str) -> bool:
    """A user message on the phone or about it, settled before the reply is written: writing while it rings answers,
    a goodbye on the line hangs up, and asking to call starts one when they can pick up (else the reply says why)."""
    if not ACTIVE or message['role'] != 'user' or message['status'] != 'complete':
        return False
    now = parse(message['created_at'])
    found = as_saved(connection, companion, now)
    if found and found['status'] == 'on' and together.in_person(connection, companion, now):
        end(connection, found, now)  # They came over (or met up) during the call: the call is over.
        return False
    if found and found['status'] == 'ringing':
        answer(connection, found, now)
        return True
    if found and found['status'] == 'on':
        if hanging_up(message['text']):
            end(connection, found, now, message['id'])
        return True
    if not asked(message['text']) or blocked(connection, companion, now):
        return False
    if optional(connection, 'SELECT id FROM together_asks WHERE message_id=?', (message['id'],)) or \
            optional(connection, 'SELECT id FROM calls WHERE message_id=?', (message['id'],)):
        return True
    reason = why_not(connection, companion, now)
    if reason:
        return together.record(connection, companion, message, 'call', reason, timestamp)
    hang_up_others(connection, companion, now)
    insert(connection, companion, 'you', 'on', now, message['id'])
    return True


# --- What the chat context says ---------------------------------------------------------------------------------

def context_lines(connection, companion: dict, now: datetime, fresh_ids: set[str]) -> list[tuple[str, str]]:
    """(identity, line) for the 'where' section: the call under way and how it started, a goodbye on the line, a
    call that ended a little while ago, and a call one of you missed."""
    found = now_for(connection, companion, now)
    if found is None or together.in_person(connection, companion, now):
        return []  # In person, the together lines say where they are; a call that ended for it goes unsaid.
    timezone = companion['version']['timezone']
    if found['status'] == 'on' or (found['status'] == 'ended' and found['ended_by'] in fresh_ids):
        return on_lines(connection, companion, found, now, fresh_ids)
    ended = parse(found['ended_at']) if found['ended_at'] else parse(found['created_at'])
    if not timedelta(0) <= now - ended < TOLD_FOR:
        return []
    at = parse(found['created_at']).astimezone(zone(timezone)).strftime('%H:%M')
    if found['status'] == 'ended':
        minutes = max(1, round((ended - parse(found['started_at'])).total_seconds() / 60))
        return [(f"call-ended:{found['id']}", f'- You and the user talked on the phone for about {minutes} minute{"s" if minutes != 1 else ""} '
                 'and hung up a little while ago. You are texting again.')]
    if found['direction'] == 'you':
        why = together.reason_text(found['reason']) if found['reason'] else 'you were busy'
        return [(f"call-missed:{found['id']}", f"- The user tried to call you at {at} and you didn't pick up: {why}. "
                 'You are texting.')]
    answered = 'declined' if found['status'] == 'declined' else "didn't pick up"
    return [(f"call-missed:{found['id']}", f'- You tried to call the user at {at} and they {answered}. You are '
             'texting.')]


def on_lines(connection, companion: dict, found: dict, now: datetime, fresh_ids: set[str]) -> list[tuple[str, str]]:
    local = parse(found['created_at']).astimezone(zone(companion['version']['timezone']))
    who = 'You called the user' if found['direction'] == 'them' else 'The user called you'
    lines = [(f"call:{found['id']}", f'- You are on a phone call with the user right now. {who} at {local:%H:%M}. '
              f'{ON_CALL}')]
    if found['ended_by'] in fresh_ids:
        lines.append((f"call-goodbye:{found['id']}", '- The user is saying goodbye to end the call. Say goodbye back, '
                      'out loud; the call ends after this.'))
        return lines
    if found['message_id'] in fresh_ids:
        lines.append((f"call-picked-up:{found['id']}", '- The user asked to talk on the phone and you picked up: this '
                      'reply is the first thing you say on the call.'))
    elif found['direction'] == 'them' and not said_since(connection, found, 'companion'):
        why = found['reason'].get('why_called') or WHY[1]
        lines.append((f"call-answered:{found['id']}", f'- They just picked up. You called because {why}: tell them, '
                      'in your own words.'))
    if parse(found['until_at']) - now <= WRAP_UP:
        lines.append((f"call-wrap-up:{found['id']}", '- You have to go in a few minutes: start wrapping up the call, '
                      'kindly.'))
    return lines


def said_since(connection, found: dict, role: str) -> bool:
    return bool(optional(connection, "SELECT id FROM messages WHERE timeline_id=? AND role=? AND status='complete' "
                         'AND created_at>=? LIMIT 1', (found['timeline_id'], role, found['started_at'])))


# --- The state, in plain words ------------------------------------------------------------------------------------

def state(connection, companion: dict, now: datetime) -> dict | None:
    """{state, kind, text} while a call is on or ringing, else None (together.state reads this first)."""
    found = now_for(connection, companion, now)
    if found and found['status'] == 'on':
        return {'state': 'call', 'kind': 'call', 'text': 'On a call'}
    if found and found['status'] == 'ringing':
        return {'state': 'apart', 'kind': 'ringing', 'text': 'Calling you'}
    return None


def view(connection, companion: dict, now: datetime) -> dict | None:
    """The call the strip shows: one on or ringing, or one that ended or went unanswered a moment ago."""
    found = now_for(connection, companion, now)
    if found is None:
        return None
    done = found['status'] not in ('on', 'ringing')
    if done and together.in_person(connection, companion, now):
        return None  # The strip shows the time together instead.
    if done and now - parse(found['ended_at'] or found['created_at']) >= SHOWN_FOR:
        return None
    return {'id': found['id'], 'direction': found['direction'], 'status': found['status'],
            'started_at': found['started_at'], 'until_at': found['until_at'], 'ended_at': found['ended_at']}


# --- How close they are -----------------------------------------------------------------------------------------


def close(connection, companion: dict, now: datetime) -> bool:
    from dungeon.memory import closeness
    return closeness.state(connection, companion, now)['level'] >= CLOSE

