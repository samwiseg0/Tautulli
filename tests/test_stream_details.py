"""Stream details for a history row (datafactory.get_stream_details).

fd4e13b5 added transcode_decision to session_history, which made the
column ambiguous in the row_id query. a0f42d55 qualified it and gave the
three tables aliases. The guest filter still named
session_history.user_id, and SQLite rejects a table's own name once the
table has an alias, so every guest call raised "no such column". The
guest filter now names the alias.

The guest is simulated by patching session.get_session_user_id, as in
test_guest_history.py. bob (user_id 2) owns rows 3 and 5. alice owns
rows 1, 2, 4 and 6.
"""

import json

import pytest

import plexpy.session
from plexpy import datafactory
from plexpy import webserve  # noqa: F401  (registers the handlers on API2)
from plexpy.api2 import API2

from tests.test_history_table import seed_history


def stream_details(row_id):
    return datafactory.DataFactory().get_stream_details(row_id=row_id)


@pytest.fixture
def guest_bob(app_db, monkeypatch):
    seed_history(app_db)
    monkeypatch.setattr(plexpy.session, "get_session_user_id", lambda: "2")
    return app_db


def test_admin_gets_any_row(app_db):
    seed_history(app_db)

    assert stream_details(1)["title"] == "Alpha Show - Episode 1"
    assert stream_details(3)["title"] == "Beta Movie"


def test_guest_gets_their_own_row(guest_bob):
    details = stream_details(3)

    assert details["title"] == "Beta Movie"
    assert details["media_type"] == "movie"


def test_guest_gets_nothing_for_another_users_row(guest_bob):
    assert stream_details(1) == {}


@pytest.mark.parametrize("params, current", [
    ({"row_id": "3", "session_key": "7"}, ""),
    ({"session_key": "7"}, 1),
])
def test_history_row_is_not_a_current_session(app_db, app_config, params, current):
    seed_history(app_db)
    app_db.action("INSERT INTO sessions (session_key, user_id, title) VALUES (7, 1, 'Live Stream')")
    app_config.API_ENABLED = 1
    app_config.API_KEY = "a" * 32

    out = API2()._api_run(apikey=app_config.API_KEY, cmd="get_stream_data", **params)

    assert json.loads(out)["response"]["data"]["current_session"] == current
