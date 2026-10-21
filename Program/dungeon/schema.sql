-- Prospero Dungeon workspace schema. One database is one world: its persona, its story and the settings that
-- follow the user from world to world (dungeon/worlds.py). Nothing here is migrated: a schema change makes the app
-- upgrade a copy of the workspace (dungeon/upgrade.py), and CREATE TABLE IF NOT EXISTS keeps existing tables.

CREATE TABLE IF NOT EXISTS app_identity (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspace_settings (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  user_timezone TEXT NOT NULL DEFAULT 'UTC',
  -- 'default' until set: 'pc' follows this PC's timezone, 'chosen' was picked in Settings and is kept.
  user_timezone_source TEXT NOT NULL DEFAULT 'default' CHECK (user_timezone_source IN ('default', 'pc', 'chosen')),
  -- Start the local programs in use when the Dungeon starts (dungeon/launcher.py); off until turned on.
  auto_launch INTEGER NOT NULL DEFAULT 0 CHECK (auto_launch IN (0, 1)),
  -- The app's colors, Prospero's Study's palettes. custom_palette is JSON hex colors.
  color_scheme TEXT NOT NULL DEFAULT 'ink' CHECK (color_scheme IN ('ink', 'slate', 'umber', 'moss', 'wine', 'ash', 'custom')),
  custom_palette TEXT NOT NULL DEFAULT '',
  -- Light or dark: 'system' matches the computer (Paper or Ink), 'paper' is the light profile, 'scheme' uses color_scheme.
  theme TEXT NOT NULL DEFAULT 'scheme' CHECK (theme IN ('system', 'scheme', 'paper')),
  -- "Why it went this way": the odds behind how a turning went (dungeon/consequences.py).
  show_odds INTEGER NOT NULL DEFAULT 0 CHECK (show_odds IN (0, 1)),
  -- The adult side of life (dungeon/world/intimacy.py): off until the user turns it on; showing what townsfolk
  -- are like that way is a hidden value.
  adult_side INTEGER NOT NULL DEFAULT 0 CHECK (adult_side IN (0, 1)),
  show_adult_side INTEGER NOT NULL DEFAULT 0 CHECK (show_adult_side IN (0, 1)),
  -- Settings > Debug: write every model request and response in full to logs/model-calls (dungeon/model_calls.py).
  record_model_calls INTEGER NOT NULL DEFAULT 0 CHECK (record_model_calls IN (0, 1)),
  -- Automatic backups of every world (dungeon/auto_backup.py).
  auto_backups TEXT NOT NULL DEFAULT 'daily' CHECK (auto_backups IN ('off', 'daily', 'weekly')),
  -- The first-run notice: the story is AI written, and the user is 18 or older.
  ai_notice_at TEXT,
  updated_at TEXT NOT NULL
);

-- Settings > Models: one provider, model and saved key each (config is JSON; the key lives in the
-- OS credential vault under credential_ref).
CREATE TABLE IF NOT EXISTS model_profiles (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  config TEXT NOT NULL,
  credential_ref TEXT,
  revision INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Which profile does each job; a job without a row uses the 'chat' job's profile.
CREATE TABLE IF NOT EXISTS model_routes (
  job TEXT PRIMARY KEY,
  profile_id TEXT NOT NULL REFERENCES model_profiles(id) ON DELETE CASCADE,
  updated_at TEXT NOT NULL
);

-- Built-in recall (Settings > Models, dungeon/providers/builtin_recall.py): a llama.cpp server the
-- Dungeon starts on this PC with an embedding model file the user downloaded. While enabled it does
-- semantic recall instead of a profile.
CREATE TABLE IF NOT EXISTS builtin_recall (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0, 1)),
  model_path TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL
);

-- The user's own wording for an editable prompt (dungeon/prompt_library.py); without a row the default is used.
-- default_text is the default it replaced, so a newer default can be pointed out.
CREATE TABLE IF NOT EXISTS prompt_overrides (
  name TEXT PRIMARY KEY,
  text TEXT NOT NULL,
  default_text TEXT,
  updated_at TEXT NOT NULL
);

-- Local programs the Dungeon starts (dungeon/launcher.py): where each is installed, found or typed by the
-- user (`chosen`), and KoboldCpp's model file. Whether they all start with the Dungeon is
-- workspace_settings.auto_launch.
CREATE TABLE IF NOT EXISTS local_programs (
  program TEXT PRIMARY KEY CHECK (program IN ('lmstudio', 'ollama', 'kobold', 'comfyui')),
  path TEXT NOT NULL DEFAULT '',
  chosen INTEGER NOT NULL DEFAULT 0 CHECK (chosen IN (0, 1)),
  model_path TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL
);

-- An image backend (Settings > Images). Secrets live in the OS vault under `credential_ref`, never here.
CREATE TABLE IF NOT EXISTS image_backends (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('comfyui', 'codex', 'hosted')),
  provider TEXT NOT NULL,
  label TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  position INTEGER NOT NULL,
  config TEXT NOT NULL DEFAULT '{}',
  credential_ref TEXT,
  -- The user marked a non-loopback ComfyUI address as a machine they control.
  controlled_machine INTEGER NOT NULL DEFAULT 0 CHECK (controlled_machine IN (0, 1)),
  concurrency INTEGER NOT NULL DEFAULT 1,
  -- Set when the backend must not run until the user acts, such as signing in to Codex again.
  blocked_reason TEXT,
  disclosure_accepted_at TEXT,
  allows_nsfw INTEGER NOT NULL DEFAULT 0 CHECK (allows_nsfw IN (0, 1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Debug time (Settings > Debug, dungeon/debug_time.py). While the row exists the app clock reads
-- app_anchor + (real time since real_anchor) * speed. `snapshot` is the database copy taken first, which
-- returning to real time restores unless the user keeps what happened; `backup` is the verified archive.
CREATE TABLE IF NOT EXISTS debug_time (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  app_anchor TEXT NOT NULL,
  real_anchor TEXT NOT NULL,
  speed REAL NOT NULL DEFAULT 1 CHECK (speed >= 1),
  started_at TEXT NOT NULL,
  app_started_at TEXT NOT NULL,
  snapshot TEXT NOT NULL,
  backup TEXT NOT NULL
);

-- Who the user is in this world (dungeon/worlds.py): the persona the world belongs to, copied from worlds.json
-- in the data folder whenever the world opens or the persona changes. The narrator's prompt reads it here.
-- `town_seed` is the world's own, set once when the world is made ('' in the first world); `townsfolk_key` names a
-- townsperson the user plays. The home is the world's (dungeon/world/where.py).
CREATE TABLE IF NOT EXISTS persona (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  persona_id TEXT NOT NULL,
  name TEXT NOT NULL DEFAULT '',
  gender TEXT NOT NULL DEFAULT '',
  age INTEGER,
  about TEXT NOT NULL DEFAULT '',
  birthday TEXT NOT NULL DEFAULT '',
  townsfolk_key TEXT NOT NULL DEFAULT '',
  town_seed TEXT NOT NULL DEFAULT '',
  home_city_id TEXT NOT NULL DEFAULT '',
  home_neighbourhood TEXT NOT NULL DEFAULT '',
  kind TEXT NOT NULL DEFAULT '',
  lifespan INTEGER,
  updated_at TEXT NOT NULL
);

-- Cities the user wrote or copied. Built-in cities ship as files and are never stored here.
CREATE TABLE IF NOT EXISTS world_cities (
  id TEXT PRIMARY KEY,
  definition TEXT NOT NULL,
  revision INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Changes to a city the workspace keeps (dungeon/world/changes.py): the user's own (`origin` 'real' and
-- `observation_id` are left from real-world lookups and stay unused). Seeded changes are computed from the city and
-- month, not stored; one the user dismisses is listed in world_change_dismissals and never happens.
CREATE TABLE IF NOT EXISTS world_changes (
  id TEXT PRIMARY KEY,
  city_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('opening', 'closing', 'renovation', 'roadworks', 'news')),
  origin TEXT NOT NULL CHECK (origin IN ('user', 'real')),
  place_id TEXT,
  neighborhood_id TEXT,
  name TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  details TEXT,
  announced_on TEXT NOT NULL,
  starts_on TEXT NOT NULL,
  ends_on TEXT,
  observation_id TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS world_changes_city ON world_changes(city_id, starts_on);

CREATE TABLE IF NOT EXISTS world_change_dismissals (
  change_id TEXT PRIMARY KEY,
  city_id TEXT NOT NULL,
  dismissed_at TEXT NOT NULL
);

-- Lore from imported lorebooks (dungeon/lore.py): a book belongs to one city, or to the whole world when city_id
-- is NULL. An entry joins the prompt when one of its keywords is in the story, or always when `always` is set;
-- `pattern` marks entries whose search patterns the app cannot match, which stay off.
CREATE TABLE IF NOT EXISTS lore_books (
  id TEXT PRIMARY KEY,
  city_id TEXT,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  source_format TEXT NOT NULL DEFAULT '',
  source_file TEXT NOT NULL DEFAULT '',
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lore_entries (
  id TEXT PRIMARY KEY,
  book_id TEXT NOT NULL REFERENCES lore_books(id) ON DELETE CASCADE,
  position INTEGER NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  text TEXT NOT NULL,
  keywords TEXT NOT NULL DEFAULT '[]',
  always INTEGER NOT NULL DEFAULT 0 CHECK (always IN (0, 1)),
  pattern INTEGER NOT NULL DEFAULT 0 CHECK (pattern IN (0, 1)),
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1))
);

CREATE INDEX IF NOT EXISTS lore_entries_book ON lore_entries(book_id, position);

-- The story (dungeon/story.py): one scene (where the user is) and its history.
CREATE TABLE IF NOT EXISTS story_scene (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  city_id TEXT NOT NULL,
  place_id TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS story_messages (
  id TEXT PRIMARY KEY,
  seq INTEGER NOT NULL UNIQUE,
  role TEXT NOT NULL CHECK (role IN ('user', 'narrator', 'scene')),
  text TEXT NOT NULL,
  client_id TEXT UNIQUE,
  reply_to TEXT,
  status TEXT NOT NULL DEFAULT 'complete' CHECK (status IN ('complete', 'failed')),
  error TEXT,
  city_id TEXT NOT NULL,
  place_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  -- The branch the message was written in (dungeon/timeline.py); 'first' is the story's first.
  branch_id TEXT NOT NULL DEFAULT 'first'
);

-- Branches of the story (dungeon/timeline.py). A branch shows its parent's messages before `fork_seq`, then its
-- own. `tip` is the game state where the player left it, kept while another branch is played.
CREATE TABLE IF NOT EXISTS story_branches (
  id TEXT PRIMARY KEY,
  parent_id TEXT,
  fork_seq INTEGER,
  tip TEXT,
  created_at TEXT NOT NULL
);

-- Which branch is being played.
CREATE TABLE IF NOT EXISTS story_timeline (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  branch_id TEXT NOT NULL DEFAULT 'first'
);

-- The game state at the start of each of the player's turns: going back to a turn puts it back.
CREATE TABLE IF NOT EXISTS story_saves (
  message_id TEXT PRIMARY KEY REFERENCES story_messages(id) ON DELETE CASCADE,
  state TEXT NOT NULL
);

-- MARVEL stats per actor (dungeon/sheet.py); 'persona' is the player's character.
CREATE TABLE IF NOT EXISTS character_stats (
  actor TEXT NOT NULL,
  stat TEXT NOT NULL CHECK (stat IN ('Mind', 'Allure', 'Resolve', 'Vitality', 'Essence', 'Luck')),
  value INTEGER NOT NULL CHECK (value BETWEEN 1 AND 30),
  updated_at TEXT NOT NULL,
  PRIMARY KEY (actor, stat)
);

-- Every roll of a turn (dungeon/turn.py), made once per player message before the narrator writes; retelling
-- keeps the dice. Shown to the player only while Settings > World > Show the dice is on.
CREATE TABLE IF NOT EXISTS story_rolls (
  id TEXT PRIMARY KEY,
  message_id TEXT NOT NULL REFERENCES story_messages(id) ON DELETE CASCADE,
  position INTEGER NOT NULL,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  said INTEGER NOT NULL DEFAULT 0 CHECK (said IN (0, 1)),
  stat TEXT NOT NULL,
  difficulty TEXT NOT NULL,
  die INTEGER,
  natural INTEGER NOT NULL,
  bonus INTEGER NOT NULL,
  shift INTEGER NOT NULL,
  total INTEGER NOT NULL,
  band TEXT NOT NULL CHECK (band IN ('critical_failure', 'failure', 'failure_upside', 'success_cost', 'success',
                                     'critical_success')),
  created_at TEXT NOT NULL,
  UNIQUE (message_id, position)
);

-- People the user has met in their story (dungeon/story_people.py): one meeting a local day, a few notes.
CREATE TABLE IF NOT EXISTS story_people (
  key TEXT PRIMARY KEY,
  city_id TEXT NOT NULL,
  name TEXT NOT NULL,
  first_met_at TEXT NOT NULL,
  last_met_at TEXT NOT NULL,
  last_day TEXT NOT NULL,
  meetings INTEGER NOT NULL DEFAULT 1,
  notes TEXT NOT NULL DEFAULT '[]'
);

-- Author's note (dungeon/authors_note.py): the user's note for the story, sent with every turn while it is on.
-- `chat` is 'story'. Never a message: not in the transcript or the narrator's history.
CREATE TABLE IF NOT EXISTS authors_notes (
  chat TEXT PRIMARY KEY,
  text TEXT NOT NULL DEFAULT '',
  enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
  updated_at TEXT NOT NULL
);

-- The town's mix (dungeon/world/mix.py, Settings > Debug): the shares townsfolk rolls use for looks and who people
-- are drawn to. No row is the built-in mix. Each world keeps its own; a new world starts from the one it was made from.
CREATE TABLE IF NOT EXISTS townsfolk_mix (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  mix TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- Personality sliders the user changed on a townsperson's profile (dungeon/world/personality.py), by town (the
-- world's town seed) and townsperson key. The rest stays rolled.
CREATE TABLE IF NOT EXISTS townsfolk_personality (
  town TEXT NOT NULL,
  key TEXT NOT NULL,
  sliders TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (town, key)
);

-- Everyone gets older (dungeon/life/ages.py). The row with kind 'town' and an empty key holds the day the town's
-- people started getting older; a townsperson's age moves on from their seeded age on that day.
CREATE TABLE IF NOT EXISTS birth_dates (
  kind TEXT NOT NULL CHECK (kind IN ('town')),
  person_key TEXT NOT NULL,
  born_on TEXT NOT NULL,
  birthday TEXT NOT NULL,
  from_age INTEGER NOT NULL,
  anchored_on TEXT NOT NULL,
  held_age INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (kind, person_key)
);

-- The town changes hands (dungeon/world/turnover.py): the levels the town's pace, passing away and growing
-- families held before a change, until the week they stopped holding, so a change only moves the town on from
-- then. `loss` is 0 when nobody passes away, else the loss level plus one.
CREATE TABLE IF NOT EXISTS town_levels (
  until_week INTEGER PRIMARY KEY,
  pace INTEGER NOT NULL,
  loss INTEGER NOT NULL,
  families INTEGER NOT NULL,
  created_at TEXT NOT NULL
);
