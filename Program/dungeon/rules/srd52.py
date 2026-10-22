"""5E via the SRD 5.2.1 (docs/requirements.md "Rulesets"; content in dungeon/rules/packs/srd52, under CC-BY-4.0).

- **The sheet.** Six ability scores, a class, a species and a background from the pack, a level, proficiency in the
  class's saving throws and in skills (the background's two and the class's own picks), hit points from the class's
  hit die and Constitution, and Armor Class (unarmored: 10 + Dexterity; Barbarians add Constitution, Monks Wisdom).
  A new character takes the standard array (15, 14, 13, 12, 10, 8) placed where the player likes, then the
  background's +2 and +1.
- **A check** is a d20 plus the ability modifier, plus the proficiency bonus when the character is proficient in the
  skill (or the save), against a DC: 10 easy, 15 normal, 20 hard, 25 very hard, 30 extreme. Advantage rolls two d20
  and keeps the higher, disadvantage the lower.
- **The outcome ladder: pass or fail as written** (the pack's `resolution.outcome_mapping`). Meeting the DC is a
  success, else a failure. A natural 20 or 1 is a critical only on attack rolls and death saves.
- **The Referee still speaks in approaches** (MARVEL's six stats, which name what an action leans on); code reads
  the skill from the action's words and its ability from the skill, else from the approach (EQUIVALENT).
"""
import json
import random
import re
from functools import cache
from pathlib import Path

ID = 'srd52'
NAME = '5E (SRD 5.2.1)'
PACK = Path(__file__).parent / 'packs' / 'srd52'
ABILITIES = ('str', 'dex', 'con', 'int', 'wis', 'cha')
ABILITY_NAMES = {'str': 'Strength', 'dex': 'Dexterity', 'con': 'Constitution', 'int': 'Intelligence',
                 'wis': 'Wisdom', 'cha': 'Charisma'}
STANDARD_ARRAY = (15, 14, 13, 12, 10, 8)
SCORE_RANGE = (1, 30)
DCS = {'easy': 10, 'normal': 15, 'hard': 20, 'very_hard': 25, 'extreme': 30}
# What each of the Referee's approaches leans on, when the action's words name no skill. Essence is the class's
# spellcasting ability, else Wisdom.
EQUIVALENT = {'Mind': 'int', 'Allure': 'cha', 'Resolve': 'wis', 'Vitality': 'str', 'Essence': None, 'Luck': 'dex'}
# Words that name a skill, the more specific first.
SKILL_WORDS = (
    ('sleight-of-hand', ('pickpocket', 'steal', 'palm', 'pick the lock', 'pick a lock', 'lift his', 'lift her',
                         'sleight')),
    ('stealth', ('sneak', 'hide', 'slip past', 'creep', 'unseen', 'quietly')),
    ('acrobatics', ('dodge', 'tumble', 'balance', 'flip', 'roll away', 'squeeze', 'slip free')),
    ('athletics', ('climb', 'jump', 'leap', 'swim', 'shove', 'wrestle', 'grapple', 'lift', 'force', 'break',
                   'push', 'tackle', 'run')),
    ('deception', ('lie', 'bluff', 'deceive', 'disguise', 'pretend', 'con ')),
    ('intimidation', ('intimidate', 'threaten', 'stare down', 'menace', 'scare')),
    ('persuasion', ('persuade', 'convince', 'charm', 'haggle', 'bargain', 'negotiate', 'beg', 'flatter', 'plead',
                    'talk them', 'talk him', 'talk her', 'talk my way', 'sweet-talk', 'seduce', 'flirt')),
    ('performance', ('perform', 'sing', 'dance', 'play the', 'recite', 'taunt')),
    ('insight', ('read his', 'read her', 'read their', 'tell if', 'sense', 'motive', 'lying to me')),
    ('perception', ('notice', 'spot', 'listen', 'look out', 'keep watch', 'hear')),
    ('investigation', ('search', 'examine', 'investigate', 'deduce', 'figure out', 'study', 'inspect')),
    ('medicine', ('treat', 'patch', 'bandage', 'stitch', 'heal', 'stabilize', 'diagnose')),
    ('survival', ('track', 'forage', 'hunt', 'find the way', 'navigate', 'find our way', 'find my way')),
    ('animal-handling', ('calm the horse', 'calm the dog', 'ride', 'tame', 'soothe the')),
    ('arcana', ('magic', 'spell', 'rune', 'arcane', 'ward', 'enchant')),
    ('religion', ('pray', 'god', 'rite', 'holy', 'shrine')),
    ('history', ('recall', 'remember', 'history', 'legend')),
    ('nature', ('plant', 'herb', 'weather', 'beast')),
)
# The save that resists what an approach stands up to (fear and pain with Resolve, a blow with Vitality).
SAVE_EQUIVALENT = {'Mind': 'int', 'Allure': 'cha', 'Resolve': 'wis', 'Vitality': 'con', 'Essence': None, 'Luck': 'dex'}
UNARMORED = {'barbarian': 'con', 'monk': 'wis'}


@cache
def pack(name: str) -> list | dict:
    return json.loads((PACK / f'{name}.json').read_text(encoding='utf-8'))


def by_id(name: str) -> dict[str, dict]:
    return {item['id']: item for item in pack(name)}


def skills() -> dict[str, dict]:
    return {skill['id']: skill for skill in pack('rules')['skills']}


def skill_id(name: str) -> str:
    return name.strip().lower().replace(' ', '-')


def attribution() -> str:
    return pack('pack')['license']['attribution']


def modifier(score: int) -> int:
    return (score - 10) // 2


def proficiency(level: int) -> int:
    return 2 + (max(1, level) - 1) // 4


def signed(value: int) -> str:
    return f'+{value}' if value >= 0 else str(value)


# The sheet --------------------------------------------------------------------------------------------------

def spell_ability(class_id: str) -> str | None:
    found = by_id('classes').get(class_id, {}).get('spellcasting')
    return found.get('ability') if isinstance(found, dict) else None


def armor_class(class_id: str, scores: dict[str, int]) -> int:
    extra = UNARMORED.get(class_id)
    return 10 + modifier(scores['dex']) + (modifier(scores[extra]) if extra else 0)


def with_background(scores: dict[str, int], background: dict) -> dict[str, int]:
    """The background's +2 to the best of its three abilities as placed, +1 to the next (2024 rules)."""
    ranked = sorted(background['ability_scores'], key=lambda ability: (-scores[ability], ABILITIES.index(ability)))
    raised = dict(scores)
    raised[ranked[0]] += 2
    raised[ranked[1]] += 1
    return {ability: min(20, value) for ability, value in raised.items()}


def build(class_id: str, species_id: str, background_id: str, scores: dict[str, int], picks: list[str]) -> dict:
    """A level 1 character from the pack. `scores` places the standard array; `picks` are the class's skills."""
    from dungeon.errors import require
    classes, species, backgrounds = by_id('classes'), by_id('species'), by_id('backgrounds')
    require(class_id in classes, 'That class is not in the 5E pack.', 422)
    require(species_id in species, 'That species is not in the 5E pack.', 422)
    require(background_id in backgrounds, 'That background is not in the 5E pack.', 422)
    require(set(scores) == set(ABILITIES) and sorted(scores.values(), reverse=True) == list(STANDARD_ARRAY),
            'Place the standard array (15, 14, 13, 12, 10, 8) on the six abilities, one each.', 422)
    chosen, background = classes[class_id], backgrounds[background_id]
    from_background = [skill_id(name) for name in background['skill_proficiencies']]
    allowed = {skill_id(name) for name in chosen['skill_choices']['from']} - set(from_background)
    picks = list(dict.fromkeys(skill_id(name) for name in picks))
    require(len(picks) == chosen['skill_choices']['count'] and set(picks) <= allowed,
            f"Pick {chosen['skill_choices']['count']} of the {chosen['name']}'s skills the background doesn't give.", 422)
    final = with_background(scores, background)
    hp = chosen['hit_die'] + modifier(final['con'])
    return {'class': class_id, 'species': species_id, 'background': background_id, 'level': 1, 'xp': 0,
            'abilities': final, 'skills': sorted(set(from_background) | set(picks)), 'saves': chosen['saving_throws'],
            'max_hp': max(1, hp), 'hp': max(1, hp), 'ac': armor_class(class_id, final),
            'speed': species[species_id]['speed'], 'spell_ability': spell_ability(class_id)}


def suggested(class_id: str, background_id: str) -> dict:
    """A quick build: the standard array on the class's primary abilities first, the class's first skills."""
    chosen, background = by_id('classes')[class_id], by_id('backgrounds')[background_id]
    primary = [ability for ability, name in ABILITY_NAMES.items() if name in chosen['primary_ability']]
    order = primary + [ability for ability in ('con', 'dex', 'wis', 'str', 'cha', 'int') if ability not in primary]
    scores = dict(zip(order, STANDARD_ARRAY))
    taken = {skill_id(name) for name in background['skill_proficiencies']}
    picks = [skill_id(name) for name in chosen['skill_choices']['from'] if skill_id(name) not in taken]
    return {'scores': scores, 'picks': picks[:chosen['skill_choices']['count']]}


def view(sheet: dict) -> dict:
    """The sheet as the screen shows it: names, modifiers, every skill's bonus and the attribution."""
    bonus = proficiency(sheet['level'])
    names = {'class': by_id('classes')[sheet['class']]['name'], 'species': by_id('species')[sheet['species']]['name'],
             'background': by_id('backgrounds')[sheet['background']]['name']}
    return {'ruleset': ID, 'ruleset_name': NAME, **sheet, 'names': names, 'proficiency': bonus,
            'modifiers': {ability: modifier(score) for ability, score in sheet['abilities'].items()},
            'skill_bonuses': {skill['id']: {'name': skill['name'], 'ability': skill['ability'],
                                            'bonus': modifier(sheet['abilities'][skill['ability']])
                                            + (bonus if skill['id'] in sheet['skills'] else 0),
                                            'proficient': skill['id'] in sheet['skills']}
                              for skill in pack('rules')['skills']},
            'attribution': attribution()}


def described(sheet: dict) -> str:
    """The character in a line, for the narrator."""
    view_names = view(sheet)['names']
    strong = [ABILITY_NAMES[ability] for ability, score in sheet['abilities'].items() if score >= 15]
    weak = [ABILITY_NAMES[ability] for ability, score in sheet['abilities'].items() if score <= 9]
    return (f"A level {sheet['level']} {view_names['species']} {view_names['class']} ({view_names['background']})"
            + (f"; strong in {', '.join(strong)}" if strong else '') + (f"; weak in {', '.join(weak)}" if weak else '')
            + '.')


# Checks -----------------------------------------------------------------------------------------------------

def skill_for(text: str) -> str | None:
    lowered = text.lower()
    return next((skill for skill, words in SKILL_WORDS if any(re.search(rf'\b{re.escape(word)}', lowered)
                                                                for word in words)), None)


def read(sheet: dict, approach: str, text: str) -> tuple[str | None, str]:
    """The skill an action uses (None for a plain ability check) and its ability."""
    skill = skill_for(text)
    if skill:
        return skill, skills()[skill]['ability']
    return None, EQUIVALENT.get(approach) or sheet.get('spell_ability') or 'wis'


def d20(rng: random.Random, edge: str = '') -> tuple[int, list[int]]:
    rolls = [rng.randint(1, 20)] + ([rng.randint(1, 20)] if edge in ('advantage', 'disadvantage') else [])
    return (max(rolls) if edge == 'advantage' else min(rolls) if edge == 'disadvantage' else rolls[0]), rolls


def check(sheet: dict, approach: str, difficulty: str, text: str = '', rng: random.Random | None = None,
          save: bool = False, edge: str = '') -> dict:
    """An ability check (or a saving throw) against the DC for the difficulty, pass or fail as written."""
    rng = rng or random.SystemRandom()
    skill, ability = (None, SAVE_EQUIVALENT.get(approach) or sheet.get('spell_ability') or 'wis') if save else \
        read(sheet, approach, text)
    proficient = (ability in sheet['saves']) if save else (skill in sheet['skills'])
    bonus = modifier(sheet['abilities'][ability]) + (proficiency(sheet['level']) if proficient else 0)
    natural, rolls = d20(rng, edge)
    dc = DCS.get(difficulty, DCS['normal'])
    total = natural + bonus
    label = (skills()[skill]['name'] if skill else ABILITY_NAMES[ability]) + (' save' if save else '')
    return {'natural': natural, 'die': 20, 'bonus': bonus, 'shift': 0, 'total': total, 'target': dc,
            'skill': label, 'ability': ability, 'rolls': rolls,
            'band': 'success' if total >= dc else 'failure'}
