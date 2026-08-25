"""Tests for ActivityProcessor.group_history (plexpy/activity_processor.py).

group_history decides whether a freshly-inserted session_history row belongs
to an existing playback group (a resume) or starts a new one, by comparing
it against the most recent row for the same user_id + rating_key.

Note: in this codebase reference_id has no DB trigger and no column
DEFAULT that ties it to id. A fresh insert leaves it NULL (see
write_session_history's value_dict, which never sets reference_id).
group_history is solely responsible for setting it, via the UPDATE at the
end of the method. These tests insert rows the same way and then call
group_history directly, the way write_session_history does right after
each insert (`last_id = db.last_insert_id(); self.group_history(last_id,
session, metadata)`). ActivityProcessor() takes no constructor arguments
and does not touch cherrypy request state, so it is used directly.

Only the non-live path is covered: it is keyed off rating_key/view_offset
and is what the plan calls out (resumed play, different user, different
item, reference_id chaining). The live-TV path (grouped by guid within a
1-day window) is a separate branch and out of scope here.
"""

import pytest

import plexpy
from plexpy import activity_processor


MOVIE = "movie"
DURATION = 1000  # session['duration']; watched threshold is computed from this


@pytest.fixture
def db(app_db):
    # check_watched (called from group_history) reads these from CONFIG.
    # Pin them explicitly so the join/no-join assertions don't quietly
    # depend on plexpy.config's current defaults.
    plexpy.CONFIG.MOVIE_WATCHED_PERCENT = 90  # threshold = 900 for DURATION=1000
    plexpy.CONFIG.WATCHED_MARKER = 3
    return app_db


def insert_row(db, row_id, user_id, rating_key, view_offset):
    """Insert a lean session_history row, the columns group_history's
    non-live query actually reads. reference_id is left NULL, matching a
    real insert (write_session_history never sets it)."""
    db.action(
        "INSERT INTO session_history (id, reference_id, user_id, rating_key, view_offset) "
        "VALUES (?, NULL, ?, ?, ?)",
        [row_id, user_id, rating_key, view_offset],
    )


def session_for(user_id, rating_key):
    return {
        "live": 0,
        "user_id": user_id,
        "rating_key": rating_key,
        "media_type": MOVIE,
        "duration": DURATION,
        "marker_credits_first": None,
        "marker_credits_final": None,
    }


def reference_id_of(db, row_id):
    row = db.select_single("SELECT reference_id FROM session_history WHERE id = ?", [row_id])
    return row["reference_id"]


def test_first_play_references_itself(db):
    ap = activity_processor.ActivityProcessor()
    insert_row(db, 1, user_id=1, rating_key=100, view_offset=500)

    ap.group_history(1, session_for(1, 100))

    assert reference_id_of(db, 1) == 1


def test_resumed_play_joins_group_and_chain_keeps_head_id(db):
    ap = activity_processor.ActivityProcessor()

    insert_row(db, 1, user_id=1, rating_key=100, view_offset=500)
    ap.group_history(1, session_for(1, 100))

    insert_row(db, 2, user_id=1, rating_key=100, view_offset=600)
    ap.group_history(2, session_for(1, 100))

    insert_row(db, 3, user_id=1, rating_key=100, view_offset=700)
    ap.group_history(3, session_for(1, 100))

    assert reference_id_of(db, 1) == 1
    assert reference_id_of(db, 2) == 1
    # Row 3 groups off row 2, but row 2's reference_id already points at
    # the group head (row 1), so row 3 lands on the head too, not row 2.
    assert reference_id_of(db, 3) == 1


def test_different_user_starts_new_group(db):
    ap = activity_processor.ActivityProcessor()

    insert_row(db, 1, user_id=1, rating_key=100, view_offset=500)
    ap.group_history(1, session_for(1, 100))

    insert_row(db, 2, user_id=2, rating_key=100, view_offset=600)
    ap.group_history(2, session_for(2, 100))

    assert reference_id_of(db, 2) == 2


def test_different_item_starts_new_group(db):
    ap = activity_processor.ActivityProcessor()

    insert_row(db, 1, user_id=1, rating_key=100, view_offset=500)
    ap.group_history(1, session_for(1, 100))

    insert_row(db, 2, user_id=1, rating_key=200, view_offset=600)
    ap.group_history(2, session_for(1, 200))

    assert reference_id_of(db, 2) == 2


@pytest.mark.parametrize(
    "prev_offset, new_offset, joins_group",
    [
        (500, 600, True),   # forward resume of an unfinished play -> joins
        (950, 990, False),  # previous play already crossed the watched threshold -> new group
        (600, 100, False),  # view_offset went backwards (replay from the start) -> new group
    ],
)
def test_group_join_decision(db, prev_offset, new_offset, joins_group):
    ap = activity_processor.ActivityProcessor()

    insert_row(db, 1, user_id=1, rating_key=100, view_offset=prev_offset)
    ap.group_history(1, session_for(1, 100))

    insert_row(db, 2, user_id=1, rating_key=100, view_offset=new_offset)
    ap.group_history(2, session_for(1, 100))

    assert reference_id_of(db, 2) == (1 if joins_group else 2)
