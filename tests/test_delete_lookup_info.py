"""delete_lookup_info reads delete_all as a bool.

The raw string reached DataFactory, so delete_all=0 emptied the lookup table.
"""

import json

import pytest

from plexpy import webserve  # noqa: F401  (registers the handlers on API2)
from plexpy.api2 import API2


@pytest.fixture
def api(app_db, app_config):
    app_config.API_ENABLED = 1
    app_config.API_KEY = "a" * 32
    for key in (1, 2, 3):
        app_db.action("INSERT INTO tvmaze_lookup (rating_key, tvmaze_id) VALUES (?, ?)", [key, key])

    def run(**kwargs):
        out = API2()._api_run(apikey=app_config.API_KEY, cmd="delete_lookup_info", **kwargs)
        return json.loads(out)["response"]["result"]
    return run


def tvmaze_keys(db):
    return [row["rating_key"] for row in db.select("SELECT rating_key FROM tvmaze_lookup ORDER BY rating_key")]


@pytest.mark.parametrize("value", ["0", "false", "no", "off"])
def test_delete_all_false_keeps_the_table(api, app_db, value):
    assert api(service="tvmaze", delete_all=value) == "error"
    assert tvmaze_keys(app_db) == [1, 2, 3]


@pytest.mark.parametrize("value", ["1", "true"])
def test_delete_all_true_empties_the_table(api, app_db, value):
    assert api(service="tvmaze", delete_all=value) == "success"
    assert tvmaze_keys(app_db) == []


def test_rating_key_deletes_one_row(api, app_db):
    assert api(rating_key="2") == "success"
    assert tvmaze_keys(app_db) == [1, 3]
