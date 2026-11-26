"""delete_hosted_images with a rating_key deletes only that item's images.

With Cloudinary and delete_all, a rating_key deleted every image but kept the other items' rows.
"""

import json

import pytest

from plexpy import helpers
from plexpy import webserve  # noqa: F401  (registers the handlers on API2)
from plexpy.api2 import API2


@pytest.fixture
def api(app_db, app_config, monkeypatch):
    app_config.API_ENABLED = 1
    app_config.API_KEY = "a" * 32
    for rating_key in (10, 20):
        img_hash = "h%d" % rating_key
        app_db.action("INSERT INTO image_hash_lookup (img_hash, img, rating_key) VALUES (?, ?, ?)",
                      [img_hash, "/library/metadata/%d/thumb" % rating_key, rating_key])
        app_db.action("INSERT INTO cloudinary_lookup (img_hash, cloudinary_title) VALUES (?, 't')", [img_hash])
    deleted = []
    monkeypatch.setattr(helpers, "delete_from_cloudinary", lambda **kwargs: deleted.append(kwargs))

    def run(**kwargs):
        out = API2()._api_run(apikey=app_config.API_KEY, cmd="delete_hosted_images", service="cloudinary", **kwargs)
        rows = [row["img_hash"] for row in app_db.select("SELECT img_hash FROM cloudinary_lookup ORDER BY img_hash")]
        return json.loads(out)["response"]["result"], deleted, rows
    return run


@pytest.mark.parametrize("delete_all", ["true", "false"])
def test_rating_key_deletes_one_item(api, delete_all):
    assert api(rating_key="10", delete_all=delete_all) == ("success", [{"rating_key": 10}], ["h20"])


def test_delete_all_deletes_every_image(api):
    assert api(delete_all="true") == ("success", [{"delete_all": True}], [])
