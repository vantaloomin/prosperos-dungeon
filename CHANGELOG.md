# Changelog

## Unreleased

- **How it's written.** Tone and rules (and session zero's Fine-tune) let you choose the narration's point of view
  (close third, second or first person), tense (past or present) and length (short, medium or long), and change them
  at any time. New campaigns start in close third person, past tense; stories already under way keep "you" and the
  present tense until you change them.
- **Fate.** A new ruleset to pick when a story starts. Your character is a high concept, a trouble and a few more
  aspects in your own words, six approaches (Careful, Clever, Flashy, Forceful, Quick, Sneaky) and a stunt or two.
  Each try rolls four Fate dice against the Fate ladder. When a roll falls short, a fitting aspect is invoked for a
  Fate point; when your trouble gets you into it, you earn one back. Sleep refreshes them.
- **Custom layout.** Settings > Appearance > Story layout > Custom turns the scene panel into tiles you arrange:
  press Arrange to move them, size them small, wide or tall, add or remove them, and save layouts by name.
- **Decision models for the Referee.** Settings > Models has a Decisions section and a Referee decisions job. A
  decision model gives the odds of each answer instead of writing: whether an action needs a roll, which stat and
  how hard. Choose Jev through OpenRouter, OpenAI Decisions, or a small model on your computer (Qwen3.5 4B, say);
  a text profile on a local server works too, so the narrator's own model can decide. If it fails, the Referee
  decides as before.
- **Updating after a squash merge.** update.bat and update.command no longer stop with "Not possible to
  fast-forward" when your main has commits GitHub's main doesn't (as after a squash merge). They save those commits
  on a dated `backup/main-...` branch, then move main to match GitHub. Uncommitted edits still stop the update.
- **Claude and ChatGPT sign-in on Windows.** Testing a Claude Code or Codex profile no longer fails with a server
  error when Dungeon runs in development mode (dev.bat); if the CLI can't be started, the test says so plainly.
- **Work and oaths.** Cyrel's reeve, the Timber Guild and the wardens past the stones put work your way: find a
  deserter, collect a debt, carry a message nobody should know about. It pays and wins standing, and failing it
  costs you. Promises you make in the story are kept as oaths with deadlines, and the people you swore to remember
  if you break them.
- **Factions.** Cyrel's crown, the Timber Guild, the elves past the border stones and the powers beyond pursue
  their own ends on the story clock: a war levy, a sawmill bought out, border stones moved in the night. The news
  reaches you in town whether or not you had a hand in it. Powers beside the story shows who you know of and how
  you stand with them.
- **The world happens to you.** Life Cards now turn up in play: a day in Kingswood, a road, a night in the open can
  bring news, trouble, a choice or a fight, and the game keeps what really happened apart from what you were told.
  "How eventful" beside the story sets how often, from Quiet to Merciless; it never touches the dice.
- **Stress.** Your first kill, a horror in the dark, a beating that nearly ends you: each tests your Resolve and
  can fray your nerve. Push it too far and it leaves a mark on the mind (nightmares, a temper, the shakes, a thirst
  for drink) that makes some things harder. Rest eases it.
- **Lasting injuries and treatment.** A maiming or a critical hit can leave a lost eye, a limp, a ruined hand or a
  scar: some things get harder, and people notice. Choose beside the story whether they stay, fade with time, or
  never happen. Bandage a wound from your pack, or pay a healer like Mother Rook to treat it; a bad treatment can
  make it worse.
- **Rest.** "I make camp", "I sleep" or "I rest for three days" is decided by the game. Inns and towns are safe;
  out in the open each night can go wrong (rain, cold, raiders in the Badlands, Brynwyr's wardens), less so if you
  keep watch, hide the camp or set an alarm. Wounds now mend gritty: a night for a graze, four for a real wound,
  a week for a maiming, and a hungry night mends nothing.
- **Journeys.** "I set out for Eriane" walks the roads of Vallarith: hours on foot, nights camped, a day's food
  from your pack for each day, and the region's dangers on the way (bandits on the Cyrel road, raiders in the
  Badlands, wardens in Brynwyr's forest). The Map beside the story shows where you have been and what you have
  heard of; the rest stays in the fog.
- **Two Claude accounts.** A Claude Code profile can name its own account folder (Settings > Models), so a
  second Claude plan gets its own profile. Test connection says how to sign in to it and which account it is.
- **Rewrite.** When the game spots a problem it had no time to fix (a dead man waving, a stock phrase), that
  paragraph is softly marked; the "?" says why, and Rewrite asks the narrator for new words. Select any passage
  of the story to rewrite it too, with a note if you like. The dice and what happened stay the same, and Switch
  wording goes back to how it was.
- **What's in the chest is decided before anyone describes it.** Search a chest, a drawer, a body or a stranger's
  pockets in Kingswood and the game rolls what is there first, keeps it, and notes it in your journal; the
  narrator describes only that, and it is the same the next time you look. A failed search misses it. "I take the
  coins" moves what you found into your purse and pack.
- **Faster turns.** The story now streams in a sentence at a time, and the record keeping (facts, the story so
  far) happens after you can read the reply. Plain lines like walking or ordering a drink skip the Referee's
  model, and the check against the record runs only when the narration names someone who is dead. Each turn has
  a time budget (Settings > Models > Turn speed); past it, the polishing steps give way, never the dice or the
  record. With the dice shown, each line says how long its turn took.
- **Haggle and buy in the story.** In an open shop, "I haggle over the rope" rolls Allure and moves the shop's
  prices for the rest of the day: up to a quarter off, or dearer if it goes badly. "I buy two loaves of bread"
  buys them at that price before the narrator writes the scene. The counter shows today's haggled prices.
- **How far the story goes.** Each world sets its own intensity and narrator voice: Kingswood is unflinching and
  grim. "How far the story goes" beside the story turns violence, sex, horror, cruelty and drugs down to mature or
  restrained, or back to the world's own, at any time; the next line follows it.
- **A fixed Story screen.** On a wide screen your character sheet, pack, the shop counter, what you know and the
  people you've met sit in a panel beside the story instead of piling up above it. On a narrow screen the panel
  folds above the story and scrolls on its own, so the story keeps its room.
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
