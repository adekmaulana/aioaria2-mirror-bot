from typing import Any, ClassVar

import pyrogram

from .. import command, module


class CoreModule(module.Module):
    name: ClassVar[str] = "Core"

    db: Any

    async def on_load(self):
        self.db = self.bot.get_db("core")

    @command.desc("add sudo user into database")
    @command.usage("[user id/username or reply?]", optional=True, reply=True)
    async def cmd_addsudo(self, ctx: command.Context) -> str:
        user = ctx.input
        if ctx.msg.reply_to_message:
            user = ctx.msg.reply_to_message.from_user

        if not user:
            return "__Reply to user or input user id/username"

        if not isinstance(user, pyrogram.types.User):
            user = await self.bot.client.get_users(user)

        self.bot.sudo_users.add(user.id)
        await self.db.find_one_and_update(
            {"_id": self.name},
            {
                "$addToSet": {"sudo_users": user.id}
            },
            upsert=True
        )

        return f"**{user.first_name}** added to sudo"

    @command.desc("remove sudo user from database")
    @command.usage("[user id/username or reply?]", optional=True, reply=True)
    async def cmd_rmsudo(self, ctx: command.Context) -> str:
        user = ctx.input
        if ctx.msg.reply_to_message:
            user = ctx.msg.reply_to_message.from_user

        if not user:
            return "__Reply to user or input user id/username"

        if not isinstance(user, pyrogram.types.User):
            user = await self.bot.client.get_users(user)

        self.bot.sudo_users.add(user.id)
        await self.db.find_one_and_update(
            {"_id": self.name},
            {
                "$pull": {"sudo_users": user.id}
            }
        )

        return f"**{user.first_name}** removed from sudo"
