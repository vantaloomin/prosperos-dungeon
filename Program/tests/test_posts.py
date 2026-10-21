"""Posts of the companion's life, which pictures hang on, and the Today view (PRD F1, F4, Today, C5)."""
import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from conftest import reconcile, set_life
from life_posts import posts

from dungeon.errors import DomainError
from dungeon.life import feed as feed_module


def commit_all(client):
    for event in client.get('/api/events?history=true').json():
        if event['status'] == 'proposed':
            client.post(f"/api/events/{event['id']}/commit")


def test_a_return_batch_makes_one_digest_that_waits_for_review(client, life, clock):
    set_life(client, automatic_events=False)
    clock.advance(timedelta(days=1))
    reconcile(client)
    assert posts(client) == []
    proposed = client.get('/api/events?history=true').json()
    client.post(f"/api/events/{proposed[0]['id']}/commit")
    client.post(f"/api/events/{proposed[1]['id']}/reject")
    [digest] = posts(client)
    assert digest['kind'] == 'digest' and [event['id'] for event in digest['events']] == [proposed[0]['id']]
    assert digest['events'][0]['caption'] == 'Lovely light today.'
    assert digest['image']['status'] == 'none'
    commit_all(client)
    assert len(posts(client)[0]['events']) == 2


def test_a_corrected_event_changes_its_post(client, life, clock):
    set_life(client, automatic_events=True)
    clock.advance(timedelta(days=1))
    reconcile(client)
    event = posts(client)[0]['events'][0]
    corrected = client.post(f"/api/events/{event['id']}/correct", json={'summary': 'Painted by the river'}).json()
    shown = posts(client)[0]['events'][0]
    assert shown['id'] == corrected['id'] and shown['summary'] == 'Painted by the river' and shown['revision'] == 2


def test_background_batches_post_each_event(app, client, life, clock):
    client.put('/api/settings', json={'background_activity': True})
    set_life(client, automatic_events=True)
    clock.advance(timedelta(hours=20))
    asyncio.run(app.state.life.reconcile('background'))
    found = posts(client)
    assert len(found) == 1 and found[0]['kind'] == 'event'


def test_image_hook_ignores_a_late_result(client, life, clock):
    set_life(client, automatic_events=True)
    clock.advance(timedelta(days=1))
    reconcile(client)
    post = posts(client)[0]
    database = client.app.state.database
    feed_module.set_image(database, post['id'], 'job-1', 'queued')
    feed_module.set_image(database, post['id'], 'job-2', 'queued')
    with pytest.raises(DomainError) as late:
        feed_module.set_image(database, post['id'], 'job-1', 'completed', ref='old.png')
    assert late.value.status == 409
    done = feed_module.set_image(database, post['id'], 'job-2', 'completed', ref='new.png')
    assert done['image'] == {**done['image'], 'status': 'completed', 'ref': 'new.png', 'job_id': 'job-2'}


def test_today_shows_routine_review_changes_and_availability(client, life, clock):
    set_life(client, automatic_events=False)
    clock.instant = datetime(2026, 10, 6, 10, 0, tzinfo=UTC)
    reconcile(client)
    view = client.get('/api/today').json()
    assert view['availability']['state'] == 'free' and view['routine']['current']['block']['key'] == 'morning'
    assert len(view['review']) == 2 and view['changes'] == [] and view['last_seen_at'] is None
    assert view['last_run']['status'] == 'completed' and view['limits']['catch_up_max_events'] == 3
    for event in view['review']:
        client.post(f"/api/events/{event['id']}/commit")
    seen = client.post('/api/today/seen').json()['last_seen_at']
    assert client.get('/api/today').json()['changes'] == []
    clock.instant = datetime(2026, 10, 6, 23, 30, tzinfo=UTC)  # 00:30 in Lisbon
    view = client.get('/api/today').json()
    assert view['availability']['state'] == 'asleep' and view['last_seen_at'] == seen
    clock.instant = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)  # clock moved backward
    assert client.post('/api/today/seen').json()['last_seen_at'] == seen


def test_today_reads_the_precomputed_day_so_a_holiday_is_not_work(client, life, clock):
    import json

    from dungeon.characters import require_current
    clock.instant = datetime(2026, 10, 6, 10, 0, tzinfo=UTC)
    reconcile(client)
    block = {'key': 'work', 'label': 'Thanksgiving (day off)', 'kind': 'leisure', 'holiday': 'Thanksgiving'}
    with client.app.state.database.connect(write=True) as connection:
        timeline = require_current(connection)['active_timeline_id']
        connection.execute("DELETE FROM life_agenda WHERE timeline_id=?", (timeline,))
        connection.execute("INSERT INTO life_agenda (id, timeline_id, subject, slot_key, starts_at, ends_at, local_date, "
                           "block, basis, created_at) VALUES ('a1', ?, 'companion', 'work@2026-10-06', "
                           "'2026-10-06T08:00:00Z', '2026-10-06T16:00:00Z', '2026-10-06', ?, 'routine', "
                           "'2026-10-06T00:00:00Z')", (timeline, json.dumps(block)))
    view = client.get('/api/today').json()
    assert view['availability'] == {'state': 'free', 'label': 'Thanksgiving (day off)',
                                    'until': '2026-10-06T16:00:00Z'}
    assert view['routine']['current']['block']['label'] == 'Thanksgiving (day off)'
