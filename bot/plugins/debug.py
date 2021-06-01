import inspect
import io
import os
import re
import sys
import traceback
from datetime import datetime
from typing import Any, ClassVar, Tuple

import pyrogram
import speedtest
from meval import meval

from bot import command, plugin, util


class Debug(plugin.Plugin):
    name: ClassVar[str] = "Debug"

    async def cmd_ping(self, ctx: command.Context) -> str:
        start = datetime.now()
        await ctx.respond("Calculating response time...")
        end = datetime.now()
        latency = (end - start).microseconds / 1000

        return f"Latency: {latency} ms"

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

    async def cmd_eval(self, ctx: command.Context) -> str:
        code = ctx.input
        if not code:
            return "Give me code to evaluate."

        out_buf = io.StringIO()

        async def _eval() -> Tuple[str, Any]:
            async def send(*args: Any, **kwargs: Any) -> pyrogram.types.Message:
                return await ctx.msg.reply(*args, **kwargs)

            def _print(*args: Any, **kwargs: Any) -> None:
                if "file" not in kwargs:
                    kwargs["file"] = out_buf

                return print(*args, **kwargs)

            eval_vars = {
                # Contextual info
                "self": self,
                "ctx": ctx,
                "bot": self.bot,
                "loop": self.bot.loop,
                "client": self.bot.client,
                "commands": self.bot.commands,
                "listeners": self.bot.listeners,
                "plugins": self.bot.plugins,
                "stdout": out_buf,
                # Convenience aliases
                "context": ctx,
                "msg": ctx.msg,
                "message": ctx.msg,
                "db": self.bot.db,
                # Helper functions
                "send": send,
                "print": _print,
                # Built-in modules
                "inspect": inspect,
                "os": os,
                "re": re,
                "sys": sys,
                "traceback": traceback,
                # Third-party modules
                "pyrogram": pyrogram,
                # Custom modules
                "command": command,
                "plugin": plugin,
                "util": util,
            }

            try:
                return "", await meval(code, globals(), **eval_vars)
            except Exception as e:  # skipcq: PYL-W0703
                # Find first traceback frame involving the snippet
                first_snip_idx = -1
                tb = traceback.extract_tb(e.__traceback__)
                for i, frame in enumerate(tb):
                    if frame.filename == "<string>" or frame.filename.endswith(
                        "ast.py"
                    ):
                        first_snip_idx = i
                        break

                # Re-raise exception if it wasn't caused by the snippet
                if first_snip_idx == -1:
                    raise e

                # Return formatted stripped traceback
                stripped_tb = tb[first_snip_idx:]
                formatted_tb = util.error.format_exception(e, tb=stripped_tb)
                return "⚠️ Error executing snippet\n\n", formatted_tb

        before = util.time.usec()
        prefix, result = await _eval()
        after = util.time.usec()

        # Always write result if no output has been collected thus far
        if not out_buf.getvalue() or result is not None:
            print(result, file=out_buf)

        el_us = after - before
        el_str = util.time.format_duration_us(el_us)

        out = out_buf.getvalue()
        # Strip only ONE final newline to compensate for our message formatting
        if out.endswith("\n"):
            out = out[:-1]

        return f"""{prefix}**In:**
```{code}```

**Out:**
```{out}```

Time: {el_str}"""