import asyncio
import io
from datetime import datetime
from typing import Any, ClassVar, Optional, Tuple, Union

import pyrogram
from aiofile import AIOFile
from pyrogram.errors import StickersetInvalid
from pyrogram.raw.functions.messages import GetStickerSet
from pyrogram.raw.types import InputStickerSetShortName

from .. import command, module, util

PNG_MAGIC = b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a"

# Sticker bot info and return error strings
STICKER_BOT_USERNAME = "Stickers"


class LengthMismatchError(Exception):
    pass


class StickerModule(module.Module):
    name: ClassVar[str] = "Sticker"

    db: Any
    kang_db: Optional[Any]

    async def on_load(self):
        self.db = self.bot.get_db("stickers")

        check = await self.db.find_one({"_id": self.name})
        self.kang_db = check.get("pack_name") if check is not None else None

    async def add_sticker(
        self,
        sticker_data: Union[pyrogram.types.Sticker, bytes],
        pack_name: str,
        emoji: str = "❓",
        *,
        target: str = STICKER_BOT_USERNAME,
    ) -> Tuple[bool, str]:
        commands = [
            ("text", "/cancel", None),
            ("text", "/addsticker", "Choose the sticker pack"),
            ("text", pack_name, "send me the sticker"),
            ("file", sticker_data, "send me an emoji"),
            ("text", emoji, "added your sticker"),
            ("text", "/done", "done"),
        ]

        success = False
        before = datetime.now()

        async with self.bot.conversation(target) as conv:

            async def reply_and_ack():
                # Wait for a response
                resp = await conv.get_response()
                # Ack the response to suppress its notification
                await conv.mark_read()

                return resp

            try:
                for cmd_type, data, expected_resp in commands:
                    if cmd_type == "text":
                        await conv.send_message(data)
                    elif cmd_type == "file":
                        await conv.send_file(data, force_document=True)
                    else:
                        raise TypeError(f"Unknown command type '{cmd_type}'")

                    # Wait for both the rate-limit and the bot's response
                    try:
                        resp_task = self.bot.loop.create_task(reply_and_ack())
                        done, _ = await asyncio.wait((resp_task,))
                        # Raise exceptions encountered in coroutines
                        for fut in done:
                            fut.result()

                        response = resp_task.result()
                        if expected_resp and expected_resp not in response.text:
                            return False, f'Sticker creation failed: "{response.text}"'
                    except asyncio.TimeoutError:
                        after = datetime.now()
                        delta_seconds = int((after - before).total_seconds())

                        return (
                            False,
                            f"Sticker creation timed out after {delta_seconds} seconds.",
                        )

                success = True
            finally:
                # Cancel the operation if we return early
                if not success:
                    await conv.send_message("/cancel")

        return True, f"https://t.me/addstickers/{pack_name}"

    async def create_pack(
        self,
        sticker_data: Union[pyrogram.types.Sticker, bytes],
        pack_name: str,
        emoji: str = "❓",
        *,
        target: str = STICKER_BOT_USERNAME,
    ) -> Tuple[bool, str]:
        commands = [
            ("text", "/cancel", None),
            ("text", "/newpack", "Yay!"),
            ("text", pack_name, "send me the sticker"),
            ("file", sticker_data, "send me an emoji"),
            ("text", emoji, "/publish"),
            ("text", "/publish", "/skip"),
            ("text", "/skip", "Animals"),
            ("text", pack_name, "Kaboom!")
        ]

        success = False
        before = datetime.now()

        async with self.bot.conversation(target, max_messages=9) as conv:

            async def reply_and_ack():
                # Wait for a response
                resp = await conv.get_response()
                # Ack the response to suppress its notification
                await conv.mark_read()

                return resp

            try:
                for cmd_type, data, expected_resp in commands:
                    if cmd_type == "text":
                        await conv.send_message(data)
                    elif cmd_type == "file":
                        await conv.send_file(data, force_document=True)
                    else:
                        raise TypeError(f"Unknown command type '{cmd_type}'")

                    # Wait for both the rate-limit and the bot's response
                    try:
                        resp_task = self.bot.loop.create_task(reply_and_ack())
                        done, _ = await asyncio.wait((resp_task,))
                        # Raise exceptions encountered in coroutines
                        for fut in done:
                            fut.result()

                        response = resp_task.result()
                        if expected_resp and expected_resp not in response.text:
                            return False, f'Sticker creation failed: "{response.text}"'
                    except asyncio.TimeoutError:
                        after = datetime.now()
                        delta_seconds = int((after - before).total_seconds())

                        return (
                            False,
                            f"Sticker creation timed out after {delta_seconds} seconds.",
                        )

                success = True
            finally:
                # Cancel the operation if we return early
                if not success:
                    await conv.send_message("/cancel")

        return True, f"https://t.me/addstickers/{pack_name}"

    @command.desc("Copy a sticker into another pack")
    @command.alias("stickercopy", "kang")
    @command.usage("[sticker pack VOL number? if not set] [emoji?]", optional=True)
    async def cmd_copysticker(self, ctx: command.Context) -> str:
        if not ctx.msg.reply_to_message:
            return "__Reply to a sticker to copy it.__"

        pack_VOL = None
        emoji = ""

        for arg in ctx.args:
            if util.text.has_emoji(arg):
                # Allow for emoji split across several arguments, since some clients
                # automatically insert spaces
                emoji += arg
            else:
                pack_VOL = arg

        if not pack_VOL:
            pack_name = self.kang_db.get("1") if self.kang_db is not None else None
        else:
            pack_name = self.kang_db.get(pack_VOL) if self.kang_db is not None else None

        if not pack_name:
            ret = await self.cmd_createpack(ctx)
            await self.on_load()

            return ret

        try:
            await self.bot.client.send(GetStickerSet(
                stickerset=InputStickerSetShortName(short_name=pack_name)
                )
            )
        except StickersetInvalid:
            ret = await self.cmd_createpack(ctx)

            return ret

        reply_msg = ctx.msg.reply_to_message

        await ctx.respond("Copying sticker...")

        sticker_file = await reply_msg.download()
        async with AIOFile(sticker_file, "rb") as sticker:
            sticker_bytes = await sticker.read()
        sticker_buf = io.BytesIO(sticker_bytes)
        await util.image.img_to_png(sticker_buf)

        sticker_buf.seek(0)
        sticker_buf.name = "sticker.png"
        status, result = await self.add_sticker(
            sticker_buf, pack_name, emoji=emoji or reply_msg.sticker.emoji
        )
        if status:
            await self.bot.log_stat("stickers_created")
            return f"[Sticker copied]({result})."

        return result

    @command.desc("Create another sticker pack")
    @command.usage("[sticker pack VOL number?]", optional=True)
    async def cmd_createpack(self, ctx: command.Context) -> str:
        if not ctx.msg.reply_to_message:
            return "__Reply to a message sticker to create a new pack.__"

        reply_msg = ctx.msg.reply_to_message
        if not reply_msg.sticker:
            return "__That message is not a sticker.__"

        num = ctx.input if ctx.input else "1"
        check = self.kang_db.get(num) if self.kang_db is not None else None
        if check:
            try:
                await self.bot.client.send(GetStickerSet(
                    stickerset=InputStickerSetShortName(short_name=check)
                    )
                )
            except StickersetInvalid:
                pass
            else:
                return "__Pack with that name already exists, use 'kang' instead.__"

        emoji = ctx.args[1] if len(ctx.args) > 1 else "❓"
        pack_name = self.bot.user.username + f"_kangPack_VOL{num}"
        await self.db.update_one(
            {"_id": self.name},
            {
                "$set": {
                    f"pack_name.{num}": pack_name
                }
            },
            upsert=True
        )

        try:
            await self.bot.client.send(GetStickerSet(
                stickerset=InputStickerSetShortName(short_name=pack_name)
                )
            )
        except StickersetInvalid:
            pass
        else:
            await self.on_load()
            return "__Pack with that name already exists, use 'kang' instead.__"

        await ctx.respond("Creating new pack...")

        sticker_file = await reply_msg.download()
        async with AIOFile(sticker_file, "rb") as sticker:
            sticker_bytes = await sticker.read()
        sticker_buf = io.BytesIO(sticker_bytes)
        await util.image.img_to_png(sticker_buf)

        sticker_buf.seek(0)
        sticker_buf.name = "sticker.png"
        status, result = await self.create_pack(
            sticker_buf, pack_name, emoji=reply_msg.sticker.emoji or emoji
        )
        if status:
            await self.bot.log_stat("stickers_created")

            # Update the database
            await self.on_load()
            return f"[Pack Created]({result})."

        return result

    @command.desc("Glitch an image")
    @command.usage("[block offset strength?]", optional=True)
    async def cmd_glitch(self, ctx: command.Context) -> Optional[str]:
        if not ctx.msg.reply_to_message:
            return "__Reply to an image or sticker to glitch it.__"

        offset = 8
        if ctx.input:
            try:
                offset = int(ctx.input)
            except ValueError:
                return "__Invalid distorted block offset strength.__"

        reply_msg = ctx.msg.reply_to_message
        if not (reply_msg.photo or reply_msg.sticker):
            return "__That message isn't an image nor sticker.__"

        await ctx.respond("Glitching image...")

        orig_file = await reply_msg.download()
        async with AIOFile(orig_file, "rb") as image:
            orig_bytes = await image.read()

        # Convert to PNG if necessary
        if orig_bytes.startswith(PNG_MAGIC):
            png_bytes = orig_bytes
        else:
            png_buf = io.BytesIO(orig_bytes)
            await util.image.img_to_png(png_buf)
            png_bytes = png_buf.getvalue()

        # Invoke external 'corrupter' program to glitch the image
        # Source code: https://github.com/r00tman/corrupter
        try:
            stdout, stderr, ret = await util.system.run_command(
                "corrupter",
                "-boffset",
                str(offset),
                "-",
                stderr=asyncio.subprocess.PIPE,
                in_data=png_bytes,
                text=util.system.StderrOnly,
                timeout=15,
            )
        except asyncio.TimeoutError:
            return "🕑 `corrupter` failed to finish within 15 seconds."
        except FileNotFoundError:
            return "❌ The `corrupter` [program](https://github.com/r00tman/corrupter) must be installed on the host system."

        if ret != 0:
            return (
                f"⚠️ `corrupter` failed with return code {ret}. Error: ```{stderr}```"
            )

        with io.BytesIO(stdout) as file:
            if reply_msg.sticker:
                file.name = "glitch.webp"
                await ctx.msg.reply_sticker(file)
                await ctx.msg.delete()
                return None

            file.name = "glitch.png"
            await ctx.respond(document=file, mode="repost")

        return None
