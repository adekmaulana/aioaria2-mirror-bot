import asyncio
import os
import inspect
import re
import io
import sys
import traceback
from pathlib import Path
from typing import Any, ClassVar, Dict, Optional, Tuple

import aiohttp
import pyrogram
import speedtest
from meval import meval

from .. import command, module, util


class SystemModule(module.Module):
    name: ClassVar[str] = "System"

    db: Any
    restart_pending: bool

    async def on_load(self):
        self.restart_pending = False

        self.db = self.bot.get_db("system")

    @command.desc("Get how long this bot has been up for")
    async def cmd_uptime(self, ctx: command.Context) -> str:
        delta_us = util.time.usec() - self.bot.start_time_us
        await ctx.respond(f"Uptime: {util.time.format_duration_us(delta_us)}")

    @command.desc("Get information about the host system")
    @command.alias("si")
    async def cmd_sysinfo(self, ctx: command.Context) -> str:
        await ctx.respond("Collecting system information...")

        try:
            stdout, _, ret = await util.system.run_command(
                "neofetch", "--stdout", timeout=60
            )
        except asyncio.TimeoutError:
            return "🕑 `neofetch` failed to finish within 1 minute."
        except FileNotFoundError:
            return (
                "❌ [neofetch](https://github.com/dylanaraps/neofetch) "
                "must be installed on the host system."
            )

        err = f"⚠️ Return code: {ret}" if ret != 0 else ""
        sysinfo = "\n".join(stdout.split("\n")[2:]) if ret == 0 else stdout
        return f"```{sysinfo}```{err}"

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

    @command.desc("Run a snippet in a shell")
    @command.usage("[shell snippet]")
    @command.alias("sh")
    async def cmd_shell(self, ctx: command.Context) -> str:
        snip = ctx.input
        if not snip:
            return "Give me command to run."

        await ctx.respond("Running snippet...")
        before = util.time.usec()

        try:
            stdout, _, ret = await util.system.run_command(
                snip, shell=True, timeout=120  # skipcq: BAN-B604
            )
        except FileNotFoundError as E:
            after = util.time.usec()
            return (
                f"**In:**\n```{snip}```\n\n"
                "**Out:**\n"
                f"⚠️ Error executing command:\n```{util.error.format_exception(E)}```\n\n"
                f"Time: {util.time.format_duration_us(after - before)}"
            )
        except asyncio.TimeoutError:
            after = util.time.usec()
            return (
                f"**In:**\n```{snip}```\n\n"
                "**Out:**\n"
                "🕑 Snippet failed to finish within 2 minutes.\n\n"
                f"Time: {util.time.format_duration_us(after - before)}"
            )

        after = util.time.usec()

        el_us = after - before
        el_str = f"\nTime: {util.time.format_duration_us(el_us)}"

        if not stdout:
            stdout = "[no output]"
        elif stdout[-1:] != "\n":
            stdout += "\n"

        stdout = self.bot.redact_message(stdout)
        err = f"⚠️ Return code: {ret}" if ret != 0 else ""
        return f"**In:**\n```{snip}```\n\n**Out:**\n```{stdout}```{err}{el_str}"

    @command.desc("Evaluate code")
    @command.usage("[code snippet]")
    @command.alias("ev", "exec")
    async def cmd_eval(self, ctx: command.Context) -> str:
        code = ctx.input
        if not code:
            return "Give me code to evaluate."

        out_buf = io.StringIO()

        async def _eval() -> Tuple[str, str]:
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
                "modules": self.bot.modules,
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
                "aria": self.bot.modules.get("Aria2"),
                "aria2": self.bot.modules.get("Aria2"),
                "command": command,
                "module": module,
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

    @command.desc("Stop this bot")
    async def cmd_stop(self, ctx: command.Context) -> None:
        await ctx.respond("Stopping bot...")
        self.bot.stop_manual = True
        await ctx.respond("Stopped")
        await self.bot.stop()

    @command.desc("Restart this bot")
    @command.alias("re", "rst")
    async def cmd_restart(
        self,
        ctx: command.Context,
        *,
        restart_time: Optional[int] = None,
        reason="manual",
    ) -> None:
        resp_msg = await ctx.respond("Restarting bot...")

        # Save time and status message so we can update it after restarting
        await self.db.find_one_and_update(
            {"_id": self.name},
            {
                "$set": {
                    "restart.status_chat_id": resp_msg.chat.id,
                    "restart.status_message_id": resp_msg.message_id,
                    "restart.time": restart_time or util.time.usec(),
                    "restart.reason": reason
                    }
            },
            upsert=True
        )
        # Initiate the restart
        self.restart_pending = True
        self.bot.stop_manual = True
        self.log.info("Preparing to restart...")
        await self.bot.stop()

    async def on_start(self, time_us: int) -> None:  # skipcq: PYL-W0613
        # Update restart status message if applicable
        data: Optional[Dict[str, Dict[str, Any]]
                       ] = await self.db.find_one({"_id": self.name})
        if data is not None:
            restart = data.get("restart")
            # Fetch status message info
            rs_time: Optional[int] = restart.get("time")
            rs_chat_id: Optional[int] = restart.get("status_chat_id")
            rs_message_id: Optional[int] = restart.get("status_message_id")
            rs_reason: Optional[str] = restart.get("reason")

            # Delete DB keys first in case message editing fails
            await self.db.delete_one({"_id": self.name})

            # Bail out if we're missing necessary values
            if rs_chat_id is None or rs_message_id is None:
                return

            # Show message
            updated = "updated and " if rs_reason == "update" else ""
            duration = util.time.format_duration_us(util.time.usec() - rs_time)
            self.log.info(f"Bot {updated}restarted in {duration}")
            status_msg = await self.bot.client.get_messages(rs_chat_id, rs_message_id)
            await self.bot.respond(
                status_msg, f"Bot {updated}restarted in {duration}.", mode="repost")

    async def on_stopped(self) -> None:
        if self.restart_pending:
            self.log.info("Starting new bot instance...\n")
            # This is safe because original arguments are reused. skipcq: BAN-B606
            os.execv(sys.executable, (sys.executable, "-m", "caligo"))
            sys.exit()

    async def run_workflows(self) -> int:
        headers = {"accept": "application/vnd.github.v3+json"}
        payload = {"ref": "refs/heads/staging"}

        user = self.bot.getConfig["github_repo"].split("/")[0]
        repo = self.bot.getConfig["github_repo"].split("/")[1]
        path = f"/repos/{user}/{repo}/actions/workflows/container.yml/dispatches"
        uri = "https://api.github.com"
        auth = aiohttp.BasicAuth(user, self.bot.getConfig["github_token"])

        async with self.bot.http.post(
            uri + path,
            auth=auth,
            headers=headers,
            json=payload
        ) as resp:
            return resp.status

    @command.desc("Update this bot from Git and restart")
    @command.usage("[deploy flag?]", optional=True)
    @command.alias("up", "upd")
    async def cmd_update(self, ctx: command.Context) -> Optional[str]:
        if not util.git.have_git:
            return "__The__ `git` __command is required for self-updating.__"

        # Attempt to get the Git repo
        repo = await util.run_sync(util.git.get_repo)
        if not repo:
            return "__Unable to locate Git repository data.__"

        # Get current branch's tracking remote
        remote = await util.run_sync(util.git.get_current_remote)
        if remote is None:
            return f"__Current branch__ `{repo.active_branch.name}` __is not tracking a remote.__"

        # Save time and old commit for diffing
        update_time = util.time.usec()
        old_commit = await util.run_sync(repo.commit)

        # GitHub workflows to push into heroku
        if ctx.input == "deploy":
            if not self.bot.getConfig["container"]:
                return "__Deploying only works if your bot is run on container.__"

            if (self.bot.getConfig["github_token"] and
                    self.bot.getConfig["github_repo"]) and (
                    self.bot.getConfig["heroku_api_key"] and
                    self.bot.getConfig["heroku_app_name"]):
                ret = await self.run_workflows()

                resp_msg = await ctx.respond("Deploying bot...")

                await self.db.find_one_and_update(
                    {"_id": self.name},
                    {
                       "$set": {
                           "restart.status_chat_id": resp_msg.chat.id,
                           "restart.status_message_id": resp_msg.message_id,
                           "restart.time": update_time,
                           "restart.reason": "update"
                       }
                    },
                    upsert=True
                )
                return

            return "__Deploying needs Heroku and GitHub credential set properly.__"

        # Pull from remote
        await ctx.respond(f"Pulling changes from `{remote}`...")
        await util.run_sync(remote.pull)

        # Return early if no changes were pulled
        diff = old_commit.diff()
        if not diff:
            return "No updates found."

        # Check for dependency changes
        if any(change.a_path == "poetry.lock" for change in diff):
            # Update dependencies automatically if running in venv
            prefix = util.system.get_venv_path()
            if prefix:
                pip = str(Path(prefix) / "bin" / "pip")

                await ctx.respond("Updating dependencies...")
                stdout, _, ret = await util.system.run_command(
                    pip, "install", repo.working_tree_dir
                )
                if ret != 0:
                    return f"""⚠️ Error updating dependencies:

```{stdout}```

Fix the issue manually and then restart the bot."""
            else:
                return """Successfully pulled updates.

**Update dependencies manually** to avoid errors, then restart the bot for the update to take effect.

Dependency updates are automatic if you're running the bot in a virtualenv."""

        # Restart after updating
        await self.cmd_restart(ctx, restart_time=update_time, reason="update")
        return None
