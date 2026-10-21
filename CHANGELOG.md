# Changelog

## Unreleased

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
