from app.persona.whatsapp import parse_whatsapp_export

ANDROID_EXPORT = """\
12/03/24, 9:15 pm - Messages and calls are end-to-end encrypted.
12/03/24, 9:15 pm - Riya: hey! are we still on for tomorrow
12/03/24, 9:16 pm - Owner: yes definitely
can't wait
12/03/24, 9:17 pm - Riya: haha same
12/03/24, 9:18 pm - Owner: <Media omitted>
12/03/24, 9:19 pm - Owner created group "Trip"
12/03/24, 9:20 pm - Owner: see you then
"""

IOS_EXPORT = """\
[12/03/24, 9:15:02 PM] Riya: hey! are we still on for tomorrow
[12/03/24, 9:16:10 PM] Owner: yes definitely
can't wait
[12/03/24, 9:17:00 PM] Riya: haha same
[12/03/24, 9:18:45 PM] Owner: image omitted
[12/03/24, 9:20:00 PM] Owner: see you then
"""


def test_android_format_keeps_only_owner_messages():
    messages = parse_whatsapp_export(ANDROID_EXPORT, "Owner")
    assert messages == ["yes definitely\ncan't wait", "see you then"]


def test_ios_format_keeps_only_owner_messages():
    messages = parse_whatsapp_export(IOS_EXPORT, "Owner")
    assert messages == ["yes definitely\ncan't wait", "see you then"]


def test_other_peoples_words_are_never_returned():
    messages = parse_whatsapp_export(ANDROID_EXPORT, "Owner")
    assert not any("hey!" in m or "haha" in m for m in messages)


def test_media_omitted_lines_are_dropped():
    messages = parse_whatsapp_export(ANDROID_EXPORT, "Owner")
    assert not any("media omitted" in m.lower() or "image omitted" in m.lower() for m in messages)


def test_system_lines_are_dropped_and_dont_leak_into_messages():
    messages = parse_whatsapp_export(ANDROID_EXPORT, "Owner")
    assert not any("encrypted" in m or "created group" in m for m in messages)


def test_owner_name_match_is_case_insensitive():
    messages = parse_whatsapp_export(ANDROID_EXPORT, "owner")
    assert "see you then" in messages


def test_multiline_message_is_joined_with_newline():
    messages = parse_whatsapp_export(ANDROID_EXPORT, "Owner")
    assert "yes definitely\ncan't wait" in messages


def test_empty_export_returns_no_messages():
    assert parse_whatsapp_export("", "Owner") == []


def test_export_with_only_other_person_returns_no_messages():
    text = "12/03/24, 9:15 pm - Riya: hi\n12/03/24, 9:16 pm - Riya: you there?\n"
    assert parse_whatsapp_export(text, "Owner") == []
