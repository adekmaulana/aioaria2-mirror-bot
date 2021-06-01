import platform
import uuid
from collections import defaultdict
from typing import Any, ClassVar, Dict, List, MutableMapping, Optional

import pyrogram
from pyrogram.types import (
    CallbackQuery,
    InlineQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent
)

from .. import __version__, command, listener, module, util


class CoreModule(module.Module):
    name: ClassVar[str] = "Core"

    cache: Dict[int, int]
    db: Any

    async def on_load(self):
        self.cache = {}
        self.db = self.bot.get_db("core")

    def build_button(self) -> List[List[InlineKeyboardButton]]:
        modules = list(self.bot.modules.keys())
        button: List[InlineKeyboardButton] = []
        for mod in modules:
            button.append(InlineKeyboardButton(
                mod, callback_data=f"menu({mod})".encode()))
        buttons = [
            button[i * 3:(i + 1) * 3]
            for i in range((len(button) + 3 - 1) // 3)
        ]
        buttons.append(
            [
                InlineKeyboardButton(
                    "✗ Close",
                    callback_data="menu(Close)".encode()
                )
            ]
        )

        return buttons

    async def on_inline_query(self, query: InlineQuery) -> None:
        repo = self.bot.getConfig["github_repo"]
        answer = [
            InlineQueryResultArticle(
                id=uuid.uuid4(),
                title="About Caligo",
                input_message_content=InputTextMessageContent(
                    "__Caligo is SelfBot based on Pyrogram library.__"),
                url=f"https://github.com/{repo}",
                description="A Selfbot Telegram.",
                thumb_url=None,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "⚡️ Repo",
                                url=f"https://github.com/{repo}"),
                            InlineKeyboardButton(
                                "📖️ How To",
                                url=f"https://github.com/{repo}#Installation"),
                        ]
                    ]
                )
            )
        ]
        if query.from_user and (query.from_user.id == self.bot.uid):
            button = await util.run_sync(self.build_button)
            answer.append(
                InlineQueryResultArticle(
                    id=uuid.uuid4(),
                    title="Menu",
                    input_message_content=InputTextMessageContent(
                        "**Caligo Menu Helper**"),
                    url=f"https://github.com/{repo}",
                    description="Menu Helper.",
                    thumb_url=None,
                    reply_markup=InlineKeyboardMarkup(button)
                )
            )

        await query.answer(results=answer, cache_time=3)
        return

    @listener.pattern(r"menu\((\w+)\)$")
    async def on_callback_query(self, query: CallbackQuery) -> None:
        if query.from_user and query.from_user.id != self.bot.uid:
            await query.answer("Sorry, you don't have permission to access.",
                               show_alert=True)
            return

        mod = query.matches[0].group(1)
        if mod == "Back":
            button = await util.run_sync(self.build_button)
            await query.edit_message_text(
                "**Caligo Menu Helper**",
                reply_markup=InlineKeyboardMarkup(button))
            return
        if mod == "Close":
            button = await util.run_sync(self.build_button)
            for msg_id, chat_id in list(self.cache.items()):
                try:
                    msg = await self.bot.client.get_messages(chat_id, msg_id)
                except pyrogram.errors.PeerIdInvalid:
                    continue
                else:
                    try:
                        await msg.delete()
                    except AttributeError:
                        # Trying to delete the deleted message already
                        del self.cache[msg_id]
                        continue
                    else:
                        del self.cache[msg_id]
                        break
            else:
                await query.answer("😿️ Couldn't close expired message")
                await query.edit_message_text(
                    "**Caligo Menu Helper**",
                    reply_markup=InlineKeyboardMarkup(button[:-1]))

            return

        modules: MutableMapping[str, MutableMapping[str, str]] = defaultdict(dict)
        for _, cmd in self.bot.commands.items():
            if cmd.module.name != mod:
                continue

            desc = cmd.desc if cmd.desc else "__No description provided__"
            aliases = ""
            if cmd.aliases:
                aliases = f' (aliases: {", ".join(cmd.aliases)})'

            mod_name = type(cmd.module).name
            modules[mod_name][cmd.name] = desc + aliases

        response = None
        for mod_name, commands in sorted(modules.items()):
            response = util.text.join_map(commands, heading=mod_name)

        if response is not None:
            button = [[InlineKeyboardButton(
                    "⇠ Back", callback_data="menu(Back)".encode()
            )]]
            await query.edit_message_text(
                response, reply_markup=InlineKeyboardMarkup(button))

            return

        await query.answer(f"😿️ {mod} doesn't have any commands.")
        return

    @command.desc("List the commands")
    @command.usage("[filter: command or module name?]", optional=True)
    async def cmd_help(self, ctx: command.Context) -> Optional[str]:
        if self.bot.has_bot and not ctx.input:
            await ctx.msg.delete()
            response = await self.bot.client.get_inline_bot_results(
                self.bot.bot_user.username)
            res = await self.bot.client.send_inline_bot_result(
                ctx.msg.chat.id, response.query_id, response.results[1].id)
            self.cache[res.updates[0].id] = ctx.msg.chat.id

            return

        filt = ctx.input
        modules: MutableMapping[str, MutableMapping[str, str]] = defaultdict(dict)
        if filt and filt not in self.bot.modules:
            if filt in self.bot.commands:
                cmd = self.bot.commands[filt]

                aliases = f"`{'`, `'.join(cmd.aliases)}`" if cmd.aliases else "none"

                if cmd.usage is None:
                    args_desc = "none"
                else:
                    args_desc = cmd.usage

                    if cmd.usage_optional:
                        args_desc += " (optional)"
                    if cmd.usage_reply:
                        args_desc += " (also accepts replies)"

                return f"""`{cmd.name}`: **{cmd.desc if cmd.desc else '__No description provided.__'}**

Module: {cmd.module.name}
Aliases: {aliases}
Expected parameters: {args_desc}"""

            return "__That filter didn't match any commands or modules.__"

        for name, cmd in self.bot.commands.items():
            if filt:
                if cmd.module.name != filt:
                    continue
            else:
                if name != cmd.name:
                    continue

            desc = cmd.desc if cmd.desc else "__No description provided__"
            aliases = ""
            if cmd.aliases:
                aliases = f' (aliases: {", ".join(cmd.aliases)})'

            mod_name = type(cmd.module).name
            modules[mod_name][cmd.name] = desc + aliases

        response = None
        for mod_name, commands in sorted(modules.items()):
            section = util.text.join_map(commands, heading=mod_name)
            add_len = len(section) + 2
            if response and (len(response) + add_len > util.tg.MESSAGE_CHAR_LIMIT):
                await ctx.respond_multi(response)
                response = None

            if response:
                response += "\n\n" + section
            else:
                response = section

        if response:
            await ctx.respond_multi(response)

    @command.desc("Get or change this bot prefix")
    @command.alias("setprefix", "getprefix")
    @command.usage("[new prefix?]", optional=True)
    async def cmd_prefix(self, ctx: command.Context) -> str:
        new_prefix = ctx.input

        if not new_prefix:
            return f"The prefix is `{self.bot.prefix}`"

        self.bot.prefix = new_prefix
        await self.db.find_one_and_update(
            {"_id": self.name},
            {
                "$set": {"prefix": new_prefix}
            }
        )

        return f"Prefix set to `{self.bot.prefix}`"

    @command.desc("Get information about this bot instance")
    @command.alias("botinfo")
    async def cmd_info(self, ctx: command.Context) -> None:
        # Get tagged version and optionally the Git commit
        commit = await util.run_sync(util.version.get_commit)
        dirty = ", dirty" if await util.run_sync(util.git.is_dirty) else ""
        unofficial = (
            ", unofficial" if not await util.run_sync(util.git.is_official) else ""
        )
        version = (
            f"{__version__} (<code>{commit}</code>{dirty}{unofficial})"
            if commit
            else __version__
        )

        # Clean system version
        sys_ver = platform.release()
        try:
            sys_ver = sys_ver[: sys_ver.index("-")]
        except ValueError:
            pass

        # Get current uptime
        now = util.time.usec()
        uptime = util.time.format_duration_us(now - self.bot.start_time_us)

        # Get total uptime from stats module (if loaded)
        stats_module = self.bot.modules.get("Stats", None)
        get_start_time = getattr(stats_module, "get_start_time", None)
        total_uptime = None
        if stats_module is not None and callable(get_start_time):
            stats_start_time = await get_start_time()
            total_uptime = util.time.format_duration_us(now - stats_start_time) + "\n"
        else:
            uptime += "\n"

        # Get total number of chats, including PMs
        num_chats = await self.bot.client.get_dialogs_count()

        response = util.text.join_map(
            {
                "Version": version,
                "Python": f"{platform.python_implementation()} {platform.python_version()}",
                "Pyrogram": f"{pyrogram.__version__}",
                "System": f"{platform.system()} {sys_ver}",
                "Uptime": uptime,
                **({"Total uptime": total_uptime} if total_uptime else {}),
                "Commands loaded": len(self.bot.commands),
                "Modules loaded": len(self.bot.modules),
                "Listeners loaded": sum(
                    len(evt) for evt in self.bot.listeners.values()
                ),
                "Events activated": f"{self.bot.events_activated}\n",
                "Chats": num_chats,
            },
            heading='<a href="https://github.com/adekmaulana/caligo">Caligo</a> info',
            parse_mode="html",
        )

        # HTML allows us to send a bolded link (nested entities)
        await ctx.respond(response, parse_mode="html")
