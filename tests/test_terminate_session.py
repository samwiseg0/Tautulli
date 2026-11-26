"""terminate_session ends only the stream that session_key and session_id both name in Plex.

A session_key of one stream with the session_id of another ended the session_id stream.
The pair is checked against the live Plex sessions, because the stored session_id can be stale or blank.
"""

import json

import pytest

from plexpy import plextv, pmsconnect
from plexpy import webserve  # noqa: F401  (registers the handlers on API2)
from plexpy.api2 import API2

LIVE = [{"session_key": "1", "session_id": "stream-A"},
        {"session_key": "3", "session_id": "stream-C"},
        {"session_key": "4", "session_id": "stream-D"}]


class Ok:
    ok = True


@pytest.fixture
def terminate(app_db, app_config, monkeypatch):
    app_config.API_ENABLED = 1
    app_config.API_KEY = "a" * 32
    # Key 2 ended in Plex. Keys 3 and 4 hold a stale and a blank session_id.
    app_db.action("INSERT INTO sessions (session_key, session_id, rating_key) "
                  "VALUES (1, 'stream-A', 10), (2, 'stream-B', 20), (3, 'old-C', 30), (4, '', 40)")
    ended = []
    monkeypatch.setattr(plextv.PlexTV, "get_plexpass_status", lambda self: True)
    monkeypatch.setattr(pmsconnect.PmsConnect, "get_current_activity", lambda self, session_key=None: {
        "sessions": [s for s in LIVE if s["session_key"] == str(session_key)]})
    monkeypatch.setattr(pmsconnect.PmsConnect, "get_sessions_terminate",
                        lambda self, session_id="", reason="": ended.append(session_id) or Ok())

    def run(**kwargs):
        out = json.loads(API2()._api_run(apikey=app_config.API_KEY, cmd="terminate_session", **kwargs))
        return out["response"]["result"], out["response"]["message"], ended
    return run


@pytest.mark.parametrize("kwargs", [
    {"session_key": "1", "session_id": "stream-D"},
    {"session_key": "2", "session_id": "stream-B"},
    {"session_key": "9", "session_id": "stream-A"},
    {"session_key": "9"},
])
def test_pair_that_names_no_live_stream_ends_nothing(terminate, kwargs):
    message = "Failed to terminate session: Invalid session_key (%s) or session_id (%s)." % (
        kwargs["session_key"], kwargs.get("session_id", ""))

    assert terminate(**kwargs) == ("error", message, [])


@pytest.mark.parametrize("kwargs, stream", [
    ({"session_key": "1", "session_id": "stream-A"}, "stream-A"),
    ({"session_key": "3", "session_id": "stream-C"}, "stream-C"),
    ({"session_key": "4", "session_id": "stream-D"}, "stream-D"),
    ({"session_key": "1"}, "stream-A"),
    ({"session_id": "stream-B"}, "stream-B"),
])
def test_live_pair_ends_the_stream(terminate, kwargs, stream):
    assert terminate(**kwargs) == ("success", "Session terminated.", [stream])


def test_unreachable_plex_refuses_the_pair(terminate, monkeypatch):
    # get_current_activity answers [] when it cannot read /status/sessions.
    monkeypatch.setattr(pmsconnect.PmsConnect, "get_current_activity", lambda self, session_key=None: [])
    message = "Failed to terminate session: Invalid session_key (1) or session_id (stream-A)."

    assert terminate(session_key="1", session_id="stream-A") == ("error", message, [])


def test_unknown_key_makes_no_live_lookup(terminate, monkeypatch):
    lookups = []
    monkeypatch.setattr(pmsconnect.PmsConnect, "get_current_activity",
                        lambda self, session_key=None: lookups.append(session_key))

    assert terminate(session_key="9", session_id="stream-A")[0] == "error"
    assert lookups == []
