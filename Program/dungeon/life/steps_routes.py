"""Next steps API (dungeon/life/steps.py): where the user and the open companion stand, setting the step and the
"just friends" lock, and the Family panel's kids they had before (dungeon/life/kids.py)."""
from fastapi import APIRouter, Request
from pydantic import Field

from dungeon.characters import require_current
from dungeon.database import settings
from dungeon.life import kids, steps
from dungeon.models import Input

router = APIRouter(prefix='/api/life/steps')


class StepsUpdate(Input):
    step: str | None = Field(default=None, max_length=40, pattern=r'^[a-z_]+$')
    just_friends: bool | None = None


def read(connection, companion, now) -> dict:
    return steps.view(connection, companion, now, bool(settings(connection).get('show_odds')))


@router.get('')
def read_steps(request: Request):
    """The steps panel on the Character page; what is planned and the odds only with Hidden values' odds on."""
    database = request.app.state.database
    now = database.clock.now()
    with database.connect(write=True) as connection:
        companion = require_current(connection)
        steps.ensure(connection, companion, now)
        return read(connection, companion, now)


@router.put('')
def update_steps(request: Request, body: StepsUpdate):
    """Set the step (further along or further back) or the "just friends" lock."""
    database = request.app.state.database
    now = database.clock.now()
    with database.connect(write=True) as connection:
        companion = require_current(connection)
        if body.step is not None:
            steps.set_step(connection, companion, body.step, now)
        if body.just_friends is not None:
            steps.set_lock(connection, companion, body.just_friends, database.now())
        return read(connection, companion, now)


class KidsUpdate(Input):
    pattern: str | None = Field(default=None, max_length=20, pattern=r'^[a-z_]+$')
    remove: str | None = Field(default=None, max_length=64, pattern=r'^[0-9a-f]+$')
    restore: str | None = Field(default=None, max_length=64, pattern=r'^[0-9a-f]+$')


def read_kids_view(connection, companion, world, now) -> dict:
    return kids.view(connection, companion, world, now, bool(settings(connection).get('show_odds')))


@router.get('/kids')
def read_kids(request: Request):
    """The Family panel's kids (dungeon/life/kids.py): their children, where they live and their other parent."""
    database = request.app.state.database
    now = database.clock.now()
    with database.connect(write=True) as connection:
        return read_kids_view(connection, require_current(connection), request.app.state.life.world, now)


@router.put('/kids')
def update_kids(request: Request, body: KidsUpdate):
    """Set where the kids live ('auto' lets the app decide), or take a child out of their life."""
    database = request.app.state.database
    now = database.clock.now()
    with database.connect(write=True) as connection:
        companion = require_current(connection)
        kids.update(connection, companion, now, body.pattern, body.remove, body.restore)
        return read_kids_view(connection, companion, request.app.state.life.world, now)
