from datetime import datetime
from typing import ClassVar

from .. import command, module


class DebugModule(module.Module):
    name: ClassVar[str] = "Debug"

    @command.desc("Pong")
    async def cmd_ping(self, ctx: command.Context) -> str:
        start = datetime.now()
        await ctx.respond("Calculating response time...")
        end = datetime.now()
        latency = (end - start).microseconds / 1000

        return f"Request response time: **{latency} ms**"
