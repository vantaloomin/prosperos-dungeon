"""Children of a companion and their own partner after a split, and the parents the world spares while their children
are small.

The app decides, the user overrides ("the world exists outside of User", Vanta 2026-10-08). Rules and seeds only, no
model:

- A companion and their own partner (dungeon/life/own_family.py) who split with a child: the ex stays in their
  circle as the child's other parent, and where the child lives is the engine's kids:custody, as for kids they had
  before (dungeon/life/kids.py).
- Loss (dungeon/life/loss.py): children are never the one who passes away; a parent with a baby under one, or one on
  the way, is spared until the baby turns one, and the other parent of a child the companion shares with them (an
  ex co-parent, the kids' other parent) until the child is 18 (Vanta 2026-10-19).
"""
from datetime import date, timedelta

from dungeon import consequences
from dungeon.database import decode, encode, many, optional
from dungeon.life import families

BABY_DAYS = 365
SHARED_UNTIL = 18  # The other parent of a child the companion shares is spared until the child is grown.
OWN_CHOICE = 'kids:custody'
OWN_PATTERNS = ('with_them', 'shared', 'weekends')


def first(name: str) -> str:
    return name.split()[0] if name.split() else name


def shares_child(connection, person_id: str, day: date) -> bool:
    """Whether a love-life partner has a child under 18 with the companion (own_family.py), born or on the way."""
    rows = [row for row in families.children_of(connection, person_id) if row.get('whose') == 'companion']
    return any(row['status'] == 'expected' or families.age_of(row, day) < 18 for row in rows)


def keep_coparent(connection, person_id: str, day: date) -> bool:
    """A partner the companion split up with who shares a child stays in their circle as the child's other parent.
    Returns whether they stay."""
    person = optional(connection, 'SELECT * FROM circle_people WHERE id=?', (person_id,))
    if person is None or not shares_child(connection, person_id, day):
        return False
    details = decode(person['details']) or {}
    connection.execute("UPDATE circle_people SET role='ex', status='active', details=?, revision=revision+1 WHERE id=?",
                       (encode({**details, 'co_parent': True}), person_id))
    return True


def own_outcome(connection, companion: dict, person: dict, now=None) -> dict:
    """The engine's kids:custody for a child the companion has with an ex of theirs."""
    from dungeon.life import kids
    subject_ = f"{OWN_CHOICE}:own:{person['id']}"
    away = int(not (decode(person['details']) or {}).get('local', True))
    if now is not None:
        return kids.decide_choice(connection, companion, OWN_CHOICE, subject_, {'away': away},
                                  {'other': first(person['name'])}, now)
    recorded = consequences.recorded(connection, subject_, OWN_CHOICE)
    if recorded:
        return recorded
    options = consequences.odds(OWN_CHOICE, {'away': away}, {'name': first(companion['version']['definition']['name']),
                                                             'other': first(person['name'])})
    return {'id': None, 'picked': consequences.roll(f"{companion['active_timeline_id']}:{subject_}", options)}


def own_line(connection, companion: dict, child: dict, now=None) -> tuple[str, str] | None:
    """'- Ivy lives with you and spends every other weekend with Sam.' for a child whose parents split up."""
    person = optional(connection, "SELECT * FROM circle_people WHERE id=? AND status='active' AND role='ex'",
                      (child['parent_id'],))
    if person is None or not (decode(person['details']) or {}).get('co_parent'):
        return None
    pattern = OWN_PATTERNS[own_outcome(connection, companion, person, now)['picked']]
    other, name = first(person['name']), first(child['name'])
    text = {'with_them': f'{name} lives with you and spends every other weekend with {other}.',
            'shared': f'{name} spends a week with you, then a week with {other}, turn and turn about.',
            'weekends': f'{name} lives with {other} and spends every other weekend with you.'}[pattern]
    return f"custody:{child['id']}:{pattern}", f'- Since you and {other} split up, {text}'


def own_advance(connection, companion: dict, now) -> None:
    """Once a day: where a child of a split-up companion and their ex lives is decided once."""
    from dungeon.life import own_family
    for child in own_family.own_children(connection, companion['active_timeline_id']):
        if child['status'] == 'born':
            own_line(connection, companion, child, now)


def copy(connection, parent_id: str, new_id: str, ids: dict) -> None:
    """A fork (dungeon/timelines.py) keeps where a companion's own child lives with an ex of theirs."""
    for row in many(connection, 'SELECT id, subject FROM consequences WHERE timeline_id=? AND choice=? AND subject '
                    'LIKE ?', (parent_id, OWN_CHOICE, f'{OWN_CHOICE}:own:%')):
        person_id = row['subject'].rsplit(':', 1)[-1]  # A companion's own child with an ex of theirs (own_line).
        if person_id in ids:
            consequences.copy(connection, row['id'], new_id, f'{OWN_CHOICE}:own:{ids[person_id]}')


# Loss ---------------------------------------------------------------------------------------------------------------

def spared(connection, person: dict, day: date) -> bool:
    """Never a parent while their baby is under one or on the way (circle_children under them), and never the other
    parent of a child under 18 the companion shares with them: the companion's own child with them (own_family.py) or
    the kids they had before (kids.py)."""
    young = (day - timedelta(days=BABY_DAYS)).isoformat()
    if optional(connection, "SELECT id FROM circle_children WHERE parent_id=? AND (status='expected' OR "
                "(status='born' AND born_on>?)) LIMIT 1", (person['id'], young)):
        return True
    shared = many(connection, "SELECT born_on FROM circle_children WHERE parent_id=? AND whose='companion' AND "
                  "status='born'", (person['id'],))
    shared += many(connection, "SELECT c.born_on FROM companion_kids k JOIN circle_children c ON "
                   "c.storyline_id='kids:' || k.timeline_id WHERE k.other_id=? AND c.status='born'", (person['id'],))
    return any(families.age_of(child, day) < SHARED_UNTIL for child in shared)
