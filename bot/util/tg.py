import io
import uuid
from typing import Any

import bprint
import pyrogram

MESSAGE_CHAR_LIMIT = 4096
TRUNCATION_SUFFIX = "... (truncated)"


def mention_user(user: pyrogram.types.User) -> str:
    """Returns a string that mentions the given user, regardless of whether they have a username."""

    if user.username:
        # Use username mention if possible
        name = f"@{user.username}"
    else:
        # Use the first and last name otherwise
        if user.first_name and user.last_name:
            name = user.first_name + " " + user.last_name
        elif user.first_name and not user.last_name:
            name = user.first_name
        else:
            # Deleted accounts have no name; behave like the official clients
            name = "Deleted Account"

    return f"[{name}](tg://user?id={user.id})"


def filter_code_block(inp: str) -> str:
    """Returns the content inside the given Markdown code block or inline code."""

    if inp.startswith("```") and inp.endswith("```"):
        inp = inp[3:][:-3]
    elif inp.startswith("`") and inp.endswith("`"):
        inp = inp[1:][:-1]

    return inp


def _bprint_skip_predicate(name: str, value: Any) -> bool:
    return (name.startswith("_") or value is None or callable(value))


def pretty_print_entity(entity) -> str:
    """Pretty-prints the given Telegram entity with recursive details."""

    return bprint.bprint(entity,
                         stream=str,
                         skip_predicate=_bprint_skip_predicate)


def truncate(text: str) -> str:
    """Truncates the given text to fit in one Telegram message."""
    suffix = TRUNCATION_SUFFIX
    if text.endswith("```"):
        suffix += "```"

    if len(text) > MESSAGE_CHAR_LIMIT:
        return text[:MESSAGE_CHAR_LIMIT - len(suffix)] + suffix

    return text


async def send_as_document(content: str,
                           msg: pyrogram.types.Message,
                           caption: str) -> pyrogram.types.Message:
    with io.BytesIO(str.encode(content)) as o:
        o.name = str(uuid.uuid4()).split("-")[0].upper() + ".TXT"
        return await msg.reply_document(
            document=o,
            caption="❯ ```" + caption + "```",
        )
