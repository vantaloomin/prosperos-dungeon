"""The Referee (docs/requirements.md "Turn loop" and "Referee model"): splits the player's intent into actions and
decides, for each, whether it needs a roll, which MARVEL stat and how hard it is. Code then rolls.

A text model does it when one is chosen for the Referee job in Settings > Models; it answers in JSON and anything
it gets wrong is dropped. Without one, or when its answer cannot be read, keyword rules decide. The narrator's own
model is never borrowed for this, so a turn costs one narrator call unless the player asks for more.
"""
import json
import re

from dungeon.providers.scheduling import CONVERSATION
from dungeon.rules import marvel
from dungeon.text_models import config_for, key_for, routes

JOB = 'referee'
MOST_ACTIONS = 4

# Words that make an action uncertain, and the stat they test. The first stat with a match wins, so the more
# specific lists come first.
KEYWORDS = (
    ('Essence', ('cast', 'spell', 'magic', 'pray', 'ritual', 'channel', 'enchant', 'curse', 'ward', 'hex', 'summon',
                 'bless', 'heal')),
    ('Allure', ('persuade', 'convince', 'charm', 'flirt', 'seduce', 'lie', 'bluff', 'haggle', 'bargain', 'deceive',
                'perform', 'sing', 'negotiate', 'beg', 'taunt', 'flatter', 'talk them', 'talk him', 'talk her',
                'talk the', 'talk my way', 'talk our way', 'sweet-talk')),
    ('Resolve', ('resist', 'withstand', 'intimidate', 'stare down', 'refuse to', 'hold my ground', 'keep calm',
                 'steady', 'endure the', 'threaten', 'command')),
    ('Vitality', ('attack', 'hit', 'punch', 'strike', 'fight', 'swing', 'stab', 'slash', 'shoot', 'lift', 'shove',
                  'push', 'run', 'climb', 'jump', 'leap', 'wrestle', 'grab', 'tackle', 'kick', 'break', 'force',
                  'swim', 'chase', 'flee', 'dodge', 'block', 'parry', 'carry')),
    ('Mind', ('search', 'examine', 'study', 'recall', 'remember', 'notice', 'spot', 'investigate', 'deduce',
              'figure out', 'pick the lock', 'pick a lock', 'track', 'listen', 'read the', 'decipher', 'steal',
              'pickpocket', 'forge', 'repair', 'treat the', 'patch')),
    ('Luck', ('sneak', 'hide', 'gamble', 'bet', 'guess', 'hope', 'slip past', 'luck')),
)

SYSTEM = f"""You are the Referee of a tabletop roleplaying game. You never write story. Read the player's turn and \
split it into the separate things their character tries to do, at most {MOST_ACTIONS}. For each one decide whether \
the outcome is uncertain enough to need a roll (talking, looking around, walking somewhere or ordinary actions do \
not), which stat it tests and how hard it is.

Stats: Mind (reason, perception, knowledge, skill with the hands), Allure (charm, persuasion, deception, \
performance), Resolve (will, nerve, intimidation, resisting pain or influence), Vitality (strength, speed, \
fighting, endurance), Essence (magic, faith, the uncanny), Luck (chance, stealth, timing).
Difficulty: easy, normal, hard, very_hard or extreme.

Answer with JSON only, in this shape:
{{"actions": [{{"action": "what they try, in a few words", "roll": true, "stat": "Vitality", "difficulty": "hard"}}]}}"""


def sentences(text: str) -> list[str]:
    parts = re.split(r'(?<=[.!?])\s+|\s+(?:and then|then)\s+', text.strip(), flags=re.I)
    parts = [re.sub(r'^(?:and then|then|and)\s+', '', part.strip(' .!?'), flags=re.I) for part in parts]
    return [part for part in parts if part]


def stat_for(text: str) -> str | None:
    lowered = text.lower()
    for stat, words in KEYWORDS:
        if any(re.search(rf'\b{re.escape(word)}', lowered) for word in words):
            return stat
    return None


def by_keywords(text: str) -> list[dict]:
    """The rules with no model: each sentence that names something uncertain is an action at normal difficulty."""
    actions = []
    for part in sentences(text):
        stat = stat_for(part)
        if stat:
            actions.append({'action': part, 'roll': True, 'stat': stat, 'difficulty': 'normal', 'said': True})
    return actions[:MOST_ACTIONS]


def checked(answer: str) -> list[dict] | None:
    """The model's actions, keeping only well-formed ones; None when nothing in the answer can be read."""
    match = re.search(r'\{.*\}', answer, re.S)
    try:
        data = json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        return None
    items = data.get('actions') if isinstance(data, dict) else None
    if not isinstance(items, list):
        return None
    actions = []
    for item in items[:MOST_ACTIONS]:
        if not isinstance(item, dict) or not str(item.get('action') or '').strip():
            continue
        action = str(item['action']).strip()[:200]
        if item.get('roll') and item.get('stat') in marvel.STATS:
            difficulty = item.get('difficulty') if item.get('difficulty') in marvel.DIFFICULTIES else 'normal'
            actions.append({'action': action, 'roll': True, 'stat': item['stat'], 'difficulty': difficulty})
    return actions


def own_model(connection) -> dict | None:
    """The Referee's model, only when the player chose one for the job."""
    return config_for(connection, JOB) if routes(connection).get(JOB) else None


async def decide(state, text: str, config: dict | None) -> list[dict]:
    """The rolled actions of one turn, from the Referee's model when there is one, else from the keyword rules."""
    if config is not None:
        try:
            async with state.scheduler.reserve(config, CONVERSATION):
                answer = ''.join([chunk.text async for chunk in state.provider.stream(
                    config, key_for(state.vault, config), SYSTEM, [{'role': 'user', 'content': text}])])
        except Exception:  # noqa: BLE001 - a Referee that fails falls back to the rules; the turn goes on.
            answer = ''
        actions = checked(answer)
        if actions is not None:
            return actions
    return by_keywords(text)
