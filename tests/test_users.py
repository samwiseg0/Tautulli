import json

import pytest

from plexpy import database
from plexpy.api2 import API2
from plexpy.datafactory import DataFactory
from plexpy import webserve
from plexpy.users import Users

from tests.test_history_table import insert_history_row


# Draw shape reduced from webserve.py's get_user_logins(): the dt_columns it
# builds when the caller sends no json_data.
LOGIN_COLUMNS = [
    ("timestamp", True, False),
    ("ip_address", True, True),
    ("host", True, True),
    ("os", True, True),
    ("browser", True, True),
]


def login_draw():
    return {
        "draw": 1,
        "start": 0,
        "length": 25,
        "search": {"value": "", "regex": False},
        "order": [{"column": 0, "dir": "desc"}],
        "columns": [
            {"data": name, "orderable": orderable, "searchable": searchable,
             "search": {"value": "", "regex": False}}
            for name, orderable, searchable in LOGIN_COLUMNS
        ],
    }


# The Plex "Local" user has user_id 0. Every guard below used to be a plain
# truthiness check, which reads 0 as "no user given" and falls through to the
# no-user branch.

@pytest.fixture
def local_user(app_db):
    # dbcheck seeds the Local user itself, so this only fills in the columns
    # the tests read.
    app_db.action("UPDATE users SET allow_guest = ?, user_token = ?, server_token = ? WHERE user_id = ?",
                  [1, "token0", "server0", 0])
    return app_db


def test_get_tokens_for_user_id_zero(local_user):
    assert Users().get_tokens(user_id=0) == {
        "allow_guest": 1,
        "user_token": "token0",
        "server_token": "server0",
    }


def test_get_tokens_without_a_user_id_returns_the_empty_default(local_user):
    assert Users().get_tokens() == {"allow_guest": 0, "user_token": "", "server_token": ""}


def test_undelete_user_id_zero(local_user):
    local_user.action("UPDATE users SET deleted_user = 1, keep_history = 0 WHERE user_id = ?", [0])

    assert Users().undelete(user_id=0) is True
    assert local_user.select_single(
        "SELECT deleted_user, keep_history FROM users WHERE user_id = ?", [0]
    ) == {"deleted_user": 0, "keep_history": 1}


def test_undelete_falls_through_to_username_for_a_non_numeric_user_id(local_user):
    # A user_id that is not a number takes neither the numeric branch nor a
    # lookup of its own, so the username is what restores the user.
    local_user.action("UPDATE users SET deleted_user = 1, keep_history = 0 WHERE user_id = ?", [0])

    assert Users().undelete(user_id="not-a-number", username="Local") is True
    assert local_user.select_single(
        "SELECT deleted_user FROM users WHERE user_id = ?", [0]
    ) == {"deleted_user": 0}


def test_datatables_user_login_filters_on_user_id_zero(local_user):
    local_user.action("INSERT INTO users (user_id, username) VALUES (?, ?)", [1, "someone"])
    for row_user_id, user in ((0, "Local"), (1, "someone")):
        local_user.action("INSERT INTO user_login (timestamp, user_id, user, user_group, success) "
                          "VALUES (?, ?, ?, ?, ?)", [1700000000, row_user_id, user, "guest", 1])

    result = Users().get_datatables_user_login(user_id=0, kwargs={"json_data": json.dumps(login_draw())})

    assert [row["user_id"] for row in result["data"]] == [0]
    assert result["recordsFiltered"] == 1


def test_datatables_user_login_without_a_user_id_returns_every_row(local_user):
    local_user.action("INSERT INTO users (user_id, username) VALUES (?, ?)", [1, "someone"])
    for row_user_id, user in ((0, "Local"), (1, "someone")):
        local_user.action("INSERT INTO user_login (timestamp, user_id, user, user_group, success) "
                          "VALUES (?, ?, ?, ?, ?)", [1700000000, row_user_id, user, "guest", 1])

    result = Users().get_datatables_user_login(kwargs={"json_data": json.dumps(login_draw())})

    assert sorted(row["user_id"] for row in result["data"]) == [0, 1]


# get_user_devices feeds the new device notification check: an empty list
# reads as "this user has no known devices", so every play by the Local user
# fired a new device notification.

def test_get_user_devices_for_user_id_zero(local_user):
    local_user.action("INSERT INTO session_history (user_id, machine_id) VALUES (?, ?)", [0, "machine-a"])
    local_user.action("INSERT INTO session_history (user_id, machine_id) VALUES (?, ?)", [1, "machine-b"])

    assert DataFactory().get_user_devices(user_id=0) == ["machine-a"]


def test_get_user_devices_includes_continued_sessions_for_user_id_zero(local_user):
    local_user.action("INSERT INTO session_history (user_id, machine_id) VALUES (?, ?)", [0, "machine-a"])
    local_user.action("INSERT INTO sessions_continued (user_id, machine_id) VALUES (?, ?)", [0, "machine-c"])

    assert sorted(DataFactory().get_user_devices(user_id=0, history_only=False)) == ["machine-a", "machine-c"]


@pytest.mark.parametrize("user_id", ["", None])
def test_get_user_devices_without_a_user_id_returns_nothing(local_user, user_id):
    local_user.action("INSERT INTO session_history (user_id, machine_id) VALUES (?, ?)", [0, "machine-a"])

    assert DataFactory().get_user_devices(user_id=user_id) == []


@pytest.fixture
def deleted_bob(app_db):
    app_db.action("INSERT INTO users (user_id, username, deleted_user) VALUES (1, 'alice', 0)")
    app_db.action("INSERT INTO users (user_id, username, deleted_user) VALUES (2, 'bob', 1)")
    return app_db


def user_list_ids(**kwargs):
    # The database seeds a local user, user_id 0
    rows = webserve.WebInterface().get_user_list(**kwargs)["data"]
    return {row["user_id"] for row in rows} - {0}


def test_users_table_lists_deleted_users_when_asked(deleted_bob):
    assert user_list_ids() == {1}
    assert user_list_ids(include_deleted="0") == {1}
    assert user_list_ids(include_deleted="1") == {1, 2}


def test_users_table_flags_deleted_users(deleted_bob):
    rows = webserve.WebInterface().get_user_list(include_deleted="1")["data"]

    assert {row["user_id"]: row["deleted_user"] for row in rows if row["user_id"]} == {1: 0, 2: 1}


def test_users_table_hides_deleted_users_from_a_guest(deleted_bob, monkeypatch):
    monkeypatch.setattr("plexpy.session.get_session_user_id", lambda: "2")

    assert user_list_ids(include_deleted="1") == set()


@pytest.fixture
def alice_row_id(app_db, app_config):
    app_config.API_ENABLED = 1
    app_config.API_KEY = "a" * 32
    app_db.action("INSERT INTO users (user_id, username) VALUES (1, 'alice')")
    insert_history_row(app_db, 1, 1, 1, "alice", 1000, 1600, 301, "First Movie", "movie")
    return app_db.select_single("SELECT id FROM users WHERE user_id = 1")["id"]


def delete_by_row_ids(app_db, app_config, cmd, row_ids):
    out = API2()._api_run(apikey=app_config.API_KEY, cmd=cmd, row_ids=row_ids)
    plays = app_db.select_single("SELECT COUNT(*) AS n FROM session_history")["n"]
    return json.loads(out)["response"]["result"], plays


@pytest.mark.parametrize("cmd", ["delete_user", "delete_all_user_history"])
def test_delete_with_row_ids_of_no_user_answers_an_error(alice_row_id, app_db, app_config, cmd):
    assert delete_by_row_ids(app_db, app_config, cmd, "999999") == ("error", 1)


@pytest.mark.parametrize("cmd", ["delete_user", "delete_all_user_history"])
def test_delete_with_a_user_row_id_deletes_the_history(alice_row_id, app_db, app_config, cmd):
    assert delete_by_row_ids(app_db, app_config, cmd, str(alice_row_id)) == ("success", 0)


@pytest.mark.parametrize("cmd", ["delete_user", "delete_all_user_history"])
def test_delete_with_a_failed_history_delete_answers_an_error(alice_row_id, app_db, app_config, monkeypatch, cmd):
    monkeypatch.setattr(database, "delete_user_history", lambda **kwargs: False)

    assert delete_by_row_ids(app_db, app_config, cmd, str(alice_row_id)) == ("error", 1)


@pytest.mark.parametrize("cmd", ["delete_user", "delete_all_user_history"])
def test_delete_with_one_failed_history_delete_of_two_answers_an_error(alice_row_id, app_db, app_config, monkeypatch, cmd):
    app_db.action("INSERT INTO users (user_id, username) VALUES (2, 'bob')")
    bob_row_id = app_db.select_single("SELECT id FROM users WHERE user_id = 2")["id"]
    real_delete = database.delete_user_history
    monkeypatch.setattr(database, "delete_user_history",
                        lambda user_id=None: str(user_id) != "2" and real_delete(user_id=user_id))

    assert delete_by_row_ids(app_db, app_config, cmd, "%s,%s" % (alice_row_id, bob_row_id)) == ("error", 0)
