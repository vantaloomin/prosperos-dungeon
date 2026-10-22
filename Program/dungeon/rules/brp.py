"""BRP (docs/requirements.md "Rulesets"; content in dungeon/rules/packs/brp, from Chaosium's Basic Roleplaying ORC
Content Document, under the ORC License).

- **The sheet.** Seven characteristics (STR, CON, SIZ, INT, POW, DEX, CHA), bought point-based as written: all start
  at 10, 24 points to spend, DEX, INT and POW cost 3 a point, each from 3 to 21. From them: hit points (CON+SIZ,
  halved, rounded up), the major wound level (half that), power points (POW), the experience bonus (half INT) and the
  damage modifier (STR+SIZ on the table).
- **Skills** start at their base chance. A personality type adds 20 to each of its skills (its "any combat skill"
  is the profession's weapon). A profession's 250 points go to its ten skills, none past 75; the personal pool
  (INT x10) goes to the same skills, then Dodge, Spot, Listen and Stealth. Code spreads the points evenly, so a
  character is a profession, a personality and seven characteristics.
- **A roll** is d100 under the skill (or a characteristic x5 when no skill fits: Effort, Stamina, Idea, Luck,
  Agility, Charm). Easy doubles it, Difficult halves it, and the harder steps take 20 and 40 more off the halved
  chance. 01-05 always succeeds, 96-00 always fails. A roll at 1/20 of the chance is a critical, at 1/5 a special, and
  the top 1/20 of the chance of failure is a fumble (00 always). On the shared ladder: critical critical_success,
  special and success success, failure failure, fumble critical_failure.
- **Experience.** A skill that succeeds when it mattered (not an Easy roll) gets an experience check. After a
  night's rest code makes the experience roll for each: d100 plus the experience bonus over the skill raises it 1D6.
"""
import json
import math
import random
import re
from functools import cache
from pathlib import Path

ID = 'brp'
NAME = 'Percentile'
PACK = Path(__file__).parent / 'packs' / 'brp'
CHARACTERISTICS = ('str', 'con', 'siz', 'int', 'pow', 'dex', 'cha')
NAMES = {'str': 'STR', 'con': 'CON', 'siz': 'SIZ', 'int': 'INT', 'pow': 'POW', 'dex': 'DEX', 'cha': 'CHA'}
# The characteristic roll an approach falls back on when no skill fits: (characteristic, roll name).
EQUIVALENT = {'Mind': ('int', 'Idea'), 'Allure': ('cha', 'Charm'), 'Resolve': ('pow', 'Luck'),
              'Vitality': ('str', 'Effort'), 'Essence': ('pow', 'Luck'), 'Luck': ('pow', 'Luck')}
# Resisting: Stamina for the body, Luck (POW) for the rest.
SAVE = {'Vitality': ('con', 'Stamina')}
# Skills by the words of an action, the more specific first.
SKILL_WORDS = (
    ('first_aid', ('bandage', 'stitch', 'patch up', 'tend the wound', 'tend his', 'tend her', 'first aid', 'splint',
                   'bind my', 'binds my', 'bind up', 'binds up', 'bind the wound', 'bind his wound', 'bind her wound',
                   'dress the wound', 'dress my', 'wrap the wound', 'wrap my', 'clean the wound', 'tourniquet')),
    ('medicine', ('treat', 'cure', 'heal', 'diagnose', 'physic', 'poultice')),
    ('sleight_of_hand', ('pickpocket', 'palm', 'lift his', 'lift her', 'sleight', 'cut the purse', 'cutpurse')),
    ('fine_manipulation', ('pick the lock', 'pick a lock', 'disarm the trap', 'untie')),
    ('stealth', ('sneak', 'creep', 'slip past', 'quietly', 'unseen', 'tiptoe')),
    ('hide', ('hide', 'conceal', 'take cover')),
    ('dodge', ('dodge', 'duck', 'evade', 'tumble', 'roll away')),
    ('climb', ('climb', 'scale', 'clamber')),
    ('jump', ('jump', 'leap', 'vault')),
    ('swim', ('swim', 'dive', 'wade')),
    ('ride', ('ride', 'gallop', 'spur')),
    ('throw', ('throw', 'hurl', 'toss')),
    ('track', ('track', 'follow the trail', 'follow the tracks')),
    ('navigate', ('find the way', 'navigate', 'which way', 'get our bearings')),
    ('fast_talk', ('lie', 'bluff', 'deceive', 'fast talk', 'con him', 'con her', 'trick')),
    ('bargain', ('haggle', 'bargain', 'barter', 'price')),
    ('command', ('order', 'command', 'rally')),
    ('persuade', ('persuade', 'convince', 'charm', 'talk him', 'talk her', 'talk them', 'plead', 'beg', 'reason with',
                  'threaten', 'intimidate', 'seduce', 'flirt')),
    ('etiquette', ('bow', 'courtesy', 'manners', 'curtsy', 'etiquette')),
    ('perform', ('sing', 'dance', 'perform', 'play the', 'recite')),
    ('disguise', ('disguise', 'pass as', 'pass for')),
    ('insight', ('read his', 'read her', 'read their', 'tell if', 'motive', 'lying to me', 'size him up', 'size her up')),
    ('appraise', ('appraise', 'what is it worth', 'value of')),
    ('listen', ('listen', 'hear', 'eavesdrop')),
    ('spot', ('look', 'search', 'spot', 'watch', 'scan', 'notice', 'examine', 'inspect')),
    ('research', ('research', 'read through', 'study the', 'look it up')),
    ('knowledge_occult', ('ritual', 'magic', 'arcane', 'curse', 'occult', 'demon')),
    ('knowledge_religion', ('pray', 'prayer', 'god', 'scripture', 'temple')),
    ('knowledge_natural_history', ('forage', 'herb', 'plant', 'animal', 'beast')),
    ('knowledge_history', ('remember', 'recall', 'history', 'legend', 'lore')),
    ('craft', ('craft', 'build', 'carve', 'forge', 'mend', 'cook', 'sew')),
    ('repair', ('repair', 'fix')),
    ('grapple', ('grapple', 'wrestle', 'pin', 'hold him', 'hold her', 'tackle')),
    ('brawl', ('punch', 'kick', 'headbutt', 'head-butt', 'fist', 'elbow', 'knee')),
)
POWER_LEVEL = {'professional': 250, 'cap': 75}
SPREAD_AFTER = ('dodge', 'spot', 'listen', 'stealth')
# A premade's profession, and where its 24 points go, by its strongest MARVEL stat.
QUICK = {'Vitality': ('warrior', 'brutal', {'str': 15, 'con': 14, 'siz': 13, 'dex': 14}),
         'Mind': ('scholar', 'cunning', {'int': 16, 'con': 12, 'siz': 11, 'cha': 13}),
         'Allure': ('entertainer', 'charming', {'cha': 16, 'dex': 15, 'con': 12, 'siz': 11}),
         'Resolve': ('priest', 'charming', {'pow': 16, 'cha': 14, 'con': 12, 'siz': 10}),
         'Essence': ('wizard', 'cunning', {'pow': 14, 'int': 14, 'con': 10, 'siz': 10}),
         'Luck': ('thief', 'skilled', {'dex': 16, 'con': 12, 'siz': 11, 'cha': 13})}
FUMBLE = 100


@cache
def pack() -> dict:
    return json.loads((PACK / 'brp.json').read_text(encoding='utf-8'))


@cache
def manifest() -> dict:
    return json.loads((PACK / 'pack.json').read_text(encoding='utf-8'))


def attribution() -> str:
    return manifest()['license']['attribution']


@cache
def by_id(kind: str) -> dict[str, dict]:
    return {item['id']: item for item in pack()[kind]}


def skills() -> dict[str, dict]:
    return by_id('skills')


# The sheet --------------------------------------------------------------------------------------------------

def cost(characteristics: dict[str, int]) -> int:
    rules = pack()['creation']
    return sum((value - rules['start']) * (rules['costly_price'] if stat in rules['costly'] else 1)
               for stat, value in characteristics.items())


def bought(characteristics: dict[str, int]) -> dict[str, int]:
    """Characteristics bought as written: every one from 3 to 21, costing no more than the points."""
    from dungeon.errors import require
    rules = pack()['creation']
    chars = {stat: rules['start'] for stat in CHARACTERISTICS} | dict(characteristics)
    require(set(chars) == set(CHARACTERISTICS), 'Give the seven characteristics: STR, CON, SIZ, INT, POW, DEX, CHA.', 422)
    require(all(isinstance(value, int) and rules['least'] <= value <= rules['most'] for value in chars.values()),
            f"Each characteristic is from {rules['least']} to {rules['most']}.", 422)
    require(cost(chars) <= rules['points'], f"The characteristics can cost {rules['points']} points at most (DEX, INT "
            f"and POW cost {rules['costly_price']} a point).", 422)
    return chars


def damage_modifier(chars: dict[str, int]) -> str:
    total = chars['str'] + chars['siz']
    for most, modifier in pack()['damage_modifier']:
        if total <= most:
            return modifier
    return f'+{5 + math.ceil((total - 104) / 16)}D6'


def hit_points(chars: dict[str, int]) -> int:
    return max(1, math.ceil((chars['con'] + chars['siz']) / 2))


def base(skill: dict, chars: dict[str, int]) -> int:
    value = skill['base']
    if isinstance(value, int):
        return value
    return {'dex*2': chars['dex'] * 2, 'int+pow': chars['int'] + chars['pow'], 'int*5': chars['int'] * 5}[value]


def spend(values: dict[str, int], targets: list[str], points: int, cap: int) -> int:
    """Points spread evenly over `targets`, a point at a time, none past `cap`; returns what is left."""
    while points > 0:
        open_ = [skill for skill in targets if values[skill] < cap]
        if not open_:
            return points
        for skill in open_:
            if points <= 0:
                break
            values[skill] += 1
            points -= 1
    return 0


def personality_skills(personality: dict, profession: dict) -> list[str]:
    weapons = [skill for skill in profession['skills'] if skills()[skill]['category'] == 'combat'] + ['brawl', 'dodge']
    picks, combat = [], iter(dict.fromkeys(weapons))
    for skill in personality['skills']:
        picks.append(next(combat) if skill == 'combat' else skill)
    return list(dict.fromkeys(picks))


def build(characteristics: dict[str, int], profession_id: str, personality_id: str) -> dict:
    """A new character: bought characteristics, a personality's 20s, the profession's and the personal points."""
    from dungeon.errors import require
    require(profession_id in by_id('professions'), 'Choose a profession from the BRP pack.', 422)
    require(personality_id in by_id('personalities'), 'Choose a personality: brutal, skilled, cunning or charming.', 422)
    chars = bought(characteristics)
    profession, personality = by_id('professions')[profession_id], by_id('personalities')[personality_id]
    rules = pack()['creation']
    values = {skill_id: base(skill, chars) for skill_id, skill in skills().items()}
    for skill in personality_skills(personality, profession):
        values[skill] += rules['personality_points']
    left = spend(values, profession['skills'], rules['professional_points'], rules['professional_cap'])
    left = spend(values, profession['skills'], left + chars['int'] * rules['personal_per_int'], rules['professional_cap'])
    spend(values, list(SPREAD_AFTER), left, rules['professional_cap'])
    hp = hit_points(chars)
    return {'characteristics': chars, 'skills': values, 'profession': profession_id, 'personality': personality_id,
            'hp': hp, 'max_hp': hp, 'pp': chars['pow'], 'max_pp': chars['pow'], 'armor': profession['armor'],
            'weapons': list(profession['weapons']), 'checks': [], 'major_wounds': []}


def suggested(top: str) -> dict:
    """A quick build from a MARVEL stat: a profession, a personality and where the 24 points go."""
    profession, personality, spread = QUICK[top]
    return {'characteristics': {stat: pack()['creation']['start'] for stat in CHARACTERISTICS} | spread,
            'profession': profession, 'personality': personality}


def major_wound(sheet: dict) -> int:
    return math.ceil(sheet['max_hp'] / 2)


def xp_bonus(sheet: dict) -> int:
    return math.ceil(sheet['characteristics']['int'] / 2)


def view(sheet: dict) -> dict:
    chars = sheet['characteristics']
    armor = by_id('armor').get(sheet.get('armor') or '')
    top = sorted(sheet['skills'].items(), key=lambda item: (-item[1], skills()[item[0]]['name']))
    return {'ruleset': ID, 'ruleset_name': NAME, **sheet,
            'names': {'profession': by_id('professions')[sheet['profession']]['name'],
                      'personality': by_id('personalities')[sheet['personality']]['name']},
            'rolls': {name: chars[stat] * 5 for stat, name in
                      (('str', 'Effort'), ('con', 'Stamina'), ('int', 'Idea'), ('pow', 'Luck'), ('dex', 'Agility'),
                       ('cha', 'Charm'))},
            'damage_modifier': damage_modifier(chars) or 'none', 'major_wound': major_wound(sheet),
            'xp_bonus': xp_bonus(sheet), 'armor_name': armor['name'] if armor else 'none',
            'armor_value': armor['av'] if armor else 0,
            'skill_list': [{'id': skill, 'name': skills()[skill]['name'], 'value': value,
                            'checked': skill in sheet.get('checks', [])} for skill, value in top],
            'attribution': attribution()}


def described(sheet: dict) -> str:
    """The character in a line, for the narrator."""
    chars = sheet['characteristics']
    best = [skills()[skill]['name'] for skill, _ in
            sorted(sheet['skills'].items(), key=lambda item: -item[1])[:5]]
    return (f"A {by_id('professions')[sheet['profession']]['name'].lower()}, "
            f"{by_id('personalities')[sheet['personality']]['name'].lower()} by nature: "
            + ', '.join(f'{NAMES[stat]} {chars[stat]}' for stat in CHARACTERISTICS)
            + f"; best at {', '.join(best)}. Hit points {sheet['hp']} of {sheet['max_hp']}.")


# The roll ---------------------------------------------------------------------------------------------------

def skill_for(text: str) -> str | None:
    lowered = text.lower()
    return next((skill for skill, words in SKILL_WORDS
                 if any(re.search(rf'\b{re.escape(word)}', lowered) for word in words)), None)


def chance_for(value: int, difficulty: str) -> int:
    """The chance after the difficulty: Easy doubles, Difficult halves, the harder steps take 20 and 40 more."""
    if difficulty == 'easy':
        return value * 2
    if difficulty == 'normal':
        return value
    halved = math.ceil(value / 2)
    return max(0, halved - {'hard': 0, 'very_hard': 20, 'extreme': 40}.get(difficulty, 0))


def level(natural: int, chance: int, floor: bool = True) -> str:
    """The roll's degree of success: critical, special, success, failure or fumble."""
    # The Skill Results table reads each band of five by its lowest chance (56-60 fumbles on 98-00).
    lowest = (max(1, min(chance, 96)) - 1) // 5 * 5 + 1
    fumble = FUMBLE - max(1, math.ceil((100 - lowest) / 20)) + 1
    if natural >= fumble:
        return 'fumble'
    if natural <= max(1, math.ceil(chance / 20)) and chance > 0:
        return 'critical'
    if natural <= max(1, math.ceil(chance / 5)) and chance > 0:
        return 'special'
    if (natural <= 5 and floor) or (natural <= chance and natural < 96):
        return 'success'
    return 'failure'


def shown(chance: int) -> int:
    """The chance as the roll card shows it: 96-00 always fails, so nothing reads over 95%. The full chance still
    sets criticals and specials."""
    return min(chance, 95)


BANDS = {'critical': 'critical_success', 'special': 'success', 'success': 'success', 'failure': 'failure',
         'fumble': 'critical_failure'}


def read(sheet: dict, approach: str, text: str, save: bool = False) -> tuple[str | None, str, str, int]:
    """(skill or None, characteristic, label, value) an action rolls."""
    if not save and (skill := skill_for(text)):
        return skill, '', skills()[skill]['name'], sheet['skills'][skill]
    stat, name = (SAVE.get(approach) or ('pow', 'Luck')) if save else EQUIVALENT.get(approach, ('int', 'Idea'))
    return None, stat, name, sheet['characteristics'][stat] * 5


def check(sheet: dict, approach: str, difficulty: str, text: str = '', rng: random.Random | None = None,
          save: bool = False) -> dict:
    """A skill roll (or a characteristic roll) under the chance for the difficulty."""
    rng = rng or random.SystemRandom()
    skill, stat, label, value = read(sheet, approach, text, save)
    chance = chance_for(value, difficulty)
    natural = rng.randint(1, 100)
    # A skill with a base chance of 5% or more always succeeds on 01-05.
    floor = skill is None or not isinstance(skills()[skill]['base'], int) or skills()[skill]['base'] >= 5
    degree = level(natural, chance, floor)
    return {'natural': natural, 'die': 100, 'bonus': 0, 'shift': 0, 'total': natural, 'target': chance,
            'skill': f'{label} {shown(chance)}%' + (f' ({degree})' if degree in ('critical', 'special', 'fumble') else ''),
            'ability': skill or stat, 'rolls': [natural], 'band': BANDS[degree], 'degree': degree,
            'brp_skill': skill, 'easy': difficulty == 'easy'}


# Experience -------------------------------------------------------------------------------------------------

def check_skill(sheet: dict, roll: dict) -> bool:
    """An experience check for a skill that succeeded (not an Easy roll); True when it is new."""
    skill = roll.get('brp_skill')
    if not skill or roll.get('easy') or roll['band'] not in ('success', 'critical_success') or \
            skill in sheet.setdefault('checks', []):
        return False
    sheet['checks'].append(skill)
    return True


def improve(sheet: dict, rng: random.Random | None = None) -> list[str]:
    """After a rest, the experience roll for each checked skill: d100 + the experience bonus over the skill raises it
    1D6. The checks clear."""
    rng = rng or random.SystemRandom()
    lines = []
    for skill in sheet.get('checks', []):
        value = sheet['skills'][skill]
        if rng.randint(1, 100) + xp_bonus(sheet) > value:
            gained = rng.randint(1, 6)
            sheet['skills'][skill] = value + gained
            lines.append(f"What the character has been through has taught them: {skills()[skill]['name']} grows from "
                         f'{value}% to {value + gained}%.')
    sheet['checks'] = []
    return lines
