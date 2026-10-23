"""Ironsworn's tracks outside a fight (dungeon/rules/ironsworn.py; docs/story.md "Supply, spirit and vows").

- **Supply.** A day on the road spends a point of supply in place of a food from the pack (dungeon/travel.py), and
  a Life Card's food comes as supply. Resupply, read from the action's words, brings it back.
- **Spirit** follows the stress track (dungeon/stress.py): 5 while steady, down to 0 at the top.
- **Vows** are progress tracks. A line that pursues an open vow by name and lands a roll reaches a milestone, once a
  story day per vow: ticks by the vow's rank (dungeon/rules/ironsworn.py MILESTONE). A quest or an oath done is
  Fulfill Your Vow, the deed that ends it a last milestone: a progress roll of the filled boxes against two challenge
  dice. A strong hit gives experience by its rank, a weak hit one less, a miss none (the story already says it
  ended; the vow is not what was sworn). Experience is spent by code.
- **Bonds** is a progress track too: each bond forged (dungeon/bonds.py) marks a tick.
"""
import math

from dungeon import sheet
from dungeon.rules import ironsworn

LANDED = ('success_cost', 'success', 'critical_success')


def played(connection) -> dict | None:
    """The character's Ironsworn sheet, when the campaign plays Ironsworn."""
    return sheet.native(connection) if sheet.ruleset(connection) == ironsworn.ID else None


def spend_supply(connection, days: int) -> tuple[int, int] | None:
    """(spent, left) for `days` on the road; None when the campaign keeps food in the pack."""
    found = played(connection)
    if found is None:
        return None
    spent = max(0, min(days, found['supply']))
    found['supply'] -= spent
    sheet.set_native(connection, found, '')
    return spent, found['supply']


def restock(connection, amount: int) -> int | None:
    """Supply gained (up to 5), or None when the campaign keeps food in the pack."""
    found = played(connection)
    if found is None:
        return None
    before = found['supply']
    found['supply'] = min(5, before + amount)
    sheet.set_native(connection, found, '')
    return found['supply'] - before


def resupplied(connection, roll: dict) -> str:
    """What a Resupply roll brought back."""
    gained = restock(connection, ironsworn.RESUPPLY.get(roll['band'], 0)) if roll.get('move') == 'resupply' else None
    return f"Resupply: +{gained} supply, now {played(connection)['supply']} of 5." if gained else ''


def follow_stress(connection, points: int, top: int):
    found = played(connection)
    spirit = 5 - math.ceil(points * 5 / top)
    if found and found['spirit'] != spirit:
        found['spirit'] = spirit
        sheet.set_native(connection, found, '')


def rank(quest: dict) -> str:
    return 'dangerous' if quest.get('kind') == 'oath' else ironsworn.rank_of(quest.get('tier'))


def milestone(connection, quest: dict, day: str) -> str:
    """Reach a Milestone on a vow, once a story day: its progress ticks by its rank."""
    found = played(connection)
    if found is None:
        return ''
    vows = found.setdefault('vows', {})
    track = vows.setdefault(quest['id'], {'title': quest['title'], 'rank': rank(quest), 'ticks': 0, 'day': ''})
    if track['day'] == day:
        return ''
    track['ticks'], track['day'] = ironsworn.mark(track['ticks'], track['rank']), day
    sheet.set_native(connection, found, '')
    return (f"Reach a Milestone on the vow {quest['title']}: progress {track['ticks'] // ironsworn.TICKS_PER_BOX} of "
            f"{ironsworn.BOXES}.")


def fulfil(connection, quest: dict, rng=None) -> str:
    """Fulfill Your Vow: a progress roll on the vow's track; experience by its rank and the hit, spent on the
    character's assets."""
    found = played(connection)
    if found is None:
        return ''
    track = found.get('vows', {}).pop(quest['id'], None) or {'ticks': 0}
    ranked = rank(quest)
    # The deed that ends it is a milestone of its own.
    rolled = ironsworn.progress_roll(ironsworn.mark(track['ticks'], ranked), rng)
    weak, miss = rolled['band'] == 'success_cost', rolled['band'] in ('failure', 'critical_failure')
    gained = 0 if miss else ironsworn.vow_xp(ranked, weak)
    found['xp'] = found.get('xp', 0) + gained
    grown = ironsworn.spend(found)
    sheet.set_native(connection, found, '')
    hit = 'a miss: the vow is not what was sworn' if miss else 'a weak hit: more remains to be done' if weak \
        else 'a strong hit'
    first, second = rolled['challenge']
    return (f"Fulfill Your Vow, {ranked} ({quest['title']}), progress {rolled['score']} vs {first} and {second}, "
            f"{hit}: {gained} experience" + (f"; {'; '.join(grown)}." if grown else f", {found['xp']} unspent."))


def forge_bond(connection, name: str):
    """Forge a Bond marks a tick on the bonds track."""
    found = played(connection)
    if found is not None:
        found['bonds'] = min(ironsworn.BOXES * ironsworn.TICKS_PER_BOX, found.get('bonds', 0) + 1)
        sheet.set_native(connection, found, '')


def bonds_line(connection) -> str:
    found = played(connection)
    if not found or not found.get('bonds'):
        return ''
    plural = 's' if found['bonds'] != 1 else ''
    return f"Forge a Bond: the bonds track has {found['bonds']} tick{plural}."


def pursued(connection, text: str, rolls: list[dict], day: str) -> list[str]:
    """A line that pursues an open vow by name and lands a roll reaches a milestone on it."""
    from dungeon import quests
    if played(connection) is None or not any(roll.get('band') in LANDED for roll in rolls):
        return []
    quest = quests.named(connection, text)
    line = milestone(connection, quest, day) if quest else ''
    return [line] if line else []


def prompt_text(lines: list[str]) -> str:
    return '## Vows (decided by the game)\n' + '\n'.join(f'- {line}' for line in lines) if lines else ''
