# Story

The **Story** is the app's home screen: the user plays their persona in one of the cities, and a narrator
describes the place and voices the people there. Since Milestone 0 it is the whole app; the dice, the rulesets
and the rest of the game are built on it from Milestone 1 ([the roadmap](../../docs/roadmap.md)).

## Who decides what

The app decides the scene (`dungeon/story.py`):

- **Where:** the city and place the user picked under "Go somewhere else…". A new story starts in Kingswood,
  the slice town, at its tavern or another opening place. A line that goes to a place in town by name or kind ("I
  go to the shrine", "I sleep at the bunkhouses") moves there too, before the narrator writes; words that fit two
  places equally move nobody. Moving adds a line to the story ("You arrive at …") that the narrator sees as a note.
- **When:** the story clock (`dungeon/story_clock.py`), in the city's own timezone. It starts at campaign start
  and moves with what the player does: 5 minutes for talk, 10 for a rolled action, 30 for a walk somewhere, the
  hours they say for "I wait two hours" or "for three hours", a day, morning or evening spent at something (10, 4
  and 3 hours: "I spend the day felling trees"), the nights of a rest (see "Rest"), 20 minutes to cross town and 6 hours to
  reach another city. Out-of-character lines take no time. A story with no campaign start runs on the app clock
  (debug time included), as Companion's did. The clock is branched with the story.
- **Weather:** the city's typical weather for the date (`generators.conditions`).
- **Who is there:** the townsfolk rules at that moment (`story.present`): people seeded at the place and
  residents whose routines bring them there. Each world's town has its own seed (`persona.town_seed`), so the
  same streets hold different people in different worlds.

The narrator model only voices the scene. Its prompt is built in layers (`dungeon/narration/prompt.py`):
"The Story narrator" and "The narrator's writing rules" in Settings > Developer ([prompts.md](prompts.md)),
the narration format (second person, present tense, short turns), the intensity, then a `## Scene` section
with the facts above. After each reply, `dungeon/narration/prose.py` removes em dashes and asks the model for
one rewrite when the reply has the strongest AI tells (see "Narrator prompting" in the top-level
docs/requirements.md). The narrator gets the names of the people present, with a rule not to use a name until
that person gives it. The screen lists them only as the user would see them ("the barista", "a regular").

The narrator stays in the story. Sentences saying it is an AI are dropped (`in_character.Guard`), and OOC: or
((…)) gets a plain answer from the game master, from what
the game holds and the travel map as the character knows it; it names the model only when asked. Its model is the **Story narrator** job in Settings > Models.

## Campaign start

A new story opens on "Who are you?" (`dungeon/campaign.py`). The player picks one of the town's premade characters
(`dungeon/world/data/premades/<city>.json`; Kingswood and Haddon Harbor ship three each) or makes their own: a name, gender, age, a
few lines about them, and MARVEL stats bought from 60 points, each from 4 to 18. Either way the world's persona takes
on that name and those lines, the stats go on the sheet, and the story opens with "You arrive at …".

The narrator gets the persona in its own layer, "The player's character": their name, what the player wrote, and
what their stats make them good and poor at (14 and up, 7 and down), in words, never numbers. It is told to voice
them from what is there and invent nothing about their past.

Session zero follows (`src/features/story/SessionZero.tsx`): one screen, "How this campaign plays", with three preset
cards (`dungeon/table.py` PRESETS: "As the world is written", "Gentler", "Harsher"), the world's own pre-picked so
Start is one click away. A preset sets the tone and the director's hand; "Fine-tune" shows every rule it set, whether
the dice show, and what is chosen once for the campaign (how far and fast the character rises, Ironman, an earlier
story). Under 5E it also has "Foes decide a defeat" (the Table's `defeat`). The ruleset stays on "Who are you?", as it decides how a character is made. `POST /api/story/start` takes
the rules as `table`; `GET /api/story/start` gives `presets` and `table`, the rules a new campaign would start with.

## The Table

Each campaign keeps its own rules (`dungeon/table.py`, columns on `story_campaign`), so they no longer follow the
player from world to world the way settings do. Tone (intensity, how eventful, lasting injuries, a 5E defeat) starts as the world's
at every new campaign; what is shown (the dice, rolling them, townsfolk's adult side, the GM view, meanwhile
cutaways) starts where the player last left it, which the workspace settings remember. A rule the player sets before
the campaign begins is kept. A campaign from before the Table keeps the rules it was played by. The rules are not in
`timeline.SAVED`, so going back never undoes one. The Story screen's "Tone and rules" fold sets them
(`PUT /api/story/table`); `PUT /api/settings` still sets them for the campaign being played too.

## Rulesets

The campaign's ruleset is picked on the start screen ("Rules") and locked for the whole campaign
(`story_campaign.ruleset`, `dungeon/sheet.py`). A world names its default; every built-in world plays MARVEL for
now. Whatever the ruleset, the Referee still names an approach (one of MARVEL's six stats) and a difficulty, and
`sheet.check` rolls the persona's checks the ruleset's way, on the shared outcome ladder. Everyone else (foes,
healers, townsfolk) keeps MARVEL stats for now.

- **MARVEL** (`dungeon/rules/marvel.py`): see "Who decides what".
- **5E via the SRD 5.2.1** (`dungeon/rules/srd52.py`, content in `dungeon/rules/packs/srd52`, CC-BY-4.0; the
  attribution shows on the start screen and the sheet). A character is a class, species and background from the pack,
  the standard array placed on the six abilities with the background's +2 and +1, the background's skills and the
  class's picks, level 1 hit points, and Armor Class from the armour in the class's starting equipment (a Fighter's
  Chain Mail, AC 16). A premade has its own 5E build (`srd52` in its premade
  data), or one from its strongest stat. A check is a d20 plus the ability modifier, plus proficiency in the skill,
  against a DC (10 easy, 12 normal, 15 hard, 20 very hard, 25 extreme, set so a hard check passes about half the time
  for a starting character, as MARVEL's does): pass or fail as written. The skill comes from
  the action's words ("climb" is Athletics), else the approach's ability. Resisting stress and clinging on in a
  fight are saving throws (Wisdom, Constitution). The roll card reads "Athletics · DC 15" and lands a single d20. Growth by use is MARVEL's
  and does not run under 5E.

### 5E levels and spells

- **XP and levels** (`dungeon/combat5e.py gain`, `srd52.advance`). A won fight gives each beaten foe's XP (down or
  broken, from its stat block); a milestone (a town quest done, a rise in standing) gives the level's high encounter
  budget. XP reaching the advancement table's next row is a level, at once: the hit die's fixed average plus
  Constitution in hit points, the class's features for the level, and at an Ability Score Improvement +2 to the
  class's primary ability (up to 20, the rest to the next best). Proficiency follows the level.
- **Spells** (`srd52.with_spells`, `sheet.cast`). A caster has the class's cantrips and prepared spells for its
  level, picked by code (damaging and healing spells first, the highest level it can cast) and kept as it levels,
  with the class's slots (Pact Magic's few slots of one level for a Warlock). A line that names a known spell casts
  it: out of a fight it is a check with the spellcasting ability and proficiency against the DC; a levelled spell
  spends the lowest slot it fits, and with none left it just fails, with no dice (the card says no roll). A healing
  spell (Cure Wounds, Healing Word) always works and heals the character. In a fight a damaging spell is a spell attack on AC, or the foe's save against the
  spell save DC (8 + ability + proficiency), as in "Fights under 5E". A long rest gives every slot back.
- The sheet shows the level, XP to the next, the features, the spells and the slots left.

Not yet: choosing spells and the ability increase yourself, subclasses, class features in fights (Rage, Sneak
Attack, Second Wind), upcasting and spells' other effects (conditions, areas, concentration).

- **Ironsworn** (`dungeon/rules/ironsworn.py`, content in `dungeon/rules/packs/ironsworn`: Datasworn's Ironsworn
  data, CC-BY-4.0; the attribution shows on the start screen and the sheet). A character places 3, 2, 2, 1 and 1 on
  edge, heart, iron, shadow and wits and chooses three assets (paths, companions, combat talents, rituals); a
  premade leans on the stat its strongest MARVEL stat maps to, with assets that fit. Health, spirit and supply start
  at 5, momentum at 2. Each action is a move read from its words (searching is Gather Information, talking someone
  round Compel, preparing Secure an Advantage, else Face Danger), on the stat the move or the words name (sneaking
  and lying are shadow), else the approach's. The action roll is a d6 plus the stat against two d10s: a strong hit
  is a success (critical on matching dice), a weak hit a success at a cost, a miss a failure (critical on a match).
  Ironsworn has no DCs, so an easy action adds +1 and a hard one -1 (very hard -2, extreme -3). Code burns momentum
  when it beats a die the roll did not, and the moves that give momentum on a hit give it. The roll card reads
  "Face Danger +iron" and lands the action die and both challenge dice. Resisting stress is Endure Stress (+heart);
  clinging on is Endure Harm (+iron).

Supply, spirit and vows under Ironsworn are described below. Not yet: Starforged (its Datasworn package's planet
images are non-commercial).

- **Narrative** (`dungeon/rules/narrative.py`, `dungeon/judge.py`; requirements "Narrative Only"): no stats and no
  dice. The sheet is the character's own About text plus two optional lists, good at and bad at. Each action the
  Referee finds gets a verdict from the judge: No (failure), No, but (failure with an upside), Yes, but (success at a
  cost) or Yes (success), with a one-line reason. The judge is the Referee's own model, else the narrator's, asked
  once per turn with the character, their condition, the scene (the people there and how they feel toward the
  character), the player's words and each action's difficulty on its face. The verdict is kept in the roll row
  (`skill` "No, but: …", no die) and reaches the narrator as the band plus "Why: …". With no model or an unreadable
  answer, the difficulty decides in code: easy Yes, normal Yes, but, hard No, but, harder No. There is no roll card:
  `dice_shown` is off under Narrative whatever the Table says, except in the GM view. No stat growth; milestones give
  nothing (what the character is known for is in the record). Fights use the shared wound levels.
- **Percentile** (`dungeon/rules/brp.py`, content in `dungeon/rules/packs/brp`: the core of Chaosium's Basic
  Roleplaying from its ORC Content Document, transcribed for a world before firearms). Vanta's call: the app names
  the ruleset "Percentile", and BRP appears only in the ORC notice and credit on the start screen and the sheet. A
  character buys STR, CON, SIZ, INT, POW, DEX and CHA point-based as written (all at 10, 24 points, DEX, INT and POW
  3 a point, each 3 to 21) and picks a profession and a personality type; code spreads the skill points (the
  personality's +20s, the profession's 250 and INT x10 personal points over the profession's skills, none past 75).
  A premade takes a profession from its strongest MARVEL stat. Each action rolls d100 under the skill its words name
  (climbing is Climb, haggling Bargain, looking about Spot), else a characteristic roll (Idea, Charm, Luck, Effort).
  The roll card never shows a chance over 95% (96-00 always fails), though the full chance still sets criticals
  and specials. Easy doubles the chance, hard halves it, very hard and extreme take 20 and 40 more off the half. Critical (1/20),
  special (1/5) and fumble follow the Skill Results table; critical is critical_success, special and success
  success, failure failure, fumble critical_failure. A skill that succeeds gets an experience check, rolled after a
  night's rest (d100 plus half INT over the skill raises it 1D6). First Aid on the character's own wound restores
  1D3 hit points once a wound. The roll card reads "Climb 75%" and lands the two percentile dice.

Not yet: powers (magic, sorcery, psychic abilities), hit locations, fatigue, sanity, parrying with a weapon or a
shield, training and research.

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
the Story screen. "Show the dice" (Story > Tone and rules) shows each roll under the user's line; off, rolls stay
hidden and the story reads the same. With the dice shown, "Roll the dice on screen" (off by default) has the dice act
out each roll before its result shows: 3D dice (`@3d-dice/dice-box-threejs`, MIT, loaded only when they roll) thrown
over the story with the library's predetermined "@" notation, so they land on the faces the code already rolled. A
PC without WebGL gets flat tumbling dice instead, reduced motion shows them landed, and a click lands them at once.

### The turn receipt

Under each narration, a row of chips says what the turn changed (`dungeon/receipt.py`,
`src/features/story/StoryReceipt.tsx`): coins in or out, items gained or lost, being hurt or mending, a lasting
injury, a quest heard of or ended, and what the character learned about (by subject). Nothing new is stored: each
player line already saves the game state as it arrives (`dungeon/timeline.py`), so a receipt is that save against the
next line's, or the game as it stands for the latest turn. Facts pulled from the story after the reply show up once
extraction has run. Only what the player could already see goes in; hidden truth, feelings and standings stay out.
The 40 latest turns have receipts; `GET /api/story` carries them as `receipt` on the player's lines.

## The record and the story so far

The record (`dungeon/record.py`, table `record_entries`) is what the game holds true: deaths, items, wounds,
promises, places, secrets, relationships and other facts, each marked as world truth (hidden from the player's
character), the character's belief, or both. Code records the facts it decides. After each narration the
**Continuity** model, when one is chosen for that job in Settings > Models, lists the new lasting facts in JSON;
code keeps the well-formed ones and refuses any about someone the record says is dead. "Tell it again" drops the
old reply's facts with it. The narrator gets the record every turn (every death and promise, then the newest of the
rest, 40 in all), with hidden truth marked as hidden, and is told never to contradict it.

**Schema-first.** The Continuity model fills a JSON Schema (`record.schema`): the facts (kind, subject, text and
truth, each kind and truth from a fixed list), plus a part for each other system's question that turn (quest
endings, oaths, feelings, dark tracks), every list empty when nothing applies. The backend enforces it where it can
(`dungeon/providers/requests.py` `structured`): structured output on OpenAI, Anthropic and Gemini,
`response_format` on OpenRouter and OpenAI-compatible servers (llama.cpp and LM Studio enforce it by grammar),
`--json-schema` on Claude Code and `--output-schema` on Codex. Kobold gets the prompt alone. A backend that refuses
the schema, or an answer that still cannot be read, is asked again without it. A weak model that gives no readable
JSON even then is asked one field at a time: the facts as lines, then their kinds, subjects and truths, each for all
of them in one question. Code checks every fact against the record either way.

**What Continuity is told and what code refuses.** The prompt defines each kind (a secret is something someone
hides, a relationship is a tie between two people, a death is a named person dying), and the last 20 facts are sent
as "Already in the record" so the model does not repeat them. Code also drops a fact that says the same as one already
kept (most of its words shared with one on the same subject), and an item the character "took" or "picked up" that
their pack does not hold: the narrator cannot hand out gear the game never gave. A threat or ultimatum someone made
of the character is not their oath.

"What you know" on the Story screen is the player's journal: every fact their character knows. They can correct or
remove one, or add their own note; each correction is logged in `record_corrections`. Hidden truth never shows here,
unless the player turns on the **GM view** there (workspace setting `gm_view`): it shows the whole record, hidden
truth included, to correct or remove, and "Ask again" on a fact the model pulled from the story asks the Continuity
model for that one fact again from its turn, without redoing the turn. The new fact is checked against the record and
logged like a correction.

The journal also shows **the story so far** as the narrator keeps it (the rolling summary). With the GM view on,
**Behind the story** (`dungeon/gm.py`, `GET /api/story/gm`) shows what the game keeps behind it: every quest with
its hidden truth and whether the character knows of it, the director's arcs at their stages with their truths and
antagonists, its open threads and nemeses, how everyone met feels (each axis set by hand there) and their
impressions, the factions' standing (set by hand), the dark tracks' points, and the log of corrections to the record.

The narrator reads the latest messages word for word. Once 30 recent ones plus 20 more are waiting, the oldest 20 are
folded into one rolling summary (`story_summary`) by the Continuity model, or the Default one without it, and the
narrator gets that summary as "The story so far" in their place. The summary calls the character by name, never
"the player" or "the party". The record and the summary are branched with the story.

## Layered recall and forgetting

`dungeon/remembering.py` decides what the narrator is reminded of each turn:

- **Layered recall.** The narrator reads the recent turns word for word, the story so far as a summary, and up to 40
  facts from the record: every death and promise first, then the facts about who is present, the place, and
  anything named in the player's line or the last two messages, then the newest of the rest.
- **Context fits the model.** The workspace setting `context_cap` (Settings > Models > Turn speed) caps the tokens a
  turn sends. When the system prompt would take more than half the window, the summary goes first, then the facts
  fall to a quarter, so the recent turns keep their room.
- **Forgetting, but grudges stick.** Each fact has a weight (1 to 3: deaths, promises, debts and betrayals are 3;
  secrets, wounds and relationships 2; the rest 1) and the turn the character last had it in mind. A weight-1 fact
  fades after 25 turns and a weight-2 one after 100; weight 3 never does. A fact about someone the character feels
  strongly about (any feeling at 3 or more either way) stays sharp, and a fact named again in a line or a narration
  is fresh again. Hidden truth never fades. The narrator is told which facts are faded; the journal marks them
  "fading". The record itself keeps every fact.
- **Recalling a faded detail.** A line that tries to remember something ("I try to remember the ferryman") that
  matches a faded fact takes a Mind roll in place of the Referee's; a success brings the facts about it back to mind.
- **The contradiction check** (`contradiction_check`, on by default) rewrites a narration that has the dead acting
  before the player reads it. Off is faster on slow local models; the passage is then flagged for the player to
  rewrite.

## Chapters and the branch tree

`dungeon/chapters.py` gives the story its structure.

- **Chapters close at scene breaks:** a new place, a journey or a rest, a fight over, a quest done or failed, or the
  player ending one themselves ("End the chapter", with a name if they like). The break waits
  (`story_chapter_break`, branched game state) and the player's next line opens the next chapter. "Go somewhere else"
  leaves a break too, and a line that goes somewhere ("I go to the shrine") opens the new chapter itself, so the move
  is not left as a one-line chapter. After that turn the
  Continuity model (or the Default one) summarizes and names the chapter that ended; a name the player gave stays.
- **Chapters follow the branches.** A chapter (`story_chapters`) starts at one of the player's lines, and its end
  (`story_chapter_ends`) is kept on the branch where it ended. Both are read through `timeline.visible` like the
  messages, so a branch shares its parent's chapters up to where it forked, and a chapter that ended differently on
  another branch is still open here.
- **The chapter list** reads the branch being played like a table of contents; any chapter can be read in full. The
  **tree** shows every branch under the one it forked from, with the chapters it began itself. A branch left with
  the character dead or lost is marked by how it ended (`story_branches.ending`). "Play from here" goes back to a
  chapter's first line in its branch, with new dice.
- **Bookmarks** name a player's line to find it again; "Go there" plays on in its branch and shows the line.
- **Ironman** is chosen at campaign start (`story_campaign`). It turns off going back to a line and switching branch,
  so death is final; telling a line again keeps its dice, so it is still allowed.
- **The notebook** (`story_notebook`) is the player's own. It spans every branch and no model ever reads it.

## Export and legacy

- **The story as a book** (`dungeon/book.py`, `GET /api/story/export/book?format=md|epub|pdf`, Story > Export): the
  branch being played, chapter by chapter with their titles, the player's lines set apart (quoted in Markdown,
  in italics in EPUB and PDF). Nothing hidden goes in: no GM notes, record or rolls. The EPUB 3 and the PDF (6 by 9
  inches, in the built-in Helvetica faces) are written with the standard library alone.
- **The campaign file** (`dungeon/legacy.py`, `GET /api/story/export/campaign`) is a verified Dungeon archive of the
  world being played: every branch, save, the record and the settings. "Import a campaign file" on the Worlds page
  (`POST /api/worlds/import`, the file as the body) makes it a new world under the persona that played it (made
  again if this install has none); saved credentials stay behind, as with any restore.
- **Legacy.** At campaign start, another world's story can come in as history ("An earlier story"): its character,
  whether they died, and what its chapters say they did (given as an old account for the narrator to retell in the
  past tense, never to quote). As a **legend**, the world remembers them and their deeds.
  As a **villain**, they are believed gone but live on, turned, as hidden truth and a nemesis the director brings
  back. As a **corpse**, the record holds their death, so the narrator never has them act. These facts are weight 3
  and never fade.

## What is happening

A town's adventure file (`dungeon/world/data/adventures/<city>.json`, `dungeon/quests.py`) lists its quests and its
dangerous places. Kingswood ships "The Heartwood contract" and a hidden one, "The wardens' eyes".

- **Quests** start with the story (campaign start), each with a hook, a hidden truth and a deadline in days of story
  time. The narrator gets "What is happening" every turn: each open quest, its truth, how long is left and whether
  the character knows of it yet. It lets them press on the scene and never ends one itself.
- **Deadlines** are code's: when the story clock passes one with the quest still open, the quest is missed, its
  stakes go in the record, and the narrator is told it is over.
- **Ending a quest:** with a Continuity model chosen, its question after each turn lists the open quests, and it may
  answer that the turn settled one (done or failed, with a sentence). Unknown ids are ignored.
- **Dangerous places:** each turn in one adds a Luck roll at the place's difficulty to the turn's rolls (shown with
  the dice, like any other). On a failure, the place's threat comes with the outcome for the narrator to write.
- The player's journal ("What you know") shows the quests they know of and the time left. Quests branch with the
  story.

## Gear and the shop

Code owns every item and coin (`dungeon/inventory.py`). A town's item file (`dungeon/world/data/items/<city>.json`)
lists its items with base prices in the city's currency (Kingswood: silver crowns, a logger earning 1 to 2 a day),
its shops with their starting stock, and each premade's starting kit (plus a default kit for a made character).

- **Purse and pack.** Money is kept in hundredths. Each item takes slots (a knife a quarter, a sword one); the
  character carries 5 plus half their Vitality. The narrator is told what they carry and what is in the purse,
  and that nothing appears or goes without the game.
- **The shop window.** In a shop (Kingswood: Pell's Provisions) the Story screen shows "The counter": the stock,
  its prices and how many are left. The shop is open while one of its staff is at work. Buying takes the item from
  finite stock; selling gets the shop's sell rate (half the base price) for what it deals in. Each trade is logged
  (`story_trades`) and adds a line to the story ("You buy Rope, fifty feet for 0.75 cr.").
- **In the story** the narrator is given the stock and prices to quote exactly. A line that buys something in an
  open shop ("I buy two loaves of bread and a rope") buys it at today's price before the narrator writes, and the
  narrator is told what changed hands, or why not (too dear, too heavy, sold out) under "At the counter".
- **Haggling** is a roll: an Allure action aimed at a better price ("I haggle over the rope") in an open shop sets
  the shop's prices for the rest of the story day by how it landed. A critical gets a quarter off, a success 15%,
  a success at a cost 10% (and the keeper likes the character less), a failure with an upside 5%; a failure changes
  nothing and a critical failure makes everything 20% dearer. One haggle a shop a day; asking again gets nowhere.
  Cold feelings make it harder, like any persuasion. Haggles are kept in `story_haggles`, and what happened at the
  counter on a line in `story_counter`, so "Tell it again" retells it the same.
- Everything branches with the story and is cleared by a new story.

Not in v0: an opposed roll against the keeper's Resolve, selling in the story, restocking, shopkeeper cash, stolen goods and fences, wear, loot, appearance state.

## Fights

Code runs the fight and the narrator writes it (`dungeon/combat.py`). One line of the player's is one round.

- **Starting.** A fight starts when the player attacks someone in the scene, by name or by what they do ("I punch
  the barkeep"), or when a dangerous place's threat brings a foe (Kingswood's Heartwood: a ley-mad boar, or two
  wardens who want the character taken). An attack on someone the scene does not hold, an extra the narrator brought
  in ("I punch him", "I hit the big logger"), fights a stand-in named as the line names them (not on the line straight after a fight ended: the one beaten is gone). Mid-fight every line
  goes to the Referee, told who the character is fighting, so "I go for the nearest one" or "I keep at him" is an
  attack, not a walk or a question.
- **A round.** The player's rolled actions land first. An attack that succeeds wounds its target by the band (a
  success with a cost one level, a success two, a critical three), plus one with a sword or felling axe and minus
  one bare-handed. A successful dodge, block or parry makes the foes' attacks hard this round; a successful flight
  ends the fight. Foes at a distance close in; engaged foes roll Vitality to hit back the same way.
- **Morale.** A foe at Maimed is down. When one falls or is badly hurt, the rest roll Resolve, and on a failure they
  break: they flee or give up. The fight is won when nobody is left standing and unbroken.
- **Wounds.** Grazed, Hurt, Wounded, Maimed, Dying. Wounded makes physical actions a step harder; Maimed makes every
  action a step harder and physical ones two. MARVEL heals gritty: a wound drops one level after nights of rest set
  by its severity (Grazed 1, Hurt 2, Wounded 4, Maimed 7; see "Rest"), and a new wound starts the count again. The narrator is told the character's condition every turn.
- **Defeat.** At Dying the character rolls their Vitality (hard) to cling on (which rules death out), then the defeat table is
  weighted by what the foes want: beasts kill, wardens capture, robbers rob, a brawl ends with the character
  beaten and thrown out, and sometimes someone drags them clear. Death is real: a dead character plays no more
  lines, and "Go back here" on an earlier line brings them back.
- **Held prisoner.** A capture keeps the character held (`story_wounds.captors`): no moving on, by line, by "Go
  somewhere else" or by road, until a line that tries to get free (slip the bonds, pick the lock, bribe, run)
  succeeds. The narrator is told every turn, and the Story screen shows who holds them. A prisoner is held, not out
  in the place: its danger rolls nothing, and no beast comes for them in the night.
- **In the story.** The narrator gets "The fight" with the round exactly as it went and who is still fighting, and
  writes only that. The Story screen shows the character's condition and the foes, with their wound levels while
  the dice are shown. Moving elsewhere is refused mid-fight.
- Each round is decided once and kept with the player's line (`story_rounds`): "Tell it again" retells the same
  round. Wounds and the fight branch with the story.

### Fights under 5E

The same fight, on 5E's numbers from the SRD 5.2.1 pack (`dungeon/combat5e.py`):

- **Foes are SRD stat blocks.** A foe's spec can name its monster (`"srd52": "giant-boar"` on the ley-mad boar), else
  one is read from its name (a bandit or thief is a Bandit, a press-gang thug a Tough, a warden a Scout, a ghoul a
  Ghoul), else picked by how tough the MARVEL spec is. Each has its AC, hit points rolled from the block's formula,
  and the block's first attack.
- **The player's attack** (an unarmed strike for a punch, a kick or a shove, and for every blow after it until a
  line names a weapon; else the weapon the line names, else the best carried) keeps the d20 the turn already rolled: the natural plus the attack bonus (Strength, or
  Dexterity with a finesse or ranged weapon, plus proficiency when the class has the weapon) against the target's
  AC. A natural 20 is a critical hit (the damage dice twice), a natural 1 always misses. Damage is the carried
  weapon's die plus the same ability (unarmed, 1 + Strength). The roll's card is rewritten as the attack and the AC.
- **A dodge** needs no roll: the foes attack with disadvantage that round. Getting away keeps its roll.
- **Foes attack** the character's AC and roll their damage against the sheet's hit points. The game's wound levels
  follow the hit points and read as 5E words (lightly hurt, bloodied, badly hurt, barely standing, at 0 hit points),
  and a lasting injury rolls only on a critical hit or a drop to 0, as the lingering injuries rule has it; and a wound dealt outside a fight (a Life Card) moves
  the hit points to match. There are no wound penalties.
- **Morale** is a Wisdom save, DC 10, when a foe is badly hurt or down.
- **At 0 hit points, death saves** (d20, 10 or more a success, three of either decides; a natural 1 is two
  failures). A natural 20 is back up with 1 hit point and still fighting. Three failures is death. Stable, the
  defeat table decides the rest without death, and the character comes to with 1 hit point. With "Foes decide a
  defeat" on at the Table (`defeat` 'by_aim'; off, 'as_written', by default), only foes out to kill bring the death
  saves; wardens, robbers and brawlers skip them and the defeat table takes what they came for.
- **A long rest** (a night's sleep) restores every hit point, as written. Lasting injuries still need their own care.
- The Story screen shows the character's hit points, and the foes' while the dice are shown.

### Fights under Ironsworn

The same fight on Ironsworn's moves (`dungeon/combat_iron.py`):

- **Foes are the pack's NPCs**, read from the foe's name (a raider is a Raider, a warden a Hunter, the ley-mad boar
  a Boar), else by how tough the MARVEL spec is. Each has its rank, deals harm equal to it, and has a progress track
  of ten boxes the character's harm fills (3 boxes a harm for a troublesome foe, 2 dangerous, 1 formidable, less for
  extreme and epic).
- **Initiative.** Whoever starts the fight has it (`story_fight.initiative`). With it the character's attack is
  Strike: a strong hit inflicts +1 harm and keeps it, a weak hit inflicts harm and loses it, a miss loses it. Without
  it the attack is Clash: a strong hit inflicts harm and takes it, a weak hit inflicts harm and the foe strikes
  back. Harm is 1, or 2 with a deadly weapon; a punch is 1. The roll card reads "Strike +iron" or "Clash +iron".
- **End the Fight.** After a strong hit, once a foe has 8 boxes, code makes the decisive move: the boxes against the
  challenge dice. A strong hit and the foe is out; a weak hit too, and the character Endures Harm; a miss and they
  pay for it, enduring harm, and fight on.
- **Endure Harm.** A foe with the upper hand hits: -health by its rank, then +health or +iron (a strong hit +1
  momentum, a miss -1). A dodge that lands turns the attack aside and takes the upper hand.
- **Face Death.** At 0 health a miss on Endure Harm brings the character to the brink: +heart, a strong or weak hit
  and death lets them go (the defeat table, without death), a miss and they are dead. Only a foe who would kill
  brings Face Death: a brawl to drive the character off ends in a beating and being thrown out. Endure Harm and
  Face Death show as roll cards after the line's own.
- **Health** reads as the game's wound words (unharmed, bruised, hurt, battered, badly hurt, at death's door); a
  wound outside a fight lowers health to match, and a night's rest gives +1 health (Make Camp).

Not in v0: zones beyond near and engaged, armour, ranged weapons and ammunition, allies, injuries with lasting
effects, healers and medicine, a fight started by an NPC without a danger roll.

### Fights under Percentile

The same fight on BRP's rules (`dungeon/combat_brp.py`):

- **Foes are the pack's sample characters and animals**, read from the foe's name (a thug or bandit is a Thug, a
  raider or guard a Viking, a wolf a Wolf), else by how tough the MARVEL spec is: hit points, armour, Dodge and their
  first attack.
- **The character's attack** keeps the turn's d100 against the carried weapon's skill (a sword is Melee Weapon
  (Sword), bare hands Brawl), and the foe dodges. A line that dodges and attacks ("I dodge his swing and cut at
  him") does both. A made character starts with the town's items for their profession's weapons (a warrior's
  broadsword and bow). The Attack and Defense Matrix decides: a dodge at the attack's
  level or better stops it, and each level short takes the attack down one. Damage is the weapon's dice plus the
  damage modifier (half for a bow or a thrown weapon), less armour; a special impales (the dice twice), a critical
  does the dice's most and ignores armour. The roll card reads "Sword, Broad 59% (special)".
- **Foes attack** with their skill. The character dodges the first attack each round, and every one when the line
  says they defend, dodge or parry. A dodge that works earns Dodge an experience check, as a hit does the weapon.
- **Major wounds.** A blow of half the character's hit points or more is a major wound. A Luck roll (POW x5) lets it
  heal clean; a failure rolls the Major Wound Table and takes characteristic points for good, unless Injury
  persistence is none. At 2 hit points or fewer after one, or on a result that leaves them unable to fight, the
  character collapses: the defeat table without death. At 0 hit points the wound is fatal, and the defeat table
  decides (someone may yet drag them clear).
- **Morale:** once a foe is down or under half its hit points, the rest roll Luck; a failure breaks them.
- **Healing is slow**, as written: each hit point back takes 7 days divided by a 1D3 roll (3, 4 or 7 nights' rest).
  The rest of the game reads hit points as the same words as 5E (unhurt to at 0 hit points).

### Supply, spirit and vows under Ironsworn

`dungeon/sworn.py` keeps Ironsworn's tracks outside a fight:

- **Supply.** Ironsworn keeps its abstract Supply track: a day on the road costs a point of supply instead of a food
  from the pack, and with none left the character goes hungry as before. A Life Card's food comes as supply.
  Resupply, read from the action's words (forage, hunt for, scavenge), brings back 2 on a strong hit and 1 on a weak
  one, shown on the roll card ("+2 supply").
- **Spirit** follows the stress track: 5 while steady, down to 0 at its top. Resisting stress is Endure Stress on
  heart.
- **Vows.** A quest or an oath done is a vow fulfilled. Its rank comes from the quest's tier (tier 1 dangerous,
  2 formidable, 3 extreme, higher epic; an oath is dangerous) and gives experience as written, 1 for troublesome to
  5 for epic. Code spends it: 2 upgrades an asset (its next ability), else 3 buys a new asset that fits the
  character's best stat. MARVEL's milestones give Ironsworn nothing; its growth is its vows.

Not yet: progress tracks for vows marked as the story goes, journeys as progress tracks, Sojourn, debilities from
the suffer moves, bonds.

## Going back

Every line the player sends is a save point (`dungeon/timeline.py`): the game state as the line arrives (the scene,
the people met, the sheet, the record and the summary: the tables in `timeline.SAVED`) is kept in `story_saves`. "Go back here" under any of
the player's lines starts a new branch from just before it, puts that state back and returns the line to the
composer to send again. Nothing is rolled until it is sent, so the dice are always new.

The branch left behind is kept with its state (`story_branches.tip`) and listed under "Other branches", where
"Play this branch" picks it up where it was left. Messages carry their `branch_id` (the first branch is `first`); a
branch shows its parent's messages before the line it went back to, then its own, and the narrator sees only those.
"Tell it again" works on lines of the branch being played; a shared line keeps the reply it was told. A system that
keeps game state adds its tables to `timeline.SAVED`.

## What is inside

Milestone 1 item 12, decide before describing (`dungeon/finds.py`, requirements "Decide before describing"). When
the player's line looks into something unsettled ("I search the chest", "I pick his pockets", "I go through the
desk"), code rolls what is there before the narrator writes a word, from the town's tables
(`dungeon/world/data/finds/<city>.json`: chests, drawers, crates, bodies, purses and rooms, each with the words a
player uses for it, how many draws and a weighted table of catalog items, coins, notes and the odd trap). The
narrator gets "What is there" and describes only that.

- **Rolled once, kept.** Contents are stored (`story_finds`, keyed by town, place and the word used) and noted in
  the record as a fact the character knows. Looking again shows the same things, whatever the dice.
- **A failed search misses it.** When the line's Mind roll fails, the narrator is told what is there and that the
  character misses it; the contents stay unseen for a better look.
- **Taking it.** A line that takes what was found ("I take the coins", "I pocket the knife", "I take everything in
  the chest") moves coins to the purse and items to the pack while they fit; notes and what does not fit stay.
  "I take a seat" takes nothing: the line has to name the money, an item, the container or "it/them/everything".
- What a line looked into and took is decided once (`story_looks`), so "Tell it again" keeps it; finds branch with
  the story.

Not in v0: doors and what is behind them, finds tied to a particular person or body, traps that do harm by
themselves, and other towns' tables.

## Turn speed

Milestone 1 item 11 (`dungeon/pace.py`, requirements "Turn speed"). A turn can chain the Referee, the narrator,
the prose rewrite, a contradiction check, fact extraction and the summary, so each turn has a time budget and
every step is timed.

- **The budget** is Settings > Models > Turn speed: automatic (90 seconds when the narrator runs on this PC, 30 for
  an online model) or a fixed time. Each step's time, and what gave way, is kept with the player's line
  (`story_turn_steps`) and shown under it while the dice are shown.
- **The narration streams** a sentence at a time (`POST /api/story/messages/stream`), as the in-character guard
  passes it on.
- **Fact extraction and the summary run after the reply is on screen.** They finish before the next turn starts:
  a new line, or "Tell it again", waits for them.
- **The contradiction check runs only when it is needed:** when the narration names someone the record says is
  dead. The narrator's model is asked once to rewrite only what has them alive, and the rewrite is used only if it
  stays about the same length. A clean turn costs no extra call.
- **Obvious lines skip the Referee's model:** a line that is only speech and plain acts (walking, looking, sitting,
  ordering, asking about something) has nothing to roll, so no model is asked. Telling or asking someone *to* do
  something is persuasion and still goes to the Referee.
- **Over budget, the optional steps give way:** the prose rewrite first, then the contradiction check. Dice, the
  record and the em dash fix are never skipped.

Not in v0: dead and spent items or people elsewhere in the contradiction check (only the dead), a GM view of
skipped checks, and the dice log.

## Journeys

`dungeon/travel.py`, with each world's travel map in `dungeon/world/data/travel/` (Vallarith first): places joined
by roads, each road with its hours on foot, terrain and danger (none, low, medium, high), and each region's road
encounters. A place is a whole town (Kingswood: its city and the place one arrives at) or a place on **the Road**
(`world/data/cities/vallarith-road.json`, built by `scripts/world/vallarith_road.py` from the world package's
settlements): a gate, an edge or a ruin to arrive at, until that town is built out as a city of its own.

- **Fog of war.** The character knows where they have been, every place one road from there, and the famous
  places everybody has heard of (Cyrel, Asania). The Map in the side panel shows those and the roads between
  them; Set out puts "I set out for …" in the box to send.
- **Decided before the narrator writes.** "I set out for Eriane" (travel, head, ride, walk, journey, go … with
  a place on the map) plans the shortest way in hours and rolls each road against its danger (15, 30 or 50 in
  100). The first road that turns something up draws from its region's table: a sight or a meeting, which the
  narrator weaves in, or a danger to get past, a Luck roll like a dangerous place in town. A failed roll brings
  the threat; one with foes starts a fight there and the journey stops at that road's end. A place the character
  has not heard of is not reached: the narrator is told they do not know the way.
- **Time and food.** Walking takes the roads' hours, ten a day; the nights between pass camped on the road (14
  hours each). Each day eats one food from the pack (bread, then dried meat, then cheese); the days without go
  hungry. The story clock moves by all of it, so deadlines pass on the way; walking is no rest, so wounds do not
  mend on the road.
- The narrator gets "## The journey" with what happened, and the scene opens with "You arrive at …". The places
  known (`story_map`) are branched with the story; each line's journey is kept (`story_journeys`), so telling it
  again walks no further.

## Rest

`dungeon/rest.py`. A line that beds down ("I sleep", "we make camp", "I rest for three days", "for a week") is a
rest, decided before the narrator writes it. A journey line is not; a rest with a fight on is refused.

- **Where decides the danger.** A town (a safe place on the travel map, or a city with no map) is safe, unless the
  place is a dangerous one, whose own danger is rolled every turn as before. Out in the open (the Abandoned Keep,
  Adlmyr, Brynwyr's forest), each night rolls against the region's danger in the travel map's `regions` (15, 30
  or 50 in 100). Precautions in the line cut it: a watch kept (half), a hidden camp or no fire (six tenths), an
  alarm or ward (seven tenths).
- **One night can go wrong.** The first night that turns something up draws from the region's `camp` table: a
  sight the narrator weaves in, or a danger to get past, a Luck roll a step harder asleep with no watch. A danger
  that comes true costs that night's rest; one with foes starts a fight in the dark and the rest ends there,
  four hours into that night.
- **Time, food and mending.** One night runs to seven the next morning when it starts in the evening or the night
  (6 to 15 hours off), else 8 hours; each more night is a day. Out in the open each day after the first eats
  one food from the pack, and a hungry night does not mend. Each good night counts toward the wound's mending
  (`combat.mend`, `story_wounds.rested`); the narrator is told how far it has come.
- The narrator gets "## The rest" with what happened. Each line's rest is kept (`story_rests`), so telling it again
  sleeps no more.

## Lasting injuries and treatment

`dungeon/injuries.py`, with the lasting-injury table in `dungeon/rules/injuries.json`. All of it follows the
**Lasting injuries** setting beside the story (`injury_persistence`): Permanent (the default), Temporary or None.

- **Lasting injuries are rolled.** A foe's hit that leaves the character Maimed (or worse), or a foe's critical hit,
  rolls on the table once that round, but only from foes who would kill: a brawl to drive the character off leaves
  bruises, not a lost eye (`combat.maimed_by`). The table: a lost eye, a limp, a ruined hand, two lost fingers, a disfiguring scar,
  ribs that knit wrong, a deaf ear, a tremor in the sword hand. The same one never twice. It goes in the record
  as a wound, shows as "Lasting: …" under the character's condition, and the narrator is told what people see.
- **Each one makes some actions a step harder**, by the words in the action (a limp: run, climb, chase, sneak; a
  lost eye: shoot, aim, spot, search). Under Permanent they stay; under Temporary each fades after its days of
  story time (25 to 60); under None nothing is rolled and the old ones stop showing.
- **Treatment.** A line that treats a wound ("I bandage it", "can you tend my wound?") while hurt and not
  fighting:
  - with a healer in the scene (a shrine keeper or herb seller whose role or story says healer), the healer
    treats it for 2.00 in the town's money, rolling their own skill (15), a step easier than the wound's own
    difficulty; with too little money, nothing happens;
  - otherwise with bandages or a poultice from the pack, a Mind roll of the character's (easy for Grazed, normal
    for Hurt, hard for Wounded, very hard for Maimed; a poultice a step easier), using one up.
  - A success mends a level now, a critical two; a critical failure turns the wound bad, a level worse. A wound is
    treated once ("now it needs rest"); a fresh wound can be treated again. Each line's treatment is kept
    (`story_treatments`) and the narrator gets "## The treatment".
  - With no wound at all ("I bind my wounds" unhurt), nothing is rolled: the Referee's roll for the line is dropped
    and the narrator is told the character has no wound to treat.

## Stress

`dungeon/stress.py`. A stress track, 0 to 12, shown beside the condition as "Nerve: shaken" (with the number
when the dice are shown): steady, shaken (1 to 3), strained (to 7), frayed (to 11), breaking (12).

- **Trauma adds to it**, from what code knows happened: the first life the character takes (2), facing something
  dreadful (a foe marked `horror`, such as the Badlands' ward-ghoul: 2), being maimed (1), and the defeat table's
  outcome: beaten senseless (1), robbed and left for dead or rescued half-dead (2), taken prisoner (3). Fights
  report these to `stress.aftermath` (`combat.turn`'s `aftermath`).
- **Resolve resists.** A critical success shrugs it off, a success (or at a cost) takes half, a failure all of it,
  a critical failure one more.
- **Past each threshold** (4, 8, 12), and each time more lands at the top, a lasting condition of the mind is rolled
  from `rules/injuries.json` `conditions` (nightmares, a fear of the dark, a horror of blood, numbness, checking, a
  temper, the shakes, drink). Conditions work like lasting injuries: some actions a step harder, a look the
  narrator plays, kept, fading or ruled out by the Lasting injuries setting.
- **Rest eases it**: one point a good night (see "Rest"). The narrator is told the track every turn.

## Life Cards

`dungeon/happenings.py` draws the world's Life Cards (`dungeon/life/cards.py`, `docs/life-cards.md`) into the
story, with the deck and region from the travel map (`world`, `regions.*.cards`).

- **When.** A day in town draws once, on the first line of the story day spent in a town (not on the Road, not mid
  fight). A journey draws once for the road it ends on, unless a road encounter's fight stopped it. A rest out in
  the open draws once; a card that brings foes ends the rest like a bad night.
- **How eventful.** Beside the story, "How eventful": the world's own (Kingswood's is Eventful) or Quiet, Uneasy,
  Eventful, Merciless (`workspace_settings.drama`; worlds set `intensity.drama`). It sets how often a scene draws
  and which cards can turn up; the intensity preset leaves out what it does not allow. It never changes the dice.
  Cards that need someone the game cannot name yet ({bond}, {them}, {faction}) are left out until companions,
  beats and factions exist.
- **Played by code.** The record keeps the card's truth as the world's, and what the character sees as their
  belief when it is not the whole truth. The narrator gets "## What the world brings": what the character sees,
  the choice it puts to them, and what code applied: stress (against Resolve), a wound, coin in day wages (the
  town's `day-wage` price), food gained or lost, time, the feelings of someone there, a fight (`FOES`). Market,
  rumor, quest, faction, fate and pursuer effects wait for their systems.
- Each draw is kept (`story_cards`, branched with the story), so telling a turn again draws nothing new, and a
  card is not drawn again within the deck's `repeat_days`.

## Factions

`dungeon/factions.py`, with each world's factions in play in `dungeon/world/data/factions/<world>.json` (Vallarith's
built by `scripts/world/vallarith_factions.py` from the world package: the Kingdom of Cyrel, Asania, the Timber
Guild, the High Elves of Brynwyr, the Unguruk, the Mossrun expedition), each with goals, the travel-map places it
holds, rivals, allies and clocks.

- **Clocks run on the world clock.** Each story day that passes (`pass_time`), each open clock moves a segment with
  the file's `pace` chance (25 in 100). A full clock's `done` happens: the record keeps it as the world's truth, and
  on the character's next line in a town "News reaches town: …" goes to the narrator and the journal. Life Cards'
  `clock` effects move the first open clock of a faction with a hand in the place. `factions.tick` is the one way
  a clock moves, so other systems (a story director, jobs) can nudge them.
- **Standing** (`story_reputation`, -5 to 5): an enemy, distrusted, frowned on, unknown, noticed, trusted, honoured.
  Life Cards' `reputation` effects move it. The panel's Powers lists the factions the character knows of (holding
  a place they have been, or that know them), with the standing (and its number with the dice shown).
- **The narrator** gets "## The powers here": each faction holding the place, its summary, goals, clocks and the
  character's standing, to act through their people without announcing a clock.
- Life Cards naming `{faction}` can now be drawn where a faction holds the place, and name one of them.

## Jobs and oaths

`dungeon/jobs.py` and `dungeon/quests.py`. Besides a town's authored quests, `story_quests` holds quests of their
own text (`kind` job or oath, with `title`, `hook`, `truth`, `missed`), and for the story director an `arc_id`, a
`thread_id` and `ties` (the loose ends a quest leaves, `[{kind: npc|clue|item|faction, ref}]`).

- **Jobs.** Each faction lists the jobs it needs done in the towns it holds (`jobs` in the factions file: giver,
  hook, truth, missed, days, pay in day wages, standing, ties). On a town day, while a faction holding the town has
  no job open, it may offer one it has not offered before (`jobs.OFFER`, 50 in 100). The narrator gets "Work is
  going: …"; the journal shows it as a Job with its time left. Done (the Continuity model's call, as for any quest)
  it pays and earns its standing; failed, it costs a point of standing; left to lapse, only its `missed` happens.
- **Oaths.** Every turn the Continuity model is also asked for promises, oaths, threats and bargains the player's
  character made. Each becomes an Oath quest to the one it was sworn to, due in the days it gives (7 if it gives
  none). Broken or let lapse, it costs that person two points of trust and one of respect, and the record keeps it.
  An oath sworn on a quest the character already knows of, named in the line ("I swear an iron vow the Heartwood
  contract will fail"), is that quest, now a vow: the record keeps what was sworn, and no second oath is filed.

## Institutions

`dungeon/institutions.py`. A school, a guild or an army the character belongs to, from the world's
`engine/institutions/<world>.json` (`institutions`: id, name, city_id, faction, default, core, terms, classes,
demands, attendance_weight).

- **Enrolment** (`story_enrollment`). A premade starts in what its `enrolled` names; a made character in a world
  with a `default` institution starts in it with its `core` classes. `PUT /api/story/institutions/{id}`
  `{classes?}` joins (or changes classes), `DELETE` leaves.
- **Terms** run once on set dates (`start`, `end`) or every year (`from`, `to` as month-day). **Classes** meet on
  their `days` at `start` during a term. When the story clock passes a class's start, the character attended if the
  scene is at its `place_id` (anywhere in the institution's town when it names none); otherwise it is missed and
  the record keeps it (`story_attendance`). A long sleep or journey checks at most three weeks.
- **Demands are quests** (job quests with `institution`, `demand` and `weight` set, shown as Coursework).
  `every_days` demands open each period and are due `due_days` later; `week` demands (exams) are due that many
  weeks into the term and open `notice_days` (7) before. Each opens once (`demand` is `id@when`). The Continuity
  model decides done or failed; a deadline passed is missed.
- **Grades** (`story_grades`). A demand settled is a mark (done 90, failed 60, missed 0) at its weight; attendance is
  one more mark at `attendance_weight` (2). The term's weighted average gives a letter and a grade point (A 4.0, B
  3.0, C 2.0, D 1.0, F 0). Failed or missed work costs a point of standing with the institution's `faction`; work
  done earns the tier track like any job. Faction jobs ignore coursework when deciding whether a faction is busy.
- **A world's own date.** The tier file's `start` (`"2009-08-31T08:00"`) is when its campaigns begin on the story
  clock, so a school's terms line up; with none, the story starts today.
- **The narrator** gets "## School and duties": the term, the rest of today's classes and the grades so far, and
  is told never to invent another class. The journal shows each institution with its term, grades and today.

## Off-page beats and word getting around

`dungeon/beats.py`. The people the character is connected to keep living while the character is elsewhere: anyone
they have met more than once, or who feels strongly about them (a feeling at 2 or more either way), who is not in
the scene and is not dead.

- **When.** Each story day passed since the last look may bring a beat (the world deck's `beat` scene, at the drama
  level), up to three a line; with no day passed, the third quiet line in a row brings one for sure, so a long
  scene does not freeze the world. `beats.fire` takes a `pressure` (a person's key) for the story director to say
  who the next beat lands on.
- **What it does.** Code plays the card on `{them}`: the record keeps its truth as the world's (a death as the
  world's death), feelings move, a faction's standing moves, and a fate sticks (`story_fates`: wounded, sick,
  captured, dead, turned, missing, …). The dead, captured, missing and conscripted are gone from town: the
  townsfolk rules leave them out until something changes it. A captive draws only cards a captive can (an escape).
  The narrator gets "## Off the page" with everyone not as the character last saw them, kept from the character.
- **Word gets around.** What the character would hear (the card's `seen`, as wrong as the card says) travels a day
  (`story_word`) and reaches them on their next line in a town: "Word reaches the character: …" goes to the
  narrator, and into the journal as belief when it is not the whole truth.
- **Cutaways.** "Meanwhile cutaways" in the side panel (`workspace_settings.cutaways`, off by default) gives the
  narrator "## Meanwhile" with the beat as it happens, to show the player apart from the scene.

Fates, beats, word and the off-page clock are game state (`timeline.SAVED`); each line's beats are kept with it
(`story_cards` scene `beat`), so telling the line again brings the same ones.

## Scaling and tiers

`dungeon/tiers.py`. One ladder for every world and ruleset: Local, Regional, Realm, World, Mythic. Each world names
the track that sets the character's tier (`dungeon/world/data/tiers/<world>.json`); Vallarith's is renown, earned by
work done (4 times the work's tier, doubled for work above the character; oaths earn none).

- **The arc.** The start screen asks how far the character can rise (grounded: Local to Regional; classic: Local to
  Mythic; epic: Realm to Mythic) and how fast (slow burn needs twice the track, a fast rise half). The world sets
  the defaults. A rise tells the narrator once; the panel's Powers shows the tier in words, with the track's
  numbers when the dice are shown.
- **Work at the character's tier.** Jobs carry a tier. A faction offers only jobs at the character's tier, and one
  time in ten one a tier above, with a warning that it is beyond them. Nothing two tiers up comes unasked. A line
  that goes looking for work (asking who is hiring, reading the notices) finds it on any line, at their tier or
  below.
- **The world keeps its tiers.** Each region has one (the travel map's `regions`: the Kingdom of Cyrel Local, the
  Kingdoms of Man and the Badlands Regional, Brynwyr Realm). A journey that ends somewhere above the character
  warns them first, and the narrator is told the place outmatches them. A Life Card's foes come at the region's
  tier. Each faction has a tier too: one the character has made an enemy of, above the region's tier, sends its
  own after them on the road, at its tier.

The track is game state (`story_tier`, in `timeline.SAVED`).

## Progression

`dungeon/growth.py`, with the dark tracks in `dungeon/rules/dark.json`. MARVEL characters grow by use, plus
milestones (5e and Ironsworn will keep their own growth rules).

- **Use.** A roll of the character's that mattered (one that succeeded, or one with a danger riding on it) marks
  its stat (`story_marks`, once a line however often it is told). After a night's rest code rolls for each marked
  stat, Basic Roleplaying style: over three times the stat on a d100, it rises a point. The marks clear. The sheet
  shows a marked stat with a dot.
- **Milestones.** A town's own quest done, or a rise in tier (`dungeon/tiers.py`), gives 2 points to the stat used
  most since the last one. The rise and the boost go in the record, so the narrator knows.
- **Dark tracks:** corruption, addiction and infamy, 0 to 10, with thresholds at 3, 6 and 9. Every turn the
  Continuity model is also asked whether the character did something that feeds one (a pact with something under
  the Heartwood, a drug, an atrocity others saw); each it names rises a point. Life Cards' `corruption` effects
  move it too (the Vallarith deck's "Something under the Heartwood" rest card). Each threshold grants power
  (corruption +2 Essence, addiction +1 Vitality, infamy +1 Allure) and rolls a lasting change to body, mind or how
  people treat them, from those the intensity setting allows. The top of a track costs the player the character:
  the story stops, as it does for a death, until they go back to an earlier line.
- **Shown as the dice are.** The sheet shows the tracks in words ("Corruption: tainted") with their lasting changes,
  and the points only with the dice shown. The narrator gets "## What the character is becoming" and shows it
  without naming the track.

Marks and dark tracks are game state (`timeline.SAVED`).

## The director

`dungeon/director.py` v0 (requirements "The director"), with each world's arcs for its era in
`dungeon/world/data/arcs/<world>.json` (Vallarith Post-Reform: the Eight Pieces, entered through the Heartwood
contract; the Long Border, through Bastion's deserters; the Failing Wards, through the Abandoned Keep). Each arc has
stages, each with its tier, the world's truth, a seed the narrator may plant and the word that reaches a character
who is not there; the words that tell code play touched it; and its antagonist, with where they work.

- **Arcs and the spine.** A new campaign seeds every arc at its first stage, each with a thread. Every line that
  touches an arc's threads is a bite on it; the first to six bites becomes the spine (within three chapters of 20
  lines; after that, the world's default, the Eight Pieces). An arc bitten twice as hard can take the spine's place.
- **Threads** (`story_threads`): an arc's mystery, each quest's lead (each job, oath and town quest opens one, its id
  in `story_quests.thread_id`), each nemesis's grudge. Heat rises by 3 when play touches one and cools by a third
  every line. Closing a quest closes its thread. The journal's "Loose ends" shows the mysteries and grudges the
  character has come across, as they understand them.
- **The hand**, picked on the start screen: Soft, Guiding (the default) or Firm. Each story day, each arc may move a
  stage (10, 15 or 20 in 100 by the hand; twice that for the spine), changing the world's truth in the record. Under
  Soft that is all; under Guiding the note brings the arc's people looking for the character; under Firm it shows
  in the scene wherever they are. A stage above the character's tier reaches them only as a rumor.
- **The hidden GM note** ("## The game master's note"), kept with each line: the pressure the tension curve calls
  for, what of the arcs is due, a seed from the arc in focus (each once), the threads the people present carry, and
  the antagonist of an arc in play if they work here.
- **The tension curve.** Each line is a crisis (a fight), pressure (a roll with a danger on it), social (people
  about) or quiet. After a crisis the note lets the next scene breathe; after a slack run (5, 4, 3 or 2 quiet or
  social lines, by the drama setting) it asks for pressure: a nemesis who is due, the hottest thread, or the spine.
  The line it asks on counts as pressure, so the next run starts over rather than every line after asking again.
- **Side quests.** A job offered links into the arc in focus one time in three, carrying the arc's current seed as a
  clue tie.
- **Nemeses.** A foe who broke and got away from a fight the character won, or who robbed, took or threw out the
  character, becomes a nemesis half the time: a grudge, the stat the character relies on most, a thread. Three days
  on they come back through the note, with a plan. Killed on the page, they stay dead.

### The director: seeds, adopted details and planned beats

`dungeon/plotting.py` is the director, full (M3):

- **Seeds pay off (the Chekhov list, `story_seeds`).** Every seed the note plants is logged with its arc and the
  truth it points to, and a payoff window of 30 lines. After each narration code checks which seeds reached the page
  (two of their words or more). When a seed's arc is due or its window is closing (5 lines left), the note asks for
  it to come back; once it does, it is paid. A seed whose window ends unpaid is retired.
- **Adopted details.** The Continuity model's question after each turn also asks which details the narrator made up
  the player's line took an interest in (a stranger at the bar, a symbol on a door). Half the time the director gives
  one a meaning tied to the hottest arc thread: drafted by the **director** model when one is chosen for that job in
  Settings > Models, else from the thread's own truth. It is refused if it has the dead acting, then kept as hidden
  truth in the record and as a seed already on the page.
- **Beats planned a stage at a time (`story_arc_beats`).** When an arc reaches a stage with no plan, the director
  model drafts three beats from the stage's truth, where the arc plays and the hottest threads of that arc only;
  code keeps those that name none of the dead and none of another arc's own names (its cast and places), and without the model the plan is the stage's own seed and word. When the arc is due, the note gives its next
  beat.
- **Co-planning in the GM view.** "Behind the story" lists the seeds (planted, paid, retired) and each arc's planned
  beats. The player can bring a seed back next or retire it, and cut, restore or move up a beat.
- **"Previously" openers.** When a chapter ends, the Continuity model (or the Default one) gives its title, a summary
  and the hook it leaves open, before the next line. The line that opens the next chapter carries a hidden
  "## Previously" from them and the hottest threads the character knows of, and the narrator begins with two or
  three sentences of it. Only when it is worth it: after 6 of the player's lines since the last one, or a chapter the
  player closed themselves; a short chapter just read gets none. The chapter list shows each chapter's hook as "Still open".

## Rewrite

`dungeon/passages.py`. The automatic rewrites still run when there is time; whatever the checks find and do not
fix is flagged for the player instead of lost.

- **Flagged paragraphs.** A strong prose tell the rewrite pass left (or never ran on, over budget), or someone
  the record says is dead when the contradiction check gave way for time, marks its paragraph with a soft
  highlight, a "?" that says why, and **Rewrite**. The flags are kept with the narration (`story_messages.flags`).
- **Why never gives away hidden truth.** A death the character knows of is named ("The record says Old Tom is
  dead."); one they do not know of says only "It conflicts with the story so far."
- **Any passage on request.** Select text in a narration and a Rewrite box opens with an optional note ("less
  purple", "she wouldn't say that"). The narrator's model rewrites only that passage, told to keep every event,
  outcome and fact and given the record. A rewrite far longer or shorter than the passage is refused.
- **Wording only.** The rolls and bands stay, so nothing is rolled again; going back is still the way to new
  dice. The new wording goes through the same checks, so its flags are its own, and the facts the narrator
  brought in are taken again from it (with a Continuity model chosen). The wording before the last rewrite is
  kept: **Switch wording** goes back to it and again to the rewrite.
- A part told before going back is shared with another branch, so it stays as it was.

## How far the story goes

Intensity v0 (`dungeon/story.py` `intensity`, requirements "Intensity and tone"). The narrator is told how far
violence, sex, horror, cruelty and drugs go on the page: restrained (implied, little detail), mature (shown plainly)
or unflinching (explicit, in full). One preset covers every category for now.

- **The world's own.** A city may set its `intensity`: a preset and the narrator's voice there. Kingswood, like
  Vallarith, is unflinching and grim. A city without one is unflinching with no voice.
- **The player's choice.** "How far the story goes" in the side panel picks the world's own or another preset
  (`workspace_settings.intensity`), at any time, mid-scene included; the next line follows it. The world's voice
  stays whatever the preset.

Not in v0: per-category sliders, veils, tone and drama settings, and lower settings removing outcomes from the tables.

## The screen

Four parts, from the requirements' "Play screen and widgets" (`src/features/story/Story.tsx`, `StoryPanel.tsx`); a
free grid of widgets is an optional mode late in Milestone 6.

- **The story column:** where the story is (place and city), then the status strip (`StoryStatus.tsx`): story time
  and weather, the character's condition (hit points under 5E), nerve, lasting injuries, captivity and coin, as the
  dice toggle allows. Then who is around, the fight line while there is a fight, the story text with each turn's
  receipt, and the composer.
- **The scene panel:** one or two widgets the scene needs, picked by code from the game state with no model call
  (`src/features/story/scene.ts` `sceneWidgets`): a fight shows the foes, a shop the pack and its counter, the Road
  the travel map, and people met who are at this very place "Here with you". With none of those it shows the journal.
  Below them are the widgets the player pinned, kept whatever the scene (saved in this browser).
- **The drawer:** tabs under the panel for the sheet, the pack and the journal, and More for the map, people met,
  powers, chapters, other branches, the notebook, export, and Tone and rules. Each opens in the panel, unfolded, with
  "Pin to the scene". Widgets with nothing to show are left out. A Settings search for a story setting opens Tone and
  rules.
- **Entity cards** (`EntityCard.tsx`, `entity.ts`): a person met, a place on the map, an item in the pack and a
  faction open the same card, and so do the names of people met and factions known in the narration (whole names, and
  a first name no one else shares). The card says what the character has seen of it, the journal's facts about it
  (never hidden truth, even with the GM view on), and what they can do. Each action writes a line into the composer
  ("I turn to Agnes Brill.", "I set out for Eriane.") for the turn loop to roll; only "Go to …" moves the story at once.
- **Receipt chips** open their widget in the panel: coin and items the pack, wounds the sheet, quests and facts the
  journal.
- **Wide and narrow:** on a screen 1100 pixels wide or more the panel sits beside the story and scrolls on its own,
  with the tabs at its foot. On a narrower one the tabs sit under the composer and open the panel as a sheet over the
  story; a dot on the Scene tab says the scene changed (a fight started) while it was closed, so nothing opens over
  the reading. Before the first line only people met and other branches show.
- **Classic and Reader:** two layouts for a wide screen (`deviceLook.ts` `layout`, kept per device; Settings >
  General > Appearance > Story layout, or the panel icon at the end of the tabs). Classic puts the panel beside the
  story; Reader keeps the story column alone and the panel in tabs under it, opening over the story as on a phone.
  A visual novel layout follows the Milestone 6 art.

## API

| Request | Does |
| --- | --- |
| `GET /api/story` | `{scene, messages, people, ready, dice_shown, branches, fight, intensity, map}`. `map` is the travel map as far as the character knows it (`{places, roads}`; places with `x`, `y`, `visited`, `here`), or null off any map. `intensity` is `{preset, chosen, world, voice}`: the preset in play, the player's choice (`world` follows the world) and the world's own preset and voice. `fight` is `{condition, dead, fight}`: the character's wound level, whether they are dead, and the fight under way (null when none) with its `round` and `foes` (`name`, `state`, and `wound` while the dice are shown). `branches` lists every branch with `playing`, `turns`, `last_line` and `last_at`, the one being played first. User messages carry their `rolls` and `pace` (`{steps, skipped, budget, total}`, seconds) while the dice are shown. `people` are those met, newest first, with `meetings`, `notes`, `doing` and `place` now. `scene` has the city, place, `local_time` (city clock, no offset), `weather`, the city's `places` and `around` (who is there, named only once met). `ready` is false without a model. |
| `PUT /api/story/scene` `{city_id, place_id?}` | Moves there; a city alone means its opening place. 404 for an unknown city or place, 409 in the middle of a fight. |
| `POST /api/story/messages` `{text, client_id}` | Saves the user's line once per `client_id` and returns `{message, reply}`. A failed reply is saved with `status: failed` and its `error`. Sending the same `client_id` again returns the saved reply, or tries again if it failed. 409 `no_connection` without a model; the line stays saved. 409 when the character is dead. |
| `POST /api/story/find` `{key}` | Moves the story to where someone the user has met is now. 404 if not met, 409 if they are nowhere the story can go. |
| `POST /api/story/retry` | Tells the reply to the latest user line again, replacing the one there. |
| `POST /api/story/messages/{id}/rewrite` | Rewrites `passage` of a narration in new words, with an optional `note`; same dice and facts. Returns the story. |
| `POST /api/story/messages/{id}/switch` | Switches a rewritten narration to its wording before the rewrite, and back. Returns the story. |
| `POST /api/story/messages/stream` / `POST /api/story/retry/stream` | The same, streamed as newline-delimited JSON: `{"text": piece}` as the narration is written, then `{"done": {message, reply}}` once the reply is saved, or `{"error", "code", "status"}`. Fact extraction runs after `done`. |
| `GET /api/story/start` | `{premades, points, range, stat_names, meanings}` for "Who are you?" in the scene's city. |
| `POST /api/story/start` `{premade_id}` or `{persona, stats}` | Starts the story as a premade or a made character; 409 once the story has begun, 404 for a premade not in this town, 422 for a missing name or stats outside the point-buy. |
| `GET /api/story/sheet` | `{stats, stat_names, range, dice}`: the character's MARVEL stats and the die each one adds. |
| `PUT /api/story/sheet` `{stats}` | Changes some or all stats; 422 for an unknown stat or a value outside 1 to 30. |
| `POST /api/story/back` `{message_id}` | Back to before one of the player's lines, as a new branch; the story comes back with `draft`, the line to send again. 404 for a line not in the branch being played. |
| `POST /api/story/branches/{id}/switch` | Plays on in another branch, where it was left. 404 for a branch not in this story. |
| `GET /api/story/journal` | `{entries, quests}`: the facts the player's character knows, newest first, and the quests they know of with `status`, `hook`, `outcome` and `left` (story time left). |
| `POST /api/story/journal` `{subject, text}` | Adds the player's own note. |
| `PATCH /api/story/journal/{id}` `{text}` / `DELETE /api/story/journal/{id}` | Corrects or removes a fact, logged; 404 for hidden truth or a fact not in the journal. |
| `GET /api/story/gear` | `{coins, currency, slots: {used, max}, items, shop}`. `shop` is null away from a shop, else `{place_id, open, keeper, stock, offers}`; `offers` maps the character's items to what the shop pays. |
| `POST /api/story/shop/buy` `{item_id, qty?}` / `POST /api/story/shop/sell` `{inventory_id, qty?}` | Trades at the counter. 404 with no shop here or no such item, 409 when closed, out of stock, too dear, too heavy, or not something the shop buys. |
| `GET /api/story/table` / `PUT /api/story/table` | This campaign's rules (`intensity`, `drama`, `injury_persistence`, `show_odds`, `roll_dice`, `show_adult_side`, `gm_view`, `cutaways`, `defeat`); a change to what is shown is remembered for the next campaign. `GET /api/story` carries them as `table`. |
| `DELETE /api/story` | Starts a new story: the history, every branch, the record and the people met go, the scene stays. |

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

### How they feel about you

Each person met has five feelings toward the player's character (`dungeon/feelings.py`): trust, affection and
respect from -5 to 5, fear and desire from 0 to 5. Code moves them:

- A roll whose action names them moves them by its stat and how it landed. Allure that works raises affection and
  trust and one that fails costs trust; Resolve that lands raises fear and respect; a fight raises fear and costs
  affection. A critical result moves them twice as far.
- With a Continuity model chosen, its question after each turn lists the people there by key, and it may answer
  that the turn moved someone (each change -2 to 2), with a short reason kept as one of their impressions of the
  character (the last four).
- Each change is at most 2 a turn and stays in range. "Tell it again" puts them back as they were when the line
  was sent; the kept rolls move them again.

The narrator reads them in words ("Toward the player's character: is wary of them, is uneasy around them"), with
the impressions. An Allure roll aimed at someone whose trust and affection add up to 4 or more is a step easier,
and -4 or less a step harder. With the dice shown, "People you've met" shows the feelings too ("Trusts you a
little, likes you").

Named people (a city's notables) also bring their own business to every scene: who they are and what they are
after right now (their `wants`, else their drawn goal), and the narrator is told they pursue it unprompted. A notable
who runs the place (its keeper, its priest) but is not there now is still named to the narrator as away, so no
other keeper is made up in their post.
