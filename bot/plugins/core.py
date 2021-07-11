import uuid
from collections import defaultdict
from typing import ClassVar, List, MutableMapping, Optional

import pyrogram
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent
)

from bot import command, listener, plugin, util


class Core(plugin.Plugin):
    name: ClassVar[str] = "Core"

    cache: pyrogram.types.Message

    async def on_load(self):
        self.cache = None  # type: ignore
        self.db = self.bot.db.get_collection("sudoers")

    def build_button(self) -> List[List[InlineKeyboardButton]]:
        plugins = list(self.bot.plugins.keys())
        button: List[InlineKeyboardButton] = []
        for plug in plugins:
            button.append(InlineKeyboardButton(
                plug, callback_data=f"menu({plug})".encode()))
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
        answer = [
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="About The Bot",
                input_message_content=InputTextMessageContent(
                    "__AsyncIO aria2 python mirror bot.__"),
                url="https://github.com/adekmaulana/aioaria2-mirror-bot",
                description="Telegram Bot for Mirror to Google Drive.",
                thumb_url=None,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "⚡️ Repo",
                                url="https://github.com/adekmaulana/aioaria2-mirror-bot"),
                            InlineKeyboardButton(
                                "📖️ README",
                                url="https://github.com/adekmaulana/aioaria2-mirror-bot#README"),
                        ]
                    ]
                )
            )
        ]

        await query.answer(results=answer, cache_time=3)  # type: ignore
        return

    @listener.filters(pyrogram.filters.regex(r"menu\((\w+)\)$"))
    async def on_callback_query(self, query: CallbackQuery) -> None:
        user = query.from_user
        if user and user.id != self.bot.owner and user.id not in self.bot.sudo_users:
            await query.answer("Sorry, you don't have permission to access.",
                               show_alert=True)
            return

        mod = query.matches[0].group(1)
        button = await util.run_sync(self.build_button)
        if mod == "Back":
            await query.edit_message_text(
                "**Bot Menu Helper**",
                reply_markup=InlineKeyboardMarkup(button))
            return
        if mod == "Close":
            if self.cache is not None:
                await self.cache.delete()
            else:
                await query.answer("😿️ Couldn't close expired message")
                await query.edit_message_text(
                    "**Bot Menu Helper**",
                    reply_markup=InlineKeyboardMarkup(button[:-1]))

            return

        plugins: MutableMapping[str, MutableMapping[str, str]] = defaultdict(dict)
        for _, cmd in self.bot.commands.items():
            if cmd.plugin.name != mod:
                continue

            desc = cmd.desc if cmd.desc else "__No description provided__"
            aliases = ""
            if cmd.aliases:
                aliases = f' (aliases: {", ".join(cmd.aliases)})'

            plugin_name = type(cmd.plugin).name
            plugins[plugin_name][cmd.name] = desc + aliases

        response = None
        for mod_name, commands in sorted(plugins.items()):
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

    @command.desc("Add user to sudoers")
    @command.usage("[id/username] [reply to user]")
    async def cmd_addsudo(self, ctx: command.Context) -> str:
        user = ctx.input
        if ctx.msg.reply_to_message:
            user = ctx.msg.reply_to_message.from_user

        if not user:
            return "__Reply to user or input user id/username"

        if not isinstance(user, pyrogram.types.User):
            user = await self.bot.client.get_users(user)

        if user.id in self.bot.sudo_users:  # type: ignore
            return "__User already in sudoers__"

        self.bot.sudo_users.add(user.id)  # type: ignore
        await self.db.insert_one({"_id": user.id})  # type: ignore

        return f"**{user.first_name}** added to sudo"  # type: ignore

    @command.desc("Remove user from sudoers")
    @command.usage("[id/username] [reply to user]")
    async def cmd_rmsudo(self, ctx: command.Context) -> str:
        user = ctx.input
        if ctx.msg.reply_to_message:
            user = ctx.msg.reply_to_message.from_user

        if not user:
            return "__Reply to user or input user id/username"

        if not isinstance(user, pyrogram.types.User):
            user = await self.bot.client.get_users(user)

        try:
            self.bot.sudo_users.remove(user.id)  # type: ignore
        except KeyError:
            return "__Well, they are not sudoers__"
        await self.db.delete_one({"_id": user.id})  # type: ignore

        return f"**{user.first_name}** removed from sudo"  # type: ignore


    @command.desc("List the commands")
    @command.usage("[filter: command or plugin name?]", optional=True)
    async def cmd_help(self, ctx: command.Context) -> Optional[str]:
        if not ctx.input:
            button = await util.run_sync(self.build_button)
            self.cache = await ctx.msg.reply("Menu",
                                             reply_markup=InlineKeyboardMarkup(button))

            return

        filt = ctx.input
        plugins: MutableMapping[str, MutableMapping[str, str]] = defaultdict(dict)
        if filt and filt not in self.bot.plugins:
            if filt in self.bot.commands:
                cmd = self.bot.commands[filt]

                aliases = f"`{'`, `'.join(cmd.aliases)}`" if cmd.aliases else "none"

                if cmd.usage is None:
                    args_desc = "none"
                else:
                    args_desc = cmd.usage

                    if cmd.usage_optional:
                        args_desc += " (optional)"

                return f"""`{cmd.name}`: **{cmd.desc if cmd.desc else '__No description provided.__'}**

Module: {cmd.plugin.name}
Aliases: {aliases}
Expected parameters: {args_desc}"""

            return "__That filter didn't match any commands or plugins.__"

        for name, cmd in self.bot.commands.items():
            if filt:
                if cmd.plugin.name != filt:
                    continue
            else:
                if name != cmd.name:
                    continue

            desc = cmd.desc if cmd.desc else "__No description provided__"
            aliases = ""
            if cmd.aliases:
                aliases = f' (aliases: {", ".join(cmd.aliases)})'

            plugin_name = type(cmd.plugin).name
            plugins[plugin_name][cmd.name] = desc + aliases

        response = None
        for mod_name, commands in sorted(plugins.items()):
            section = util.text.join_map(commands, heading=mod_name)

            if response:
                response += "\n\n" + section
            else:
                response = section

        if response:
            return response