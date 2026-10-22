"""Jobs from factions' needs (requirements "Quests and factions"; docs/story.md "Jobs and oaths").

Each faction in play lists the jobs it needs done in the towns it holds (world/data/factions/<world>.json `jobs`).
On a day in town, while a faction holding the town has no job open, it may offer one (OFFER in 100): a quest of the
job's own, known to the character, with its deadline on the story clock, its pay in the town's day wages and the
standing it earns. Whether it is done is the Continuity model's call, as for any quest (dungeon/quests.py); a job
that lapses costs nothing but what happens, one failed costs standing. Each job carries the loose ends it leaves
(`ties`) for the story director.
"""
import random
from datetime import datetime, timedelta

from dungeon import factions, inventory, quests
from dungeon.database import many

OFFER = 50


def offer(connection, world: str, node_id: str, city_id: str, wage: int, currency: dict, now: datetime,
          rng=None) -> list[str]:
    """A job a faction holding the town may offer today; the line that tells the narrator."""
    if not factions.ACTIVE:
        return []
    rng = rng or random.SystemRandom()
    rows = many(connection, "SELECT faction_id, title, status FROM story_quests WHERE kind='job'")
    busy = {row['faction_id'] for row in rows if row['status'] == 'open'}
    offered = {(row['faction_id'], row['title']) for row in rows}
    open_jobs = [(faction, job) for faction in factions.local(world, node_id) if faction['id'] not in busy
                 for job in faction.get('jobs', []) if (faction['id'], job['title']) not in offered]
    if not open_jobs or rng.randint(1, 100) > OFFER:
        return []
    faction, job = rng.choice(open_jobs)
    pay = job['wages'] * wage
    quests.create(connection, 'job', city_id, job['title'], job['hook'], job['truth'], job['missed'],
                  (now + timedelta(days=job['days'])).isoformat(), faction_id=faction['id'], giver=job['giver'],
                  reward=pay, standing=job['standing'], ties=job['ties'])
    return [f"Work is going: {job['giver']} ({faction['name']}) wants it done within {job['days']} days, for "
            f"{inventory.money_text(pay, currency)}: {job['hook']}"]
