"""Combat v0 (requirements "Combat", "Injuries and recovery"; docs/story.md "Fights").

Code runs the fight; the narrator writes it. One line of the player's is one round:
- A fight starts when the player attacks someone in the scene (by name or by what they do: "the barkeep"), or when
  a dangerous place's threat brings a foe (dungeon/quests.py).
- Each round the player's rolled actions land first: an attack that succeeds wounds its target by the band (a cost
  one level, a success two, a critical three) and the weapon carried (a sword or axe one more, bare hands one less).
  A successful dodge, block or parry makes the foes' attacks this round hard. A successful flight ends the fight.
- Foes at a distance close in instead of attacking. Engaged foes roll Vitality to hit back the same way.
- A foe at Maimed is down. When one falls or is badly hurt, the rest roll Resolve, and a failure breaks them: they
  flee or give up. The player wins when no foe is left standing and unbroken.
- MARVEL wounds: Grazed, Hurt, Wounded, Maimed, Dying. Wounded makes physical actions a step harder; Maimed makes
  every action a step harder and physical ones two. MARVEL heals gritty: a wound drops one level after nights of
  rest set by its severity (dungeon/rest.py), from Maimed down; a new wound starts the count again.
- At Dying the character rolls Vitality to cling on, then the defeat table, weighted by what the foes want: beasts
  kill, wardens capture, robbers rob, a brawl ends with the character thrown out. Death is real; the player can
  always go back to an earlier line.

Each round is decided once, kept with the player's line (story_rounds), and retold the same way. The fight and the
character's wounds are game state, branched with the story (dungeon/timeline.py SAVED).
"""
import json
import random
import re

from dungeon import record
from dungeon.database import encode, optional
from dungeon.rules import marvel

LEVELS = ('unhurt', 'grazed', 'hurt', 'wounded', 'maimed', 'dying')
DOWN, DYING = 4, 5
# Nights of rest that mend each level by one: Grazed, Hurt, Wounded, Maimed.
MEND_NIGHTS = {1: 1, 2: 2, 3: 4, 4: 7}
DAMAGE = {'success_cost': 1, 'success': 2, 'critical_success': 3}
WEAPONS = {'sword': 1, 'felling-axe': 1, 'hatchet': 0, 'knife': 0, 'cudgel': 0, 'crowbar': 0}
BARE_HANDS = -1
ATTACK = re.compile(r'\b(attack|hit|punch|strike|fight|swing|stab|slash|shoot|kick|tackle|wrestle|club|cut|kill)\w*',
                    re.I)
GUARD = re.compile(r'\b(dodge|block|parry|defend|duck|guard)\w*', re.I)
FLEE = re.compile(r'\b(flee|run away|run for|escape|retreat|bolt|get away)\w*', re.I)
SUCCESS = ('success_cost', 'success', 'critical_success')
HARDER = {'easy': 'normal', 'normal': 'hard', 'hard': 'very_hard', 'very_hard': 'extreme', 'extreme': 'extreme'}
PHYSICAL = ('Vitality',)
# What the winners do with a character they beat, by what they want: (outcome, weight).
DEFEAT = {
    'kill': (('death', 7), ('robbed', 1), ('rescued', 2)),
    'capture': (('captured', 7), ('death', 1), ('rescued', 2)),
    'rob': (('robbed', 7), ('death', 2), ('rescued', 1)),
    'drive_off': (('thrown_out', 8), ('rescued', 2)),
}
DEFEAT_TEXT = {
    'death': 'The player\'s character dies here.',
    'robbed': 'They take the character\'s purse and leave them for dead.',
    'captured': 'They take the character prisoner, bound and helpless.',
    'rescued': 'Someone drives the attackers off and drags the character clear, barely alive.',
    'thrown_out': 'They beat the character senseless and throw them out.',
}


# The character's condition -----------------------------------------------------------------------

def condition(connection) -> dict:
    row = optional(connection, 'SELECT level, dead, rested FROM story_wounds WHERE id=1')
    return ({'level': row['level'], 'dead': bool(row['dead']), 'rested': row['rested']} if row
            else {'level': 0, 'dead': False, 'rested': 0})


def set_condition(connection, level: int, dead: bool = False, rested: int = 0):
    """The character's wound level; the nights rested toward mending it start again whenever it changes, and a new
    wound can be treated again (dungeon/injuries.py)."""
    connection.execute('INSERT INTO story_wounds (id, level, dead, rested) VALUES (1, ?, ?, ?) ON CONFLICT(id) DO '
                       'UPDATE SET rested=CASE WHEN level=excluded.level THEN rested ELSE excluded.rested END, '
                       'treated=CASE WHEN excluded.level > level THEN 0 ELSE treated END, '
                       'level=excluded.level, dead=excluded.dead', (max(0, min(DYING, level)), int(dead), rested))


def mend(connection, nights: int) -> list[str]:
    """Nights of good rest count toward the wound's mending: each level takes its own (MEND_NIGHTS)."""
    now = condition(connection)
    if nights <= 0 or now['dead'] or not 0 < now['level'] < DYING:
        return []
    level, rested = now['level'], now['rested'] + nights
    while 0 < level < DYING and rested >= MEND_NIGHTS[level]:
        rested -= MEND_NIGHTS[level]
        level -= 1
    rested = rested if level else 0
    connection.execute('UPDATE story_wounds SET level=?, rested=? WHERE id=1', (level, rested))
    if level < now['level']:
        return [f"Rest mends the character's wounds: from {LEVELS[now['level']]} to {LEVELS[level]}."]
    left = MEND_NIGHTS[level] - rested
    return [f"The character is still {LEVELS[level]}: {left} more night{'s' if left > 1 else ''} of rest to mend."]


def adjust(connection, actions: list[dict]) -> list[dict]:
    """Wounds make actions harder: Wounded slows physical ones, Maimed everything and physical ones twice."""
    level = condition(connection)['level']
    adjusted = []
    for action in actions:
        steps = (1 if level >= 3 and action['stat'] in PHYSICAL else 0) + (1 if level >= DOWN else 0)
        difficulty = action['difficulty']
        for _ in range(steps):
            difficulty = HARDER[difficulty]
        adjusted.append(action | {'difficulty': difficulty})
    return adjusted


def condition_text(connection) -> str:
    now = condition(connection)
    if now['dead']:
        return "The player's character is dead."
    if not now['level']:
        return ''
    return f"The player's character is {LEVELS[now['level']]} (kept by the game; write the wounds as they are)."


# The fight ---------------------------------------------------------------------------------------

def fight(connection) -> dict | None:
    row = optional(connection, 'SELECT * FROM story_fight WHERE id=1')
    return row | {'foes': json.loads(row['foes'])} if row else None


def save_fight(connection, state: dict | None):
    if state is None:
        connection.execute('DELETE FROM story_fight')
        return
    connection.execute('INSERT INTO story_fight (id, round, wants, foes) VALUES (1, ?, ?, ?) ON CONFLICT(id) DO '
                       'UPDATE SET round=excluded.round, wants=excluded.wants, foes=excluded.foes',
                       (state['round'], state['wants'], json.dumps(state['foes'])))


def foes_from(spec: dict, zone: str = 'near') -> list[dict]:
    count = spec.get('count', 1)
    return [{'id': f"{spec['name']}-{n}", 'name': spec['name'] if count == 1 else f"{spec['name']} {n + 1}",
             'vitality': spec.get('vitality', 10), 'resolve': spec.get('resolve', 10), 'weapon': spec.get('weapon', 0),
             'wound': 0, 'zone': zone, 'broken': False} | ({'horror': True} if spec.get('horror') else {})
            for n in range(count)]


def person_foe(person: dict) -> dict:
    sheet = person['sheet']
    return {'name': sheet['full'] or f"the {sheet.get('occupation') or sheet['role']}", 'vitality': 10, 'resolve': 10, 'weapon': 0, 'wants': 'drive_off'}


def aimed(person: dict, action: str) -> bool:
    sheet = person['sheet']
    names = {sheet['full'], sheet.get('name') or '', sheet.get('role') or '', sheet.get('occupation') or ''}
    return any(name and len(name) > 2 and re.search(rf'(?<![\w-]){re.escape(name)}(?![\w-])', action, re.I)
               for name in names)


def attack_on(people: list[dict], rolls: list[dict]) -> dict | None:
    """The person in the scene the player's attack is aimed at, if any."""
    for roll in rolls:
        if roll['stat'] == 'Vitality' and ATTACK.search(roll['action']):
            if person := next((person for person in people if aimed(person, roll['action'])), None):
                return person
    return None


def weapon_bonus(items: list[dict]) -> int:
    held = [WEAPONS[row['item_id']] for row in items if row['item_id'] in WEAPONS]
    return max(held) if held else BARE_HANDS


def standing(state: dict) -> list[dict]:
    return [foe for foe in state['foes'] if foe['wound'] < DOWN and not foe['broken']]


def foe_word(foe: dict) -> str:
    if foe['wound'] >= DOWN:
        return 'down'
    if foe['broken']:
        return 'broken, fleeing or giving up'
    return LEVELS[foe['wound']] if foe['wound'] else 'unhurt'


def player_moves(state: dict, rolls: list[dict], items: list[dict], lines: list[str]) -> tuple[bool, bool]:
    """The player's rolled actions against the foes: (got away, guarded this round)."""
    guarded = False
    for roll in rolls:
        landed = roll['band'] in SUCCESS
        if FLEE.search(roll['action']):
            if landed:
                lines.append("The player's character gets away.")
                return True, guarded
            lines.append("The player's character tries to get away and cannot.")
        elif GUARD.search(roll['action']):
            guarded = guarded or landed
        elif roll['stat'] == 'Vitality' and ATTACK.search(roll['action']) and (targets := standing(state)):
            strike(roll, targets, items, lines)
    return False, guarded


def strike(roll: dict, targets: list[dict], items: list[dict], lines: list[str]):
    target = next((foe for foe in targets if foe['name'].lower() in roll['action'].lower()), targets[0])
    target['zone'] = 'engaged'
    if roll['band'] in SUCCESS:
        target['wound'] = min(DYING, target['wound'] + max(1, DAMAGE[roll['band']] + weapon_bonus(items)))
        lines.append(f"The player's character hits {target['name']}: now {foe_word(target)}.")
    else:
        lines.append(f"The player's character's attack on {target['name']} misses.")


def morale(state: dict, rng, lines: list[str]):
    """When a foe is badly hurt or down, the rest roll Resolve; a failure breaks them."""
    if not any(foe['wound'] >= 3 for foe in state['foes']):
        return
    for foe in standing(state):
        if marvel.roll(foe['resolve'], 'normal', rng)['band'] not in SUCCESS:
            foe['broken'] = True
            lines.append(f"{foe['name'].capitalize()} breaks: they flee or give up.")


def foes_move(connection, state: dict, guarded: bool, rng, lines: list[str]) -> int:
    """Each foe still standing closes in or attacks; returns the character's wound level after."""
    level = condition(connection)['level']
    for foe in standing(state):
        if foe['zone'] != 'engaged':
            foe['zone'] = 'engaged'
            lines.append(f"{foe['name'].capitalize()} closes in.")
            continue
        band = marvel.roll(foe['vitality'], 'hard' if guarded else 'normal', rng)['band']
        if band in SUCCESS:
            before, level = level, min(DYING, level + max(1, DAMAGE[band] + foe['weapon']))
            # A maiming or a critical hit can leave a lasting injury (dungeon/injuries.py).
            if band == 'critical_success' or before < DOWN <= level:
                state['hurt_by'] = foe['name']
            lines.append(f"{foe['name'].capitalize()} hits the player's character: now {LEVELS[level]}.")
        else:
            lines.append(f"{foe['name'].capitalize()} attacks and misses.")
    set_condition(connection, level)
    return level


def play_round(connection, state: dict, rolls: list[dict], items: list[dict], rng) -> tuple[dict, list[str], str]:
    """One round: the player's actions, then morale, then each foe. Returns the fight after it, what happened, and how
    it ended: '' while it goes on, else 'escaped', 'won' or 'dying'."""
    rng = rng or random.SystemRandom()
    lines, state = [], state | {'round': state['round'] + 1}
    escaped, guarded = player_moves(state, rolls, items, lines)
    if escaped:
        return state, lines, 'escaped'
    morale(state, rng, lines)
    if not standing(state):
        lines.append('No foe is left standing: the fight is won.')
        return state, lines, 'won'
    level = foes_move(connection, state, guarded, rng, lines)
    return state, lines, 'dying' if level >= DYING else ''


def defeat(connection, state: dict, rng, now: str) -> tuple[str, str]:
    """The character went down: cling on with Vitality, then what the winners do with them."""
    rng = rng or random.SystemRandom()
    clung = marvel.roll(10, 'hard', rng)['band'] in SUCCESS
    table = [(outcome, weight) for outcome, weight in DEFEAT[state['wants']] if not (clung and outcome == 'death')]
    pick = rng.randint(1, sum(weight for _, weight in table))
    outcome = next(name for name, weight in _running(table) if pick <= weight)
    winners = state['foes'][0]['name']
    if outcome == 'death':
        set_condition(connection, DYING, dead=True)
        record.add(connection, 'death', "the player's character", f'Killed by {winners}.', now)
    else:
        set_condition(connection, DOWN)
        if outcome == 'robbed':
            connection.execute('UPDATE story_purse SET coins=0')
        record.add(connection, 'fact', "the player's character", f'Beaten by {winners}. {DEFEAT_TEXT[outcome]}', now)
    return outcome, DEFEAT_TEXT[outcome]


def _running(table):
    total = 0
    for name, weight in table:
        total += weight
        yield name, total


# A round, kept with the player's line ------------------------------------------------------------

def saved_round(connection, message_id: str) -> list[str] | None:
    row = optional(connection, 'SELECT lines FROM story_rounds WHERE message_id=?', (message_id,))
    return json.loads(row['lines']) if row else None


def turn(connection, message_id: str, people: list[dict], rolls: list[dict], start: dict | None, items: list[dict],
         rng, now: str, aftermath=None) -> list[str]:
    """The fight's part of a turn, decided once: start a fight if one begins, play the round, and keep the lines.
    `aftermath(events)` deals with what the round did to the character, [(event, who)]: 'horror' when a fight with
    something dreadful starts, 'kill' when the character kills, 'maimed' when a hit calls for a lasting injury, and
    the defeat table's outcome; it says what that left (dungeon/stress.py)."""
    if (kept := saved_round(connection, message_id)) is not None:
        return kept
    state = fight(connection)
    if state is None:
        target = attack_on(people, rolls)
        spec = person_foe(target) if target else start
        if spec is None:
            return []
        state = {'round': 0, 'wants': spec.get('wants', 'kill'), 'foes': foes_from(spec, 'engaged' if target else 'near')}
    before = {foe['id']: foe['wound'] for foe in state['foes']}
    events = [('horror', foe['name']) for foe in state['foes'][:1] if foe.get('horror') and not state['round']]
    state, lines, ending = play_round(connection, state, rolls, items, rng)
    events += [('kill', foe['name']) for foe in state['foes'] if foe['wound'] >= DYING > before[foe['id']]]
    if ending == 'dying':
        outcome, said = defeat(connection, state, rng, now)
        lines.append(f"The player's character falls, dying. {said}")
        events.append((outcome, state['foes'][0]['name']))
    if cause := state.pop('hurt_by', None):
        events.append(('maimed', cause))
    if aftermath and events and not condition(connection)['dead']:
        lines += aftermath(events)
    save_fight(connection, None if ending else state)
    connection.execute('INSERT INTO story_rounds (message_id, lines) VALUES (?, ?)', (message_id, encode(lines)))
    return lines


def prompt_text(lines: list[str], connection) -> str:
    if not lines:
        return ''
    state = fight(connection)
    foes = '; '.join(f"{foe['name']}: {foe_word(foe)}" for foe in state['foes']) if state else ''
    return ('## The fight (decided by the game; write this round exactly as it went, nothing more)\n'
            + '\n'.join(f'- {line}' for line in lines)
            + (f'\nStill fighting: {foes}.' if foes else '\nThe fight is over.'))


def view(connection, shown: bool) -> dict:
    """The fight and the character's wounds for the screen: levels with the dice shown, words otherwise."""
    state, now = fight(connection), condition(connection)
    return {'condition': LEVELS[now['level']], 'dead': now['dead'],
            'fight': state and {'round': state['round'],
                                'foes': [{'name': foe['name'], 'state': foe_word(foe),
                                          'wound': foe['wound'] if shown else None} for foe in state['foes']]}}
