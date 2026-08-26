import pytest

from plexpy.notification_handler import build_notify_text


# Notification text can wrap a section in a media type tag so it only shows
# for that media type. build_notify_text keeps the tagged section for the
# playing media type, unwrapped, and drops every other tagged section.
ALL_SECTIONS = (
    "<movie>M</movie>"
    "<show>SH</show>"
    "<season>SE</season>"
    "<episode>E</episode>"
    "<artist>AR</artist>"
    "<album>AL</album>"
    "<track>T</track>"
    " always"
)


@pytest.mark.parametrize("media_type, expected", [
    ("movie", "M always"),
    ("show", "SH always"),
    ("season", "SE always"),
    ("episode", "E always"),
    ("artist", "AR always"),
    ("album", "AL always"),
    ("track", "T always"),
    # A media type with no tag of its own, and a play with no media type at
    # all, both drop every tagged section.
    ("photo", "always"),
    (None, "always"),
])
def test_media_type_keeps_only_its_own_section(app_config, media_type, expected):
    # agent_id 10 is Email, the branch of strip_tag that leaves HTML alone,
    # so only the media type tags are stripped here.
    subject, body = build_notify_text(subject=ALL_SECTIONS, body=ALL_SECTIONS,
                                      notify_action="on_play",
                                      parameters={"media_type": media_type},
                                      agent_id=10, test=True)
    assert (subject, body) == (expected, expected)


def test_media_type_tags_are_case_insensitive_and_span_newlines(app_config):
    subject, body = build_notify_text(subject="<MOVIE>M</MOVIE><Show>\nSH\n</Show>",
                                      body="<episode>E</episode>",
                                      notify_action="on_play",
                                      parameters={"media_type": "movie"},
                                      agent_id=10, test=True)
    assert (subject, body) == ("M", "")


def test_unmatched_media_tag_is_stripped(app_config):
    # A tag with no closing partner is not a section, so nothing is dropped,
    # but strip_tag still removes the stray tag itself.
    subject, body = build_notify_text(subject="before <episode> after", body="",
                                      notify_action="on_play",
                                      parameters={"media_type": "movie"},
                                      agent_id=None, test=True)
    assert subject == "before  after"
