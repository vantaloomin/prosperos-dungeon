"""Lorebook files (dungeon/lore.py): import them, and switch their books and entries on or off."""
from fastapi import APIRouter, Request

from dungeon import lore
from dungeon.models import LoreFile, LoreSwitch

router = APIRouter(prefix='/api')


def db(request: Request):
    return request.app.state.database


@router.post('/import/lorebook')
def import_lorebook(request: Request, body: LoreFile):
    """A lorebook file (JSON or .lorebook), imported straight away."""
    return lore.bring(db(request), body.filename, body.data)


@router.get('/lore')
def list_lore(request: Request):
    return lore.listing(db(request))


@router.put('/lore/books/{book_id}')
def switch_book(request: Request, book_id: str, body: LoreSwitch):
    return lore.set_book(db(request), book_id, body.enabled)


@router.delete('/lore/books/{book_id}')
def delete_book(request: Request, book_id: str):
    return lore.remove_book(db(request), book_id)


@router.put('/lore/entries/{entry_id}')
def switch_entry(request: Request, entry_id: str, body: LoreSwitch):
    return lore.set_entry(db(request), entry_id, body.enabled)
