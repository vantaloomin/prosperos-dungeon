# Changelog

## Unreleased

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
