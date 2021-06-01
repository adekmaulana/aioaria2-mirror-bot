import asyncio
import io
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, Tuple, Union

import aiofile
import bprint
import pyrogram

from .. import command
from .misc import human_readable_bytes as human
from .time import format_duration_td as time
from .time import sec

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


async def download_file(ctx: command.Context,
                        msg: pyrogram.types.Message,
                        text: Optional[bool] = False) -> Optional[Union[Path, str, bytes]]:
    """Downloads the file embedded in the given message."""
    download_path = ctx.bot.getConfig["download_path"]

    if text is True:
        path = await ctx.bot.client.download_media(msg)
        if path:
            path = Path(path)
            async with aiofile.async_open(path, "r") as file:
                content = await file.read()

            path.unlink()
            return content

    before = sec()
    last_update_time = None
    if msg.document:
        file_name = msg.document.file_name
    elif msg.audio:
        file_name = msg.audio.file_name
    elif msg.video:
        file_name = msg.video.file_name
    elif msg.sticker:
        file_name = msg.sticker.file_name
    elif msg.photo:
        date = datetime.fromtimestamp(msg.photo.date)
        file_name = f"photo_{date.strftime('%Y-%m-%d_%H-%M-%S')}.jpg"
    elif msg.voice:
        date = datetime.fromtimestamp(msg.voice.date)
        file_name = f"audio_{date.strftime('%Y-%m-%d_%H-%M-%S')}.ogg"
    else:
        file_name = "Unknown"

    loop = asyncio.get_event_loop()

    def prog_func(current: int, total: int) -> None:
        nonlocal last_update_time

        if not ctx:
            return

        percent = current / total
        after = sec() - before
        now = datetime.now()

        try:
            speed = round(current / after, 2)
            eta = timedelta(seconds=int(round((total - current) / speed)))
        except ZeroDivisionError:
            speed = 0
            eta = timedelta(seconds=0)
        bullets = "●" * int(round(percent * 10)) + "○"
        if len(bullets) > 10:
            bullets = bullets.replace("○", "")

        space = '    ' * (10 - len(bullets))
        progress = (f"`{file_name}`\n"
                    f"Status: **Downloading**\n"
                    f"Progress: [{bullets + space}] {round(percent * 100)}%\n"
                    f"__{human(current)} of {human(total)} @ "
                    f"{human(speed, postfix='/s')}\neta - {time(eta)}__\n\n")
        # Only edit message once every 5 seconds to avoid ratelimits
        if last_update_time is None or (now -
                                        last_update_time).total_seconds() >= 5:
            loop.create_task(ctx.respond(progress))

            last_update_time = now

    path = await ctx.bot.client.download_media(msg, file_name=str(download_path) + 
                                               "/" + file_name, progress=prog_func)
    return Path(path) if path is not None else path


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


async def get_text_input(
        ctx: command.Context,
        input_arg: Optional[str]) -> Tuple[bool, Optional[Union[str, Path, bytes]]]:
    """Returns input text from various sources in the given command context."""

    if ctx.msg.document:
        text = await download_file(ctx, ctx.msg, text=True)
    elif input_arg:
        text = filter_code_block(input_arg)
    elif ctx.msg.reply_to_message:
        reply_msg = ctx.msg.reply_to_message

        if reply_msg.document:
            text = await download_file(ctx, reply_msg, text=True)
        elif reply_msg.text:
            text = filter_code_block(reply_msg.text)
        else:
            return (
                False,
                "__Reply to a message with text or a text file, or provide text in command.__",
            )
    else:
        return False, "__Reply to a message or provide text in command.__"

    return True, text
