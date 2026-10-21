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
| Prospero's Study | "Life Cards": the Story randomness engine (`server/mechanics/`): seeded d100 activation, cooldown, major-disruption cap, ~30 event / extra / handling tables |
| Mabry Curve (RP archive) | The reference turn loop, hidden-information model, continuity tracking, off-page cadence and house rules |

## Decided

- **Start from a clean copy of Companion's code** (no git history carried over), then grow from there.
- **Rule systems are selectable** (Vanta, 2026-10-21): the player can pick from several built-in
  TTRPG rulesets, including MARVEL and open-licensed systems. See "Rulesets" below.
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

## Rulesets (proposed)

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
  allows.

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

- Rulesets: per world or per campaign; how deep each goes (resolution and sheets, or full
  classes, spells and monsters); which ship first; SRD 5.1, 5.2 or both.

- Off-page characters and their cadence (Mabry uses rolled beats every third turn).
- Which proposed progression tracks to keep.
- Which widgets and layout presets ship first.
- World package file format, and how canon, hidden truth and player knowledge are stored.
