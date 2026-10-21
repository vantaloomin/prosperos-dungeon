"""Moods (Feature Hit List #14, wave E, widened to every companion): how each companion feels right now in their own
chat with the user.

Every companion has at most one current mood (`moods`): a feeling (calm, happy, excited, annoyed, hurt, angry,
anxious, sad), an intensity from 1 to 3 and, for some, who it is about. All by rules, never a model:

- Their own day sets it when nothing else has (`day_moods`): a bad storyline beat, a mood mark from the consequence
  engine, their day going off plan. Everyday moods stay mild. A storyline beat of their own that turned out badly
  today leaves them sad, and a good one happy, when nothing else is going on.
- The user's words move it a step (`from_user`): care lifts a low mood, words that sting leave them a little hurt
  (angry only with a temper). Their own chat gets it as a per-reply note (`chat_lines`) that colors their tone.
- It fades a step every `FADE` and resets overnight, their time.
- Only someone with a temper gets angry: a temper the user wrote into their character ("hot-tempered", "quick to
  anger"), or the temper flaw a townsperson came with. Anyone else tops out at annoyed or hurt.

Moods are a hidden value: the people panel and Today show them only with the workspace's `show_moods` on.
"""
import re
from datetime import timedelta

from dungeon import consequences
from dungeon.characters import by_id
from dungeon.clock import parse, stamp, zone
from dungeon.database import decode, many, optional
from dungeon.life import pets, storylines
from dungeon.world import perception

FADE = timedelta(hours=3)
NUDGE_LIMIT = 2
NEGATION = re.compile(r"\b(?:not|never|isn't|aren't|wasn't|don't|didn't|no)\b", re.IGNORECASE)
JOKING = re.compile(r'\b(?:lol|lmao|jk|haha\w*|kidding)\b|["“”]', re.IGNORECASE)
SENTENCE = re.compile(r'(?<=[.!?])\s+|\n+')
TEMPER = re.compile(r"\b(?:hot[- ]?tempered|short[- ]tempered|quick[- ]tempered|bad[- ]tempered|(?:a|her|his|their|"
                    r"short|quick|bad|fiery|explosive) temper|hot[- ]?headed|quick to anger|easily angered|"
                    r"flies off the handle|volatile)\b", re.IGNORECASE)
SHEET_FIELDS = ('identity', 'personality', 'voice', 'background', 'flaws')
ADVERB = {1: 'a bit ', 2: '', 3: 'really '}
PREPOSITION = {'annoyed': 'with', 'hurt': 'by', 'angry': 'at', 'happy': 'with', 'excited': 'about',
               'anxious': 'about', 'sad': 'about'}


# Who has a temper ----------------------------------------------------------------------------------------

def temper(connection, key: str) -> int:
    """How strong a member's temper is: 0 without one. The user's words on the character, or the temper flaw a
    companion made from a townsperson came with."""
    companion_id = key.removeprefix('companion:') if key.startswith('companion:') else None
    companion = by_id(connection, companion_id) if companion_id else None
    if companion is None:
        return 0
    definition = companion['version']['definition']
    text = ' '.join(' '.join(value) if isinstance(value, list) else str(value or '')
                    for value in (definition.get(field) for field in SHEET_FIELDS))
    found = sum(1 for match in TEMPER.finditer(text) if not NEGATION.search(text[max(0, match.start() - 12):match.start()]))
    if companion.get('townsfolk_key') and perception.for_companion(companion['id'], definition)['picks'].get(
            'flaw') == 'temper':
        found += 1
    return found


def capped(feeling: str, intensity: int, has_temper: bool) -> tuple[str, int]:
    """Anger needs a temper; without one it is hurt, at most 2."""
    if feeling == 'angry' and not has_temper:
        return 'hurt', min(intensity, 2)
    return feeling, max(1, min(intensity, 3))


# Reading and writing ----------------------------------------------------------------------------------------

def local_day(connection, key: str, instant) -> str:
    companion = by_id(connection, key.removeprefix('companion:')) if key.startswith('companion:') else None
    timezone = zone(companion['version']['timezone']) if companion else zone('UTC')
    return instant.astimezone(timezone).date().isoformat()


def stored(connection, key: str, now) -> dict | None:
    """The mood as it stands now: faded a step per FADE since it last changed, gone overnight."""
    row = optional(connection, 'SELECT * FROM moods WHERE holder=?', (key,))
    if row is None or row['day'] != local_day(connection, key, now):
        return None
    if row['feeling'] == 'calm':
        return row  # Cheered up: it lasts the day.
    intensity = row['intensity'] - int((now - parse(row['updated_at'])) / FADE)
    return {**row, 'intensity': intensity} if intensity > 0 else None


SHIFT_FEELINGS = {'cancelled': 'sad', 'over': 'annoyed', 'late': 'annoyed', 'came_up': 'anxious', 'drop_by': 'happy'}


def day_moods(connection, companion: dict, now) -> list[dict]:
    """How their own day leaves them, mildest last: a storyline beat today (a bad one leaves them sullen, a good
    one brighter), how an outcome left them (the consequence engine's mood marks, not the ones about the user),
    then their day going off plan."""
    key, today = f"companion:{companion['id']}", storylines.local_today(companion, now)
    found = []
    for item in storylines.visible(connection, companion, now):
        beat = next((beat for beat in reversed(item['beats']) if beat['on'] == today.isoformat()), None)
        if beat and beat['tone'] in ('good', 'bad') and item['story'] not in ('secret_couple', 'family_secret'):
            found.append((('sad', 2) if beat['tone'] == 'bad' else ('happy', 1), beat['text'].rstrip('.')))
    for row in consequences.active(connection, companion['active_timeline_id'], today.isoformat(), 'mood', key):
        if not row['told']:
            found.append((('sad', 1) if row['amount'] < 0 else ('happy', 1), row['note'].rstrip('.')))
    for pet, died in pets.losses(connection, companion['active_timeline_id'], today):
        # Losing a pet weighs most that day and lingers a few days after.
        found.append((('sad', 2 if died == today else 1), f"{first_of(companion)}'s {pets.label(pet['kind'])} "
                      f"{pet['name']} died"))
    from dungeon.life import loss
    found += loss.moods(connection, companion, now)  # Grief: sad while it is raw or heavy.
    for row in many(connection, "SELECT block FROM life_agenda WHERE timeline_id=? AND subject='companion' "
                    "AND local_date=? AND status='happened' ORDER BY starts_at DESC", (companion['active_timeline_id'],
                                                                                        today.isoformat())):
        shift = decode(row['block']).get('shift') or {}
        if shift.get('key') in SHIFT_FEELINGS and shift.get('text'):
            text = shift['text'].format(friend=(shift.get('friend') or {}).get('name', 'a friend'))
            found.append(((SHIFT_FEELINGS[shift['key']], 1), f'{first_of(companion)} {text}'))
    return [{'holder': key, 'feeling': feeling, 'intensity': intensity, 'target': None, 'reason': reason,
             'furious_replies': 0} for (feeling, intensity), reason in found]


def first_of(companion: dict) -> str:
    name = companion['version']['name']
    return name.split()[0] if name.split() else name


def from_today(connection, key: str, now) -> dict | None:
    """With nothing else going on: how their own day leaves them (`day_moods`), the strongest first."""
    companion = by_id(connection, key.removeprefix('companion:')) if key.startswith('companion:') else None
    if companion is None:
        return None
    found = day_moods(connection, companion, now)
    return max(found, key=lambda mood: mood['intensity']) if found else None


def current(connection, key: str, now) -> dict | None:
    """Someone's mood right now, or None for calm."""
    return stored(connection, key, now) or from_today(connection, key, now)


def save(connection, key: str, feeling: str, intensity: int, target: str | None, reason: str, now):
    feeling, intensity = capped(feeling, intensity, temper(connection, key) > 0)
    connection.execute(
        'INSERT INTO moods (holder, feeling, intensity, target, reason, day, furious_replies, updated_at) '
        'VALUES (?, ?, ?, ?, ?, ?, 0, ?) ON CONFLICT(holder) DO UPDATE SET feeling=excluded.feeling, '
        'intensity=excluded.intensity, target=excluded.target, reason=excluded.reason, day=excluded.day, '
        'furious_replies=0, updated_at=excluded.updated_at',
        (key, feeling, intensity, target, reason[:300], local_day(connection, key, now), stamp(now)))


def furious(mood: dict | None) -> bool:
    return bool(mood) and mood['feeling'] == 'angry' and mood['intensity'] >= 3


# Events ---------------------------------------------------------------------------------------------------


# Showing it ----------------------------------------------------------------------------------------------

def text(mood: dict | None, labels: dict[str, str]) -> str:
    """"Seems angry at Sally", "Seems a bit sad"; "Seems calm" without a mood."""
    if not mood or mood['feeling'] == 'calm':
        return 'Seems calm'
    word = 'furious' if furious(mood) else f"{ADVERB[mood['intensity']]}{mood['feeling']}"
    target = labels.get(mood['target']) if mood['target'] else None
    return f"Seems {word}" + (f" {'at' if mood['feeling'] == 'angry' else PREPOSITION[mood['feeling']]} {target}"
                              if target else '')


def view(connection, key: str, labels: dict[str, str], now) -> dict:
    mood = current(connection, key, now)
    return {'feeling': mood['feeling'] if mood else 'calm', 'intensity': mood['intensity'] if mood else 0,
            'text': text(mood, labels), 'reason': mood['reason'] if mood else None}


# One-to-one chats ---------------------------------------------------------------------------------------

USER = 'user'
# Words in the user's message, checked by rules: care lifts a low mood a step; words that sting hurt a step.
KIND = re.compile(r"\b(?:sorry|that sucks|that'?s rough|that'?s awful|(?:big )?hugs?|proud of you|here for you|"
                  r"love you|miss(?:ed)? you|you'?ve got this|you got this|are you ok(?:ay)?|what'?s wrong|"
                  r"want to talk|how was your day|how are you(?: doing| feeling)?|thinking (?:of|about) you|"
                  r"cheer up|you deserve)\b", re.IGNORECASE)
HURTFUL = re.compile(r"\b(?:shut up|leave me alone|go away|whatever|(?:i )?(?:don'?t|do not) care|hate you|"
                     r"you(?:'?re| are)? (?:so |such an? |an? |really )?(?:stupid|dumb|pathetic|annoying|boring|useless|"
                     r"idiot|loser)|(?:stupid|dumb|useless|pathetic) (?:bot|robot|ai|machine|app))\b", re.IGNORECASE)
# Said to them, not about something else: "go away", "leave me alone" and "shut up" only as an order, with nothing but a
# word like "ugh" or "just" before it ("my kids wouldn't leave me alone", "we should go away for the weekend").
ORDERS = ('shut up', 'go away', 'leave me alone', 'whatever')
ORDER_LEAD = re.compile(r"^\W*(?:(?:oh|ugh|god|omg|seriously|honestly|just|please|pls|so|well|fine|ok|okay|no|now|and|"
                        r"then|can you|could you|would you|will you|i said|i told you to)\W+)*$", re.IGNORECASE)
NOT_AIMED = {
    'go away': re.compile(r"\s+(?:for (?:the|a|an|\d)|to\b|together|somewhere|on (?:a|the|holiday|vacation)|this|next|"
                          r"with\b)", re.IGNORECASE),
    'whatever': re.compile(r"\W*\w", re.IGNORECASE),  # "whatever you want": only "whatever." on its own stings.
    "don't care": re.compile(r"\s+(?:what|which|where|when|how|who|if|whether|as long|either|for|much)\b", re.IGNORECASE),
    'hate you': re.compile(r"\s+(?:have|had|got|guys|to|can'?t|couldn'?t|need|missing|being|'re|are|were)\b", re.IGNORECASE),
}
# Excited, not hurtful: "shut up, you got the job?!"
SURPRISED = re.compile(r"\?|\bno way\b|\bcongrat|\bamazing\b|\bomg\b", re.IGNORECASE)


def aimed(sentence: str, found: re.Match, text: str) -> bool:
    """Whether words that can sting are aimed at them in this sentence of the message `text`."""
    words = found.group(0).casefold().replace('do not', "don't").replace('dont', "don't")
    key = next((key for key in (*ORDERS, "don't care", 'hate you') if key in words), '')
    if key in ORDERS and not ORDER_LEAD.search(sentence[:found.start()]):
        return False
    if key == 'shut up' and SURPRISED.search(text):
        return False
    after = NOT_AIMED.get(key)
    return not (after and after.match(sentence, found.end()))


def hurtful(text: str, pattern: re.Pattern = HURTFUL, negation: re.Pattern | None = None,
            skip: re.Pattern | None = None) -> str | None:
    """The sentence of the message whose words sting, aimed at them, if any; negations (and sentences `skip` finds,
    such as jokes) don't count."""
    for sentence in SENTENCE.split(text or ''):
        if skip and skip.search(sentence):
            continue
        for found in pattern.finditer(sentence):
            before = sentence[:found.start()]
            negated = negation.search(before.casefold()) if negation else NEGATION.search(before[-20:])
            if not negated and aimed(sentence, found, text):
                return sentence.strip()
    return None


LOW = ('sad', 'hurt', 'annoyed', 'angry', 'anxious')
# Without a temper, what the user says hurts at most this much: a bit cooler, never sulking or ignoring.
USER_LIMIT = 1
STYLE = {
    'sad': ('a little low today', "subdued and a bit sullen: shorter, quieter replies, less joking, though you "
            'still answer and still care'),
    'annoyed': ('a bit irritable', 'short-tempered: keep replies short'),
    'anxious': ('a bit on edge', 'distracted and on edge'),
    'hurt': ('a little hurt', 'hurt: cooler and more guarded'),
    'angry': ('irritated', 'angry: curt'),
    'happy': ('in a good mood', 'in a great mood: warmer and more playful'),
    'excited': ('excited', 'excited and eager to share'),
}


def from_user(connection, key: str, text: str, now) -> bool:
    """The user's message nudges the companion's mood, by rules: words that sting hurt (anger needs a temper),
    care lifts a low mood a step back toward calm. At most one step a message; jokes and negations don't count.
    Returns whether it moved."""
    if not text or JOKING.search(text):
        return False
    if hurtful(text):
        has_temper = temper(connection, key) > 0
        feeling, limit = ('angry', NUDGE_LIMIT) if has_temper else ('hurt', USER_LIMIT)
        mood = stored(connection, key, now)
        same = mood and mood['feeling'] == feeling and mood['target'] == USER
        if same and mood['intensity'] >= limit:
            return False
        save(connection, key, feeling, mood['intensity'] + 1 if same else 1, USER, 'something you said stung', now)
        return True
    if not KIND.search(text):
        return False
    mood = current(connection, key, now)
    if mood is None or mood['feeling'] not in LOW:
        return False
    if mood['intensity'] <= 1:
        save(connection, key, 'calm', 1, None, 'you cheered them up', now)
    else:
        save(connection, key, mood['feeling'], mood['intensity'] - 1, mood['target'], mood['reason'], now)
    return True


def chat_lines(connection, companion: dict, now) -> list[tuple[str, str]]:
    """A one-to-one reply's note on how they feel right now and how it colors their tone."""
    key = f"companion:{companion['id']}"
    mood = current(connection, key, now)
    if not mood or mood['feeling'] == 'calm':
        return []
    mild, strong = STYLE[mood['feeling']]
    feel = strong if mood['intensity'] >= 2 else mild
    if mood['target'] == USER:
        about = ' with the user'
    elif mood['target']:
        about = f" with {labels_name(connection, mood['target'])}"
    else:
        about = ''
    return [(f"mood:{mood['feeling']}:{mood['intensity']}:{mood['target']}",
             f"- You're {feel}{about} (why: {mood['reason']}). Let it show in how you write "
             '(shorter, blunter, messier, whatever fits you), not just in what you say. Never explain it unless asked.')]


def labels_name(connection, key: str) -> str:
    companion = by_id(connection, key.removeprefix('companion:')) if key.startswith('companion:') else None
    return first_of(companion) if companion else 'someone'


def forget(connection, key: str):
    """Start over or Delete: their mood goes, and nobody stays upset with them."""
    connection.execute('DELETE FROM moods WHERE holder=? OR target=?', (key, key))
