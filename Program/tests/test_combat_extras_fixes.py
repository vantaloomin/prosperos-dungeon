"""Fixes from the combat-extras playtest (2026-10-23): tossing the purse rolls nothing, "three more hours" passes
time, every rolled move in a fight gets a line, notables keep their posts all day, and a far shot is harder."""
import json
from datetime import datetime
from pathlib import Path

from test_combat import Dice, foe, roll

from dungeon import combat, referee, story_clock
from dungeon.world import townsfolk


def test_tossing_the_purse_rolls_nothing():
    actions = [{'action': 'toss purse to road bandit 2 to end the fight', 'roll': True, 'stat': 'Vitality'}]
    assert referee.armed('I toss him my purse.', actions, fight='the road bandits') == []


def test_more_hours_pass_the_clock():
    assert story_clock.waited('I work the saws for three more hours') == 180
    assert story_clock.waited('I keep at it for another hour') == 60
    assert story_clock.minutes_for('I rest for seven hours', False) == 420


def test_a_charge_attacks_and_any_rolled_move_gets_a_line(app):
    with app.state.database.connect(write=True) as connection:
        state = {'round': 0, 'wants': 'kill', 'foes': [foe(zone='far', resolve=100)]}
        _, lines, _ = combat.play_round(connection, state, [roll('I charge him', 'critical_failure')], [], Dice(1))
        assert lines[0] == "The player's character closes on the bandit, still too far off to strike this round."
        state = {'round': 0, 'wants': 'kill', 'foes': [foe(resolve=100)]}
        _, lines, _ = combat.play_round(connection, state, [roll('I kick over the table', 'failure', 'Luck')], [],
                                        Dice(1))
        assert lines[0] == "The player's character tries this (I kick over the table): it fails."


def test_a_notable_keeps_their_post_all_day():
    data = json.loads((Path(townsfolk.__file__).parent / 'data' / 'cities' / 'kingswood.json').read_text())
    aldous = next(sheet for sheet in townsfolk.at_place(data, 'reeves-hall', datetime(2026, 10, 5).date())
                  if sheet.get('notable') == 'aldous-marr')
    assert aldous['shifts']['window'] == [8 * 60, 18 * 60] and len(aldous['shifts']['days']) == 6
