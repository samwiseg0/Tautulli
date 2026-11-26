"""notify_newsletter always sends with notify_action api.

A caller's notify_action reached newsletter_handler.notify a second time, and the API answered 500.
"""

import json

import pytest

from plexpy import newsletter_handler, newsletters
from plexpy.api2 import API2


@pytest.fixture
def sent(app_db, app_config, monkeypatch):
    app_config.API_ENABLED = 1
    app_config.API_KEY = "a" * 32
    actions = []
    monkeypatch.setattr(newsletters, "get_newsletter_config", lambda newsletter_id=None: {"id": 1})
    monkeypatch.setattr(newsletter_handler, "notify",
                        lambda newsletter_id=None, notify_action=None, **kwargs: actions.append(notify_action) or 7)
    return actions


@pytest.mark.parametrize("extra", [{}, {"notify_action": "on_cron"}])
def test_notify_newsletter_sends_as_api(sent, app_config, extra):
    api = API2()
    out = json.loads(api._api_run(apikey=app_config.API_KEY, cmd="notify_newsletter", newsletter_id="1", **extra))

    assert api._api_response_code == 200
    assert out["response"]["data"] == {"newsletter_notification_id": 7}
    assert sent == ["api"]
