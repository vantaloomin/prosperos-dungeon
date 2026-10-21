"""Posts: what pictures of the companion's life hang on (PRD F3, F4).

A post never carries its own account of an event. It references life events and shows the
current committed revision of each, so a correction updates the post, a pending proposal waits
until it is committed, and a rejected one never appears. A picture of a moment (dungeon/images),
a photo sent in chat (dungeon/images/photos.py) and the pictures in Our year are all a post's image.

Return batches make one digest post; background batches make one post per event (T5). The
image columns are a hook for a later image job: the text never waits for an image.
"""
from dungeon.characters import definition_for_timeline
from dungeon.database import decode, identifier, many, one, optional
from dungeon.errors import require
from dungeon.life import composer

# A photo sent in chat waits on a post keyed to the event its slot will become (dungeon/images/photos.py).
PHOTO_KEY = 'photo:'
IMAGE_STATES = ('none', 'queued', 'running', 'completed', 'failed', 'cancelled', 'interrupted')


def current_revision(connection, event_id) -> dict | None:
    """Follow corrections to the event's active version."""
    event = optional(connection, 'SELECT * FROM life_events WHERE id=?', (event_id,))
    while event and event['status'] == 'superseded':
        event = optional(connection, 'SELECT * FROM life_events WHERE supersedes_id=? ORDER BY revision DESC '
                         'LIMIT 1', (event['id'],))
    return event


def event_view(event) -> dict:
    details = decode(event['details'])
    return {'id': event['id'], 'summary': event['summary'], 'caption': details.get('post') or event['summary'],
            'mood': details.get('mood', ''), 'label': details.get('label', ''), 'kind': event['kind'],
            'starts_at': event['starts_at'], 'ends_at': event['ends_at'], 'revision': event['revision']}


def shown_events(connection, post_id) -> list[dict]:
    result = []
    for link in many(connection, 'SELECT event_id FROM feed_post_events WHERE post_id=? ORDER BY position',
                     (post_id,)):
        event = current_revision(connection, link['event_id'])
        if event and event['status'] == 'committed':
            result.append(event_view(event))
    return result


def image_outdated(connection, post, shown) -> bool:
    """True when the shown image was made from an event version that has since been corrected or
    withdrawn, so the post can say the picture shows the earlier account (F1, M3). Wording is
    compared rather than identities, which differ on a copied timeline."""
    if not post['image_ref']:
        return False
    job = optional(connection, 'SELECT inputs FROM image_jobs WHERE id=?', (post['image_ref'],))
    if job is None:
        return False
    drawn = [(event['summary'], event['caption']) for event in decode(job['inputs'])['events']]
    return drawn != [(event['summary'], event['caption']) for event in shown][:len(drawn)]


def said_events(connection, post, shown: list[dict]) -> list[dict]:
    """The events with the companion's own pronouns (dungeon/life/composer.said); the image check compares the
    words as written. `mine` is the caption and summary as the companion says them on their own post ("I worked
    late"); summary and caption stay as written for chat."""
    definition = definition_for_timeline(connection, post['timeline_id']) if shown else {}
    return [{**event, 'summary': composer.said(event['summary'], definition), 'mine': mine(event, definition)}
            for event in shown]


def mine(event: dict, definition: dict) -> dict:
    line = composer.mine(event['summary'], definition.get('name', ''))
    return {'caption': line if event['caption'] == event['summary'] else event['caption'], 'summary': line}


def post_view(connection, post) -> dict | None:
    removed = post['status'] == 'removed'
    shown = [] if removed else shown_events(connection, post['id'])
    if not shown and not removed:
        return None
    return {'id': post['id'], 'kind': post['kind'], 'source': 'life', 'intro': post['intro'],
            'events': said_events(connection, post, shown),
            'status': post['status'], 'read': post['read_at'] is not None, 'read_at': post['read_at'],
            'reaction': post['reaction'], 'occurs_at': post['occurs_at'], 'created_at': post['created_at'],
            'image': {'status': post['image_status'], 'job_id': post['image_job_id'], 'ref': post['image_ref'],
                      'error': post['image_error'], 'updated_at': post['image_updated_at'],
                      'outdated': image_outdated(connection, post, shown)}}


def create(connection, timeline_id, kind, key, event_ids, occurs_at, timestamp, run_id=None, intro='') -> str:
    existing = optional(connection, 'SELECT id FROM feed_posts WHERE idempotency_key=?', (key,))
    if existing:
        return existing['id']
    post_id = identifier()
    connection.execute('INSERT INTO feed_posts (id, timeline_id, kind, idempotency_key, run_id, intro, occurs_at, '
                       'created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                       (post_id, timeline_id, kind, key, run_id, intro, occurs_at, timestamp))
    connection.executemany('INSERT INTO feed_post_events (post_id, event_id, position) VALUES (?, ?, ?)',
                           [(post_id, event_id, index) for index, event_id in enumerate(event_ids)])
    return post_id


def publish_run(connection, run, results, timestamp) -> list[str]:
    """One digest for a return batch, one post per event for a background batch (T5). An event
    photographed in chat while it was happening joins its photo's post instead. Returns the
    background batch's posts."""
    event_ids = [result['event_id'] for result in results
                 if result.get('event_id') and result['outcome'] in {'proposed', 'committed'}]
    photographed = {event_id: post_id for event_id in event_ids if (post_id := photo_post(connection, event_id))}
    if run['mode'] != 'background':
        rest = [event_id for event_id in event_ids if event_id not in photographed]
        if rest:
            create(connection, run['timeline_id'], 'digest', f"digest:{run['id']}", rest, run['window_end'],
                   timestamp, run['id'])
        return []
    return [photographed.get(event_id) or event_post(connection, run, event_id, timestamp) for event_id in event_ids]


def event_post(connection, run, event_id, timestamp) -> str:
    event = one(connection, 'SELECT ends_at FROM life_events WHERE id=?', (event_id,))
    return create(connection, run['timeline_id'], 'event', f'event:{event_id}', [event_id], event['ends_at'],
                  timestamp, run['id'])


def photographed(connection, event_key) -> bool:
    """Whether a photo was sent in chat of the slot that will become the event with this key."""
    return optional(connection, "SELECT id FROM feed_posts WHERE idempotency_key=? AND status!='removed'",
                    (PHOTO_KEY + event_key,)) is not None


def photo_post(connection, event_id) -> str | None:
    """The post a chat photo of this event's slot waits on, with the event joined to it, so the feed
    shows the same picture the chat did and the event is told once."""
    event = optional(connection, 'SELECT idempotency_key FROM life_events WHERE id=?', (event_id,))
    post = event and optional(connection, "SELECT id FROM feed_posts WHERE idempotency_key=? AND status!='removed'",
                              (PHOTO_KEY + event['idempotency_key'],))
    if not post:
        return None
    connection.execute('INSERT OR IGNORE INTO feed_post_events (post_id, event_id, position) VALUES (?, ?, 0)',
                       (post['id'], event_id))
    return post['id']


def set_image(database, post_id, job_id, status, ref=None, error=None) -> dict:
    """For the image job: a result only lands if it belongs to the post's current job, so a late
    result cannot overwrite a newer one (F4). Queuing a new job replaces the current job id."""
    require(status in IMAGE_STATES, 'Unknown image state.', 422)
    with database.connect(write=True) as connection:
        post = one(connection, 'SELECT * FROM feed_posts WHERE id=?', (post_id,))
        require(post['status'] != 'removed', 'This post was removed.', 409)
        applied = apply_image(connection, post_id, job_id, status, database.now(), ref, error,
                              replace=status == 'queued')
        require(applied, 'This image job is no longer current for the post.', 409)
        return post_view(connection, one(connection, 'SELECT * FROM feed_posts WHERE id=?', (post_id,)))


def apply_image(connection, post_id, job_id, status, timestamp, ref=None, error=None, replace=False) -> bool:
    """Record a job's state on its post inside the caller's transaction. Only the post's current
    job may change it unless `replace` makes this job current. Returns whether it applied."""
    post = one(connection, 'SELECT status, image_job_id FROM feed_posts WHERE id=?', (post_id,))
    if post['status'] == 'removed' or (not replace and post['image_job_id'] != job_id):
        return False
    connection.execute('UPDATE feed_posts SET image_status=?, image_job_id=?, image_ref=COALESCE(?, image_ref), '
                       'image_error=?, image_updated_at=? WHERE id=?',
                       (status, job_id, ref, error, timestamp, post_id))
    return True
