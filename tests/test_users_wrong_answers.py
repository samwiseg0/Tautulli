"""User commands answer what the caller asked for."""

import json

import pytest

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


def test_get_users_table_keeps_its_own_default_sort(app_db, app_config):
    # The default sort column, friendly_name, is column 1.
    for user_id, name in ((1, "alice"), (2, "carol"), (3, "bob")):
        app_db.action("INSERT INTO users (user_id, username) VALUES (?, ?)", [user_id, name])

    data = api_data(app_config, cmd="get_users_table", order_column="bogus")

    assert [row["friendly_name"] for row in data["data"] if row["user_id"]] == ["carol", "bob", "alice"]


@pytest.mark.parametrize("order_dir, timestamps", [
    ("asc", [1000, 2000, 3000]),
    ("ASC", [1000, 2000, 3000]),
    ("asc,desc", [1000, 2000, 3000]),
    ("", [3000, 2000, 1000]),
    ("bad", [3000, 2000, 1000]),
])
def test_get_user_logins_default_sort_takes_the_order_dir(app_db, app_config, order_dir, timestamps):
    for timestamp in (1000, 3000, 2000):
        app_db.action("INSERT INTO user_login (timestamp, user_id, user, user_group, success) "
                      "VALUES (?, 0, 'Local', 'guest', 1)", [timestamp])

    data = api_data(app_config, cmd="get_user_logins", user_id="0", order_column="date", order_dir=order_dir)

    assert [row["timestamp"] for row in data["data"]] == timestamps


@pytest.mark.parametrize("order_column", ["date", "bogus,time"])
def test_get_user_logins_keeps_the_default_sort_for_unknown_columns(app_db, app_config, order_column):
    for timestamp in (1000, 3000, 2000):
        app_db.action("INSERT INTO user_login (timestamp, user_id, user, user_group, success) "
                      "VALUES (?, 0, 'Local', 'guest', 1)", [timestamp])

    data = api_data(app_config, cmd="get_user_logins", user_id="0", order_column=order_column)

    assert [row["timestamp"] for row in data["data"]] == [3000, 2000, 1000]
