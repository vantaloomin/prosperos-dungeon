"""The story API (dungeon/story.py, docs/story.md)."""
from fastapi import APIRouter, Request
from pydantic import Field

from dungeon import campaign, sheet, story
from dungeon.models import Input, PersonaInput

router = APIRouter(prefix='/api/story')


class StoryMessage(Input):
    text: str = Field(min_length=1, max_length=40000)
    client_id: str = Field(min_length=8, max_length=100)


class StoryScene(Input):
    city_id: str = Field(min_length=1, max_length=80)
    place_id: str | None = Field(None, min_length=1, max_length=80)


@router.get('')
def read(request: Request):
    return story.story(request.app.state.database)


@router.put('/scene')
def move(request: Request, body: StoryScene):
    return story.move(request.app.state.database, body.city_id, body.place_id)


class StoryPerson(Input):
    key: str = Field(min_length=1, max_length=200)


@router.post('/find')
def find(request: Request, body: StoryPerson):
    return story.find(request.app.state.database, body.key)


@router.post('/messages')
async def send(request: Request, body: StoryMessage):
    return await story.send(request.app.state, body.text, body.client_id)


@router.post('/retry')
async def retry(request: Request):
    return await story.retry(request.app.state)


class SheetChange(Input):
    stats: dict[str, int]


@router.get('/sheet')
def read_sheet(request: Request):
    with request.app.state.database.connect() as connection:
        return sheet.view(connection)


@router.put('/sheet')
def change_sheet(request: Request, body: SheetChange):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        sheet.set_stats(connection, body.stats, database.now())
        return sheet.view(connection)


class StoryStart(Input):
    """A premade character by id, or one the player made: who they are and their bought stats."""
    premade_id: str | None = Field(None, min_length=1, max_length=80)
    persona: PersonaInput | None = None
    stats: dict[str, int] | None = None


@router.get('/start')
def start_choices(request: Request):
    return campaign.view(request.app.state.database)


@router.post('/start')
def start(request: Request, body: StoryStart):
    return campaign.begin(request.app.state.database, body.premade_id, body.persona, body.stats)


@router.delete('')
def clear(request: Request):
    return story.clear(request.app.state.database)
