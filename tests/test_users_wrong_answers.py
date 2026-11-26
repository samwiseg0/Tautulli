"""User commands answer what the caller asked for."""

import json

from plexpy import users, webserve  # noqa: F401  (webserve registers the handlers on API2)
from plexpy.api2 import API2


def api_data(app_config, **kwargs):
    app_config.API_ENABLED = 1
    app_config.API_KEY = "a" * 32
    out = API2()._api_run(apikey=app_config.API_KEY, **kwargs)
    return json.loads(out)["response"]["data"]


def test_get_user_refreshes_an_unknown_user_with_last_seen(app_db, app_config, monkeypatch):
    # User 42 reaches the users table only through the refresh.
    monkeypatch.setattr(users, "refresh_users", lambda: app_db.action(
        "INSERT INTO users (user_id, username) VALUES (42, 'newuser')"))

    data = api_data(app_config, cmd="get_user", user_id="42", include_last_seen="1")

    assert (data["user_id"], data["username"]) == (42, "newuser")


def test_get_user_refresh_skips_archived_plays_by_default(app_db, app_config, monkeypatch):
    # The only play of user 42 is in archived library 5.
    app_db.action("INSERT INTO library_sections (server_id, section_id, section_name, section_type, is_archived) "
                  "VALUES ('server', 5, 'Old', 'movie', 1)")
    app_db.action("INSERT INTO session_history (started, stopped, user_id, section_id) VALUES (1000, 1100, 42, 5)")
    monkeypatch.setattr(users, "refresh_users", lambda: app_db.action(
        "INSERT INTO users (user_id, username) VALUES (42, 'newuser')"))

    data = api_data(app_config, cmd="get_user", user_id="42", include_last_seen="1")

    assert (data["user_id"], data["last_seen"]) == (42, None)


def test_get_user_refresh_keeps_include_archived(app_db, app_config, monkeypatch):
    # The only play of user 42 is in archived library 5.
    app_db.action("INSERT INTO library_sections (server_id, section_id, section_name, section_type, is_archived) "
                  "VALUES ('server', 5, 'Old', 'movie', 1)")
    app_db.action("INSERT INTO session_history (started, stopped, user_id, section_id) VALUES (1000, 1100, 42, 5)")
    monkeypatch.setattr(users, "refresh_users", lambda: app_db.action(
        "INSERT INTO users (user_id, username) VALUES (42, 'newuser')"))

    data = api_data(app_config, cmd="get_user", user_id="42", include_last_seen="1", include_archived="1")

    assert (data["user_id"], data["last_seen"]) == (42, 1000)
