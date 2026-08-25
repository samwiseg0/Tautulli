import pytest

from plexpy.notification_handler import str_format


def test_basic_substitution(app_config):
    assert str_format("{show_name} - {episode_name}", {"show_name": "Foo", "episode_name": "Bar"}) == "Foo - Bar"


def test_missing_key_is_literal(app_config):
    # A typo'd/unknown parameter name must not raise; it degrades to the literal {key}.
    assert str_format("{unknown_param}", {}) == "{unknown_param}"


@pytest.mark.parametrize("template, params, expected", [
    ("{video_codec!u}", {"video_codec": "hevc"}, "HEVC"),
    ("{content_rating!l}", {"content_rating": "TV-PG"}, "tv-pg"),
    ("{media_type!c}", {"media_type": "movie"}, "Movie"),
])
def test_conversion_modifiers(app_config, template, params, expected):
    assert str_format(template, params) == expected


@pytest.mark.parametrize("template, expected", [
    ("{actors:[0]}", "Actor0"),
    ("{actors:[:4]}", "Actor0, Actor1, Actor2, Actor3"),
    ("{actors:[2:]}", "Actor2, Actor3, Actor4"),
    ("{actors:[1:5]}", "Actor1, Actor2, Actor3, Actor4"),
])
def test_list_slicing(app_config, template, expected):
    actors = "Actor0, Actor1, Actor2, Actor3, Actor4"
    assert str_format(template, {"actors": actors}) == expected


@pytest.mark.parametrize("template, expected", [
    ("{rating}", "8.9"),
    ("{Rating: <rating}", "Rating: 8.9"),
    ("{rating>/10}", "8.9/10"),
    ("{Rating: <rating>/10}", "Rating: 8.9/10"),
])
def test_prefix_suffix(app_config, template, expected):
    assert str_format(template, {"rating": "8.9"}) == expected


@pytest.mark.parametrize("template, expected", [
    # When a notification parameter is available but empty, the field, its
    # prefix, and its suffix are all omitted from the output.
    ("{rating}", ""),
    ("Rating: {rating}/10", "Rating: /10"),
    ("{Rating: <rating>/10}", ""),
])
def test_prefix_suffix_with_unavailable_param(app_config, template, expected):
    assert str_format(template, {"rating": ""}) == expected
