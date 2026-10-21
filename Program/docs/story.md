# Story

The **Story** is the app's home screen: the user plays their persona in one of the cities, and a narrator
describes the place and voices the people there. Since Milestone 0 it is the whole app; the dice, the rulesets
and the rest of the game are built on it from Milestone 1 ([the roadmap](../../docs/roadmap.md)).

## Who decides what

The app decides the scene (`dungeon/story.py`):

- **Where:** the city and place the user picked under "Go somewhere else…". A new story starts in Kingswood,
  the slice town, at its tavern or another opening place. Moving adds a line to the story
  ("You arrive at …") that the narrator sees as a note.
- **When:** the story clock (`dungeon/story_clock.py`), in the city's own timezone. It starts at campaign start
  and moves with what the player does: 5 minutes for talk, 10 for a rolled action, 30 for a walk somewhere, the
  hours they say for "I wait two hours", 8 hours for a night's sleep, 20 minutes to cross town and 6 hours to
  reach another city. Out-of-character lines take no time. A story with no campaign start runs on the app clock
  (debug time included), as Companion's did. The clock is branched with the story.
- **Weather:** the city's typical weather for the date (`generators.conditions`).
- **Who is there:** the townsfolk rules at that moment (`story.present`): people seeded at the place and
  residents whose routines bring them there. Each world's town has its own seed (`persona.town_seed`), so the
  same streets hold different people in different worlds.

The narrator model only voices the scene. Its prompt is built in layers (`dungeon/narration/prompt.py`):
"The Story narrator" and "The narrator's writing rules" in Settings > Advanced ([prompts.md](prompts.md)),
the narration format (second person, present tense, short turns), the intensity, then a `## Scene` section
with the facts above. After each reply, `dungeon/narration/prose.py` removes em dashes and asks the model for
one rewrite when the reply has the strongest AI tells (see "Narrator prompting" in the top-level
docs/requirements.md). The narrator gets the names of the people present, with a rule not to use a name until
that person gives it. The screen lists them only as the user would see them ("the barista", "a regular").

The narrator stays in the story. Sentences saying it is an AI are dropped (`in_character.Guard`), and OOC: or
((…)) gets a plain answer. Its model is the **Story narrator** job in Settings > Models.

## Campaign start

A new story opens on "Who are you?" (`dungeon/campaign.py`). The player picks one of the town's premade characters
(`dungeon/world/data/premades/<city>.json`; Kingswood and Haddon Harbor ship three each) or makes their own: a name, gender, age, a
few lines about them, and MARVEL stats bought from 60 points, each from 4 to 18. Either way the world's persona takes
on that name and those lines, the stats go on the sheet, and the story opens with "You arrive at …".

The narrator gets the persona in its own layer, "The player's character": their name, what the player wrote, and
what their stats make them good and poor at (14 and up, 7 and down), in words, never numbers. It is told to voice
them from what is there and invent nothing about their past.

## The turn loop

Each line the user sends is one turn (`dungeon/turn.py`). Code settles what happens before the narrator writes:

1. **The Referee** (`dungeon/referee.py`) splits the line into the things the character tries, at most four, and
   decides for each whether the outcome is uncertain, which MARVEL stat it tests and how hard it is. A text model
   does this only when one is chosen for the **Referee** job in Settings > Models; it answers in JSON and
   anything malformed is dropped. Without one, or when its answer cannot be read, keyword rules decide (each
   sentence naming something risky, at normal difficulty). Talking, looking around and OOC lines roll nothing.
2. **The roll** (`dungeon/rules/marvel.py`): d100 plus the stat's die, minus the difficulty shift (easy −10,
   normal 0, hard +10, very hard +20, extreme +30). The stat die is d4 below 8, d6 from 8, d8 from 10, d10 from
   12 and d12 from 14. A natural 10 or less is a critical failure; otherwise the total lands on the ladder
   (`dungeon/rules/ladder.py`): 30 or less fails, 31 to 50 fails with an upside, 51 to 70 succeeds at a cost,
   71 to 89 succeeds, 90 or more is a critical success.
3. **The narrator** gets each outcome as a fact to honour, never the numbers, and writes the turn.

Rolls are saved with the user's line (table `story_rolls`), so sending it again or "Tell it again" keeps the same
dice. The character's six stats (table `character_stats`, 1 to 30, 10 to start) are set under "Your character" on
the Story screen. "Show the dice" in Settings > World shows each roll under the user's line; off, rolls stay
hidden and the story reads the same.

## The ledger and the story so far

The ledger (`dungeon/ledger.py`, table `ledger_entries`) is what the game holds true: deaths, items, wounds,
promises, places, secrets, relationships and other facts, each marked as world truth (hidden from the player's
character), the character's belief, or both. Code records the facts it decides. After each narration the
**Continuity** model, when one is chosen for that job in Settings > Models, lists the new lasting facts in JSON;
code keeps the well-formed ones and refuses any about someone the ledger says is dead. "Tell it again" drops the
old reply's facts with it. The narrator gets the record every turn (every death and promise, then the newest of the
rest, 40 in all), with hidden truth marked as hidden, and is told never to contradict it.

"What you know" on the Story screen is the player's journal: every fact their character knows. They can correct or
remove one, or add their own note; each correction is logged in `ledger_corrections`. Hidden truth never shows here.

The narrator reads the latest messages word for word. Once 30 recent ones plus 20 more are waiting, the oldest 20 are
folded into one rolling summary (`story_summary`) by the Continuity model, or the Default one without it, and the
narrator gets that summary as "The story so far" in their place. The ledger and the summary are branched with the
story.

## What is happening

A town's adventure file (`dungeon/world/data/adventures/<city>.json`, `dungeon/quests.py`) lists its quests and its
dangerous places. Kingswood ships "The Heartwood contract" and a hidden one, "The wardens' eyes".

- **Quests** start with the story (campaign start), each with a hook, a hidden truth and a deadline in days of story
  time. The narrator gets "What is happening" every turn: each open quest, its truth, how long is left and whether
  the character knows of it yet. It lets them press on the scene and never ends one itself.
- **Deadlines** are code's: when the story clock passes one with the quest still open, the quest is missed, its
  stakes go in the ledger, and the narrator is told it is over.
- **Ending a quest:** with a Continuity model chosen, its question after each turn lists the open quests, and it may
  answer that the turn settled one (done or failed, with a sentence). Unknown ids are ignored.
- **Dangerous places:** each turn in one adds a Luck roll at the place's difficulty to the turn's rolls (shown with
  the dice, like any other). On a failure, the place's threat comes with the outcome for the narrator to write.
- The player's journal ("What you know") shows the quests they know of and the time left. Quests branch with the
  story.

## Going back

Every line the player sends is a save point (`dungeon/timeline.py`): the game state as the line arrives (the scene,
the people met, the sheet, the ledger and the summary: the tables in `timeline.SAVED`) is kept in `story_saves`. "Go back here" under any of
the player's lines starts a new branch from just before it, puts that state back and returns the line to the
composer to send again. Nothing is rolled until it is sent, so the dice are always new.

The branch left behind is kept with its state (`story_branches.tip`) and listed under "Other branches", where
"Play this branch" picks it up where it was left. Messages carry their `branch_id` (the first branch is `first`); a
branch shows its parent's messages before the line it went back to, then its own, and the narrator sees only those.
"Tell it again" works on lines of the branch being played; a shared line keeps the reply it was told. A system that
keeps game state adds its tables to `timeline.SAVED`.

## API

| Request | Does |
| --- | --- |
| `GET /api/story` | `{scene, messages, people, ready, dice_shown, branches}`. `branches` lists every branch with `playing`, `turns`, `last_line` and `last_at`, the one being played first. User messages carry their `rolls` while the dice are shown. `people` are those met, newest first, with `meetings`, `notes`, `doing` and `place` now. `scene` has the city, place, `local_time` (city clock, no offset), `weather`, the city's `places` and `around` (who is there, named only once met). `ready` is false without a model. |
| `PUT /api/story/scene` `{city_id, place_id?}` | Moves there; a city alone means its opening place. 404 for an unknown city or place. |
| `POST /api/story/messages` `{text, client_id}` | Saves the user's line once per `client_id` and returns `{message, reply}`. A failed reply is saved with `status: failed` and its `error`. Sending the same `client_id` again returns the saved reply, or tries again if it failed. 409 `no_connection` without a model; the line stays saved. |
| `POST /api/story/find` `{key}` | Moves the story to where someone the user has met is now. 404 if not met, 409 if they are nowhere the story can go. |
| `POST /api/story/retry` | Tells the reply to the latest user line again, replacing the one there. |
| `GET /api/story/start` | `{premades, points, range, stat_names, meanings}` for "Who are you?" in the scene's city. |
| `POST /api/story/start` `{premade_id}` or `{persona, stats}` | Starts the story as a premade or a made character; 409 once the story has begun, 404 for a premade not in this town, 422 for a missing name or stats outside the point-buy. |
| `GET /api/story/sheet` | `{stats, stat_names, range, dice}`: the character's MARVEL stats and the die each one adds. |
| `PUT /api/story/sheet` `{stats}` | Changes some or all stats; 422 for an unknown stat or a value outside 1 to 30. |
| `POST /api/story/back` `{message_id}` | Back to before one of the player's lines, as a new branch; the story comes back with `draft`, the line to send again. 404 for a line not in the branch being played. |
| `POST /api/story/branches/{id}/switch` | Plays on in another branch, where it was left. 404 for a branch not in this story. |
| `GET /api/story/journal` | `{entries, quests}`: the facts the player's character knows, newest first, and the quests they know of with `status`, `hook`, `outcome` and `left` (story time left). |
| `POST /api/story/journal` `{subject, text}` | Adds the player's own note. |
| `PATCH /api/story/journal/{id}` `{text}` / `DELETE /api/story/journal/{id}` | Corrects or removes a fact, logged; 404 for hidden truth or a fact not in the journal. |
| `DELETE /api/story` | Starts a new story: the history, every branch, the ledger and the people met go, the scene stays. |

## People you've met

Someone present in the scene is met once their name comes up, either because the narrator voices them giving it
or because the user uses it (`dungeon/story_people.py`, table `story_people`). Each local day they come up counts
as one meeting. Up to eight sentences of narration that name them are kept as notes. The next time they are in
the scene, the narrator is told the user has met them, how often and when, along with the latest notes, so they
remember the user however far back the story has been trimmed. The screen then shows their given name ("Dana,
the barista").

Under "People you've met" each person shows how often the user has met them and what their rules have them doing
now. "Go to …" moves the story to where they are (refused while they are at home, at work elsewhere or on their
street). Starting a new story clears the people met too.
