"""Vallarith's factions in play (dungeon/factions.py, docs/story.md "Factions"): the powers with a hand on the travel
map, from the world package (worlds/vallarith/factions.json), with the clocks they run in the Post-Reform era and what
happens when each fills. Run `python scripts/world/vallarith_factions.py` to rewrite
dungeon/world/data/factions/vallarith.json.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT.parent / 'worlds' / 'vallarith' / 'factions.json'
TRAVEL = ROOT / 'dungeon' / 'world' / 'data' / 'travel' / 'vallarith.json'
OUT = ROOT / 'dungeon' / 'world' / 'data' / 'factions' / 'vallarith.json'
# Chance in 100 that a clock moves on a given story day.
PACE = 25
# Where a faction has a hand beyond what the package says it holds (the Guild runs Kingswood's work).
HOLDS = {'cyrel-timber-guild': ['kingswood', 'cyrel'], 'brynwyr-high-elves': ['brynwyr', 'kingswood']}
# The clocks each faction runs here, Post-Reform: (name, segments, what happens when it fills).
CLOCKS = {
    'kingdom-of-cyrel': [
        ('War levy', 4, "Cyrel's war levy reaches the sister towns: every household gives a son to Bastion or pays "
                        'three crowns, and the crimps are out on the roads for those who run.'),
        ('Retake Adlmyr', 8, "Cyrel's army storms Adlmyr and takes the fallen walls back from the Unguruk. The road "
                             'through the Badlands is Cyrel\'s again, for now, and the graves outside Bastion are new.'),
    ],
    'kingdom-of-asania': [
        ('Push across the Cyrel border', 6, "Asania's army crosses the border on the lake road. Eriane burns, and "
                                            'refugees choke the Cyrel road all the way to Kingswood.'),
    ],
    'cyrel-timber-guild': [
        ('Buy out the sawmill', 6, "The Timber Guild buys Kingswood's sawmill outright. Wages drop by a fifth the same "
                                   'week, and the men who complain are not taken on again.'),
    ],
    'brynwyr-high-elves': [
        ('Move the border stones', 6, 'The wardens of Brynwyr move the border stones a mile toward Kingswood in one '
                                      'night, and shoot anyone who tries to move them back.'),
    ],
    'unguruk-tribe': [
        ('Siege works at Adlmyr', 6, 'The Unguruk finish their works at Adlmyr and start raiding past the ward-keep. '
                                     'Smoke rises from the farms on the Kingswood road.'),
    ],
    'mossrun-expedition': [
        ('The Deep Nine reaches what it is digging toward', 8,
         'The Deep Nine breaks into something old under Mossrun. The shaft is sealed with the night shift still in it, '
         'and the miners who came up will not say what they heard.'),
    ],
}


def slug(name: str) -> str:
    return ''.join(ch if ch.isalnum() else '-' for ch in name.lower()).strip('-').replace('--', '-')


def build() -> dict:
    nodes = {node['id'] for node in json.loads(TRAVEL.read_text(encoding='utf-8'))['nodes']}
    factions = {item['id']: item for item in json.loads(SOURCE.read_text(encoding='utf-8'))['factions']}
    result = []
    for faction_id, clocks in CLOCKS.items():
        item = factions[faction_id]
        holds = HOLDS.get(faction_id) or [node for node in item.get('holds') or [] if node in nodes]
        result.append({
            'id': faction_id, 'name': item['name'], 'kind': item['kind'], 'summary': item['summary'],
            'goals': item.get('goals', []), 'holds': holds,
            'rivals': [other for other in item.get('rivals', []) if other in CLOCKS],
            'allies': [other for other in item.get('allies', []) if other in CLOCKS],
            'clocks': [{'id': slug(name), 'name': name, 'segments': segments, 'done': done}
                       for name, segments, done in clocks]})
    return {'about': 'Built by scripts/world/vallarith_factions.py from worlds/vallarith/factions.json.',
            'world': 'vallarith', 'pace': PACE, 'factions': result}


FACTIONS = build()

if __name__ == '__main__':
    OUT.write_text(json.dumps(FACTIONS, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Wrote {OUT}')
