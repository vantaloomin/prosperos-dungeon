"""The story clock (requirements "Time and travel": story time, with a per-world option).

Once a campaign starts, the story keeps its own time: each line the player sends moves it on by what they did (a
few minutes of talk, a walk across town, a night's sleep) and the scene, the townsfolk and deadlines follow it. A
story begun before the clock existed, or with no campaign start, lives on the app clock as Companion did.

The time is game state, branched with the story (dungeon/timeline.py SAVED).
"""
import re
from datetime import datetime, timedelta

from dungeon.database import optional

TURN_MINUTES = 10
TALK_MINUTES = 5
# Moving within a city, and to another one, until the travel map decides journeys.
ACROSS_TOWN_MINUTES = 20
ANOTHER_CITY_MINUTES = 6 * 60
WORDS = {'one': 1, 'an': 1, 'a': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'eight': 8, 'ten': 10,
         'twelve': 12, 'few': 3, 'couple of': 2}
# (pattern, minutes), first match wins.
SPANS = (
    (r'\b(sleep|go to bed|turn in|rest for the night|bed down|camp for the night)\b', 8 * 60),
    (r'\b(nap|doze|rest a while|take a rest)\b', 60),
    # A stretch of the day spent at something: "I spend the day felling trees and come back at dusk".
    (r'\b(spend|spends|spending|work|works|working|pass|passes|passing|take|takes|taking)\b.*'
     r'\b(the|all|a|an|the whole|a whole)[- ]day\b',
     10 * 60),
    (r'\b(spend|spends|spending|work|works|working|pass|passes|passing)\b.*\b(the|all) (morning|afternoon)\b',
     4 * 60),
    (r'\b(spend|spends|spending|work|works|working|pass|passes|passing)\b.*\b(the|all) evening\b',
     3 * 60),
    (r'\b(travel|ride|walk|head|hike|journey|march)\b.*\b(to|toward|towards|into|out of)\b', 30),
)


def now(connection, clock) -> datetime:
    row = optional(connection, 'SELECT at FROM story_clock WHERE id=1')
    return datetime.fromisoformat(row['at']) if row else clock.now()


def running(connection) -> bool:
    return optional(connection, 'SELECT at FROM story_clock WHERE id=1') is not None


def start(connection, at: datetime):
    connection.execute('INSERT INTO story_clock (id, at) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET at=excluded.at',
                       (at.isoformat(),))


def advance(connection, minutes: int):
    row = optional(connection, 'SELECT at FROM story_clock WHERE id=1')
    if row and minutes > 0:
        start(connection, datetime.fromisoformat(row['at']) + timedelta(minutes=minutes))


def waited(text: str) -> int | None:
    """'I wait two hours', 'wait 20 minutes' or 'I work the saws for three hours', in minutes."""
    numbers = '|'.join(sorted(WORDS, key=len, reverse=True))
    match = re.search(rf'\b(?:wait\w*\b.*?|for\s+)\b(\d+|{numbers})\s+(hour|minute)s?\b', text, re.I)
    if not match:
        return None
    amount = int(match.group(1)) if match.group(1).isdigit() else WORDS[match.group(1).lower()]
    return min(amount * (60 if match.group(2).lower() == 'hour' else 1), 24 * 60)


# "I wait until evening": the hour a time of day starts.
HOURS = {'dawn': 6, 'sunrise': 6, 'first light': 6, 'morning': 7, 'noon': 12, 'midday': 12, 'afternoon': 13,
         'evening': 17, 'dusk': 18, 'sunset': 18, 'nightfall': 20, 'dark': 20, 'night': 20, 'midnight': 0}


def until(text: str, local: datetime) -> int | None:
    """'I wait until evening', 'wait till dusk', 'wait until she opens for the evening': the minutes from the local
    time to the next such hour."""
    names = '|'.join(sorted(HOURS, key=len, reverse=True))
    match = re.search(rf'\b(?:wait\w*|sit\w*|stay\w*|linger\w*|loiter\w*)\b.*?\b(?:until|till|til)\b\s+'
                      rf'(?:[\w\']+\s+){{0,5}}?(?:the\s+)?({names})\b', text, re.I)
    if not match:
        return None
    target = local.replace(hour=HOURS[match.group(1).lower()], minute=0, second=0, microsecond=0)
    if target <= local:
        target += timedelta(days=1)
    return int((target - local).total_seconds() // 60)


def minutes_for(text: str, rolled: bool, local: datetime | None = None) -> int:
    """How long a line of the player's takes: talk is quick, a risky action takes a while, rest takes the night, and
    waiting until a time of day takes until then (from `local`, the city's time now)."""
    if (minutes := waited(text)) is not None:
        return minutes
    if local is not None and (minutes := until(text, local)) is not None:
        return minutes
    for pattern, minutes in SPANS:
        if re.search(pattern, text, re.I):
            return minutes
    return TURN_MINUTES if rolled else TALK_MINUTES
