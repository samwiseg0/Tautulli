"""Library commands answer what the caller asked for."""

import json

import pytest

from plexpy import libraries, pmsconnect, webserve
from plexpy.api2 import API2

from tests.test_history_table import seed_history


CHILD = {"added_at": "1", "media_type": "episode", "rating_key": "6", "parent_rating_key": "5",
         "grandparent_rating_key": "4", "title": "Pilot", "sort_title": "Pilot", "year": "2020",
         "media_index": "1", "parent_media_index": "1", "thumb": ""}


@pytest.mark.parametrize("params, rows", [
    ({"section_id": "999", "rating_key": "5"}, 0),
    ({"section_id": "1", "rating_key": "5"}, 1),
    ({"rating_key": "5"}, 1),
])
def test_media_info_answers_empty_for_an_unknown_section_id(app_db, app_config, tmp_path, monkeypatch,
                                                            params, rows):
    app_config.API_ENABLED = 1
    app_config.API_KEY = "a" * 32
    app_config.CACHE_DIR = str(tmp_path)
    app_config.PMS_IDENTIFIER = "server"
    app_db.action("INSERT INTO library_sections (server_id, section_id, section_name, section_type) "
                  "VALUES ('server', 1, 'Shows', 'show')")
    monkeypatch.setattr(libraries, "refresh_libraries", lambda: None)
    monkeypatch.setattr(pmsconnect.PmsConnect, "get_library_children_details",
                        lambda self, **kwargs: {"library_count": 1, "children_list": [CHILD]})

    out = API2()._api_run(apikey=app_config.API_KEY, cmd="get_library_media_info", **params)

    assert len(json.loads(out)["response"]["data"]["data"]) == rows


@pytest.mark.parametrize("params", [{"section_id": "1"}, {"rating_key": "5"}])
def test_file_sizes_succeed_for_a_known_library_or_a_rating_key(app_db, app_config, tmp_path, monkeypatch, params):
    app_config.CACHE_DIR = str(tmp_path)
    app_config.PMS_IDENTIFIER = "server"
    app_db.action("INSERT INTO library_sections (server_id, section_id, section_name, section_type) "
                  "VALUES ('server', 1, 'Movies', 'movie')")
    monkeypatch.setattr(libraries, "refresh_libraries", lambda: None)

    assert webserve.WebInterface().get_media_info_file_sizes(**params) == {"success": True}


def test_file_sizes_fail_for_an_unknown_section_id(app_db, app_config, tmp_path, monkeypatch):
    app_config.CACHE_DIR = str(tmp_path)
    monkeypatch.setattr(libraries, "refresh_libraries", lambda: None)

    assert webserve.WebInterface().get_media_info_file_sizes(section_id="999") == {"success": False}
    assert list(tmp_path.glob("media_info_*")) == []


@pytest.mark.parametrize("params, result, rows", [
    ({"server_id": "old", "section_id": "1"}, "error", 6),
    ({"server_id": "server", "section_id": "1"}, "success", 0),
    ({"row_ids": "1"}, "success", 0),
])
def test_purge_answers_error_for_another_server_id(app_db, app_config, params, result, rows):
    seed_history(app_db)
    app_config.API_ENABLED = 1
    app_config.API_KEY = "a" * 32
    app_config.PMS_IDENTIFIER = "server"
    app_db.action("INSERT INTO library_sections (server_id, section_id, section_name, section_type) "
                  "VALUES ('server', 1, 'Movies', 'movie')")

    out = API2()._api_run(apikey=app_config.API_KEY, cmd="delete_all_library_history", **params)

    assert json.loads(out)["response"]["result"] == result
    assert app_db.select_single("SELECT COUNT(*) AS n FROM session_history")["n"] == rows
