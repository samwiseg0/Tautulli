import json

from plexpy import datafactory


# ---------------------------------------------------------------------------
# datafactory.DataFactory.get_datatables_history
#
# Draw shape reduced from webserve.py's get_history(): when the caller
# sends no json_data, get_history builds this exact dt_columns list and
# passes it through helpers.build_datatables_json to make the draw dict
# that ends up as kwargs['json_data'].
# ---------------------------------------------------------------------------

HISTORY_COLUMNS = [
    ("date", True, False),
    ("friendly_name", True, True),
    ("ip_address", True, True),
    ("platform", True, True),
    ("product", True, True),
    ("player", True, True),
    ("full_title", True, True),
    ("started", True, False),
    ("paused_counter", True, False),
    ("stopped", True, False),
    ("duration", True, False),
    ("watched_status", False, False),
]


def build_draw(order_column="date", direction="desc", start=0, length=25, search=""):
    # build_datatables_json always defaults the order to date descending, so
    # a real draw never arrives with an empty order list.
    names = [c[0] for c in HISTORY_COLUMNS]
    order = [{"column": names.index(order_column), "dir": direction}]

    return {
        "draw": 1,
        "start": start,
        "length": length,
        "search": {"value": search, "regex": False},
        "order": order,
        "columns": [
            {"data": name, "orderable": orderable, "searchable": searchable,
             "search": {"value": "", "regex": False}}
            for name, orderable, searchable in HISTORY_COLUMNS
        ],
    }


def call_history(grouping=True, custom_where=None, draw=None):
    factory = datafactory.DataFactory()
    return factory.get_datatables_history(
        kwargs={"json_data": json.dumps(draw or build_draw())},
        custom_where=custom_where or [],
        grouping=grouping,
        # Keep the "sessions" table union out of scope: HISTORY_TABLE_ACTIVITY
        # defaults on, but the test db never has live sessions to union in.
        include_activity=False,
    )


# Six session_history rows across two users (alice, bob) and three items.
# Rows 1 and 2 share reference_id 10 (a paused/resumed play of the same
# episode) -- the only multi-row group; every other reference_id groups a
# single row. started is distinct on every row so ordering and paging are
# unambiguous.
#
# Row 6 is marked live (session_history_metadata.live=1) even though its
# underlying media_type is "movie", same title as row 3 (Beta Movie). This
# is what the media_type_live CASE expression in get_datatables_history is
# for: media_type_live IN ['live'] must return row 6, and
# media_type_live IN ['movie'] must exclude it despite the shared title.
#
# columns: id, reference_id, user_id, user, started, stopped, paused_counter,
#          player, rating_key, title, media_type, transcode_decision, live
_HISTORY_ROWS = [
    (1, 10, 1, "alice", 1000, 1300, 0, "Roku", 201, "Alpha Show - Episode 1", "episode", "direct play", 0),
    (2, 10, 1, "alice", 1300, 1900, 50, "Chromecast", 201, "Alpha Show - Episode 1", "episode", "transcode", 0),
    (3, 11, 2, "bob", 2000, 2600, 0, "Shield", 202, "Beta Movie", "movie", "transcode", 0),
    (4, 12, 1, "alice", 3000, 3200, 0, "Roku", 203, "Gamma Track", "track", "direct play", 0),
    (5, 13, 2, "bob", 4000, 4400, 0, "Shield", 201, "Alpha Show - Episode 1", "episode", "direct play", 0),
    (6, 14, 1, "alice", 5000, 5900, 0, "Roku", 202, "Beta Movie", "movie", "transcode", 1),
]


def seed_history(app_db):
    app_db.action("INSERT INTO users (user_id, username, friendly_name) VALUES (1, 'alice', 'Alice')")
    # Blank friendly_name: get_datatables_history falls back to username.
    app_db.action("INSERT INTO users (user_id, username, friendly_name) VALUES (2, 'bob', '')")

    for (row_id, ref_id, user_id, user, started, stopped, paused,
         player, rating_key, title, media_type, transcode, live) in _HISTORY_ROWS:
        app_db.action(
            "INSERT INTO session_history (id, reference_id, started, stopped, rating_key, "
            "user_id, user, ip_address, paused_counter, player, product, platform, "
            "machine_id, location, secure, relayed, media_type, section_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [row_id, ref_id, started, stopped, rating_key, user_id, user,
             "10.0.0.%d" % user_id, paused, player, "Plex", player,
             "mach%d" % row_id, "lan", 1, 0, media_type, 1],
        )
        app_db.action(
            "INSERT INTO session_history_metadata (id, rating_key, parent_rating_key, "
            "grandparent_rating_key, title, full_title, year, duration, guid, live, media_type) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [row_id, rating_key, rating_key - 1, rating_key - 2, title, title,
             2020, 1800, "guid-%d" % rating_key, live, media_type],
        )
        app_db.action(
            "INSERT INTO session_history_media_info (id, rating_key, transcode_decision) "
            "VALUES (?,?,?)",
            [row_id, rating_key, transcode],
        )


# ---------------------------------------------------------------------------
# Grouping: reference_id groups vs one row per session_history row.
# ---------------------------------------------------------------------------

def test_grouping_on_aggregates_by_reference_id(app_db):
    seed_history(app_db)

    grouped = call_history(grouping=True)

    # 5 distinct reference_ids: group 10 (rows 1+2) plus one each for 11-14.
    assert grouped["recordsFiltered"] == 5
    assert len(grouped["data"]) == 5
    # recordsTotal is a raw session_history row count, not group count.
    assert grouped["recordsTotal"] == 6

    group = next(row for row in grouped["data"] if row["reference_id"] == 10)
    assert group["group_count"] == 2
    assert group["started"] == 1000
    assert group["stopped"] == 1900
    # (1300-1000) + (1900-1300) - (0 + 50) paused
    assert group["duration"] == 850


def test_grouping_off_returns_every_row(app_db):
    seed_history(app_db)

    ungrouped = call_history(grouping=False)

    assert ungrouped["recordsFiltered"] == 6
    assert ungrouped["recordsTotal"] == 6
    assert len(ungrouped["data"]) == 6
    assert {row["group_count"] for row in ungrouped["data"]} == {1}


# ---------------------------------------------------------------------------
# custom_where filter
# ---------------------------------------------------------------------------

def test_custom_where_filters_by_user_id(app_db):
    seed_history(app_db)

    result = call_history(grouping=False, custom_where=[["session_history.user_id IN", ["1"]]])

    # alice has rows 1, 2, 4, 6.
    assert result["recordsFiltered"] == 4
    assert result["recordsTotal"] == 6
    assert {row["row_id"] for row in result["data"]} == {1, 2, 4, 6}
    assert all(row["user_id"] == 1 for row in result["data"])


# ---------------------------------------------------------------------------
# Global search box
# ---------------------------------------------------------------------------

def test_search_filters_by_title(app_db):
    seed_history(app_db)

    result = call_history(grouping=False, draw=build_draw(search="Beta"))

    assert result["recordsFiltered"] == 2
    assert {row["row_id"] for row in result["data"]} == {3, 6}
    assert all(row["full_title"] == "Beta Movie" for row in result["data"])


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------

def test_order_by_started_descending(app_db):
    seed_history(app_db)

    result = call_history(grouping=False, draw=build_draw(order_column="started", direction="desc"))

    assert [row["row_id"] for row in result["data"]] == [6, 5, 4, 3, 2, 1]
    assert [row["started"] for row in result["data"]] == [5000, 4000, 3000, 2000, 1300, 1000]


# ---------------------------------------------------------------------------
# Paging: first page, a trailing partial page, and a start past the end.
# ---------------------------------------------------------------------------

def test_paging_first_and_trailing_pages(app_db):
    seed_history(app_db)
    draw = lambda start, length: build_draw(order_column="started", direction="desc",
                                            start=start, length=length)

    first_page = call_history(grouping=False, draw=draw(0, 3))
    assert [row["row_id"] for row in first_page["data"]] == [6, 5, 4]
    assert first_page["recordsTotal"] == 6
    assert first_page["recordsFiltered"] == 6

    trailing_page = call_history(grouping=False, draw=draw(4, 3))
    assert [row["row_id"] for row in trailing_page["data"]] == [2, 1]
    assert trailing_page["recordsTotal"] == 6
    assert trailing_page["recordsFiltered"] == 6

    past_the_end = call_history(grouping=False, draw=draw(6, 3))
    assert past_the_end["data"] == []
    assert past_the_end["recordsTotal"] == 6
    assert past_the_end["recordsFiltered"] == 6


# ---------------------------------------------------------------------------
# Row shape: the fields callers render from a single known row.
# ---------------------------------------------------------------------------

def test_row_shape_has_fields_callers_render(app_db):
    seed_history(app_db)

    result = call_history(grouping=False,
                          custom_where=[["session_history.reference_id IN", ["11"]]])

    assert len(result["data"]) == 1
    row = result["data"][0]
    assert row["row_id"] == 3
    assert row["id"] == 3
    assert row["user"] == "bob"
    assert row["friendly_name"] == "bob"  # blank friendly_name falls back to username
    assert row["full_title"] == "Beta Movie"
    assert row["started"] == 2000
    assert row["duration"] == 600  # stopped(2600) - started(2000) - paused(0)
    assert row["transcode_decision"] == "transcode"


# ---------------------------------------------------------------------------
# media_type_live filter: session_history_metadata.live folded into a
# synthetic "live" media type via a CASE expression, so Live TV recordings
# can be filtered like any other media_type even though there is no real
# media_type value for it.
#
# Regression history:
#   b9d4f57a - the live filter combined with another custom_where filter
#              dropped the other filter.
#   87389320 - the CASE literal was double-quoted, so SQLite read it as a
#              column reference instead of the string 'live'.
#   9432fee1 - media_type=all must pass through unfiltered.
# ---------------------------------------------------------------------------

def test_media_type_live_filter_returns_only_live_rows(app_db):
    seed_history(app_db)

    result = call_history(grouping=False, custom_where=[["media_type_live IN", ["live"]]])

    assert result["recordsFiltered"] == 1
    assert {row["row_id"] for row in result["data"]} == {6}


def test_media_type_live_filter_excludes_live_rows_from_underlying_type(app_db):
    seed_history(app_db)

    # Row 6 is a live recording of a "movie"-typed item, same title as row 3
    # (Beta Movie). Filtering on the real media_type must not pull it in
    # just because session_history.media_type still says "movie".
    result = call_history(grouping=False, custom_where=[["media_type_live IN", ["movie"]]])

    assert result["recordsFiltered"] == 1
    assert {row["row_id"] for row in result["data"]} == {3}


def test_media_type_live_filter_combined_with_user_filter(app_db):
    seed_history(app_db)

    # b9d4f57a shape: a user filter and the live filter together, both must
    # hold. Row 6 (the live row) belongs to alice (user_id 1), not bob.
    alice_live = call_history(
        grouping=False,
        custom_where=[["session_history.user_id IN", ["1"]], ["media_type_live IN", ["live"]]],
    )
    assert {row["row_id"] for row in alice_live["data"]} == {6}

    bob_live = call_history(
        grouping=False,
        custom_where=[["session_history.user_id IN", ["2"]], ["media_type_live IN", ["live"]]],
    )
    assert bob_live["data"] == []


def test_media_type_live_row_carries_live_flag_and_underlying_media_type(app_db):
    seed_history(app_db)

    result = call_history(grouping=False, custom_where=[["media_type_live IN", ["live"]]])

    row = result["data"][0]
    assert row["row_id"] == 6
    assert row["live"] == 1
    # media_type_live is filter-only; the returned media_type stays the real type.
    assert row["media_type"] == "movie"
