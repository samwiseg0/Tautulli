"""Page templates list notifiers without the notify_log join.

The join visits every notify_log row. It took about 5 s on a large database.
"""

import json
import re
from pathlib import Path

import pytest

from plexpy import notifiers
from plexpy import webserve  # noqa: F401  (registers the handlers on API2)
from plexpy.api2 import API2

TEMPLATES = Path(__file__).resolve().parent.parent / "data/interfaces/default"


@pytest.mark.parametrize("template", ["info.html", "newsletter_config.html"])
def test_template_skips_the_notify_log_join(template):
    source = (TEMPLATES / template).read_text(encoding="utf-8")
    assert re.findall(r"notifiers\.get_notifiers\((.*?)\)", source) == [""]


def test_query_without_the_join_has_the_fields_the_templates_read(app_db):
    app_db.action("INSERT INTO notifiers (agent_id, agent_name, agent_label, friendly_name) "
                  "VALUES (10, 'email', 'Email', 'Mine')")

    (row,) = notifiers.get_notifiers()

    assert (row["id"], row["agent_name"], row["agent_label"], row["friendly_name"]) == (1, "email", "Email", "Mine")


@pytest.fixture
def api(app_db, app_config):
    app_config.API_ENABLED = 1
    app_config.API_KEY = "a" * 32
    app_db.action("INSERT INTO notifiers (agent_id, agent_name, agent_label, friendly_name, on_play) "
                  "VALUES (10, 'email', 'Email', 'Plays', 1), (10, 'email', 'Email', 'Quiet', 0)")

    def run(**kwargs):
        api = API2()
        out = json.loads(api._api_run(apikey=app_config.API_KEY, cmd="get_notifiers", **kwargs))
        return api._api_response_code, [row["friendly_name"] for row in out["response"]["data"]]
    return run


@pytest.mark.parametrize("last", ["0", "1"])
def test_unknown_notify_action_lists_no_notifiers(api, last):
    assert api(notify_action="on_typo", include_last_triggered=last) == (200, [])


def test_known_notify_action_lists_the_enabled_notifiers(api):
    assert api(notify_action="on_play") == (200, ["Plays"])
