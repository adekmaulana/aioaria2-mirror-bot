import asyncio
import inspect
from typing import TYPE_CHECKING, Any, Optional, Union

import pyrogram
from pyrogram.types import Chat, Message

from . import util

if TYPE_CHECKING:
    from .core import Bot


class ConversationExistError(Exception):

    def __init__(self, msg: Optional[str] = None):
        self.msg = msg
        super().__init__(self.msg)


class Conversation:
    _chat: Any

    def __init__(
        self,
        bot: "Bot",
        input_chat: Union[str, int],
        timeout: int,
        max_messages: int
    ) -> None:
        self.bot = bot
        self.client = self.bot.client

        self._counter = 0
        self._input_chat = input_chat
        self._max_incoming = max_messages
        self._timeout = timeout

    @classmethod
    async def new(cls, bot: "Bot", input_chat: Union[str, int], timeout: int,
                  max_messages: int) -> "Conversation":

        self = cls(bot, input_chat, timeout, max_messages)
        self._chat = await self.client.get_chat(self._input_chat)

        return self

    @property
    def chat(self) -> Chat:
        return self._chat

    async def send_message(self, text, **kwargs) -> Message:
        sent = await self.client.send_message(self.chat.id, text, **kwargs)

        return sent

    async def send_file(self, document, **kwargs) -> Optional[Message]:
        doc = await self.client.send_document(self.chat.id, document, **kwargs)

        return doc

    async def get_response(self, **kwargs) -> Message:
        response = await self._get_message(**kwargs)

        return response

    async def get_reply(self, **kwargs) -> Message:
        filters = pyrogram.filters.reply
        response = await self._get_message(filters=filters, **kwargs)

        return response

    async def mark_read(self, max_id: int = 0) -> bool:
        return await self.bot.client.read_history(self.chat.id, max_id)

    async def _get_message(self, **kwargs) -> Message:
        if self._counter >= self._max_incoming:
            raise ValueError("Received max messages")

        filters = kwargs.get("filters")
        fut = self.bot.CONVERSATION[self.chat.id]
        timeout = kwargs.get("timeout") or self._timeout
        before = util.time.usec()
        while True:
            after = before - util.time.usec()
            result = await asyncio.wait_for(fut.get(), timeout - after)

            if filters is not None and callable(filters):
                ready = filters(self.bot.client, result)
                if inspect.iscoroutine(ready):
                    ready = await ready
                if not ready:
                    continue

            break

        self._counter += 1

        return result
