# Prospero's Dungeon

An all-in-one, local-first AI tabletop RPG simulator for adult, morally complex, dark stories where
good outcomes are not guaranteed. The program rolls the dice and makes the decisions; the language
model narrates them.

It builds on [Prospero's Companion](https://github.com/vantaloomin/prosperos-companion) and
[Prospero's Study](https://github.com/vantaloomin/prosperos-study).

## Status

No game features are built yet. The code in `Program` is a clean copy of Prospero's Companion v0.15.0
(without its history), renamed to Dungeon so both can be installed and run side by side. It still behaves
like the Companion until the Dungeon's own systems replace or reshape those parts. See
[the requirements](docs/requirements.md) and [the build roadmap](docs/roadmap.md) for what is planned.

It runs on your computer and talks to whichever model you choose: a hosted API (OpenAI, Anthropic, Google,
OpenRouter, any OpenAI-compatible service, your Codex login) or a local model through LM Studio, Kobold or any
OpenAI-compatible server.

## Getting started

### Windows

1. Install [Git](https://git-scm.com/download/win) and clone this repository.
2. Open the `Windows` folder and double-click **`install.bat`**. It finds or installs Python 3.12+ and
   Node.js 22.13+, installs the locked dependencies and builds the interface.
3. Double-click **`launch.bat`**. The Dungeon opens in your browser at http://127.0.0.1:8785. Keep its window
   open while you use it.
4. Add a model in **Settings > Models**.

### Mac

Clone the repository, open the `Mac` folder and double-click **`install.command`**, then **`launch.command`**.
[Installing on a Mac](Program/docs/macos.md) walks through it.

### Linux

There are no helper scripts yet; [Development](Program/docs/development.md) shows how to run it from the
`Program` folder.

Data lives outside the program folder: `%LOCALAPPDATA%\ProsperoDungeon` on Windows,
`~/Library/Application Support/ProsperoDungeon` on a Mac and `~/.local/share/prospero-dungeon` on Linux.
**Settings > Data** shows where it is and can move it into a portable `Data` folder beside `Windows`, `Mac`
and `Program`.

## Running beside Study and Companion

Each app keeps its own port, data folder, credential store entry and backup format, so none of them can open
the others' data by mistake:

| App | App port | Dev interface | Data folder (Windows) |
| --- | --- | --- | --- |
| Prospero's Study | 8765 | 5173 | its own |
| Prospero's Companion | 8775 (phone LAN 8776) | 5175 | `%LOCALAPPDATA%\ProsperoCompanion` |
| Prospero's Dungeon | 8785 (phone LAN 8786) | 5177 | `%LOCALAPPDATA%\ProsperoDungeon` |

Environment variables use the `DUNGEON_` prefix (for example `DUNGEON_DATA_DIR`, `DUNGEON_PORT`).

## Which folder is for you

| Folder | Who it is for |
| --- | --- |
| [`Windows`](Windows) | Running the Dungeon on a Windows PC. |
| [`Mac`](Mac) | Running it on a Mac. |
| [`Program`](Program) | The app itself: code (`Program/dungeon`), interface (`Program/src`), tests, build scripts and docs. |
| [`docs`](docs) | Dungeon design: requirements and system notes. |

| Script | What it does |
| --- | --- |
| `install.bat` | Finds or installs Python and Node.js, installs the locked dependencies and builds the interface. |
| `launch.bat` | Starts the Dungeon on http://127.0.0.1:8785 and opens it in the browser. |
| `update.bat` | Gets the latest `main` and reruns the install. Close the Dungeon first. |
| `status.bat` | Says whether the Dungeon is running, and on which address. |
| `stop.bat` | Stops a running Dungeon, for when its window is lost. Never stops another program on the port. |
| `create-shortcut.bat` | Puts a Prospero Dungeon shortcut to `launch.bat` on the desktop. |
| `dev.bat` | Development mode: the backend reloads on Python changes and Vite serves http://127.0.0.1:5177. |

Each script has a Mac twin in `Mac` with the same name ending in `.command`.

## Documentation

- [Requirements and system design](docs/requirements.md)
- [Build roadmap](docs/roadmap.md)
- [Development](Program/docs/development.md)
- [Backbone architecture](Program/docs/architecture.md)
- [Models](Program/docs/models.md)
- [Life simulation API](Program/docs/life-api.md)
- [World data](Program/docs/world-data.md)
- [Changelog](CHANGELOG.md)

The other guides in `Program/docs` came with the Companion code and describe Companion features.

## License

Licensed under the [GNU Affero General Public License v3.0](LICENSE), matching the Prospero's Study and
Prospero's Companion code it reuses.
