import pytest

import plexpy.config


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
