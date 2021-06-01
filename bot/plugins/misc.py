import asyncio
from datetime import datetime, timedelta
from itertools import zip_longest
from typing import Any, ClassVar, Optional, Set, Tuple, Union

from aiopath import AsyncPath

from .. import command, plugin, util


class Misc(plugin.Plugin):
    name: ClassVar[str] = "Misc"

    task: Set[Tuple[int, asyncio.Task]]

    async def on_load(self) -> None:
        self.task = set()

    @command.desc("Upload local file to Telegram server")
    @command.usage("[file path]")
    async def cmd_upload(self, ctx: command.Context) -> Optional[str]:
        if not ctx.input:
            return "__Pass the file path.__"

        before = util.time.sec()
        file_path = AsyncPath(ctx.input)
        last_update_time = None

        if await file_path.is_dir():
            await ctx.respond("__The path you input is a directory.__")
            return
        if not await file_path.is_file():
            await ctx.respond("__The file you input doesn't exists.__")
            return

        human = util.file.human_readable_bytes
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
                f"{human(speed, postfix='/s')}\neta - {time(eta)}__\n\n")  # type: ignore
            # Only edit message once every 5 seconds to avoid ratelimits
            if last_update_time is None or (
                    now - last_update_time).total_seconds() >= 5:
                self.bot.loop.create_task(ctx.respond(progress))

                last_update_time = now

        task = self.bot.loop.create_task(
            self.bot.client.send_document(ctx.msg.chat.id,
                                          str(file_path),
                                          force_document=True,
                                          progress=prog_func))  # type: ignore
        self.task.add((ctx.msg.message_id, task))
        try:
            await task
        except asyncio.CancelledError:
            return "__Transmission aborted.__"
        else:
            self.task.remove((ctx.msg.message_id, task))

        await ctx.msg.delete()
        return


    @command.desc("Method for aborting Download/Upload task")
    @command.usage("[GID], [reply to task message]")
    async def cmd_abort(self, ctx) -> Optional[str]:
        if not ctx.input and not ctx.msg.reply_to_message:
            return "__Pass GID or reply to message of task to abort transmission.__"
        if ctx.msg.reply_to_message and ctx.input:
            return "__Can't pass gid while replying to message.__"

        aria2: Any = self.bot.plugins["Aria2"]
        drive: Any = self.bot.plugins["GoogleDrive"]

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

        ret = await aria2.cancelMirror(ctx.input)
        if ret is None:
            await ctx.msg.delete()

        return ret
