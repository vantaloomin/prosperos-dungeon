"""Fights under BRP (docs/requirements.md "Combat"; docs/story.md "Fights under BRP").

The fight runs as dungeon/combat.py does (one player line is one round, foes close in and attack, morale, the defeat
table by what the foes want), with BRP's numbers from the pack:
- **Foes** are the pack's sample characters and animals, read from a foe's name (a thug is a Thug, a wolf a Wolf, a
  raider a Viking), else by how tough the MARVEL spec is. Each has its hit points, armour, Dodge, first attack and
  damage modifier.
- **The player's attack** keeps the turn's own d100, against the skill of the weapon carried (a sword is Melee
  Weapon (Sword), bare hands Brawl). The foe dodges with its Dodge, and the attack and the dodge are read on the
  Attack and Defense Matrix: a dodge at the attack's level or better stops it, one a level short takes it down a
  level. Damage is the weapon's dice plus the damage modifier (half for a thrown weapon or a bow), less armour. A
  special impales (the dice twice) or does its weapon's special; a critical does the dice's most and ignores armour.
- **Foes attack** with their skill; the character dodges the first attack each round with their Dodge, every one
  when the line says they defend. Armour is the sheet's.
- **Wounds.** A blow of at least half the character's hit points is a **major wound**: a Luck roll (POW x5), and on a
  failure the Major Wound Table takes characteristic points for good (as the Injury persistence setting allows).
  At 2 hit points or fewer after one, the character collapses; at 0 or less the wound is fatal, and the defeat table
  decides (BRP has no death saves: someone may yet drag them clear).
- **Morale:** once a foe is down or under half its hit points, the others roll Luck; a failure breaks them.
- **Healing** is slow, as written: each hit point back takes 7 days divided by a 1D3 roll (3, 4 or 7 nights of
  rest). First Aid on the character's own wound restores 1D3 at once, once a wound (dungeon/sheet.py).
"""
import math
import random
import re
from functools import cache

from dungeon import combat5e, sheet
from dungeon.rules import brp

# Foes by the words of their name, the more specific first.
FOE_WORDS = (('ghoul', 'ghoul'), ('skeleton', 'skeleton'), ('zombie', 'zombie'), ('bear', 'bear'), ('wolf', 'wolf'),
             ('hound', 'dog'), ('dog', 'dog'), ('horse', 'horse'), ('boar', 'wolf'), ('knight', 'knight'),
             ('raider', 'viking'), ('soldier', 'viking'), ('guard', 'viking'), ('warden', 'tribal_warrior'),
             ('pirate', 'pirate'), ('corsair', 'pirate'), ('cultist', 'priest'), ('priest', 'priest'),
             ('sorcerer', 'sorcerer'), ('witch', 'sorcerer'), ('thug', 'thug'), ('bandit', 'thug'),
             ('press-gang', 'thug'))
BY_VITALITY = ((11, 'thug'), (13, 'viking'), (99, 'knight'))
# What the Kingswood pack's weapons are in BRP.
WEAPONS = {'sword': 'broadsword', 'felling-axe': 'wood_axe', 'hatchet': 'hand_axe', 'knife': 'knife',
           'cudgel': 'light_club', 'crowbar': 'light_club', 'bow': 'self_bow'}
LEVELS = ('fumble', 'failure', 'success', 'special', 'critical')
DICE = re.compile(r'([+-]?)(\d+)D(\d+)', re.I)


@cache
def foes() -> dict[str, dict]:
    return brp.by_id('foes')


def roll_formula(formula: str, rng: random.Random, most: bool = False) -> int:
    """'1D8+1' or '-1D4' rolled; `most` takes the dice's most (a critical)."""
    if not formula:
        return 0
    total, rest = 0, formula
    for sign, count, sides in DICE.findall(formula):
        dice = int(count) * int(sides) if most else sum(rng.randint(1, int(sides)) for _ in range(int(count)))
        total += -dice if sign == '-' else dice
        rest = rest.replace(f'{sign}{count}D{sides}', '', 1).replace(f'{sign}{count}d{sides}', '', 1)
    return total + sum(int(number) for number in re.findall(r'[+-]?\d+', rest))


def modifier_part(modifier: str, how: str, rng: random.Random) -> int:
    if how == 'none' or not modifier:
        return 0
    rolled = roll_formula(modifier, rng)
    return math.ceil(rolled / 2) if how == 'half' and rolled > 0 else rolled


# Hit points ---------------------------------------------------------------------------------------

def hit_points(connection) -> tuple[int, int] | None:
    found = sheet.native(connection) if sheet.ruleset(connection) == brp.ID else None
    return (found['hp'], found['max_hp']) if found else None


def set_hp(connection, hp: int) -> int:
    found = sheet.native(connection)
    found['hp'] = max(-found['max_hp'], min(found['max_hp'], hp))
    sheet.set_native(connection, found, '')
    return combat5e.level_for(found['hp'], found['max_hp'])


def follow_level(connection, level: int):
    """A wound word set outside a fight moves the hit points with it."""
    found = sheet.native(connection) if sheet.ruleset(connection) == brp.ID else None
    if found and combat5e.level_for(found['hp'], found['max_hp']) != level:
        found['hp'] = combat5e.hp_for(level, found['max_hp'])
        sheet.set_native(connection, found, '')


# Foes ---------------------------------------------------------------------------------------------

def foe_for(spec: dict) -> dict:
    if spec.get('brp') in foes():
        return foes()[spec['brp']]
    name = spec['name'].lower()
    found = next((foe for word, foe in FOE_WORDS if word in name), None)
    return foes()[found or next(foe for most, foe in BY_VITALITY if spec.get('vitality', 10) <= most)]


def foes_from(spec: dict, zone: str) -> list[dict]:
    block = foe_for(spec)
    count = spec.get('count', 1)
    return [{'id': f"{spec['name']}-{number}", 'name': spec['name'] if count == 1 else f"{spec['name']} {number + 1}",
             'brp': block['id'], 'hp': block['hp'], 'max_hp': block['hp'], 'armor': block['armor'],
             'dodge': block['dodge'], 'attack': block['attacks'][0], 'dm': block['damage_modifier'],
             'pow': block['characteristics'].get('pow', 10), 'wound': 0, 'zone': zone, 'broken': False}
            | ({'horror': True} if spec.get('horror') else {}) for number in range(count)]


def hurt(foe: dict, damage: int):
    foe['hp'] = max(0, foe['hp'] - damage)
    foe['wound'] = combat5e.level_for(foe['hp'], foe['max_hp'])


# The matrix ---------------------------------------------------------------------------------------

def landed(attack: str, defence: str | None) -> str | None:
    """The attack's level after the defence (the Attack and Defense Matrix), None when it is stopped."""
    if attack in ('failure', 'fumble'):
        return None
    if defence is None or defence in ('failure', 'fumble'):
        return attack
    # A dodge that succeeds takes the attack down a level, a special two, a critical three.
    after = LEVELS.index(attack) - (LEVELS.index(defence) - 1)
    return LEVELS[after] if after >= LEVELS.index('success') else None


def damage_of(weapon: dict, dm: str, level_: str, armor: int, rng: random.Random) -> int:
    critical = level_ == 'critical'
    dice = roll_formula(weapon['damage'], rng, most=critical)
    if level_ == 'special' and weapon.get('special') == 'impaling':
        dice += roll_formula(weapon['damage'], rng)
    total = dice + modifier_part(dm, weapon.get('damage_modifier', 'full'), rng)
    return max(0, total - (0 if critical else armor))


def weapon_of(items: list[dict], action: str) -> dict:
    """The weapon an attack uses: bare hands for a punch or a kick, the one the action names, else the best carried."""
    weapons = brp.by_id('weapons')
    if combat5e.BARE.search(action):
        return weapons['kick' if re.search(r'\bkick', action, re.I) else 'fist']
    held = [weapons[WEAPONS[row['item_id']]] for row in items if row['item_id'] in WEAPONS]
    named = [weapon for weapon in held if any(word in action.lower() for word in weapon_words(weapon))]
    return max(named or held, key=lambda weapon: combat5e.roll_average(weapon['damage'].lower()),
               default=weapons['fist'])


def called(weapon: dict) -> str:
    """A weapon's name in a sentence: "Sword, Broad" is a broad sword."""
    first, _, second = weapon['name'].partition(', ')
    return f'{second} {first}'.lower().replace('- ', '') if second else first.lower()


def weapon_words(weapon: dict) -> list[str]:
    own = [item.replace('-', ' ') for item, kind in WEAPONS.items() if kind == weapon['id']]
    return [weapon['name'].lower(), weapon['skill'], *own, *(word.split()[-1] for word in own)]


# The player's attack ------------------------------------------------------------------------------

def strike(connection, roll: dict, target: dict, items: list[dict], rng, lines: list[str]):
    """The character's attack on `target` with the turn's own d100 against the weapon's skill; the foe dodges."""
    found = sheet.native(connection)
    weapon = weapon_of(items, roll['action'])
    chance = found['skills'][weapon['skill']]
    attack = brp.level(roll['natural'], chance)
    combat5e.record_roll(connection, roll, f"{weapon['name']} {chance}% ({attack})", 0, roll['natural'], chance,
                         brp.BANDS[attack])
    target['zone'] = 'engaged'
    dodge = brp.level(rng.randint(1, 100), target['dodge']) if target['dodge'] and attack not in ('failure', 'fumble') \
        else None
    hit = landed(attack, dodge)
    if hit is None:
        lines.append(f"The player's character's attack on {target['name']} "
                     + ('goes badly wrong (a fumble).' if attack == 'fumble' else 'misses.' if attack == 'failure'
                        else 'is dodged.'))
        return
    damage = damage_of(weapon, brp.damage_modifier(found['characteristics']), hit, target['armor'], rng)
    hurt(target, damage)
    word = 'down' if target['hp'] <= 0 else combat5e.describe(target)
    how = {'critical': 'lands a critical hit on', 'special': 'lands a telling blow on'}.get(hit, 'hits')
    lines.append(f"The player's character {how} {target['name']} with a {called(weapon)} for {damage} damage"
                 + (' (through the armour)' if hit == 'critical' else '') + f': now {word}.')
    learned(found, weapon['skill'], hit)
    sheet.set_native(connection, found, '')


def learned(found: dict, skill: str, level_: str):
    """A weapon skill that landed gets its experience check."""
    if level_ in ('success', 'special', 'critical') and skill not in found.setdefault('checks', []):
        found['checks'].append(skill)


# The round ----------------------------------------------------------------------------------------

def morale(state: dict, standing, rng, lines: list[str]):
    if not any(foe['hp'] <= foe['max_hp'] / 2 for foe in state['foes']):
        return
    for foe in standing(state):
        if rng.randint(1, 100) > foe['pow'] * 5:
            foe['broken'] = True
            lines.append(f"{foe['name'].capitalize()} breaks: they flee or give up.")


def foes_attack(connection, state: dict, standing, guarded: bool, rng, lines: list[str]) -> int:
    """Each foe still standing closes in or attacks; the character dodges the first (every one when they defend)."""
    found = sheet.native(connection)
    armor = (brp.by_id('armor').get(found.get('armor') or '') or {}).get('av', 0)
    dodged = False
    for foe in standing(state):
        if foe['zone'] != 'engaged':
            foe['zone'] = 'engaged'
            lines.append(f"{foe['name'].capitalize()} closes in.")
            continue
        attack = brp.level(rng.randint(1, 100), foe['attack']['skill'])
        dodge = None
        if attack not in ('failure', 'fumble') and (guarded or not dodged):
            dodged, dodge = True, brp.level(rng.randint(1, 100), found['skills']['dodge'])
            if dodge in ('success', 'special', 'critical'):
                learned(found, 'dodge', dodge)
        hit = landed(attack, dodge)
        if hit is None:
            lines.append(f"{foe['name'].capitalize()} attacks and "
                         + ('misses.' if attack in ('failure', 'fumble') else 'the character dodges.'))
            continue
        damage = damage_of({'damage': foe['attack']['damage'], 'special': foe['attack']['special'],
                            'damage_modifier': foe['attack']['damage_modifier']}, foe['dm'], hit, armor, rng)
        if not damage:
            lines.append(f"{foe['name'].capitalize()} hits the player's character, and the armour takes it.")
            continue
        found['hp'] -= damage
        found['aided'] = False
        lines.append(f"{foe['name'].capitalize()} {'lands a critical hit on' if hit == 'critical' else 'hits'} the "
                     f"player's character with {foe['attack']['name'].lower()} for {damage} damage: {max(0, found['hp'])} "
                     f"of {found['max_hp']} hit points left.")
        if damage >= brp.major_wound(found) and found['hp'] > 0:
            major(connection, found, state, foe, rng, lines)
        if found['hp'] <= 0 or state.get('collapsed'):
            break
    sheet.set_native(connection, found, '')
    level_ = combat5e.level_for(found['hp'], found['max_hp'])
    return 5 if state.get('collapsed') else level_


def major(connection, found: dict, state: dict, foe: dict, rng, lines: list[str]):
    """A major wound: a Luck roll, and on a failure the Major Wound Table, as the Injury persistence setting allows."""
    from dungeon import table
    lines.append('It is a major wound.')
    if found['hp'] <= 2:
        state['collapsed'] = True
        lines.append('The character collapses from shock and loss of blood.')
    if rng.randint(1, 100) <= found['characteristics']['pow'] * 5 or table.rule(connection, 'injury_persistence') == 'none':
        lines.append('It will heal clean.')
        return
    pick = rng.randint(1, 100)
    row = next(row for row in brp.pack()['major_wounds'] if pick <= row['up_to'])
    lost = max(1, roll_formula(row['loss'], rng))
    stat = row['characteristic']
    found['characteristics'][stat] = max(1, found['characteristics'][stat] - lost)
    found.setdefault('major_wounds', []).append({'text': row['text'], 'characteristic': stat, 'lost': lost,
                                                 'by': foe['name']})
    lines.append(f"It leaves its mark for good: {row['text']} ({brp.NAMES[stat]} -{lost}).")
    if not row['can_fight']:
        state['collapsed'] = True
        lines.append('The character cannot fight on.')


def rest(connection, nights: int, rng=None) -> list[str]:
    """Each hit point back takes 7 days divided by a 1D3 roll, counted in nights of rest."""
    found = sheet.native(connection)
    if nights <= 0 or found['hp'] >= found['max_hp']:
        return []
    rng = rng or random.SystemRandom()
    before = found['hp']
    mending = found.get('mending') or {'per': math.ceil(7 / rng.randint(1, 3)), 'nights': 0}
    mending['nights'] += nights
    while found['hp'] < found['max_hp'] and mending['nights'] >= mending['per']:
        mending['nights'] -= mending['per']
        found['hp'] += 1
        mending['per'] = math.ceil(7 / rng.randint(1, 3))
    found['mending'] = mending if found['hp'] < found['max_hp'] else None
    sheet.set_native(connection, found, '')
    if found['hp'] > before:
        return [f"Rest mends the character: {found['hp']} of {found['max_hp']} hit points."]
    return [f"The character's wounds are slow to mend: {found['hp']} of {found['max_hp']} hit points."]


def first_aid(connection, found: dict, result: dict, rng) -> dict:
    """First Aid that succeeds on the character's own wound restores 1D3 hit points, once a wound."""
    if result.get('brp_skill') != 'first_aid' or result['band'] not in ('success', 'critical_success') or \
            found['hp'] >= found['max_hp'] or found.get('aided'):
        return result
    healed = min(found['max_hp'] - found['hp'], (rng or random.SystemRandom()).randint(1, 3))
    found['hp'] += healed
    found['aided'] = True
    return result | {'skill': f"{result['skill']} (heals {healed})", 'healed': healed}
