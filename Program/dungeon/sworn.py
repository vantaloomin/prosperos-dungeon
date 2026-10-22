"""Ironsworn's tracks outside a fight (dungeon/rules/ironsworn.py; docs/story.md "Supply, spirit and vows").

- **Supply.** A day on the road spends a point of supply in place of a food from the pack (dungeon/travel.py), and
  a Life Card's food comes as supply. Resupply, read from the action's words, brings it back.
- **Spirit** follows the stress track (dungeon/stress.py): 5 while steady, down to 0 at the top.
- **Vows.** A quest or an oath done is a vow fulfilled (dungeon/quests.py): experience by its rank, spent by code.
"""
import math

from dungeon import sheet
from dungeon.rules import ironsworn


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


def fulfil(connection, quest: dict) -> str:
    """A vow kept: experience by its rank, spent on the character's assets."""
    found = played(connection)
    if found is None:
        return ''
    rank = 'dangerous' if quest.get('kind') == 'oath' else ironsworn.rank_of(quest.get('tier'))
    gained = ironsworn.vow_xp(rank)
    found['xp'] = found.get('xp', 0) + gained
    grown = ironsworn.spend(found)
    sheet.set_native(connection, found, '')
    return (f"The character fulfils a {rank} vow ({quest['title']}): {gained} experience"
            + (f"; {'; '.join(grown)}." if grown else f", {found['xp']} unspent."))
