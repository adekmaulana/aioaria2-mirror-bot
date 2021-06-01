import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, Union

import pyrogram
from pyrogram.filters import Filter, create

from ..conversation import Conversation, ConversationExistError
from .base import Base

if TYPE_CHECKING:
    from .bot import Bot


class ConversationDispatcher(Base):
    CONVERSATION: Dict[int, asyncio.Queue]

    def __init__(self: "Bot", **kwargs: Any) -> None:
        self.CONVERSATION = {}

        super().__init__(**kwargs)

    def conversation_predicate(self: "Bot") -> Filter:
        async def func(_, __, conv: pyrogram.types.Message):
            return bool(self.CONVERSATION and conv.chat and
                        conv.chat.id in self.CONVERSATION)

        return create(func)

    @asynccontextmanager
    async def conversation(
        self: "Bot",
        chat_id: Union[str, int],
        *,
        timeout: int = 7,
        max_messages: int = 7
    ) -> AsyncGenerator[Conversation, None]:
        conv = await Conversation.new(self, chat_id, timeout, max_messages)
        chat_name = conv.chat.title if conv.chat.title else conv.chat.first_name
        if conv.chat.id in self.CONVERSATION:
            raise ConversationExistError(f"Conversation with '{chat_name}' exist")

        self.CONVERSATION[conv.chat.id] = asyncio.Queue(max_messages)

        try:
            yield conv
        finally:
            self.CONVERSATION[conv.chat.id].put_nowait(None)
            del self.CONVERSATION[conv.chat.id]

    async def on_conversation(
        self: "Bot",
        _: pyrogram.Client,
        msg: pyrogram.types.Message
    ) -> None:
        cache = self.CONVERSATION[msg.chat.id]
        cache.put_nowait(msg)
        msg.continue_propagation()
