"""Ironsworn (docs/requirements.md "Rulesets"; content in dungeon/rules/packs/ironsworn, under CC-BY-4.0).

- **The sheet.** Five stats (edge, heart, iron, shadow, wits) taking 3, 2, 2, 1 and 1; health, spirit and supply
  from 0 to 5, all at 5 to start; momentum from -6 to 10, starting at 2 and reset to 2; three assets from the pack
  (paths, companions, combat talents, rituals). Debilities lower the momentum ceiling and reset as written.
- **A move** is read from the action's words ("search the camp" is Gather Information, "talk him round" Compel),
  else it is Face Danger. Its stat comes from the move and the words (sneaking and lying are shadow), else the
  Referee's approach (EQUIVALENT).
- **The action roll:** a d6 plus the stat (plus an add for an easy action, minus for a hard one: Ironsworn has no
  DCs, so the Referee's difficulty becomes an add or a penalty), at most 10, against two d10 challenge dice. Beating
  both is a strong hit, one a weak hit, neither a miss; matching challenge dice make a strong hit or a miss
  dramatic. On the shared ladder: strong hit success (with a match, critical), weak hit a success with a cost, miss
  a failure (with a match, critical).
- **Momentum** is burned by code when it beats a challenge die the roll did not: the result improves and momentum
  resets. Negative momentum cancels an action die that equals it. A strong hit or weak hit on the moves that say so
  takes momentum (MOMENTUM).
"""
import json
import random
import re
from functools import cache
from pathlib import Path

ID = 'ironsworn'
NAME = 'Ironsworn'
PACK = Path(__file__).parent / 'packs' / 'ironsworn'
STATS = ('edge', 'heart', 'iron', 'shadow', 'wits')
ARRAY = (3, 2, 2, 1, 1)
METERS = ('health', 'spirit', 'supply')
MOMENTUM_START, MOMENTUM_MAX, MOMENTUM_MIN = 2, 10, -6
ASSETS = 3
# The Referee's difficulty as an add (Ironsworn has no DCs).
ADDS = {'easy': 1, 'normal': 0, 'hard': -1, 'very_hard': -2, 'extreme': -3}
# The stat an approach leans on when the words name none.
EQUIVALENT = {'Mind': 'wits', 'Allure': 'heart', 'Resolve': 'heart', 'Vitality': 'iron', 'Essence': 'wits',
              'Luck': 'edge'}
# Moves by the words of an action, the more specific first: (move, words, stat or None for the approach's).
MOVE_WORDS = (
    ('heal', ('treat', 'bandage', 'stitch', 'patch up', 'heal', 'tend the wound', 'tend his', 'tend her'), 'wits'),
    ('resupply', ('forage', 'hunt for', 'scavenge', 'gather food', 'fish', 'trap'), 'wits'),
    ('make_camp', ('make camp', 'set up camp', 'pitch camp'), None),
    ('gather_information', ('search', 'investigate', 'examine', 'ask around', 'track', 'study', 'inspect',
                            'look for clues', 'find out'), 'wits'),
    ('secure_an_advantage', ('prepare', 'scout', 'size up', 'assess', 'get ready', 'set an ambush', 'take cover',
                             'circle', 'wait for'), None),
    ('compel', ('persuade', 'convince', 'talk him', 'talk her', 'talk them', 'haggle', 'bargain', 'negotiate',
                'threaten', 'intimidate', 'lie to', 'bluff', 'charm', 'beg', 'demand'), 'heart'),
)
# Words that set the stat whatever the move: (stat, words).
STAT_WORDS = (
    ('shadow', ('sneak', 'hide', 'lie', 'bluff', 'deceive', 'steal', 'pickpocket', 'trick', 'creep', 'unseen')),
    ('iron', ('threaten', 'intimidate', 'force', 'break', 'lift', 'shove', 'endure', 'climb')),
    ('edge', ('dodge', 'run', 'leap', 'jump', 'quick', 'shoot', 'throw', 'balance', 'ride')),
)
# Momentum a move gives on a hit: {move: (strong, weak)}.
MOMENTUM = {'face_danger': (1, 0), 'secure_an_advantage': (2, 1), 'gather_information': (2, 1), 'compel': (1, 0),
            'make_camp': (0, 0), 'heal': (0, 0), 'resupply': (0, 0)}


@cache
def pack() -> dict:
    return json.loads((PACK / 'classic.json').read_text(encoding='utf-8'))


@cache
def manifest() -> dict:
    return json.loads((PACK / 'pack.json').read_text(encoding='utf-8'))


def attribution() -> str:
    return manifest()['license']['attribution']


def moves() -> dict[str, dict]:
    return {key: move for category in pack()['moves'].values() for key, move in category['contents'].items()}


def assets() -> dict[str, dict]:
    """Every asset by id ('path/alchemist'), with its category."""
    return {f'{category}/{key}': asset | {'category_id': category}
            for category, group in pack()['assets'].items() for key, asset in group['contents'].items()}


def plain(text: str) -> str:
    """Datasworn Markdown as plain text: links and emphasis dropped."""
    return re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text).replace('__', '').replace('*', '')


# The sheet --------------------------------------------------------------------------------------------------

def build(stats: dict[str, int], picks: list[str]) -> dict:
    """A new character: the array placed on the five stats, three assets."""
    from dungeon.errors import require
    require(set(stats) == set(STATS) and sorted(stats.values(), reverse=True) == list(ARRAY),
            'Place 3, 2, 2, 1 and 1 on edge, heart, iron, shadow and wits, one each.', 422)
    picks = list(dict.fromkeys(picks))
    require(len(picks) == ASSETS and all(pick in assets() for pick in picks),
            f'Choose {ASSETS} assets from the Ironsworn pack.', 422)
    return {'stats': dict(stats), 'health': 5, 'spirit': 5, 'supply': 5, 'momentum': MOMENTUM_START,
            'debilities': [], 'assets': picks, 'xp': 0}


def suggested(top: str) -> dict:
    """A quick build leaning on one stat: it takes the 3, then the next stats in order; assets that fit it."""
    order = [top] + [stat for stat in ('iron', 'wits', 'heart', 'edge', 'shadow') if stat != top]
    stats = dict(zip(order, ARRAY))
    fitting = {'iron': ['combat_talent/swordmaster', 'path/veteran', 'companion/hound'],
               'edge': ['combat_talent/archer', 'path/wayfinder', 'companion/hawk'],
               'heart': ['path/loyalist', 'path/devotant', 'companion/horse'],
               'shadow': ['path/infiltrator', 'combat_talent/cutthroat', 'path/trickster'],
               'wits': ['path/lorekeeper', 'path/herbalist', 'ritual/divination']}[top]
    return {'stats': stats, 'assets': [asset for asset in fitting if asset in assets()][:ASSETS]}


def momentum_max(sheet: dict) -> int:
    return MOMENTUM_MAX - len(sheet.get('debilities', []))


def momentum_reset(sheet: dict) -> int:
    return {0: 2, 1: 1}.get(len(sheet.get('debilities', [])), 0)


def view(sheet: dict) -> dict:
    found = assets()
    return {'ruleset': ID, 'ruleset_name': NAME, **sheet, 'momentum_max': momentum_max(sheet),
            'momentum_reset': momentum_reset(sheet),
            'asset_list': [{'id': asset, 'name': found[asset]['name'], 'category': found[asset]['category'],
                            'abilities': [plain(ability['text']) for ability in found[asset]['abilities']
                                          if ability.get('enabled')]}
                           for asset in sheet['assets'] if asset in found],
            'attribution': attribution()}


def described(sheet: dict) -> str:
    """The character in a line, for the narrator."""
    strong = [stat for stat, value in sheet['stats'].items() if value >= 3]
    weak = [stat for stat, value in sheet['stats'].items() if value <= 1]
    names = [assets()[asset]['name'] for asset in sheet['assets'] if asset in assets()]
    return (f"An Ironsworn: strong in {', '.join(strong)}; weak in {', '.join(weak)}; "
            f"{', '.join(names)}. Health {sheet['health']}, spirit {sheet['spirit']}, supply {sheet['supply']}.")


# Moves and the action roll ----------------------------------------------------------------------------------

def found_in(text: str, words) -> bool:
    lowered = text.lower()
    return any(re.search(rf'\b{re.escape(word)}', lowered) for word in words)


def read(approach: str, text: str) -> tuple[str, str]:
    """The move an action makes and the stat it rolls."""
    move, stat = next(((move, stat) for move, words, stat in MOVE_WORDS if found_in(text, words)),
                      ('face_danger', None))
    named = next((stat for stat, words in STAT_WORDS if found_in(text, words)), None)
    if stat is None or (move == 'compel' and named in ('shadow', 'iron')):
        stat = named or EQUIVALENT.get(approach, 'wits')
    return move, stat


def outcome(score: int, challenge: list[int]) -> str:
    beaten = sum(score > die for die in challenge)
    match = challenge[0] == challenge[1]
    if beaten == 2:
        return 'critical_success' if match else 'success'
    if beaten == 1:
        return 'success_cost'
    return 'critical_failure' if match else 'failure'


def roll(sheet: dict, approach: str, difficulty: str, text: str = '', rng: random.Random | None = None,
         stat: str | None = None, move: str | None = None) -> dict:
    """An action roll for a move, with momentum burned when it helps. Returns the roll and the sheet's new momentum
    under `momentum` (the caller saves it)."""
    rng = rng or random.SystemRandom()
    read_move, read_stat = read(approach, text)
    move, stat = move or read_move, stat or read_stat
    action = rng.randint(1, 6)
    challenge = [rng.randint(1, 10), rng.randint(1, 10)]
    momentum = sheet['momentum']
    cancelled = momentum < 0 and action == -momentum
    bonus = sheet['stats'][stat] + ADDS.get(difficulty, 0)
    score = min(10, (0 if cancelled else action) + bonus)
    band = outcome(score, challenge)
    burned = False
    if momentum > 0 and outcome(momentum, challenge) != band and \
            sum(momentum > die for die in challenge) > sum(score > die for die in challenge):
        band, burned, momentum = outcome(momentum, challenge), True, momentum_reset(sheet)
    strong, weak = MOMENTUM.get(move, (0, 0))
    gained = strong if band in ('success', 'critical_success') else weak if band == 'success_cost' else 0
    momentum = max(MOMENTUM_MIN, min(momentum_max(sheet), momentum + gained))
    name = moves()[move]['name'] if move in moves() else move.replace('_', ' ').title()
    return {'natural': action, 'die': 6, 'bonus': bonus, 'shift': 0, 'total': momentum if burned else score,
            'target': None, 'skill': f"{name} +{stat} vs {challenge[0]} and {challenge[1]}"
                                     + (' (momentum burned)' if burned else ''),
            'ability': stat, 'rolls': [action, *challenge], 'move': move, 'band': band, 'momentum': momentum}
