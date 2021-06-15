from datetime import datetime
from typing import ClassVar

import speedtest

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

    @command.desc("Test Internet speed")
    @command.alias("stest", "st")
    async def cmd_speedtest(self, ctx: command.Context) -> str:
        before = util.time.usec()

        st = await util.run_sync(speedtest.Speedtest)
        status = "Selecting server..."

        await ctx.respond(status)
        server = await util.run_sync(st.get_best_server)
        status += f" {server['sponsor']} ({server['name']})\n"
        status += f"Ping: {server['latency']:.2f} ms\n"

        status += "Performing download test..."
        await ctx.respond(status)
        dl_bits = await util.run_sync(st.download)
        dl_mbit = dl_bits / 1000 / 1000
        status += f" {dl_mbit:.2f} Mbps\n"

        status += "Performing upload test..."
        await ctx.respond(status)
        ul_bits = await util.run_sync(st.upload)
        ul_mbit = ul_bits / 1000 / 1000
        status += f" {ul_mbit:.2f} Mbps\n"

        delta = util.time.usec() - before
        status += f"\nTime elapsed: {util.time.format_duration_us(delta)}"

        return status
