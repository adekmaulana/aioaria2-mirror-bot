from datetime import datetime
from typing import Any, ClassVar, List, Optional, Tuple, Union

import pyrogram
from pyrogram.errors import MessageDeleteForbidden

from .. import command, module, util


class ModerationModule(module.Module):
    name: ClassVar[str] = "Moderation"

    @command.desc("Mention everyone in this group (**DO NOT ABUSE**)")
    @command.usage("[comment?]", optional=True)
    @command.alias("evo", "@everyone")
    async def cmd_everyone(
        self,
        ctx: command.Context,
        *,
        tag: str = "\U000e0020everyone",
        user_filter: Optional[str] = "all",
    ) -> Optional[str]:
        comment = ctx.input

        if ctx.msg.chat.type == "private":
            return "__This command can only be used in groups.__"

        mention_text = f"@{tag}"
        if comment:
            mention_text += " " + comment

        mention_slots = 4096 - len(mention_text)

        chat = ctx.msg.chat.id
        async for member in self.bot.client.iter_chat_members(
                chat, filter=user_filter):
            mention_text += f"[\u200b](tg://user?id={member.user.id})"

            mention_slots -= 1
            if mention_slots == 0:
                break

        await ctx.respond(mention_text, mode="repost")
        return None

    @command.desc("Mention all admins in a group (**DO NOT ABUSE**)")
    @command.usage("[comment?]", optional=True)
    @command.alias("adm", "@admin")
    async def cmd_admin(self, ctx: command.Context) -> Optional[str]:
        return await self.cmd_everyone(ctx,
                                       tag="admin",
                                       user_filter="administrators")

    @command.desc("Ban user(s) from the current chat by ID or reply")
    @command.usage("[ID(s) of the user(s) to ban?, or reply to user's message]",
                   optional=True)
    async def cmd_ban(self, ctx: command.Context) -> str:
        input_ids = ctx.args

        for index, username in enumerate(input_ids[:]):
            if isinstance(username, str):
                user = await self.bot.client.get_users(username)
                input_ids[index] = user.id

        try:
            # Parse user IDs without duplicates
            user_ids = list(dict.fromkeys(map(int, input_ids)))
        except ValueError:
            return "__Encountered invalid ID while parsing arguments.__"

        if ctx.msg.reply_to_message:
            reply_msg = ctx.msg.reply_to_message
            user_ids.append(reply_msg.from_user.id)

        if not user_ids:
            return "__Provide a list of user IDs to ban, or reply to a user's message to ban them.__"

        lines: List[str]
        single_user = len(user_ids) == 1
        if single_user:
            lines = []
        else:
            lines = [f"**Banned {len(user_ids)} users:**"]
            await ctx.respond(f"Banning {len(user_ids)} users...")

        for user_id in user_ids:
            try:
                user = await self.bot.client.get_users(user_id)
            except ValueError:
                if single_user:
                    lines.append(f"__Unable to find user__ `{user_id}`.")
                else:
                    lines.append(f"Unable to find user `{user_id}`")

                continue

            if not isinstance(user, pyrogram.types.User):
                ent_type = type(user).__name__.lower()
                lines.append(f"Skipped {ent_type} object (`{user_id}`)")
                continue

            user_spec = f"{util.tg.mention_user(user)} (`{user_id}`)"
            if single_user:
                lines.append(f"**Banned** {user_spec}")
            else:
                lines.append(user_spec)

            is_administrator = bool(
                (await self.bot.client.get_chat_member(ctx.msg.chat.id, user.id)
                ).status == "administrator")

            if is_administrator:
                return "__I'm not gonna ban admin.__"

            try:
                await ctx.msg.chat.kick_member(user.id)
            except pyrogram.errors.ChatAdminRequired:
                return "__I need permission to ban users in this chat.__"

        return util.text.join_list(lines)

    @command.desc("Prune deleted members in this group or the specified group")
    @command.alias("prune")
    @command.usage("[target chat ID/username/...?]", optional=True)
    async def cmd_prunemembers(self, ctx: command.Context) -> str:
        if ctx.input:
            chat: Any = await self.bot.client.get_chat(ctx.input)
            if chat.type == "private":
                return f"`{ctx.input}` __references a user/bot, not a chat.__"

            _chat_name = f" from **{chat.title}**"
            _chat_name2 = f" in **{chat.title}**"
        else:
            chat = ctx.msg.chat.id
            _chat_name = ""
            _chat_name2 = ""

        await ctx.respond(f"Fetching members{_chat_name}...")
        all_members = await self.bot.client.get_chat_members(chat)

        last_time = datetime.now()
        total_count = len(all_members)
        err_count = 0
        pruned_count = 0
        idx = 0

        status_text = f"Pruning deleted members{_chat_name}..."
        await ctx.respond(status_text)

        for member in all_members:
            if not member.user.is_deleted:
                continue

            try:
                await self.bot.client.kick_chat_member(chat, member.user.id)
            except pyrogram.errors.ChatAdminRequired:
                return "__I'm not an admin.__"
            except pyrogram.errors.UserAdminInvalid:
                err_count += 1
            else:
                pruned_count += 1

            percent_done = int((idx + 1) / total_count * 100)
            now = datetime.now()
            delta = now - last_time
            if delta.total_seconds() >= 5:
                await ctx.respond(
                    f"{status_text} {percent_done}% done ({idx + 1} of {total_count} processed; {pruned_count} banned; {err_count} failed)"
                )

            last_time = now
            idx += 1

        percent_pruned = int(pruned_count / total_count * 100)
        return f"Pruned {pruned_count} deleted users{_chat_name2} — {percent_pruned}% of the original member count."

    @command.desc("reply to a message, mark as start until your purge command.")
    @command.usage("purge", reply=True)
    async def cmd_purge(self,
                        ctx: command.Context) -> Union[Optional[str], Tuple[str, Union[int, float]]]:
        """ This function need permission to delete messages. """
        if not ctx.msg.reply_to_message:
            return "__Reply to a message.__"

        if ctx.msg.chat.type in ["group", "supergroup"]:
            perm = (await
                    ctx.bot.client.get_chat_member(ctx.msg.chat.id,
                                                   "me")).can_delete_messages
            creator = ctx.msg.chat.is_creator
            if perm is not True and not creator:
                return "__You can't delete message in this chat.__", 5

        await ctx.respond("Purging...")

        msg_ids = []
        purged = 0
        before = datetime.now()
        for msg_id in range(ctx.msg.reply_to_message.message_id,
                            ctx.msg.message_id):
            msg_ids.append(msg_id)
            if len(msg_ids) == 100:
                await ctx.bot.client.delete_messages(
                    chat_id=ctx.msg.chat.id,
                    message_ids=msg_ids,
                    revoke=True,
                )
                purged += len(msg_ids)
                msg_ids = []

        if msg_ids:
            await ctx.bot.client.delete_messages(
                chat_id=ctx.msg.chat.id,
                message_ids=msg_ids,
                revoke=True,
            )
            purged += len(msg_ids)

        after = datetime.now()
        run_time = (after - before).seconds
        time = "second" if run_time <= 1 else "seconds"
        msg = "message" if purged <= 1 else "messages"

        return f"__Purged {purged} {msg} in {run_time} {time}...__", 5

    @command.desc("Delete the replied message.")
    @command.usage("del", reply=True)
    async def cmd_del(self, ctx: command.Context) -> Optional[str]:
        """ reply to message as target, this function will delete that. """
        if not ctx.msg.reply_to_message:
            return "__Reply to a message.__"

        try:
            await ctx.msg.reply_to_message.delete(revoke=True)
        except MessageDeleteForbidden:
            pass
        await ctx.msg.delete()
