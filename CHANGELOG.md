# Changelog

## Unreleased

- **Fights.** Attack someone, or meet what the Heartwood holds, and the game runs the fight a round per line: hits
  wound by how well the roll went and what you carry, a parry blunts the reply, running can end it, and foes break
  when the fight turns. Your character can be grazed, hurt, wounded, maimed or dying, and a night's sleep heals a
  level. Beaten, what happens depends on who beat you: beasts kill, wardens take prisoners, robbers rob. Death is
  real, and going back to an earlier line undoes it. The Story screen shows your condition and who you are fighting.
- **Your pack and the first shop.** Your character starts with a purse and the kit that fits them, carries what
  their Vitality allows, and can buy and sell at Pell's Provisions in Kingswood while someone is behind the
  counter. The narrator knows what you carry and quotes the shop's real prices.
- **People have feelings about you.** Everyone you meet keeps trust, affection, respect, fear and desire toward
  your character. Charm, threats and fists aimed at someone move them, and so can the Continuity model, with a
  short reason they remember. Warm people are easier to persuade, cold ones harder. Kingswood's named people chase
  their own aims in every scene. With the dice shown, "People you've met" says how each feels.
- **Kingswood, the first Vallarith town, and its first quest.** A Post-Reform logging town on the edge of Brynwyr,
  with 29 places, six named people and three premade characters. "The Heartwood contract" runs seven days of story
  time; miss it and the stakes land. The border stones and the Heartwood are dangerous: every turn there rolls Luck,
  and a failure brings a threat. "What you know" shows the quests you know of and the time left.
- **The story clock.** Once a story starts, it keeps its own time: talk takes minutes, a fight longer, a night's
  sleep eight hours, a walk across town twenty minutes. The scene, the townsfolk and deadlines follow it,
  and going back puts it back.
- **The ledger and the story so far.** The game keeps a record of what is true (deaths, items, wounds, promises,
  places, secrets) and gives it to the narrator every turn. A new Continuity model job lists the facts each narration
  brings in and folds older turns into a rolling summary. "What you know" on the Story screen shows your
  character's facts, to correct, remove or add to.
- **Every turn is a save point.** "Go back here" under any of your lines starts a new branch from just before it,
  with the scene, the people you'd met and your sheet as they were, and the line back in the box to send again with
  new dice. The branch you left is kept under "Other branches" to play on later.
- **Upgrades can add columns.** `database.ADDED_COLUMNS` adds new columns to tables an older workspace already has.
- **Campaign start.** A new story asks "Who are you?": play one of the town's premade characters (Haddon Harbor
  has three) or make your own with a name, a few lines and MARVEL stats bought from 60 points. The narrator now
  knows who the player is, and what they are good and poor at, in words.
- **The turn loop (Milestone 1).** Each story turn is refereed and rolled in code before the narrator writes: the
  six MARVEL stats (Mind, Allure, Resolve, Vitality, Essence, Luck) under "Your character", a d100 roll plus the
  stat's die on the six-band ladder from critical failure to critical success, and the Referee, a model job that
  splits the turn into actions, with keyword rules when no model is chosen. "Show the dice" shows each roll under
  the line; hidden by default. Rolls are kept with the line, so a retold reply keeps the same dice.
- **Milestone 0, the companion removed.** The app opens on the Story. The focal companion and everything built
  around it are gone: the chat and its styles, the phone and pairing, Today, memories and memory extraction, the
  profile and feed, the sidecar, relationship arcs, the companion's daily life and chores, the Study importer, the
  city map, LoRA training, voice notes and chat photos. Settings keeps General, Models, World, Images, Backups,
  Debug and Advanced. Worlds and personas stay, and each new world now gets its own town.
- **Kept engines:** the narrator, odds and rolls, Life Cards, the townsfolk and world generators, the calendar,
  memory recall, every text model provider (claude -p and Codex included), image backends and the voice engines.
- **Fresh schema.** Workspaces start from a new `schema.sql` with only the tables the story uses. A Companion-era
  Dungeon workspace is not upgraded; start a new data folder.
- **Backups** hold the database only, named `dungeon-<time>.zip`. The log is `logs/dungeon.log`.
- **Starting point:** a clean copy of [Prospero's Companion](https://github.com/vantaloomin/prosperos-companion)
  v0.15.0, renamed to Prospero's Dungeon. It installs and runs beside the Companion and the Study: its own port
  (8785, dev interface 5177), data folder (`ProsperoDungeon`), credential service, backup format and
  `DUNGEON_` environment variables. Companion's own history is in its repository.
