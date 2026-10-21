# Story

The **Story** is the app's home screen: the user plays their persona in one of the cities, and a narrator
describes the place and voices the people there. Since Milestone 0 it is the whole app; the dice, the rulesets
and the rest of the game are built on it from Milestone 1 ([the roadmap](../../docs/roadmap.md)).

## Who decides what

The app decides the scene (`dungeon/story.py`):

- **Where:** the city and place the user picked under "Go somewhere else…". A new story starts in Haddon
  Harbor, the city the app ships with, at a cafe or another opening place. Moving adds a line to the story
  ("You arrive at …") that the narrator sees as a note.
- **When:** the app clock (debug time included) in the city's own timezone.
- **Weather:** the city's typical weather for the date (`generators.conditions`).
- **Who is there:** the townsfolk rules at that moment (`story.present`): people seeded at the place and
  residents whose routines bring them there. Each world's town has its own seed (`persona.town_seed`), so the
  same streets hold different people in different worlds.

The narrator model only voices the scene. Its prompt is built in layers (`dungeon/narration/prompt.py`):
"The Story narrator" and "The narrator's writing rules" in Settings > Advanced ([prompts.md](prompts.md)),
the narration format (second person, present tense, short turns), the intensity, then a `## Scene` section
with the facts above. After each reply, `dungeon/narration/prose.py` removes em dashes and asks the model for
one rewrite when the reply has the strongest AI tells (see "Narrator prompting" in the top-level
docs/requirements.md). The narrator gets the names of the people present, with a rule not to use a name until
that person gives it. The screen lists them only as the user would see them ("the barista", "a regular").

The narrator stays in the story. Sentences saying it is an AI are dropped (`in_character.Guard`), and OOC: or
((…)) gets a plain answer. Its model is the **Story narrator** job in Settings > Models.

## API

| Request | Does |
| --- | --- |
| `GET /api/story` | `{scene, messages, people, ready}`. `people` are those met, newest first, with `meetings`, `notes`, `doing` and `place` now. `scene` has the city, place, `local_time` (city clock, no offset), `weather`, the city's `places` and `around` (who is there, named only once met). `ready` is false without a model. |
| `PUT /api/story/scene` `{city_id, place_id?}` | Moves there; a city alone means its opening place. 404 for an unknown city or place. |
| `POST /api/story/messages` `{text, client_id}` | Saves the user's line once per `client_id` and returns `{message, reply}`. A failed reply is saved with `status: failed` and its `error`. Sending the same `client_id` again returns the saved reply, or tries again if it failed. 409 `no_connection` without a model; the line stays saved. |
| `POST /api/story/find` `{key}` | Moves the story to where someone the user has met is now. 404 if not met, 409 if they are nowhere the story can go. |
| `POST /api/story/retry` | Tells the reply to the latest user line again, replacing the one there. |
| `DELETE /api/story` | Starts a new story: the history and the people met go, the scene stays. |

## People you've met

Someone present in the scene is met once their name comes up, either because the narrator voices them giving it
or because the user uses it (`dungeon/story_people.py`, table `story_people`). Each local day they come up counts
as one meeting. Up to eight sentences of narration that name them are kept as notes. The next time they are in
the scene, the narrator is told the user has met them, how often and when, along with the latest notes, so they
remember the user however far back the story has been trimmed. The screen then shows their given name ("Dana,
the barista").

Under "People you've met" each person shows how often the user has met them and what their rules have them doing
now. "Go to …" moves the story to where they are (refused while they are at home, at work elsewhere or on their
street). Starting a new story clears the people met too.
