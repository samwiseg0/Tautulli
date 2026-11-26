"""get_home_stats counts time_range days back from before, or forward from after.

With before alone, the derived start bound replaced after, and YMD_to_timestamp raised TypeError on it.
"""

import json

import pytest

from plexpy import webserve  # noqa: F401  (registers the handlers on API2)
from plexpy.api2 import API2

from tests.test_history_table import insert_history_row

DEC_30 = 1767096000  # 2025-12-30 12:00 UTC
NOV_1 = 1761998400  # 2025-11-01 12:00 UTC


@pytest.fixture
def api(app_db, app_config):
    app_config.API_ENABLED = 1
    app_config.API_KEY = "a" * 32
    app_db.action("INSERT INTO users (user_id, username) VALUES (1, 'alice')")
    insert_history_row(app_db, 1, 1, 1, "alice", DEC_30, DEC_30 + 600, 301, "December Movie", "movie")
    insert_history_row(app_db, 2, 2, 1, "alice", NOV_1, NOV_1 + 600, 302, "November Movie", "movie")

    def run(**kwargs):
        call = API2()
        out = json.loads(call._api_run(apikey=app_config.API_KEY, cmd="get_home_stats", stat_id="top_movies",
                                       time_range="30", **kwargs))
        return call._api_response_code, [row["title"] for row in out["response"]["data"]["rows"]]
    return run


@pytest.mark.parametrize("kwargs, titles", [
    ({"before": "2025-12-31"}, ["December Movie"]),
    ({"after": "2025-11-01"}, ["November Movie"]),
    ({"before": "2025-12-31", "after": "2025-11-01"}, ["December Movie", "November Movie"]),
])
def test_dates_set_the_window(api, kwargs, titles):
    assert api(**kwargs) == (200, titles)
