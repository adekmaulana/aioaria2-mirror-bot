import asyncio
import urllib.parse
from datetime import datetime, timedelta
from itertools import zip_longest
from pathlib import Path
from typing import Any, ClassVar, Optional, Set, Tuple, Union

from .. import command, module, util


class Misc(module.Module):
    name: ClassVar[str] = "Misc"

    task: Set[Tuple[int, asyncio.Task]]

    async def on_load(self) -> None:
        if not self.bot.getConfig["mirror_enabled"]:
            self.bot.unregister_command(self.bot.commands["upload"])
            self.bot.unregister_command(self.bot.commands["abort"])
            return

        self.task = set()

    @command.desc("Generate a LMGTFY link (Let Me Google That For You)")
    @command.usage("[search query]")
    async def cmd_lmgtfy(self, ctx: command.Context) -> str:
        query = ctx.input
        params = urllib.parse.urlencode({"q": query})

        return f"https://lmgtfy.com/?{params}"

    @command.desc("Upload file into telegram server")
    @command.usage("[file path]")
    async def cmd_upload(self, ctx: command.Context) -> Optional[str]:
        if not ctx.input:
            return "__Pass the file path.__"

        before = util.time.sec()
        file_path = Path(ctx.input)
        last_update_time = None

        if file_path.is_dir():
            await ctx.respond("__The path you input is a directory.__")
            return
        if not file_path.is_file():
            await ctx.respond("__The file you input doesn't exists.__")
            return

        human = util.misc.human_readable_bytes
        time = util.time.format_duration_td

        def prog_func(current: int, total: int) -> None:
            nonlocal last_update_time

            percent = current / total
            after = util.time.sec() - before
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
            progress = (
                f"`{file_path.name}`\n"
                f"Status: **Uploading**\n"
                f"Progress: [{bullets + space}] {round(percent * 100)}%\n"
                f"__{human(current)} of {human(total)} @ "
                f"{human(speed, postfix='/s')}\neta - {time(eta)}__\n\n")
            # Only edit message once every 5 seconds to avoid ratelimits
            if last_update_time is None or (
                    now - last_update_time).total_seconds() >= 5:
                self.bot.loop.create_task(ctx.respond(progress))

                last_update_time = now

        task = self.bot.loop.create_task(
            self.bot.client.send_document(ctx.msg.chat.id,
                                          str(file_path),
                                          force_document=True,
                                          progress=prog_func))
        self.task.add((ctx.msg.message_id, task))
        try:
            await task
        except asyncio.CancelledError:
            return "__Transmission aborted.__"
        else:
            self.task.remove((ctx.msg.message_id, task))

        await ctx.msg.delete()
        return

    @command.desc("Abort transmission of upload or download")
    @command.usage("[file gid]", reply=True)
    async def cmd_abort(self, ctx) -> Optional[str]:
        if not ctx.input and not ctx.msg.reply_to_message:
            return "__Pass GID or reply to message of task to abort transmission.__"
        if ctx.msg.reply_to_message and ctx.input:
            return "__Can't pass gid while replying to message.__"
        aria2: Any = self.bot.modules.get("Aria2")
        drive: Any = self.bot.modules.get("GoogleDrive")

        if ctx.msg.reply_to_message:
            reply_msg = ctx.msg.reply_to_message
            msg_id = reply_msg.message_id

            i: Union[Tuple[int, asyncio.Task], None]
            j: Union[Tuple[int, asyncio.Task], None]
            for i, j in zip_longest(drive.task.copy(), self.task.copy()):
                if i is not None:
                    m_id = i[0]
                    task = i[1]
                    if m_id == msg_id:
                        task.cancel()
                        drive.task.remove((m_id, task))
                        break

                if j is not None:
                    m_id = j[0]
                    task = j[1]
                    if m_id == msg_id:
                        task.cancel()
                        self.task.remove((m_id, task))
                        break
            else:
                return "__The message you choose is not in task.__"

            await ctx.msg.delete()

            return

        gid = ctx.input
        if aria2 is None and gid:
            return "__Aria2 is not loaded.__"

        ret = await aria2.cancelMirror(gid)
        if ret is None:
            await ctx.msg.delete()

        return ret
