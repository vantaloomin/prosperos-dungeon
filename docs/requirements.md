# Prospero's Dungeon: requirements

*Gathered 2026-10-20 to 2026-10-21 in the "Requirements and system design" thread. A living document: decisions are settled, proposals are open to change.*

## Vision

An all-in-one, local-first AI TTRPG simulator for adult, morally complex, dark stories where good
outcomes are not guaranteed. Complex underneath, easy for the player. The program makes the
decisions; the language model narrates them.

## Foundations

| Source | What Dungeon takes |
| --- | --- |
| Prospero's Companion | The backbone, as a clean copy: Python backend, React/Vite UI, any model provider, model per job, timelines, memory, life simulation, world data format, townsfolk, Story-mode narrator |
| Prospero's Companion (cont.) | "Life Cards": the Life deck (`companion/life/deck.py`, `world/data/life_deck.json`): seeded draws of weighted cards into the day, gated by a drama level, alongside Study's d100 random tables reworded for life |
| Prospero's Study | The Story randomness engine Life Cards grew from (`server/mechanics/`): seeded d100 activation, cooldown, major-disruption cap, ~30 event / extra / handling tables |
| Mabry Curve (RP archive) | The reference turn loop, hidden-information model, continuity tracking, off-page cadence and house rules |

## Decided

- **Start from a clean copy of Companion's code** (no git history carried over), then grow from there.
- **Rule systems are selectable** (Vanta, 2026-10-21): the player can pick from several built-in
  TTRPG rulesets, including MARVEL and open-licensed systems. See "Rulesets" below.
  - Each world names a default ruleset. The player can change it when starting a campaign; after
    that it is locked, so sheets never need converting.
  - Each ruleset ships with its full open content from the start (classes, spells, monsters, items,
    oracles), not resolution only.
  - First three: **MARVEL**, **D&D 5e via SRD 5.2** (2024 rules), **Ironsworn/Starforged**.
    Basic Roleplaying is next.
- **MARVEL dice (the house ruleset):** d100 plus a stat-based bonus, with a difficulty shift, landing in six bands:
  Critical failure, Fail, Fail with an upside, Success at a cost, Success, Critical success.
- **MARVEL stats:** Mind, Allure, Resolve, Vitality, Essence, Luck.
- **Roll visibility:** a toggle between hidden (felt only through the story) and exposed.
- **Worlds:** Dungeon's own versions built from Vanta's bases: **Vallarith** (grimdark D&D-style),
  **Havenbrooke** (modern fantasy, supernatural university, 2009), and Mabry Curve's **BABEL** tower.
- **Player voice:** the narrator expands the player's input rather than refusing to write their
  character. "I taunt the demon and attack" becomes a taunt in the Persona's own voice, shaped by
  the roll.
- **Persona:** each world defines its own player Personas (sheet, voice, stats). The player can pick
  any main-cast member (any of Havenbrooke's nine, say) or create their own; every world allows
  player-made personas.
- **Branching and dice:** going back always brings new dice, even for the same actions.
- **Progression:** per world, built from track types the engine provides: Rank, XP, Grades, Time,
  and proposed Reputation, Bonds, Milestones, Corruption, Use-based skill growth, Wealth. A world can
  use several at once.
- **Narration format:** a player setting (length, POV, tense), not fixed per world.
- **Platform:** like Companion: local web app (Python backend, browser UI) on Windows, Mac scripts,
  phone access over the player's own Tailscale.
- **Play screen:** a customizable widget layout. Candidate widgets: story text (with clickable lore
  and character links that open modals), background art, map plus current location, VN-style
  portraits of characters in the scene, character sheet, party and relationships, inventory,
  status windows, a "what I know" journal, progression tracks. Layout presets (classic RPG,
  visual novel, text-first) on top of free arrangement.
- **Content limits:** no hard lines beyond adults only, which is the premise and always on.
- **NPCs and party:** always autonomous. They can be influenced like real people, never commanded.
- **Death:** always possible. Recovery is Study's infinite branching: go back to any earlier point
  and take another path; the dead branch is kept.

## Rulesets

Code still decides and the model still narrates, whatever ruleset is active. A ruleset is a
pluggable module that supplies:

- **Character sheet:** attributes, skills, derived values, character creation steps.
- **Resolution:** how a check is rolled (d100 roll-under, d20 + modifier vs DC, 2d6 moves, action
  die vs challenge dice) and its result.
- **Outcome mapping:** every result is translated onto one shared outcome ladder (Critical failure
  through Critical success), so the narrator, Life Cards, continuity and the UI work the same way
  under any ruleset.
- **Referee questions:** what the Referee and Jev must decide per action (MARVEL: stat + difficulty;
  5e: ability, skill and DC; Ironsworn: which move; PbtA: which move and stat).
- **Progression:** which tracks it uses (levels and XP, ranks, milestones, momentum).
- **Content packs (data, not code):** classes, spells, monsters, items, oracles, where the license
  allows. Shipped in full with the ruleset.
- **Attribution:** each pack carries its license notice, shown in the app (SRD 5.2 needs one
  attribution sentence; WotC trademarks such as "Dungeons & Dragons" are not used).

### Candidate systems and licenses

Dungeon is public, AGPL software, so a ruleset ships only if its license covers software. Licenses
marked "unverified" were checked from memory or secondary coverage, not the license text.

| System | License | Fit | Notes |
| --- | --- | --- | --- |
| **MARVEL d100** | Vanta's own | House default | Mabry Curve's system. |
| **D&D 5e: SRD 5.2** (2024 rules) | CC-BY-4.0, irrevocable (Apr 2025) | Strong | One attribution sentence. Excludes D&D Beyond Basic Rules and WotC trademarks. |
| **D&D 5e: SRD 5.1** (2014 rules) | CC-BY-4.0 | Strong | Pick 5.1 or 5.2, or both. |
| **Basic Roleplaying (Chaosium)** | ORC (2023 Universal Game Engine) | Strong | d100 percentile skills, close kin to MARVEL. |
| **Pathfinder 2e Remaster** | ORC (Archives of Nethys is the official SRD) | Medium | Very crunchy; big lift to do well. |
| **Ironsworn / Starforged** | CC-BY-4.0 for SRD, moves, assets, oracles | Strong | Built for solo play with oracles; fits an AI GM. |
| **Fate Core** | CC-BY-3.0 (unverified) | Medium | Narrative; aspects map well to LLM play. |
| **Blades in the Dark / Forged in the Dark** | CC-BY-3.0 (unverified) | Medium | Position and effect, clocks. |
| **PbtA** | Per game, not one license | Varies | Apocalypse World isn't open; Dungeon World is CC-BY-3.0 (unverified). |
| **Cairn** | CC-BY-SA-4.0 (unverified) | Medium | Share-alike applies to derived text. |
| **Year Zero Engine** | Free League Free Tabletop License | Risky | Written for tabletop games; software use unclear. |
| **Cypher System** | Cypher System Open License | Risky | Written for tabletop games; software use unclear. |
| **The Black Hack** | OGL 1.0a (unverified) | Low | OGL obligations; low priority. |

## Shops and economy

Code decides what a shop has and what it costs; the narrator only voices the shopkeeper. The
narrator never invents an item, a price or money: it gets the shop's real stock and quotes.

**What already exists in Companion:** each city has a `currency`, places with a price level,
careers with pay bands, rents, and a `prices` list of everyday goods as low–high ranges with a
seeded `price()` picker. Dungeon extends this rather than starting over.

- **Shops are places with an owner.** A shop is a world place with a type (general store, smith,
  apothecary, tailor, bookseller, fence, black market, campus store, and so on), a wealth tier, and
  a shopkeeper who is a townsperson with a schedule. Opening hours come from that schedule, so a
  shop can be closed, or the owner out sick.
- **Item catalog per world and ruleset.** Each item has a base price in the world's currency,
  category, rarity, legality, and its rules stats for the active ruleset. 5e uses SRD 5.2's
  equipment and price lists as written (in gp). MARVEL items are priced in the world's own currency;
  Havenbrooke uses real 2009 prices.
- **Realism check.** Base prices are anchored to the world's wages and rents (what a day's work
  buys), and a data test flags items that are out of line.
- **Services are priced the same way.** Inns and taverns (a night's lodging, meals, drink),
  stabling, baths, healers, scribes, guides, passage and hirelings come from the same catalog and
  modifiers. Lodging comes in comfort tiers (a floor by the fire up to a private suite), and the
  narrator only quotes the tier's real price.
- **Affordability guard.** Every catalog price is checked against what each class of people earns
  in that world, so ordinary things stay within ordinary means. Example rule: a common-room night
  plus a meal costs no more than about a day's wage for an unskilled worker, and a modest room
  about a skilled worker's day. A night at an inn never costs a year of a peasant's life. The data
  tests fail on any price that breaks its tier's bounds.
- **Stock generation.** Seeded and deterministic from shop type × settlement size × wealth tier ×
  rarity. Quantities are finite; what the player buys is gone. Rare items are few or absent in
  small places.
- **Restocking.** On the life-sim clock (deliveries on a cadence per shop type), so stock changes
  while the player is away. Shopkeepers buy the player's goods at a markdown and resell them.
- **Price modifiers.** base × region (distance from the source, local scarcity) × settlement ×
  shop tier × reputation and relationship with the owner × current events × legality markup
  (a fence pays little, a black market charges a lot). Each modifier is clamped and logged.
- **Life Cards and world events move markets.** A shortage, a caravan raid, a festival, a war or a
  plague changes stock and prices for a while. Shops can open and close as Companion's cities
  already do.
- **Haggling is a roll.** An opposed check in the active ruleset (MARVEL: Allure vs the owner's
  Resolve; 5e: Persuasion, Deception or Intimidation vs Insight; Ironsworn: Compel) mapped onto the
  outcome ladder. Success lowers the price; success at a cost gets the price but the owner
  remembers; a critical failure can raise prices or get the player thrown out.
- **Money is tracked by code.** Wallet, carried goods and a transaction log live in the database.
- **Shop window and story both (decided).** Talking to a shopkeeper in the story opens a shop
  window with the stock list, prices and buy/sell; either side can drive the purchase.
- **Selling and fencing (decided).** The player can sell loot and fence stolen goods. Stolen goods
  are tracked as such; fences pay less, and honest shops may refuse them or call the watch.
- **Shopkeeper cash (decided, toggle).** Shopkeepers have finite cash by default, so a village smith
  can't buy a dragon hoard. A setting turns this off.
- **Ironsworn (decided):** keeps its abstract Supply track and buys with moves; the world's
  currency is color only.

## Combat

Decided 2026-10-21. Code runs the fight; the narrator writes it. Whatever the ruleset, every
attack, save and morale check is rolled by code and mapped onto the shared outcome ladder.

- **Positioning: zones, grid optional.** Every ruleset tracks range bands (engaged, near, far) and
  named areas ("the bar", "the stairs") in code. An optional grid battle-map widget is available
  for 5e fights.
- **Pacing: one post is one round,** with a plan option. The player declares an action; code
  resolves every combatant in initiative order and the narrator writes the whole round. A "fight
  on my plan" option takes an intent ("hold the door, protect Kenzie") and auto-resolves rounds
  until a turning point: someone falls, morale breaks, a new threat arrives, or the plan stops
  making sense.
- **Who decides enemy actions.** Code lists the legal actions each round. Ordinary enemies use
  rule-based tactics per creature type; named enemies and autonomous allies have the Referee model
  pick using their personality and goals. Code checks legality either way.
- **Morale.** Code tracks morale per side. Losses, a fallen leader, fear and being outmatched
  trigger morale rolls; a broken side flees, surrenders or begs. That leaves the player choices
  like sparing, ransoming, interrogating or executing.
- **Surprise and ambushes are rolled.** Before a fight, code rolls stealth against awareness for
  both sides, including ambushes on the player while travelling or asleep. The surprised side
  loses its first round or acts last.
- **Damage per ruleset.** 5e keeps HP; Ironsworn keeps Health and harm. **MARVEL uses wound
  levels:** a hit lands as Grazed, Hurt, Wounded, Maimed or Dying, set by the roll band and the
  weapon, and each level carries penalties until treated.
- **Enemy status visibility follows the roll toggle.** With rolls exposed, the combat widget shows
  exact HP, wounds and conditions; with rolls hidden, only descriptive states ("bloodied",
  "staggering", "won't last").
- **Losing a fight: the defeat table.** The ruleset's own rules apply first (5e death saves,
  Ironsworn's Face Death, MARVEL's Dying level). If those are lost, code rolls the outcome,
  weighted by what the winners want: death, capture, robbed and left for dead, or rescued.
  Slavers capture, bandits rob, beasts kill. Death stays possible, and the player can always
  branch back.

## Injuries and recovery

Decided 2026-10-21. Code tracks every wound, treatment and condition; the narrator describes them.

**Everything here sits under one campaign setting, Injury persistence** (Vanta):
- **Permanent** (default): lasting injuries and stress conditions stay until something
  extraordinary fixes them.
- **Temporary:** they still happen but fade on their own over time.
- **None:** no lasting injuries or conditions; wounds matter only until they heal.

- **Healing speed: as written, with a gritty toggle.** Each ruleset heals as written by default
  (5e long rests, Ironsworn's recovery moves). A campaign setting switches on gritty healing, where
  serious wounds take days to weeks of in-game time in any ruleset. **MARVEL is gritty by
  default:** a wound drops one level after a stretch of rest set by its severity.
- **Permanent injuries are rolled.** A Maimed result, a critical hit or a failed death save rolls
  on a lasting-injury table (a lost eye, a limp, a ruined hand, a disfiguring scar). Each has a
  mechanical effect and a social one that NPCs react to. Under Permanent it stays until something
  extraordinary fixes it, such as rare magic or a master healer, at a price.
- **Treatment takes a healer, supplies and a roll, and can go wrong.** The roll uses the healer's
  skill and what they have on hand. A bad roll can mean infection, a badly set bone or a wound that
  reopens. Magic healing still works where a world has it (Vallarith's clerics, BABEL potions),
  under that world's rules. Healers and medical supplies are shop and service items with real
  prices, and Life Cards can bring plague or contaminated supplies.
- **Mental harm: a stress track.** Code tracks stress from traumatic events: horror, torture,
  loss, a first kill, betrayal. MARVEL resists with Resolve; other rulesets use their nearest
  equivalent (5e Wisdom saves, Ironsworn's Spirit). Past thresholds, code rolls a lasting condition
  such as nightmares, a phobia, numbness or a compulsion. Conditions can ease with rest, support
  and time, and the narrator plays them consistently across the campaign.

## Time and travel

Decided 2026-10-21.

- **World clock: story time, with a per-world option.** In-game time advances with what the player
  does (a conversation takes minutes, a journey days), and the life sim, shops, NPC schedules and
  deadlines all run on that clock. A world can opt into Companion-style real-time living instead,
  so it keeps moving while the app is closed (a natural fit for Havenbrooke).
- **Journeys: map crawl.** Each world has a travel map: a node graph of places joined by routes
  (with distance, terrain and danger), plus optional hex regions for open wilderness. A map
  widget shows it with fog of war, so unexplored places stay hidden until found. Every step costs
  in-game time and supplies (or Ironsworn Supply) and rolls weather and events. Vallarith's maps
  are the first candidates to digitize.
- **Road encounters: region danger plus Life Cards.** Each region has a danger level and its own
  encounter tables: monsters, bandits, patrols, travellers, merchants, strange sights. Life Cards
  and world events shift them (a war brings patrols and deserters, a plague empties the roads).
  Fights that follow use the Combat rules, including rolled ambushes.
- **Resting is risky and the world moves.** Resting outside a safe place can be interrupted by a
  roll weighted by region danger and precautions taken (watches, hidden camp, wards). While the
  player rests, time passes: NPCs act, deadlines tick, rumors spread, shops restock, and wounds
  and stress recover under the Injuries rules.

## Inventory and equipment

Decided 2026-10-21. Code owns every item; the narrator can't add, remove or invent gear.

- **Carrying limits: slots, with a toggle.** Every character has carry slots in every ruleset:
  more with Vitality (or the ruleset's strength stat), packs, and mounts or vehicles. A dagger
  takes a fraction of a slot, a sword one, armor several. A campaign setting turns carrying limits
  off entirely.
- **Visible gear is tracked.** Code knows what is worn, wielded and on display (a drawn sword,
  fine silks, a guild badge, blood on your clothes, a stolen ring its owner would recognize).
  It feeds NPC reactions, guards, thieves, reputation and shop prices.
- **Wear: breaks on bad rolls.** No durability numbers. Critical failures and heavy hits can
  damage or break weapons, armor, tools and clothes. Damaged gear works worse until repaired;
  repairs are a priced shop service (smiths, tailors, tinkers).
- **Loot: plausible, plus hoards.** Bodies and pockets hold what that person plausibly carried,
  built by code from who they were (a bandit's few coins, knife and stolen ring; a noble's signet
  and purse). Lairs, vaults and bosses use the ruleset's own treasure tables (5e SRD treasure,
  Ironsworn rewards), adapted to the world's currency.
- **Appearance state (Vanta).** Code tracks how each character looks right now, and the narrator
  describes it consistently:
  - **Cleanliness:** clean, worn, grimy, filthy, plus specific marks (blood, mud, sweat, other
    fluids, scent). Travel, fights, weather, work and sex raise it; washing, baths and laundry
    clear it. Baths and laundry are priced services.
  - **Clothing condition:** intact, rumpled, torn, ruined, per garment. Bad rolls, fights and
    deliberate tearing damage clothes; tailors repair them.
  - **State of dress:** per clothing layer (outer, under, accessories): worn, loosened, partly
    off, removed, and where a removed item ended up.
  - All of it is visible gear, so NPCs react to it. Companion's grooming data (hair, nails and
    facial hair changing over time,
    `world/data/grooming.json`) rounds out looks for modern worlds. A world can switch the
    detail level down (Vallarith might only track cleanliness and condition).

## Quests and factions

Decided 2026-10-21.

- **Quests come from three places.** Authored arcs in the world package (Havenbrooke's seasons,
  Mabry's Season events); jobs code generates from what NPCs and factions need right now (a debt,
  a missing daughter, a rival to remove); and emergent quests from promises, threats and bargains
  the player makes in play, which code records as obligations.
- **The journal shows what the character believes.** Objectives, leads and suspicions are recorded
  as the character understands them, which can be incomplete, wrong, or a lie someone told them.
  The truth is stored separately as hidden fact and surfaces only when discovered in play; where
  belief and truth differ, code keeps a wrong-footing record, as Mabry Curve does.
- **Factions act on their own goals, with clocks.** Each faction (guild, church, gang, noble house,
  campus society) has goals, resources, relationships with other factions, and progress clocks
  that advance on the world clock. They scheme, ally, trade and go to war whether or not the player
  is involved, and their needs feed generated quests. The player's standing with each is a
  Reputation track.
- **Quests have real deadlines.** Many quests carry a deadline on the story clock. If the player is
  late, the hostage dies, the rival wins or the job goes to someone else, and the world remembers
  it (reputation, NPC memory, follow-on consequences).
- **Institutions are factions; their demands are quests; the result is a track.** A university,
  guild, army or church is a faction the player belongs to. Its recurring demands become generated
  quests with deadlines on the story clock: Havenbrooke's assignments, exams, labs and club duties;
  a guild's dues and contracts. How the player does on them feeds a progression track (Grades,
  Rank) and their standing with the institution. Classes and shifts occupy fixed slots in the
  player's schedule, the same way Companion's careers do, so skipping class is a real choice with
  consequences.

## NPC minds

Decided 2026-10-21. "Autonomous but influenceable" rests on this model. Code holds each NPC's
state; the Referee and narrator read it and never contradict it.

- **Memory is tiered.** Key NPCs keep full, typed memories of the player, like Companion's
  companions. Minor NPCs keep a few short impressions ("stiffed me on the bill", "was kind to my
  daughter"). Crowds keep none. An NPC is promoted to a higher tier when they start to matter, and
  keeps what they had.
- **Feelings run on several axes.** Separate tracks for trust, affection, respect, fear and
  desire, each moved by events and rolls. An NPC can fear and want the player while trusting them
  not at all. The axes feed persuasion difficulty, what NPCs will do for the player, and when they
  turn on them.
- **Word gets around.** Code spreads news along NPC relationships and factions over time, as
  Companion already does. Accuracy degrades with each retelling, some NPCs keep what they know to
  themselves, and the player's reputation can arrive before they do.
- **NPCs keep secrets and lie, and detection is rolled.** Each NPC has hidden goals and secrets
  stored apart from what they say, like the player's own hidden truths. They may lie when it
  serves them. An insight roll against their deception decides whether the player notices, and a
  lie believed goes into the player's journal as belief, not truth.
- **NPCs have their own lives.** Key NPCs pursue their goals and follow life-sim schedules when
  they are off-scene (Companion's townsfolk and life engine), so they are somewhere, doing
  something, when the player looks for them.

## Memory and context

Decided 2026-10-21 (round 1). A campaign runs far longer than any model can read at once, so code
decides what the narrator sees each turn.

- **Layered recall.** Each turn the narrator gets the recent turns word for word, older scenes as
  chapter summaries, and facts pulled in by relevance: who is present, where the scene is, and
  anything just mentioned (names, places, items, promises). This builds on Companion's and Study's
  summarizing, and on Mabry's continuity file.
- **A code-kept canon ledger is the source of truth.** Code records facts as structured entries:
  deaths, items, injuries, promises, locations, secrets, relationships, clock states. After each
  narration a cheap model extracts new facts the narrator introduced (a scar, a name, a rumor).
  Code checks them against the ledger and stores them, and rejects any that contradict it.
  Summaries are prose on top, and the ledger wins any conflict.
- **Hidden truth and character knowledge are separate.** Each ledger entry is marked as world
  truth, character belief, or both, which keeps the journal and wrong-footing rules from
  "Quests and factions" and "NPC minds" intact.
- **The player sees and edits what their character knows.** Corrections are logged, so a model
  mistake is easy to fix. Hidden truth stays hidden by default. A settings toggle opens a full
  GM view that shows and edits everything, secrets included.
- **Context auto-fits each model, with a player cap.** Code knows each model's window and fills it
  in a fixed priority order: ruleset and persona, the current scene and state, the NPCs present,
  recent turns, recalled facts, then summaries. It trims from the bottom. A setting caps tokens
  per turn to control cost and speed on paid models.

Round 2, decided 2026-10-21:

- **Contradictions are rewritten before the player sees them.** If a narration clashes with the
  ledger (a dead NPC waves, spent coin reappears), code has the narrator redo that passage first.
  A setting skips the check for speed on slow local models.
- **Chapters close at scene breaks.** Code starts a new chapter on a location change, time skip,
  rest, or the end of a fight or quest step, and summarizes the one that ended. The player can
  also close a chapter themselves and name it. Chapters give the story view and branch view
  their structure.
- **Branches are sealed, except a player notebook.** Each branch forks the ledger at the branch
  point (with new dice). The character and NPCs know only what happened on their branch. A
  player-only notebook spans every branch, and no model ever reads it as character knowledge.
- **Characters forget, but grudges stick.** The ledger keeps every fact. What NPCs and the player
  character are treated as remembering fades by importance and age, while big events (betrayal,
  a death, a debt) stay. Memories tied to strong feelings (fear, hatred, love) stay sharp
  regardless of age. A roll can recall a faded detail.

## Campaign management

Decided 2026-10-21.

- **Every turn is a save, plus bookmarks.** Each turn is saved automatically as a point in the
  branch tree, and going back from any point gives new dice. The player can bookmark and name
  moments to find them fast. A per-campaign **Ironman** mode, chosen at campaign start, turns off
  going back, so death is final.
- **Branches have two views, as widgets.** A chapter list reads the current branch like a table of
  contents, with a switcher between branches. A tree view maps every chapter and branch; clicking
  a node reads it or plays on from there, and dead ends are marked by how they ended.
- **Campaigns are separate, with a legacy option.** Each campaign starts from a fresh copy of its
  world. At campaign start the player may import a finished campaign's outcome as world history,
  so an old character can be a legend, a villain or a corpse.
- **Export as a backup or as a book.** A full campaign file (ledger, branches, saves, settings)
  for backup or moving machines, importable again. The story of one branch also exports as a
  readable book in Markdown, EPUB or PDF.

## Art

Decided 2026-10-21. Builds on Companion's image pipeline. By default art is made only when the
player asks, so play never waits on it and costs nothing. A **Passive art** setting adds automatic
art on top.

- **Passive art (setting, off by default).** When on, code triggers images from game events: a new
  named character appears, the scene moves to a new location or time of day, a portrait goes out
  of date, or a big moment happens (a death, a reveal, a defeat, a chapter end). Most triggers are
  plain code checks on ledger and state changes; for less clear moments the decision model (Jev)
  answers "is this worth illustrating?". Passive art runs in the background and never holds up
  the text. A per-session cap limits how many images it makes.

- **Anything can be illustrated, on request.** VN-style character portraits with expressions,
  location backgrounds by time of day, full scene illustrations, and a button to illustrate any
  passage. Images are saved with their chapter, are reused
  until something changes, and go into the book export.
- **Every named character gets one reference image.** The first portrait of a named character
  becomes their reference, reused in every later image so they keep looking like themselves. No
  LoRA training is required (Companion's trainer stays available as an optional upgrade).
- **Portraits show full live state.** Images are built from what code tracks: wounds, scars and
  maims, gear, cleanliness, clothing condition, state of dress, and mood from the NPC feeling
  axes. When that state changes, the portrait is marked out of date, and the player can refresh
  it with one click.

## Intensity and tone

Decided 2026-10-21. There are no hard lines beyond adults only. These settings control what is
shown and what the tables can produce, so each player can tune the game to their comfort.

- **Intensity is set per category, with presets and veils.** Each category has its own slider:
  violence and gore, sex, horror, cruelty and abuse, drugs, and others the worlds need. Presets
  such as Restrained, Mature and Unflinching set them all at once. **Veils** name specific topics
  that may still happen but always fade to black on the page.
- **Worlds set the default, and the player can change it at any time.** Each world suggests its
  levels (Vallarith grimdark, for example). The player can adjust them at any point, even
  mid-scene, without restarting. Unlike rulesets, intensity never locks.
- **Lower settings also change what can happen.** Code filters event tables, Life Cards, defeat
  tables and injury results by the current levels, so a lower setting removes some outcomes
  entirely (for example, no sexual-violence results or fewer maims), not just their description.
  At the top setting, every outcome stays in play. Veiled topics stay in the tables but are
  narrated off the page.
- **Tone is a separate dial with two parts.** A **voice** setting (grim, wry, romantic, hopeful
  and so on) shapes how the narrator writes. A **drama** setting weights Life Cards and event
  tables toward calmer or more eventful draws, building on the Life deck's drama level. Neither
  part ever changes roll odds, so good outcomes are never guaranteed.

## Scaling and tiers

Decided 2026-10-21. Supports the classic "save cats, kill rats, eventually kill a god" arc as an
option. Work that finds the player matches their standing: nothing below it unless they go looking,
and never two or more tiers above it.

- **Standing comes from a per-world track.** Each world names which progression track sets the
  player's tier (Rank, Grades, XP, renown and so on), mapped onto one shared tier ladder (for
  example Local, Regional, Realm, World, Mythic) so code can compare quests, foes and regions
  across rulesets.
- **Offers come at your tier, with a rare +1 stretch.** Quests that come to the player unasked are
  at their tier. Now and then a +1 offer appears, flagged beforehand by a rumor or an NPC's warning
  as beyond them. Offers at +2 or above never appear. Lower-tier work is always there for a player
  who seeks it out (a notice board, a favor for a friend), but it never comes to them.
- **The world is fixed, but threats can find you.** Regions, foes and treasure keep their own tier
  and do not rise with the player. A player can walk into a region far above them; signs, rumors
  and NPCs warn first, and death is real. Faction clocks can also send higher-tier trouble after a
  player who has made powerful enemies.
- **The arc has start, ceiling and pace sliders.** Each world sets defaults. At campaign start the
  player picks a starting tier, a ceiling tier (Grounded stays low, Classic runs rats to gods,
  Epic starts high) and a pace from slow burn to fast rise. Pace controls how fast the world's
  track climbs; the tier ladder itself stays the same.

## World packages (proposed)

The three bases arrive in three shapes: Mabry (canon / hidden / continuity markdown plus dice
files), Havenbrooke (character bibles with verbal fingerprints, world docs, season story beats,
a floor plan), Vallarith (a 102-entry keyword lorebook, magic and timeline docs, deities, maps).
Dungeon would normalize them into one package per world:

- **Canon:** world docs and lorebook entries (keyword-triggered, as Study's lore engine does).
- **Cast:** NPC sheets with voice, wants, fears, relationships, stats.
- **Persona(s):** the player character sheet(s) for this world.
- **Hidden truths:** what is true that the player character doesn't know.
- **Planned beats:** optional season or arc schedules (Havenbrooke's beats, Mabry's Season events)
  that the director steers toward but doesn't force.
- **Rules:** progression ladder, death rule, Life Cards tables, house voice and hard rules.
- **Assets:** maps and images.

## Turn loop (proposed, from Mabry Curve)

1. Player writes intent only.
2. **Referee** splits the turn into actions and decides what NPCs do on their own initiative.
3. For each uncertain or opposed action: needs-a-roll, stat, difficulty, opposing actor.
4. **Code** rolls, logs, and applies the band. Life Cards may inject an event.
5. **Narrator** writes the turn from the results; never contradicts a roll.
6. **Code** updates continuity (what the player character knows vs what is true), hidden records,
   character sheets and relationships; off-page characters get rolled beats on a cadence.

## Referee model (proposed)

- Its own model slot. A cheap text model (Haiku or local 3–4B) splits actions.
- **Jev** (TypeSafe via OpenRouter, hosted only) answers per-action questions with probabilities:
  needs a roll (yes/no), which stat (choice of six), difficulty (score 1–10). Close stat calls can be
  resolved by rule (higher stat, ask, or roll both).
- Fallbacks: text model answers the same questions; with no model, keyword rules.
- Note: turn text sent to hosted services is subject to their content policies.

## Open questions


- Exact licenses for Fate, Blades in the Dark and Dungeon World before they are added.

- Off-page characters and their cadence (Mabry uses rolled beats every third turn).
- Which proposed progression tracks to keep.
- Which widgets and layout presets ship first.
- World package file format, and how canon, hidden truth and player knowledge are stored.
