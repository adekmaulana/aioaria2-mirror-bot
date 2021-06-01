import pyrogram
from pyrogram import filters


def chat_action() -> filters.Filter:
    async def func(_, __, chat: pyrogram.types.Message):
        return bool(chat.new_chat_members or chat.left_chat_member)

    return filters.create(func)
