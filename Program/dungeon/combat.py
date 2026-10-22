"""Combat v0 (requirements "Combat", "Injuries and recovery"; docs/story.md "Fights").

Code runs the fight; the narrator writes it. One line of the player's is one round:
- A fight starts when the player attacks someone in the scene (by name or by what they do: "the barkeep"), or when
  a dangerous place's threat brings a foe (dungeon/quests.py). An attack on someone the scene does not hold (an extra
  the narrator brought in) fights a stand-in.
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
  always go back to an earlier line. A character taken prisoner stays held (story_wounds.captors): they go nowhere
  until a line that tries to get free (slip the bonds, pick the lock, run) succeeds.

Under 5E the same fight runs on hit points, Armor Class and SRD stat blocks (dungeon/combat5e.py); under Ironsworn
on health, harm, initiative and progress tracks (dungeon/combat_iron.py); under BRP on skills, the Attack and Defense
Matrix, hit points and major wounds (dungeon/combat_brp.py).

Each round is decided once, kept with the player's line (story_rounds), and retold the same way. The fight and the
character's wounds are game state, branched with the story (dungeon/timeline.py SAVED).
"""
import json
import random
import re

from dungeon import combat5e, combat_brp, combat_iron, record, sheet
from dungeon.database import encode, optional
from dungeon.rules import marvel

LEVELS = ('unhurt', 'grazed', 'hurt', 'wounded', 'maimed', 'dying')
DOWN, DYING = 4, 5
# Nights of rest that mend each level by one: Grazed, Hurt, Wounded, Maimed.
MEND_NIGHTS = {1: 1, 2: 2, 3: 4, 4: 7}
DAMAGE = {'success_cost': 1, 'success': 2, 'critical_success': 3}
WEAPONS = {'sword': 1, 'felling-axe': 1, 'hatchet': 0, 'knife': 0, 'cudgel': 0, 'crowbar': 0}
BARE_HANDS = -1
ATTACK = re.compile(r'\b(attack|hit|punch|strike|fight|swing|stab|slash|shoot|kick|tackle|wrestle|club|cut|kill|hack|'
                    r'lunge|thrust|smash|bash|bite|headbutt|throttle|strangle|go(?:es)? for|sword|axe|knife|blade)\w*',
                    re.I)
# Who an attack is aimed at when it names nobody in the scene: someone the narrator brought in ("punch him", "the big
# logger"). An attack on a thing ("hack at the roots") names neither.
SOMEONE = re.compile(r'\b(him|her|them|man|woman|men|women|fellow|lad|boy|girl|stranger|drunk|thug|brute|logger|'
                     r'cutter|guard|bandit|thief|sailor|soldier|bully)\b', re.I)
OPPONENT = 'their opponent'
GUARD = re.compile(r'\b(dodge|block|parry|defend|duck|guard)\w*', re.I)
FREE = re.compile(r'\b(free|untie|slip (?:the|my|out)|loosen|pick the lock|break (?:the|my) (?:bonds|ropes|chains)|'
                  r'cut (?:the|my) (?:bonds|ropes)|bribe|break out)\w*', re.I)
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
    # Under 5E the hit points follow a wound dealt outside a fight (a Life Card, a fall).
    combat5e.follow_level(connection, max(0, min(DYING, level)))
    combat_iron.follow_level(connection, max(0, min(DYING, level)))
    combat_brp.follow_level(connection, max(0, min(DYING, level)))


def word(connection, level: int) -> str:
    """The character's condition in words: MARVEL's wound levels, or under 5E what the hit points read as."""
    return (combat5e.WORDS if fifth(connection) or basic(connection) else combat_iron.WORDS if sworn(connection)
            else LEVELS)[level]


def sworn(connection) -> bool:
    """Whether the fight runs on Ironsworn's health and harm (dungeon/combat_iron.py)."""
    return combat_iron.health(connection) is not None


def basic(connection) -> bool:
    """Whether the fight runs on BRP's hit points and skills (dungeon/combat_brp.py)."""
    return combat_brp.hit_points(connection) is not None


def points_of(connection) -> tuple[int, int] | None:
    """The character's hit points, under a ruleset that keeps them."""
    return combat5e.hit_points(connection) or combat_brp.hit_points(connection)


def fifth(connection) -> bool:
    """Whether the fight runs on 5E's hit points (dungeon/combat5e.py)."""
    return combat5e.hit_points(connection) is not None


def mend(connection, nights: int) -> list[str]:
    """Nights of good rest count toward the wound's mending: each level takes its own (MEND_NIGHTS)."""
    now = condition(connection)
    if fifth(connection) and not now['dead'] and now['level'] < DYING:
        # 5E heals as written: a long rest restores every hit point and spell slot.
        lines = combat5e.long_rest(connection, nights)
        if lines and now['level']:
            connection.execute('UPDATE story_wounds SET level=0, rested=0 WHERE id=1')
        return lines
    if basic(connection) and not now['dead'] and now['level'] < DYING:
        # BRP heals slowly, as written (dungeon/combat_brp.py rest).
        lines = combat_brp.rest(connection, nights)
        hp, most = combat_brp.hit_points(connection)
        connection.execute('UPDATE story_wounds SET level=? WHERE id=1', (combat5e.level_for(hp, most),))
        return lines
    if sworn(connection) and not now['dead'] and now['level'] < DYING:
        # Ironsworn: Make Camp, +1 health a night.
        lines = combat_iron.rest(connection, nights)
        connection.execute('UPDATE story_wounds SET level=? WHERE id=1', (combat_iron.level_for(combat_iron.health(connection)),))
        return lines
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
    if fifth(connection) or sworn(connection) or basic(connection):
        # 5E, Ironsworn and BRP have no wound penalties: hit points and health are whole until they run out.
        return actions
    adjusted = []
    for action in actions:
        steps = (1 if level >= 3 and action['stat'] in PHYSICAL else 0) + (1 if level >= DOWN else 0)
        difficulty = action['difficulty']
        for _ in range(steps):
            difficulty = HARDER[difficulty]
        adjusted.append(action | {'difficulty': difficulty})
    return adjusted


def captors(connection) -> str | None:
    """Who holds the character prisoner, if anyone."""
    row = optional(connection, 'SELECT captors FROM story_wounds WHERE id=1')
    return row['captors'] if row else None


def escape(connection, rolls: list[dict]) -> list[str]:
    """A prisoner's line that tries to get free: free on a success, still held on a failure."""
    held = captors(connection)
    tries = [roll for roll in rolls if FREE.search(roll['action']) or FLEE.search(roll['action'])] if held else []
    if not tries:
        return []
    if any(roll['band'] in SUCCESS for roll in tries):
        connection.execute('UPDATE story_wounds SET captors=NULL WHERE id=1')
        return [f"The player's character gets free of {held}."]
    return [f"The player's character tries to get free of {held} and cannot; they are still held."]


def condition_text(connection) -> str:
    now = condition(connection)
    if now['dead']:
        return "The player's character is dead."
    held = captors(connection)
    prisoner = f"The player's character is a prisoner of {held}, bound and watched; they go nowhere until they get " \
               "free (kept by the game)." if held else ''
    if not now['level']:
        return prisoner
    points = points_of(connection)
    hp = f", {max(0, points[0])} of {points[1]} hit points" if points else ''
    if (left := combat_iron.health(connection)) is not None:
        hp = f', health {left} of 5'
    return (f"The player's character is {word(connection, now['level'])}{hp} (kept by the game; write the wounds as they "
            "are)." + (f' {prisoner}' if prisoner else ''))


# The fight ---------------------------------------------------------------------------------------

def fight(connection) -> dict | None:
    row = optional(connection, 'SELECT * FROM story_fight WHERE id=1')
    return row | {'foes': json.loads(row['foes'])} if row else None


def save_fight(connection, state: dict | None):
    if state is None:
        connection.execute('DELETE FROM story_fight')
        return
    connection.execute('INSERT INTO story_fight (id, round, wants, foes, initiative) VALUES (1, ?, ?, ?, ?) ON '
                       'CONFLICT(id) DO UPDATE SET round=excluded.round, wants=excluded.wants, foes=excluded.foes, '
                       'initiative=excluded.initiative',
                       (state['round'], state['wants'], json.dumps(state['foes']), state.get('initiative')))


def foes_from(spec: dict, zone: str = 'near') -> list[dict]:
    count = spec.get('count', 1)
    return [{'id': f"{spec['name']}-{n}", 'name': spec['name'] if count == 1 else f"{spec['name']} {n + 1}",
             'vitality': spec.get('vitality', 10), 'resolve': spec.get('resolve', 10), 'weapon': spec.get('weapon', 0),
             'wound': 0, 'zone': zone, 'broken': False} | ({'horror': True} if spec.get('horror') else {})
            for n in range(count)]


def stand_in(rolls: list[dict]) -> dict | None:
    """A foe for an attack on someone the scene does not hold (the narrator's own extra), named as the action names
    them ("the big logger"), else 'their opponent'."""
    for roll in rolls:
        if roll['stat'] == 'Vitality' and ATTACK.search(roll['action']) and (who := SOMEONE.search(roll['action'])):
            named = re.search(rf'\b(?:the|that|this)\s+((?:[a-z-]+\s+){{0,2}}?{who.group(1)})\b', roll['action'], re.I)
            return {'name': f'the {named.group(1).lower()}' if named else OPPONENT, 'vitality': 10, 'resolve': 10,
                    'weapon': 0, 'wants': 'drive_off'}
    return None


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


def down(foe: dict) -> bool:
    """A MARVEL foe is down at Maimed; a 5E foe at 0 hit points."""
    if 'npc' in foe:
        return foe['out']
    return foe['hp'] <= 0 if 'hp' in foe else foe['wound'] >= DOWN


def standing(state: dict) -> list[dict]:
    return [foe for foe in state['foes'] if not down(foe) and not foe['broken']]


def foe_word(foe: dict) -> str:
    if 'hp' in foe:
        return combat5e.describe(foe) if foe['hp'] > 0 else 'down'
    if 'npc' in foe:
        return combat_iron.describe(foe)
    if down(foe):
        return 'down'
    if foe['broken']:
        return 'broken, fleeing or giving up'
    return LEVELS[foe['wound']] if foe['wound'] else 'unhurt'


def player_moves(connection, state: dict, rolls: list[dict], items: list[dict], rng,
                 lines: list[str]) -> tuple[bool, bool]:
    """The player's rolled actions against the foes: (got away, guarded this round). Under 5E a dodge needs no roll
    and an attack is made against the target's AC."""
    guarded, five, percent = False, fifth(connection), basic(connection)
    for roll in rolls:
        landed = roll['band'] in SUCCESS
        if five and (spell := combat5e.spell_in(connection, roll)):
            combat5e.cast(connection, roll, spell, standing(state), rng, lines)
        elif FLEE.search(roll['action']):
            if landed:
                lines.append("The player's character gets away.")
                return True, guarded
            lines.append("The player's character tries to get away and cannot.")
        elif GUARD.search(roll['action']):
            # Under 5E a dodge needs no roll; under BRP a line that defends dodges every attack this round.
            guarded = guarded or landed or five or percent
        elif roll['stat'] == 'Vitality' and ATTACK.search(roll['action']) and (targets := standing(state)):
            if five:
                combat5e.strike(connection, roll, aimed_at(roll, targets), items, rng, lines)
            elif percent:
                combat_brp.strike(connection, roll, aimed_at(roll, targets), items, rng, lines)
            elif 'npc' in targets[0]:
                combat_iron.strike(connection, state, roll, aimed_at(roll, targets), items, rng, lines)
            else:
                strike(roll, targets, items, lines)
    return False, guarded


def aimed_at(roll: dict, targets: list[dict]) -> dict:
    return next((foe for foe in targets if foe['name'].lower() in roll['action'].lower()), targets[0])


def strike(roll: dict, targets: list[dict], items: list[dict], lines: list[str]):
    target = aimed_at(roll, targets)
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
    escaped, guarded = player_moves(connection, state, rolls, items, rng, lines)
    if escaped:
        return state, lines, 'escaped'
    five, iron, percent = fifth(connection), sworn(connection), basic(connection)
    if five:
        combat5e.morale(state, standing, rng, lines)
    elif percent:
        combat_brp.morale(state, standing, rng, lines)
    elif not iron:
        morale(state, rng, lines)
    if not standing(state):
        lines.append('No foe is left standing: the fight is won.')
        return state, lines, 'won'
    if five or iron or percent:
        level = (combat5e if five else combat_brp if percent else combat_iron).foes_attack(connection, state, standing,
                                                                                         guarded, rng, lines)
        set_condition(connection, level)
    else:
        level = foes_move(connection, state, guarded, rng, lines)
    return state, lines, 'dying' if level >= DYING else ''


def defeat(connection, state: dict, rng, now: str, saved: bool | None = None) -> tuple[str, str]:
    """The character went down: cling on with Vitality, then what the winners do with them. Under 5E the death saves
    already decided (`saved`): three failures is death, stable is the table without it."""
    rng = rng or random.SystemRandom()
    if saved is False:
        outcome = 'death'
    else:
        clung = saved or sheet.check(connection, 'Vitality', 'hard', rng=rng, save=True)['band'] in SUCCESS
        table = [(outcome, weight) for outcome, weight in DEFEAT[state['wants']] if not (clung and outcome == 'death')]
        pick = rng.randint(1, sum(weight for _, weight in table))
        outcome = next(name for name, weight in _running(table) if pick <= weight)
    winners = state['foes'][0]['name']
    if outcome == 'death':
        set_condition(connection, DYING, dead=True)
        record.add(connection, 'death', "the player's character", f'Killed by {winners}.', now)
    else:
        set_condition(connection, DOWN)
        if fifth(connection):
            combat5e.set_hp(connection, 1, now)
        if basic(connection):
            combat_brp.set_hp(connection, 1)
        if outcome == 'robbed':
            connection.execute('UPDATE story_purse SET coins=0')
        if outcome == 'captured':
            connection.execute('UPDATE story_wounds SET captors=? WHERE id=1', (winners,))
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
    something dreadful starts, 'kill' when the character kills, 'fled' when a foe gets away from a fight the character
    won, 'maimed' when a hit calls for a lasting injury, and
    the defeat table's outcome; it says what that left (dungeon/stress.py)."""
    if (kept := saved_round(connection, message_id)) is not None:
        return kept
    rng = rng or random.SystemRandom()
    freed = escape(connection, rolls) if fight(connection) is None else []
    state = fight(connection) or begin(connection, people, rolls, start, rng)
    if state is None:
        if freed:
            connection.execute('INSERT INTO story_rounds (message_id, lines) VALUES (?, ?)', (message_id, encode(freed)))
        return freed
    before = {foe['id']: foe['wound'] for foe in state['foes']}
    events = [('horror', foe['name']) for foe in state['foes'][:1] if foe.get('horror') and not state['round']]
    state, lines, ending = play_round(connection, state, rolls, items, rng)
    lines = freed + lines
    events += [('kill', foe['name']) for foe in state['foes'] if foe['wound'] >= DYING > before[foe['id']]]
    # A foe who broke and got away alive (the story director may make a nemesis of them).
    events += [('fled', foe['name']) for foe in state['foes'] if ending == 'won' and foe['broken'] and not down(foe)]
    if ending == 'dying':
        ending = fall(connection, state, rng, now, lines, events)
    if ending == 'won' and fifth(connection):
        lines += combat5e.gain(connection, combat5e.fight_xp(state), 'the fight won', now)
    if cause := state.pop('hurt_by', None):
        events.append(('maimed', cause))
    if aftermath and events and not condition(connection)['dead']:
        lines += aftermath(events)
    save_fight(connection, None if ending else state)
    connection.execute('INSERT INTO story_rounds (message_id, lines) VALUES (?, ?)', (message_id, encode(lines)))
    return lines


def begin(connection, people: list[dict], rolls: list[dict], start: dict | None, rng) -> dict | None:
    """A fight that starts this turn: on someone in the scene the player attacks, a danger's foe, or a stand-in."""
    target = attack_on(people, rolls)
    spec = person_foe(target) if target else start or stand_in(rolls)
    if spec is None:
        return None
    zone = 'near' if spec is start else 'engaged'
    if fifth(connection):
        foes = combat5e.foes_from(spec, zone, rng)
    elif sworn(connection):
        foes = combat_iron.foes_from(spec, zone)
    elif basic(connection):
        foes = combat_brp.foes_from(spec, zone)
    else:
        foes = foes_from(spec, zone)
    # Ironsworn: whoever starts it has the upper hand.
    return {'round': 0, 'wants': spec.get('wants', 'kill'), 'foes': foes,
            'initiative': 'foe' if spec is start else 'player'}


def fall(connection, state: dict, rng, now: str, lines: list[str], events: list) -> str:
    """The character dropped: under 5E the death saves first (a natural 20 is back up and fighting), then the defeat
    table. Returns how the fight stands: '' when it goes on, else 'dying'."""
    saved = None
    if fifth(connection):
        saved, up, saves = combat5e.death_saves(rng)
        rolled = ', '.join(str(natural) for natural in saves)
        if up:
            set_condition(connection, combat5e.set_hp(connection, 1, now))
            lines.append(f"The player's character drops to 0 hit points, then rolls a natural 20 on a death save "
                         f"({rolled}) and is back on their feet with 1 hit point.")
            return ''
        lines.append(f"The player's character drops to 0 hit points. Death saves: {rolled}: "
                     f"{'stable' if saved else 'three failures'}.")
    elif basic(connection):
        # BRP: a collapse from a major wound is not death; a fatal wound leaves it to the defeat table.
        saved = True if state.pop('collapsed', False) and combat_brp.hit_points(connection)[0] > 0 else None
    elif sworn(connection):
        saved, how = combat_iron.face_death(connection, rng)
        lines.append(f"The player's character is brought to the brink of death and faces it: {how or 'it takes them.'}")
    outcome, said = defeat(connection, state, rng, now, saved)
    lines.append(f"The player's character falls, dying. {said}")
    events.append((outcome, state['foes'][0]['name']))
    return 'dying'


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
    points = points_of(connection)
    return {'condition': word(connection, now['level']), 'dead': now['dead'], 'captors': captors(connection),
            'fight': state and {'round': state['round'],
                                'foes': [{'name': foe['name'], 'state': foe_word(foe),
                                          'wound': foe['wound'] if shown else None}
                                         | ({'hp': foe['hp'], 'max_hp': foe['max_hp']} if shown and 'hp' in foe else {})
                                         for foe in state['foes']]}} \
        | ({'hp': max(0, points[0]), 'max_hp': points[1]} if points else {})
