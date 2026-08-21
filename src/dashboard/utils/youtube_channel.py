"""What an artist pastes vs what the collector needs: the YouTube channel id.

Type: Utility
Uses: nothing (pure) — the API call lives in the caller
Depends on: nothing
Persists in: nothing

The form asks for a `UC…` channel id. Nobody knows theirs. What an artist has to
hand is the address bar or the handle under their name: `@benken`,
`youtube.com/@benken`, `youtube.com/channel/UC…`, `youtube.com/c/Benken`. Pasting
any of those produced « Channel ID introuvable » — a dead end at the last step of
the setup, and Benken's actual failure (2026-06-19).

Two shapes, deliberately separated:

  * `parse_channel_input()` is pure and answers "what did they give me?" — an id
    that can be used as-is, or a handle/name that has to be resolved upstream.
  * the caller does the resolving, because it owns the API key and the HTTP
    budget, and because resolution must be REPORTED, never applied silently:
    a tenant's identity is not something this codebase infers on the artist's
    behalf (`.claude/rules/python.md`, ADR-006). We tell them the id we found and
    let them put it in.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# A channel id is `UC` + 22 chars of base64url. Anything else that starts with UC
# is a typo, and saying so beats a 404 from the API.
_CHANNEL_ID = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
_CHANNEL_ID_LOOSE = re.compile(r"^UC[A-Za-z0-9_-]+$")

_HANDLE = re.compile(r"^@[A-Za-z0-9._-]{3,30}$")

# Only the forms YouTube itself serves. A path we do not recognise is reported as
# such rather than guessed at — a wrong guess here silently collects someone
# else's catalogue, which is the class this repo spent two sessions removing.
_URL_PATTERNS = (
    (re.compile(r"youtube\.com/channel/(UC[A-Za-z0-9_-]+)"), "id"),
    (re.compile(r"youtube\.com/(@[A-Za-z0-9._-]+)"), "handle"),
    (re.compile(r"youtube\.com/c/([A-Za-z0-9._-]+)"), "name"),
    (re.compile(r"youtube\.com/user/([A-Za-z0-9._-]+)"), "user"),
)


@dataclass(frozen=True)
class ChannelInput:
    """What the artist gave, classified.

    `kind` is one of:
      `id`      — a usable `UC…`, in `value`
      `handle`  — `@name`, resolvable via the API's `forHandle`
      `user`    — a legacy username, resolvable via `forUsername`
      `name`    — a `/c/` vanity name; the API has no lookup for it, so this is
                  reported to the artist as "not resolvable, read it in Studio"
      `malformed` — starts like an id but is not one (wrong length)
      `unknown` — anything else
    """

    kind: str
    value: str

    @property
    def is_usable(self) -> bool:
        return self.kind == "id"

    @property
    def is_resolvable(self) -> bool:
        """Can an API lookup turn this into an id?"""
        return self.kind in ("handle", "user")


def parse_channel_input(raw: str | None) -> ChannelInput:
    """Classify whatever was pasted into the Channel ID field. Pure."""
    text = (raw or "").strip()
    if not text:
        return ChannelInput("unknown", "")

    # A full URL first: `youtube.com/channel/UC…` contains a valid id, and a
    # handle URL must not be mistaken for a vanity name.
    for pattern, kind in _URL_PATTERNS:
        m = pattern.search(text)
        if m:
            value = m.group(1)
            if kind == "id":
                return ChannelInput("id" if _CHANNEL_ID.match(value) else "malformed", value)
            return ChannelInput(kind, value)

    if _CHANNEL_ID.match(text):
        return ChannelInput("id", text)
    if _CHANNEL_ID_LOOSE.match(text):
        # Starts right, wrong length — almost always a truncated copy/paste.
        return ChannelInput("malformed", text)
    if _HANDLE.match(text):
        return ChannelInput("handle", text)
    return ChannelInput("unknown", text)


def lookup_params(parsed: ChannelInput) -> dict[str, str] | None:
    """The `channels.list` filter that resolves this input, or None.

    Kept next to the parser so the two cannot drift: adding a resolvable kind
    above without a filter here would silently stop resolving it.
    """
    if parsed.kind == "handle":
        return {"forHandle": parsed.value}
    if parsed.kind == "user":
        return {"forUsername": parsed.value}
    return None


def topic_channel_query(artist_name: str | None) -> str | None:
    """The search term that finds an artist's auto-generated « … - Topic » channel.

    A distributed artist usually has two channels: the one they post to, and the
    `- Topic` one YouTube generates for their music. The streams live on the
    second. The connection test already says so when a channel resolves with zero
    videos; this gives the caller something to search with.
    """
    name = (artist_name or "").strip()
    return f"{name} - Topic" if name else None
