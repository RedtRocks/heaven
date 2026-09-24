"""WhatsApp export -> Style Samples. Keeps only the Owner's own messages."""

import re

_MEDIA_MARKERS = (
    "<media omitted>",
    "image omitted",
    "video omitted",
    "audio omitted",
    "sticker omitted",
    "gif omitted",
    "document omitted",
)

# Android: "12/03/24, 9:15 pm - Name: message"
_ANDROID_MESSAGE_RE = re.compile(
    r"^\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}\s*[ap]\.?m\.?\s*-\s*(?P<sender>[^:]+):\s*(?P<msg>.*)$",
    re.IGNORECASE,
)
_ANDROID_SYSTEM_RE = re.compile(
    r"^\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}\s*[ap]\.?m\.?\s*-\s*.*$",
    re.IGNORECASE,
)

# iOS: "[12/03/24, 9:15:02 PM] Name: message"
_IOS_MESSAGE_RE = re.compile(
    r"^\[\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}:\d{2}\s*[AP]M\]\s*(?P<sender>[^:]+):\s*(?P<msg>.*)$",
    re.IGNORECASE,
)
_IOS_SYSTEM_RE = re.compile(
    r"^\[\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}:\d{2}\s*[AP]M\]\s*.*$",
    re.IGNORECASE,
)


def _is_media_line(msg: str) -> bool:
    stripped = msg.strip().lower()
    return any(marker in stripped for marker in _MEDIA_MARKERS)


def parse_whatsapp_export(text: str, owner_name: str) -> list[str]:
    """Extract the Owner's own messages from a WhatsApp chat export.

    Handles Android and iOS export formats, multi-line messages, media
    placeholders ("<Media omitted>") and system lines (e.g. "X added Y",
    "Messages are end-to-end encrypted"). Other people's messages are never
    returned or stored, per the Style Sample glossary rule.
    """
    messages: list[str] = []
    current: list[str] | None = None

    def flush() -> None:
        nonlocal current
        if current:
            joined = "\n".join(current).strip()
            if joined:
                messages.append(joined)
        current = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n").strip("﻿")
        if not line.strip():
            continue

        match = _ANDROID_MESSAGE_RE.match(line) or _IOS_MESSAGE_RE.match(line)
        if match:
            flush()
            sender = match.group("sender").strip()
            msg = match.group("msg").strip()
            if sender.casefold() == owner_name.strip().casefold() and msg and not _is_media_line(msg):
                current = [msg]
            continue

        if _ANDROID_SYSTEM_RE.match(line) or _IOS_SYSTEM_RE.match(line):
            # A timestamped line that isn't "sender: message" -> system notice.
            flush()
            continue

        # Continuation line of a multi-line message (no timestamp prefix).
        if current is not None:
            current.append(line.strip())

    flush()
    return messages
