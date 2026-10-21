"""Wanting children (Hit List #73, v0.15 Room to Grow): whether a companion wants children of their own.

Every companion wants children (yes), wants them someday, or not (no). Their own description says it first ("never
wanted kids", "always wanted a big family"); otherwise the consequence engine decides it once from their age, warmth
and description (choice family:wants), with the odds under Hidden values. A "someday" the dice picked turns into a yes
once a baby is born in their circle (dungeon/life/families.py). `wants` is the one place every feature reads it from:
their own babies with a partner (dungeon/life/own_family.py) and the kids they had before (dungeon/life/kids.py).
No model decides anything.
"""
import re

from dungeon import consequences
from dungeon.database import optional
from dungeon.life import steps

WANTS = ('yes', 'someday', 'no')
TOPIC = 'having children'

# What their own description says, read in this order: "never wanted kids" before "wanted kids", "kids someday"
# before "wants kids". Each list is a set of alternatives.
_KIDS = r'(?:kids|children|a child|a baby|babies|a family|a big family)'
_PARENT = r'(?:a )?(?:mom|mum|mother|dad|father|parent)'
_SELF = r'(?:her|him|them|my|your|one)sel(?:f|ves)'
_WANT = r'want(?:s|ed)?'
_NOT = r"(?:don'?t|doesn'?t|do not|does not|won'?t|didn'?t|did not|never)"
# "never wanted kids to see her cry" is not about wanting children.
_NOT_ABOUT = r'(?! (?:to|around|near|in|at)\b)'
_SAYS_NO = (
    rf"never (?:planned on|planned to have) {_KIDS}",
    rf"{_NOT} (?:ever |really )?{_WANT} (?:to (?:have|raise) )?{_KIDS}{_NOT_ABOUT}",
    rf"{_NOT} (?:ever |really )?{_WANT} to be {_PARENT}",
    r'child[- ]?free',
    rf"no (?:interest in|desire for|plans for|intention of|wish for|wish to have) (?:having |raising )?{_KIDS}",
    r'not (?:the|a) (?:parenting|parent|maternal|paternal|family|kids?|baby) (?:type|person)',
    r"(?:hates|can'?t stand) (?:kids|children)",
    r"(?:kids|children|motherhood|fatherhood|parenthood|parenting|a family) (?:are|is|were|was|aren'?t|isn'?t|weren'?t|"
    r"wasn'?t) (?:never |not )?(?:in the cards|for (?:me|him|her|them))",
    r'decided (?:against|not to have) (?:having )?(?:kids|children)',
    r"(?:would|'d) rather not have (?:kids|children)",
    rf"never (?:saw|sees|see|pictured|imagined) {_SELF} (?:as {_PARENT}|with (?:kids|children))",
    rf"can'?t (?:imagine|see) (?:{_SELF} )?(?:being {_PARENT}|as {_PARENT}|having (?:kids|children))",
)
_SAYS_SOMEDAY = (
    rf"{_KIDS} (?:someday|some day|one day|eventually|down the line|later on)(?! soon)",
    r'maybe (?:kids|children)',
    r'someday,? (?:kids|children|a family)',
    r'not ready for (?:kids|children|a family|a baby) yet',
    r'(?:kids|children)\W+maybe later',
)
_SAYS_YES = (
    rf"(?:always )?(?:{_WANT}|hop(?:es|ing)? to have|(?:would|'d) like to have) {_KIDS}{_NOT_ABOUT}",
    rf"(?:always )?{_WANT} to (?:have|start|raise) {_KIDS}",
    rf"(?:always )?{_WANT} to be {_PARENT}",
    rf"{_WANT} (?:a houseful|lots|a bunch|two|three|four|five|several) (?:of )?(?:kids|children)",
    rf"dreams? (?:of|about) (?:a family|having (?:kids|children)|being {_PARENT})",
    rf"(?:would|'d) love (?:kids|children|a family|to be {_PARENT})",
    rf"can'?t wait to (?:be {_PARENT}|have (?:kids|children|a family|a baby))",
    r'baby fever',
    r'longs? for (?:a family|children|kids)',
    r'family[- ](?:minded|oriented)',
    rf"(?:always )?(?:pictured|pictures|imagined|imagines|sees|saw) {_SELF} (?:with (?:kids|children)|as {_PARENT})",
)
SAYS = tuple((wants, re.compile(rf"\b(?:{'|'.join(found)})\b", re.IGNORECASE))
             for wants, found in (('no', _SAYS_NO), ('someday', _SAYS_SOMEDAY), ('yes', _SAYS_YES)))


def described(definition: dict) -> str | None:
    """'yes', 'someday' or 'no' when their own description says it, else None."""
    themes = ' '.join(definition.get('life_themes') or [])
    text = f"{consequences.sheet_text(definition)} {definition.get('history_together') or ''} {themes}"
    text = text.replace('’', "'").replace('‘', "'")  # "doesn’t" as typed on a phone.
    return next((wants for wants, pattern in SAYS if pattern.search(text)), None)


def persona(connection) -> dict:
    return optional(connection, 'SELECT gender, age, about, kind, lifespan FROM persona WHERE id=1') or {}


def age_of(connection, companion: dict, now) -> int:
    """Their life age (dungeon/world/lifespans.py), what the family odds read: their real age for a human."""
    from dungeon.life import ages
    day = steps.local_today(companion, now) if now else None
    return ages.companion_life_age(connection, companion['id'], companion['version']['definition'], day) or 0


def wants_facts(connection, companion: dict, now) -> dict:
    from dungeon.world import personality
    definition = companion['version']['definition']
    levels = personality.levels_of(definition.get('personality_sliders') or {})
    return {'age': age_of(connection, companion, now), 'warmth': levels.get('warmth', 1),
            'sheet': {group for group in consequences.WORDS if consequences.sheet_has(definition, group)}}


def rolled(connection, companion: dict, choice: str, subject: str, facts: dict, now) -> dict:
    """The engine's outcome for a choice decided once per companion: recorded with `now`, else worked out with the
    same seed and not kept (a read with no clock)."""
    if now is not None and companion.get('active_timeline_id'):
        return steps.decide(connection, companion, choice, subject, facts, TOPIC, now)
    found = consequences.recorded(connection, subject, choice)
    if found:
        return found
    options = consequences.odds(choice, facts, steps.names(companion, TOPIC))
    return {'id': None, 'picked': consequences.roll(f"{companion.get('active_timeline_id')}:{subject}:{choice}", options),
            'decided_on': None}


def nudged_by(connection, companion: dict, outcome: dict) -> str | None:
    """A baby born in their circle since it was decided turns a seeded "someday" into a yes: the baby's name."""
    if not outcome.get('decided_on') or not companion.get('active_timeline_id'):
        return None
    row = optional(connection, "SELECT name FROM circle_children WHERE timeline_id=? AND status='born' AND born_on>=? "
                   'ORDER BY born_on LIMIT 1', (companion['active_timeline_id'], outcome['decided_on']))
    return row['name'] if row else None


def wants(connection, companion: dict, now=None) -> str:
    """Whether this companion wants children: 'yes', 'someday' or 'no'."""
    said = described(companion['version']['definition'])
    if said:
        return said
    outcome = rolled(connection, companion, 'family:wants', f"family:wants:{companion['id']}",
                     wants_facts(connection, companion, now), now)
    found = WANTS[outcome['picked']]
    return 'yes' if found == 'someday' and nudged_by(connection, companion, outcome) else found
