"""Fate (dungeon/rules/fate.py): aspects, approaches, 4dF against the ladder, Fate points spent by code."""
import random

import pytest
from test_rulesets import start
from test_travel import ok

from dungeon import combat, growth, sheet, story
from dungeon.rules import fate

APPROACHES = {'Sneaky': 3, 'Clever': 2, 'Quick': 2, 'Careful': 1, 'Flashy': 1, 'Forceful': 0}


class Dice(random.Random):
    """Fate dice that come up as given, in order."""
    def __init__(self, faces):
        super().__init__(0)
        self.faces = list(faces)

    def choice(self, options):
        return self.faces.pop(0)


def made(client, **extra):
    body = {'high_concept': 'Dockside cutpurse with a conscience', 'trouble': 'Owes the Hollins gang',
            'aspects': ['Knows every alley in the river ward'], 'approaches': APPROACHES,
            'stunts': ['Because I grew up on the docks, I get +2 when I Sneakily slip through a crowd']} | extra
    return start(client, persona={'name': 'Wren'}, ruleset='fate', fate=body)


def test_a_made_fate_character_keeps_their_aspects_approaches_and_fate_points(client):
    ok(made(client))
    view = ok(client.get('/api/story/sheet'))
    assert (view['ruleset'], view['ruleset_name'], view['high_concept'], view['trouble']) == \
        ('fate', 'Fate', 'Dockside cutpurse with a conscience', 'Owes the Hollins gang')
    assert view['approaches'] == APPROACHES and (view['fate_points'], view['refresh']) == (3, 3)
    assert view['stress'] == [False, False, False] and 'Evil Hat' in view['attribution']
    choices = ok(client.get('/api/story/start'))
    assert choices['fate']['approaches'] == list(fate.APPROACHES) and choices['fate']['array'] == [3, 2, 2, 1, 1, 0]


def test_a_fate_character_needs_a_high_concept_and_the_array(client):
    assert made(client, high_concept='  ').status_code == 422
    assert made(client, approaches=APPROACHES | {'Forceful': 3}).status_code == 422
    assert start(client, persona={'name': 'Wren'}, ruleset='fate').status_code == 422


def test_a_premade_takes_their_description_as_high_concept(client):
    ok(start(client, premade_id='agna-holt', ruleset='fate'))
    view = ok(client.get('/api/story/sheet'))
    assert view['high_concept'] and sorted(view['approaches'].values(), reverse=True) == [3, 2, 2, 1, 1, 0]


@pytest.mark.parametrize(('shifts', 'band'), [(-1, 'failure'), (0, 'success_cost'), (2, 'success'),
                                              (3, 'critical_success')])
def test_shifts_land_on_the_shared_ladder(shifts, band):
    assert fate.outcome(shifts) == band


def sheet_of(**extra):
    return fate.build('Dockside cutpurse with a conscience', 'Owes the Hollins gang',
                      ['Knows every alley in the river ward'], APPROACHES,
                      ['Because I grew up on the docks, I get +2 when I Sneakily slip through a crowd']) | extra


def test_the_words_pick_the_approach_and_a_fitting_stunt_adds_two():
    found = fate.roll(sheet_of(), 'Mind', 'normal', 'I slip through the crowd at the market', Dice([0, 0, 0, 0]))
    # Sneaky +3, the docks stunt +2, against Fair (+2): succeeding by 3 is success with style.
    assert (found['ability'], found['bonus'], found['total'], found['target'], found['band']) == \
        ('Sneaky', 5, 5, 2, 'critical_success')
    assert 'stunt +2' in found['skill'] and found['fate_points'] == 3
    plain = fate.roll(sheet_of(), 'Vitality', 'hard', 'I put my shoulder to the gate', Dice([1, 0, 0, -1]))
    assert (plain['ability'], plain['total'], plain['band']) == ('Forceful', 0, 'failure')


def test_a_fitting_aspect_is_invoked_for_a_fate_point_when_the_roll_falls_short():
    found = fate.roll(sheet_of(), 'Mind', 'hard', 'I lose them in the alley behind the tannery',
                      Dice([-1, -1, 0, 0]))
    # Clever +2 - 2 = 0 against Good (+3); invoking the alleys makes it 2: still a failure, a Fate point spent.
    assert found['fate_points'] == 2 and 'invoked “Knows every alley in the river ward”' in found['skill']
    nothing = fate.roll(sheet_of(fate_points=0), 'Mind', 'hard', 'I lose them in the alley', Dice([-1, -1, 0, 0]))
    assert nothing['fate_points'] == 0 and 'invoked' not in nothing['skill']


def test_a_failure_the_trouble_fits_is_a_compel_and_gains_a_fate_point():
    found = fate.roll(sheet_of(), 'Allure', 'very_hard', 'I try to talk the Hollins gang out of my debt',
                      Dice([-1, 0, 0, 0]))
    assert found['band'] == 'failure' and found['fate_points'] == 4 and 'compelled' in found['skill']


def test_a_check_saves_the_fate_points_and_a_night_refreshes_them(client, app):
    ok(made(client))
    with app.state.database.connect(write=True) as connection:
        sheet.set_native(connection, sheet.native(connection) | {'fate_points': 1}, '')
        found = sheet.check(connection, 'Mind', 'hard', 'I lose them in the alley', Dice([-1, -1, 0, 0]))
        assert found['ruleset'] == 'fate' and sheet.native(connection)['fate_points'] == 0
        assert combat.mend(connection, 1) == ['Rested: 3 Fate points.']
        assert sheet.native(connection)['fate_points'] == 3


def test_a_milestone_raises_the_weakest_approach(client, app):
    ok(made(client))
    with app.state.database.connect(write=True) as connection:
        assert growth.milestone(connection, 'the gang paid off', '') == 'The character has grown: Forceful rises to +1.'
        assert sheet.native(connection)['approaches']['Forceful'] == 1


def test_the_narrator_reads_the_aspects(client, app):
    ok(made(client))
    with app.state.database.connect() as connection:
        described = story.persona_text(connection)[0]
    assert 'Dockside cutpurse' in described and 'Owes the Hollins gang' in described
