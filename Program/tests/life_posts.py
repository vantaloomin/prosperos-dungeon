"""Posts as tests read them, now that no screen lists them (dungeon/life/feed.py keeps them for pictures)."""
from dungeon.characters import require_current
from dungeon.database import many, one
from dungeon.life import feed


def posts(client) -> list[dict]:
    """The current companion's posts with something to show, newest first."""
    with client.app.state.database.connect() as connection:
        timeline_id = require_current(connection)['active_timeline_id']
        rows = many(connection, "SELECT * FROM feed_posts WHERE timeline_id=? AND status='visible' "
                    'ORDER BY occurs_at DESC, id DESC', (timeline_id,))
        return [view for view in (feed.post_view(connection, row) for row in rows) if view]


def post(client, post_id: str) -> dict:
    with client.app.state.database.connect() as connection:
        return feed.post_view(connection, one(connection, 'SELECT * FROM feed_posts WHERE id=?', (post_id,)))


def post_event(client, event_id: str) -> dict:
    """A post for a committed event, as the simulation would make one."""
    database = client.app.state.database
    with database.connect(write=True) as connection:
        event = feed.current_revision(connection, event_id)
        post_id = feed.photo_post(connection, event['id']) or feed.create(
            connection, event['timeline_id'], 'event', f"event:{event['id']}", [event['id']], event['ends_at'],
            database.now())
    return post(client, post_id)
