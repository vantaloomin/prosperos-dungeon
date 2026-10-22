# World packages

Milestone 5 (requirements "World packages"). A world (a setting such as Vallarith, not a save: see
[worlds.md](worlds.md) for those) is one SQLite file: its canon, cast, personas, hidden truths, planned beats,
rules, tables, prices and assets. The same world can be written out as a folder of Markdown and JSON and read back
in. `dungeon/packages.py` does both.

## The folder

`dungeon/world/packages/vallarith/` is the built-in example, and its README describes each file.

| Path | Kept as |
|---|---|
| `world.json` | `meta.world`: the world's id, name and settings |
| `canon/*.md` and any other `.md` | `documents`, word for word |
| `lore.json`, `regions.json`, `settlements.json`, `factions.json`, `deities.json`, `cast.json`, `personas.json`, `hidden-truths.json`, `beats.json` | `entries`: one row per entry, with its section, id, position, name and whether it holds a hidden truth. The rest of the file (schema_version, fields, notes) is kept in `meta.sections` |
| `engine/<kind>/<key>.json` | `engine`: the game's own data (`adventures`, `arcs`, `cities`, `factions`, `finds`, `items`, `premades`, `tiers`, `travel`) |
| `assets/**` | `assets`: bytes and media type |

An entry hides a truth when its section is `hidden-truths` or it has a `secret`, `secrets`, `guise`,
`mortal_life`, `truth` or `hidden` field. The editor will mark those rows.

## Checks

A folder is checked before it becomes a package. Every entry needs a lowercase kebab-case id that is unique in its
section, and references have to name an entry that exists: a settlement's `region` and `faction`, and a cast
member's `faction` and `settlement`. A broken JSON file is named. Nothing is written until the folder passes.

## Built-in worlds

Built-in worlds ship as folders. For now the game's own data for them stays in `dungeon/world/data`, and the build
gathers it into the package's `engine` part. That covers the world's travel map, arcs, factions in play and tiers,
and for each town on its map the town's adventure, items, finds, premades and city file. The package is built into
the data folder (`packages/<id>.sqlite`) when first asked for. It is built again whenever a source changes, which a
fingerprint of the contents tells.

## In play

- **Lore.** A campaign that starts in a world with a package gets the package's `lore` section as one of the
  world's lore books, "<World> (world package)" (`dungeon/package_lore.py`). The narrator reads its entries by
  keyword like any imported lorebook (docs/story.md "Lore"), and the player can switch entries off on the Lore
  screen. Only entries that hold in the campaign's era come in (the era is `world.json` `starting_place.era`; an
  entry with no `eras` holds in all). Hidden truths never come in this way. The book is read from the package file,
  so an edited or imported world plays as edited. When the lore changes, the next campaign start replaces the book.

## API

- `GET /api/packages`: the built-in and imported worlds, each with its sections' entry counts (and how many hide a
  truth), documents, engine data, assets and size.
- `GET /api/packages/{id}/file`: the world as its SQLite file, to share.
- `POST /api/packages/{id}/export`: the world written out as a folder in the data folder (`exports/<id>-<time>`),
  and the path.
- `POST /api/packages/import` `{folder}`: a world folder on this computer, checked and made into a package. A
  built-in world's id is refused.

Not yet: the game reading its data from the package instead of `dungeon/world/data`, the importer that drafts sections with a model for review, and the built-in editor.
