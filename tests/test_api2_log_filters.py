"""get_notification_log and get_newsletter_log take exact id and action filters.

The DataTables search matches substrings, so notifier 1 also matched 10 and 21.
"""

import json

import cherrypy
import pytest

from plexpy import webserve  # noqa: F401  (registers the handlers on API2)
from plexpy.api2 import API2


@pytest.fixture
def api(app_db, app_config):
    app_config.API_ENABLED = 1
    app_config.API_KEY = "a" * 32
    for notifier_id, action in ((1, "on_play"), (10, "on_stop"), (21, "on_play"), (1, "on_stop")):
        app_db.action("INSERT INTO notify_log (notifier_id, notify_action) VALUES (?, ?)", [notifier_id, action])
    for newsletter_id, action in ((1, "on_cron"), (10, "api"), (21, "on_cron"), (1, "api")):
        app_db.action("INSERT INTO newsletter_log (newsletter_id, notify_action) VALUES (?, ?)",
                      [newsletter_id, action])

    def run(cmd, id_key, **kwargs):
        out = API2()._api_run(apikey=app_config.API_KEY, cmd=cmd, **kwargs)
        assert cherrypy.response.status == 200
        data = json.loads(out)["response"]["data"]
        rows = [(row[id_key], row["notify_action"]) for row in data["data"]]
        assert data["recordsFiltered"] == len(rows)
        return set(rows)
    return run


LOGS = [("get_notification_log", "notifier_id", "on_play", "on_stop"),
        ("get_newsletter_log", "newsletter_id", "on_cron", "api")]


@pytest.mark.parametrize("cmd, id_key, action, other", LOGS)
def test_no_filter_returns_every_row(api, cmd, id_key, action, other):
    assert api(cmd, id_key) == {(1, action), (1, other), (10, other), (21, action)}


@pytest.mark.parametrize("cmd, id_key, action, other", LOGS)
def test_one_id_matches_that_id_exactly(api, cmd, id_key, action, other):
    assert api(cmd, id_key, **{id_key: "1"}) == {(1, action), (1, other)}


@pytest.mark.parametrize("cmd, id_key, action, other", LOGS)
def test_an_id_list_matches_each_id(api, cmd, id_key, action, other):
    assert api(cmd, id_key, **{id_key: "10, 21"}) == {(10, other), (21, action)}


@pytest.mark.parametrize("cmd, id_key, action, other", LOGS)
def test_one_action_matches_that_action(api, cmd, id_key, action, other):
    assert api(cmd, id_key, notify_action=action) == {(1, action), (21, action)}


@pytest.mark.parametrize("cmd, id_key, action, other", LOGS)
def test_an_action_list_and_an_id_combine(api, cmd, id_key, action, other):
    assert api(cmd, id_key, notify_action=action + ", " + other, **{id_key: "1"}) == {(1, action), (1, other)}


@pytest.mark.parametrize("value", ["999", "%", "1) OR (1=1"])
@pytest.mark.parametrize("cmd, id_key, action, other", LOGS)
def test_an_id_that_matches_nothing_returns_no_rows(api, cmd, id_key, action, other, value):
    assert api(cmd, id_key, **{id_key: value}) == set()
