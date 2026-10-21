# Build roadmap

Drafted 2026-10-21 from [requirements.md](requirements.md). The goal is a **playable slice as soon
as possible**: one small place, one ruleset, the core turn loop working end to end. Everything else
layers on afterwards. Each milestone ends in something Vanta can play.

The code base is PR #1: Prospero's Companion v0.15.0 forked and renamed to Dungeon, with the
unneeded features removed.

## Milestone 0: Foundation (days)

- Merge PR #1 into `main`. It is waiting on Vanta's squash-or-merge-commit choice in the
  "Companion code fork" thread. Then sync the local `main` on Vanta's PC.
- Hide the Companion screens the slice doesn't use (companion chat, phone), without deleting code
  yet. The leftover-code cleanup pass stays optional and can come later.

## Milestone 1: Playable slice

**Fastest path:** build on Companion's **Story mode** (`story.py`, `story_people.py`). It already
has a narrator walking a city, with places, local time, weather and townsfolk all decided by code.
The slice turns it into a game loop.

**Slice world:** one hand-authored small town from Vallarith, written in Companion's existing city
JSON format (places, prices, pay bands, townsfolk), with 4 to 6 named NPCs, one authored quest with
a deadline, and one dangerous place nearby. The world package format and importer wait until
Milestone 5.

**In the slice:**

1. **Campaign start:** pick a premade persona or make a quick custom one. MARVEL stats only.
2. **Turn loop:** the player writes intent, a text model splits it into actions, the Referee
   decides needs-a-roll, stat and difficulty (Jev if a key is set, keyword rules otherwise), and
   code rolls d100 plus stat onto the six-band outcome ladder. The narrator writes the result in
   the persona's voice and never contradicts a roll.
3. **Roll visibility toggle:** hidden or exposed.
4. **Ledger v0:** code records facts (deaths, items, wounds, promises, locations). Recall is the
   recent turns plus one rolling summary.
5. **NPCs v0:** named NPCs act on their own initiative, with trust, affection, respect, fear and
   desire axes, and short memories of the player.
6. **Combat v0:** zones, one post per round, code tactics for mooks, morale rolls, MARVEL wound
   levels, and the defeat table.
7. **Inventory and one shop:** carry slots, finite stock and prices from Companion's pricing, plus
   buying and selling in the shop window and in-story.
8. **Death and branching:** every turn is a save point, and going back to any turn gives new dice.
   This builds on Companion's timelines (`timelines.py`, `lineage.py`).
9. **Intensity v0:** one preset (world default) that shapes narration. Per-category sliders come
   later.
10. **Screen:** a fixed layout with story text, character sheet, inventory, journal, shop window,
    and clock with location. The free grid comes in Milestone 6.

**Not in the slice:** other rulesets, travel map, factions and clocks, off-page beats, Life Cards
events, art, tiers, chapters and the branch tree, world packages, DB editor, themes.

**Done when:** Vanta can start a character in the town, talk, haggle, take the quest, fight, get
hurt or die, and go back to an earlier turn and try again with new dice.

## Milestone 2: Living world

- Time and travel: story clock, map crawl with fog of war, region danger tables, rest
  interruptions.
- Life Cards events drawn into play, with the tone dial's drama level.
- Factions with goals and clocks; generated quests from NPC and faction needs; emergent quests from
  promises.
- Off-page beats on world time with a turn minimum; news spreads with "word gets around".
- Injuries and recovery (treatment, permanent injuries, stress track) under the Injury
  persistence setting.
- Scaling and tiers: per-world track on the shared tier ladder, banded offers, start, ceiling and
  pace sliders.
- Progression: use-based MARVEL growth plus milestones; dark tracks.

## Milestone 3: Memory and campaigns

- Full layered recall, model fact extraction checked by code, rewrite-on-contradiction (with skip
  toggle), forgetting with grudges.
- Chapters at scene breaks, the chapter list, the branch tree, bookmarks, Ironman mode, the
  player-only notebook.
- Memory view of what the character knows, plus the GM view toggle.
- Export as a backup file and as a book (Markdown, EPUB, PDF); legacy import.

## Milestone 4: Rulesets

- D&D 5e via SRD 5.2, then Ironsworn/Starforged (with Supply), each mapped onto the shared outcome
  ladder with full content packs.
- Basic Roleplaying next. Fate, Blades and Dungeon World only after the license check thread
  reports back.

## Milestone 5: Worlds

- The SQLite world package format.
- The importer (built on Study's) with per-section review.
- The built-in world DB editor and the Markdown/JSON round-trip.
- Import Vallarith in full, then Havenbrooke (institutions, Grades, class schedule), then BABEL.

## Milestone 6: Presentation

- Art on request, passive art toggle, reference images, live-state portraits.
- Map widget, VN portraits, background art.
- Free grid, saved layouts, the three presets plus per-world layouts, themes, phone tabs.
- Full intensity sliders with veils and table filtering; tone voice setting.

## Order and parallel work

Milestone 0 and 1 are sequential and come first. After the slice, Milestones 2 and 3 can run in
parallel threads. Milestones 4, 5 and 6 can each start once Milestone 1 has merged.
