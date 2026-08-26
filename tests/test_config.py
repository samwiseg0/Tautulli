import pytest

import plexpy.config
from plexpy import logger


# ---------------------------------------------------------------------------
# defaults from an empty/nonexistent ini
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name, expected, expected_type", [
    ("PMS_PORT", 32400, int),
    ("CACHE_SIZEMB", 32, int),
    ("DATE_FORMAT", "YYYY-MM-DD", str),
    ("PMS_IP", "127.0.0.1", str),
    ("HOME_SECTIONS", ["current_activity", "watch_stats", "library_stats", "recently_added"], list),
    ("GET_FILE_SIZES_HOLD", {"section_ids": [], "rating_keys": []}, dict),
])
def test_defaults_from_empty_ini(app_config, name, expected, expected_type):
    value = getattr(app_config, name)
    assert value == expected
    assert type(value) is expected_type


# ---------------------------------------------------------------------------
# round trip: set, write(), reread with a fresh Config on the same file
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name, value", [
    ("PMS_PORT", 12345),
    ("DATE_FORMAT", "MM/DD/YYYY"),
    ("HOME_SECTIONS", ["watch_stats", "recently_added"]),
])
def test_round_trip_setting(tmp_path, name, value):
    ini_path = str(tmp_path / "config.ini")
    config = plexpy.config.Config(ini_path)
    setattr(config, name, value)
    config.write()

    reloaded = plexpy.config.Config(ini_path)
    assert getattr(reloaded, name) == value
    assert type(getattr(reloaded, name)) is type(value)


# ---------------------------------------------------------------------------
# hand-edited ini values: configobj strips quotes from scalars, so a
# quoted int still arrives at Config as a plain string that gets cast
# ---------------------------------------------------------------------------

def test_quoted_int_in_ini_is_cast_to_int(tmp_path):
    ini_path = tmp_path / "config.ini"
    ini_path.write_text('[PMS]\npms_port = "12345"\n')

    config = plexpy.config.Config(str(ini_path))
    assert config.PMS_PORT == 12345
    assert type(config.PMS_PORT) is int


@pytest.mark.parametrize("raw, expected", [
    ("false", 0),
    ("no", 0),
    ("true", 1),
    ("1", 1),
])
def test_bool_int_setting_coerces_string_values(tmp_path, raw, expected):
    # VERIFY_SSL_CERT uses the custom bool_int caster, not plain int().
    ini_path = tmp_path / "config.ini"
    ini_path.write_text(f'[Advanced]\nverify_ssl_cert = {raw}\n')

    config = plexpy.config.Config(str(ini_path))
    assert config.VERIFY_SSL_CERT == expected
    assert type(config.VERIFY_SSL_CERT) is int


def test_unparseable_int_falls_back_to_default(tmp_path):
    # A comma in a hand-edited int value makes configobj parse it as a
    # list, which int() can't cast; _cast_setting falls back to the
    # type-default rather than raising.
    ini_path = tmp_path / "config.ini"
    ini_path.write_text("[PMS]\npms_port = 12345, 6\n")

    config = plexpy.config.Config(str(ini_path))
    assert config.PMS_PORT == 32400
    assert type(config.PMS_PORT) is int


# ---------------------------------------------------------------------------
# _upgrade(): the version-walk migration cascade runs on every non-import
# Config() construction, from whatever CONFIG_VERSION is on disk up to the
# latest. These lock in the terminal state after a full walk from 0, and a
# walk that starts partway through with real old-style values.
# ---------------------------------------------------------------------------

def test_upgrade_migrates_fresh_config_to_latest_version(tmp_path):
    ini_path = tmp_path / "config.ini"
    ini_path.write_text("")

    config = plexpy.config.Config(str(ini_path))

    assert config.CONFIG_VERSION == 22
    assert config.GIT_USER == "Tautulli"
    assert config.GIT_REPO == "Tautulli"
    assert config.HTTP_ROOT == ""
    assert config.HTTP_HASH_PASSWORD == 1
    assert config.ANON_REDIRECT == ""
    assert config.ANON_REDIRECT_DYNAMIC == 1
    assert config.PMS_UPDATE_CHANNEL == "plex"
    assert config.CHECK_GITHUB_INTERVAL == 6


def test_upgrade_migrates_old_style_values(tmp_path):
    # config_version 9: a 'plexpass' update channel is renamed to 'beta'.
    # config_version 15: a non-root, non-empty HTTP_ROOT forces a JWT secret
    # rotation. Starting below both versions exercises the walk through them.
    ini_path = tmp_path / "config.ini"
    ini_path.write_text(
        "[Advanced]\n"
        "config_version = 3\n"
        "\n"
        "[PMS]\n"
        "pms_update_channel = plexpass\n"
        "\n"
        "[General]\n"
        "http_root = /tautulli/\n"
    )

    config = plexpy.config.Config(str(ini_path))

    assert config.CONFIG_VERSION == 22
    assert config.PMS_UPDATE_CHANNEL == "beta"
    assert config.HTTP_ROOT == "/tautulli/"
    assert config.JWT_UPDATE_SECRET == 1


# ---------------------------------------------------------------------------
# _blacklist(): token/password-like values get redacted from the logs.
# logger._BLACKLIST_WORDS is a process-global set, so swap it out for a
# fresh one and let monkeypatch put the real one back after the test.
# ---------------------------------------------------------------------------

def test_blacklist_redacts_tokens_and_passwords(tmp_path, monkeypatch):
    monkeypatch.setattr(logger, "_BLACKLIST_WORDS", set())

    ini_path = tmp_path / "config.ini"
    ini_path.write_text(
        "[PMS]\npms_token = supersecrettoken123\n"
        "[General]\ndate_format = MM/DD/YYYY\n"
    )

    plexpy.config.Config(str(ini_path))

    assert "supersecrettoken123" in logger._BLACKLIST_WORDS
    assert "MM/DD/YYYY" not in logger._BLACKLIST_WORDS


# ---------------------------------------------------------------------------
# TAUTULLI_* environment overrides (documented Docker feature): an env var
# wins over both the ini default and a later in-process setattr.
# ---------------------------------------------------------------------------

def test_env_override_wins_over_ini_default(tmp_path, monkeypatch):
    monkeypatch.setenv("TAUTULLI_PMS_PORT", "9999")
    ini_path = tmp_path / "config.ini"

    config = plexpy.config.Config(str(ini_path))

    assert config.PMS_PORT == 9999
    assert type(config.PMS_PORT) is int


def test_env_override_wins_over_setattr(tmp_path, monkeypatch):
    monkeypatch.setenv("TAUTULLI_PMS_PORT", "9999")
    ini_path = tmp_path / "config.ini"
    config = plexpy.config.Config(str(ini_path))

    # set_setting() refuses to write when the env var is present, so the
    # ini stays untouched and the env value keeps winning on read.
    config.PMS_PORT = 12345

    assert config.PMS_PORT == 9999
