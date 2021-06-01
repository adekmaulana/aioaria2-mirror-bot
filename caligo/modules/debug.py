from datetime import datetime
from typing import ClassVar, Optional

import aiohttp
from pyrogram.errors import UsernameInvalid, PeerIdInvalid

from .. import command, module, util


class DebugModule(module.Module):
    name: ClassVar[str] = "Debug"

    @command.desc("Pong")
    async def cmd_ping(self, ctx: command.Context):
        start = datetime.now()
        await ctx.respond("Calculating response time...")
        end = datetime.now()
        latency = (end - start).microseconds / 1000

        return f"Request response time: **{latency} ms**"

    @command.desc("Send text")
    @command.usage("[text to send]")
    async def cmd_echo(self, ctx: command.Context) -> Optional[str]:
        return ctx.input

    @command.desc("Dump all the data of a message")
    @command.alias("msginfo", "minfo")
    async def cmd_mdump(self, ctx: command.Context) -> str:
        if not ctx.msg.reply_to_message:
            return "__Reply to a message to get its data.__"

        reply_msg = ctx.msg.reply_to_message
        data = util.tg.pretty_print_entity(reply_msg)

        return f"```{data}```"

    @command.desc("Get all available information about the given entity")
    @command.usage(
        '[entity ID/username/... or "chat" for the current chat?, or reply]',
        optional=True,
    )
    @command.alias("einfo")
    async def cmd_entity(self, ctx: command.Context) -> str:
        entity_ref = ctx.input

        if ctx.input == "chat":
            entity = ctx.msg.chat
        elif ctx.input:
            if ctx.input.isdigit():
                try:
                    entity_ref = int(ctx.input)
                except ValueError:
                    return f"Unable to parse `{entity_ref}` as ID!"
            else:
                entity_ref = ctx.input

            try:
                entity = await self.bot.client.get_chat(entity_ref)
            except (UsernameInvalid, PeerIdInvalid):
                return f"Error getting entity `{entity_ref}`"
        elif ctx.msg.reply_to_message:
            entity = ctx.msg.reply_to_message
        else:
            return "__No entity given via argument or reply.__"

        pretty_printed = util.tg.pretty_print_entity(entity)
        return f"```{pretty_printed}```"

    @command.desc("Get all contextually relevant IDs")
    @command.alias("user")
    async def cmd_id(self, ctx: command.Context) -> None:
        lines = []

        if ctx.msg.chat.id:
            lines.append(f"Chat ID: `{ctx.msg.chat.id}`")

        lines.append(f"My user ID: `{self.bot.uid}`")

        if ctx.msg.reply_to_message:
            reply_msg = ctx.msg.reply_to_message
            sender = reply_msg.from_user
            lines.append(f"Message ID: `{reply_msg.message_id}`")

            if sender:
                lines.append(f"Message author ID: `{sender.id}`")

            if reply_msg.forward_from:
                lines.append(
                    f"Forwarded message author ID: `{reply_msg.forward_from.id}`"
                )

            f_chat = None
            if reply_msg.forward_from_chat:
                f_chat = reply_msg.forward_from_chat

                lines.append(
                    f"Forwarded message {f_chat.type} ID: `{f_chat.id}`"
                )

            f_msg_id = None
            if reply_msg.forward_from_message_id:
                f_msg_id = reply_msg.forward_from_message_id
                lines.append(f"Forwarded message original ID: `{f_msg_id}`")

            if f_chat is not None and f_msg_id is not None:
                uname = f_chat.username
                if uname is not None:
                    lines.append(
                        "[Link to forwarded message]"
                        f"(https://t.me/{uname}/{f_msg_id})"
                    )
                else:
                    lines.append(
                        "[Link to forwarded message]"
                        f"(https://t.me/{f_chat.id}/{f_msg_id})"
                    )

        text = util.tg.pretty_print_entity(
            lines).replace("'", "").replace("list", "**List**")
        await ctx.respond(text, disable_web_page_preview=True)

    @command.desc("Paste message text to Dogbin")
    @command.alias("deldog", "dogbin")
    @command.usage(
        "[text to paste?, or upload/reply to message or file]", optional=True
    )
    async def cmd_dog(self, ctx: command.Context) -> str:
        input_text = ctx.input

        status, text = await util.tg.get_text_input(ctx, input_text)
        if not status:
            if isinstance(text, str):
                return text

            return "__Unknown error.__"

        await ctx.respond("Uploading text to [Dogbin](https://del.dog/)...")

        async with self.bot.http.post("https://del.dog/documents", data=text) as resp:
            try:
                resp_data = await resp.json()
            except aiohttp.ContentTypeError:
                return "__Dogbin is currently experiencing issues. Try again later.__"

            return f'https://del.dog/{resp_data["key"]}'
