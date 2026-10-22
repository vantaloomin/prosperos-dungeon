"""The story API (dungeon/story.py, docs/story.md)."""
import asyncio
import json
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from pydantic import Field

from dungeon import campaign, chapters, director, growth, quests, record, sheet, story, story_clock
from dungeon.errors import DomainError
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
async def send(request: Request, body: StoryMessage, background: BackgroundTasks):
    result = await story.send(request.app.state, body.text, body.client_id)
    background.add_task(story.settled, request.app.state)
    return result


@router.post('/retry')
async def retry(request: Request, background: BackgroundTasks):
    result = await story.retry(request.app.state)
    background.add_task(story.settled, request.app.state)
    return result


class StoryRewrite(Input):
    passage: str = Field(min_length=1, max_length=20000)
    note: str = Field('', max_length=300)


@router.post('/messages/{message_id}/rewrite')
async def rewrite(request: Request, message_id: str, body: StoryRewrite, background: BackgroundTasks):
    result = await story.rewritten(request.app.state, message_id, body.passage, body.note)
    background.add_task(story.settled, request.app.state)
    return result


@router.post('/messages/{message_id}/switch')
async def switch_wording(request: Request, message_id: str, background: BackgroundTasks):
    result = await story.switched(request.app.state, message_id)
    background.add_task(story.settled, request.app.state)
    return result


def streamed(state, start) -> StreamingResponse:
    """A turn as newline-delimited JSON: the turn's stages as they happen ({"stage": "reading"}, {"actions": [...]}
    and one {"roll": {...}} each, {"stage": "writing"}; dungeon/story.py `answer`), {"text": piece} as the narration
    is written, then {"done": result} once the reply is saved (or {"error": message, "status": n}). Fact extraction
    runs after "done" (dungeon/pace.py)."""
    pieces: asyncio.Queue = asyncio.Queue()

    async def on_text(piece: str):
        await pieces.put({'text': piece})

    async def run():
        try:
            await pieces.put({'done': await start(on_text, pieces.put)})
        except DomainError as failure:
            await pieces.put({'error': failure.message, 'code': failure.code, 'status': failure.status})
        finally:
            await pieces.put(None)

    async def lines():
        task = asyncio.ensure_future(run())
        while (item := await pieces.get()) is not None:
            yield json.dumps(item, ensure_ascii=False) + '\n'
        await task
        await story.settled(state)

    return StreamingResponse(lines(), media_type='application/x-ndjson')


@router.post('/messages/stream')
async def send_streamed(request: Request, body: StoryMessage):
    state = request.app.state
    return streamed(state, lambda on_text, on_event: story.send(state, body.text, body.client_id, on_text, on_event))


@router.post('/retry/stream')
async def retry_streamed(request: Request):
    state = request.app.state
    return streamed(state, lambda on_text, on_event: story.retry(state, on_text, on_event))


class SheetChange(Input):
    stats: dict[str, int]


@router.get('/sheet')
def read_sheet(request: Request):
    with request.app.state.database.connect() as connection:
        return sheet.view(connection) | {'growth': growth.view(connection, story.dice_shown(connection))}


@router.put('/sheet')
def change_sheet(request: Request, body: SheetChange):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        sheet.set_stats(connection, body.stats, database.now())
        return sheet.view(connection) | {'growth': growth.view(connection, story.dice_shown(connection))}


class StoryStart(Input):
    """A premade character by id, or one the player made: who they are and their bought stats."""
    premade_id: str | None = Field(None, min_length=1, max_length=80)
    persona: PersonaInput | None = None
    stats: dict[str, int] | None = None
    # The arc (how far the character can rise) and its pace (dungeon/tiers.py); the world's own when left out.
    arc: Literal['grounded', 'classic', 'epic'] | None = None
    pace: Literal['slow', 'steady', 'fast'] | None = None
    # How hard the director's hand pushes (dungeon/director.py).
    hand: Literal['soft', 'guiding', 'firm'] | None = None
    # Ironman (dungeon/chapters.py): no going back for the whole campaign, so death is final.
    ironman: bool = False


@router.get('/start')
def start_choices(request: Request):
    return campaign.view(request.app.state.database)


@router.post('/start')
def start(request: Request, body: StoryStart):
    return campaign.begin(request.app.state.database, body.premade_id, body.persona, body.stats, body.arc,
                          body.pace, body.hand, body.ironman)


class StoryBack(Input):
    message_id: str = Field(min_length=1, max_length=80)


@router.post('/back')
def back(request: Request, body: StoryBack):
    """Back to before one of the player's lines, as a new branch; the story so far is kept."""
    return story.back(request.app.state.database, body.message_id)


@router.post('/branches/{branch_id}/switch')
def switch_branch(request: Request, branch_id: str):
    return story.switch_branch(request.app.state.database, branch_id)


class ChapterClose(Input):
    title: str = Field('', max_length=80)


@router.post('/chapters/close')
def close_chapter(request: Request, body: ChapterClose):
    """The player ends the chapter here, naming it if they like; their next line opens the next one."""
    database = request.app.state.database
    with database.connect(write=True) as connection:
        chapters.mark(connection, 'player', body.title)
    return story.story(database)


@router.get('/chapters/{chapter_id}')
def read_chapter(request: Request, chapter_id: str, branch_id: str | None = None):
    """A chapter's lines as they were told in a branch (the one being played by default), to read."""
    with request.app.state.database.connect() as connection:
        return {'lines': chapters.read(connection, chapter_id, branch_id)}


@router.post('/chapters/{chapter_id}/back')
def chapter_back(request: Request, chapter_id: str):
    """Play on from the start of a chapter in the tree, with new dice."""
    return story.chapter_back(request.app.state.database, chapter_id)


class BookmarkInput(Input):
    message_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=80)


@router.post('/bookmarks')
def add_bookmark(request: Request, body: BookmarkInput):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        chapters.bookmark(connection, body.message_id, body.name, database.now())
    return story.story(database)


@router.delete('/bookmarks/{bookmark_id}')
def remove_bookmark(request: Request, bookmark_id: str):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        chapters.unbookmark(connection, bookmark_id)
    return story.story(database)


@router.post('/bookmarks/{bookmark_id}/go')
def go_to_bookmark(request: Request, bookmark_id: str):
    return story.bookmark_go(request.app.state.database, bookmark_id)


class NotebookNote(Input):
    text: str = Field(min_length=1, max_length=4000)


@router.get('/notebook')
def notebook(request: Request):
    """The player's own notes, across every branch; no model reads them (dungeon/chapters.py)."""
    with request.app.state.database.connect() as connection:
        return {'notes': chapters.notebook(connection)}


@router.post('/notebook')
def add_to_notebook(request: Request, body: NotebookNote):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        chapters.write_note(connection, body.text, database.now())
        return {'notes': chapters.notebook(connection)}


@router.patch('/notebook/{note_id}')
def change_notebook(request: Request, note_id: str, body: NotebookNote):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        chapters.write_note(connection, body.text, database.now(), note_id)
        return {'notes': chapters.notebook(connection)}


@router.delete('/notebook/{note_id}')
def remove_from_notebook(request: Request, note_id: str):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        chapters.remove_note(connection, note_id)
        return {'notes': chapters.notebook(connection)}


class JournalNote(Input):
    subject: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=500)


class Trade(Input):
    qty: int = Field(1, ge=1, le=99)


class Purchase(Trade):
    item_id: str = Field(min_length=1, max_length=80)


class Sale(Trade):
    inventory_id: str = Field(min_length=1, max_length=80)


class JournalChange(Input):
    text: str = Field(min_length=1, max_length=500)


def journal_view(connection, database) -> dict:
    gm = record.gm_view(connection)
    return {'entries': record.entries(connection, known_only=not gm), 'gm': gm,
            'quests': quests.view(connection, story_clock.now(connection, database.clock)),
            'threads': director.journal(connection)}


@router.get('/journal')
def journal(request: Request):
    """What the player's character knows, from the record (dungeon/record.py); hidden truth stays out."""
    with request.app.state.database.connect() as connection:
        return journal_view(connection, request.app.state.database)


@router.post('/journal')
def add_note(request: Request, body: JournalNote):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        record.add(connection, 'fact', body.subject, body.text, database.now(), 'player')
        return journal_view(connection, request.app.state.database)


@router.patch('/journal/{entry_id}')
def change_note(request: Request, entry_id: str, body: JournalChange):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        record.correct(connection, entry_id, database.now(), body.text)
        return journal_view(connection, request.app.state.database)


@router.delete('/journal/{entry_id}')
def remove_note(request: Request, entry_id: str):
    database = request.app.state.database
    with database.connect(write=True) as connection:
        record.correct(connection, entry_id, database.now())
        return journal_view(connection, request.app.state.database)


@router.post('/journal/{entry_id}/regenerate')
async def regenerate_note(request: Request, entry_id: str):
    """The GM view asks the Continuity model again for one fact it pulled from the story (dungeon/record.py)."""
    await record.regenerate(request.app.state, entry_id)
    with request.app.state.database.connect() as connection:
        return journal_view(connection, request.app.state.database)


@router.delete('')
def clear(request: Request):
    return story.clear(request.app.state.database)


@router.get('/gear')
def gear(request: Request):
    """The character's purse and pack, and the shop window where the story is (dungeon/inventory.py)."""
    return story.gear(request.app.state.database)


@router.post('/shop/buy')
def buy(request: Request, body: Purchase):
    return story.trade(request.app.state.database, 'buy', body.item_id, body.qty)


@router.post('/shop/sell')
def sell(request: Request, body: Sale):
    return story.trade(request.app.state.database, 'sell', body.inventory_id, body.qty)
