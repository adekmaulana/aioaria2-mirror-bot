import asyncio
import signal
from typing import TYPE_CHECKING, Any, Optional, Type, Union

import pyrogram
from pyrogram import Client, filters
from pyrogram.handlers import (
    CallbackQueryHandler,
    DeletedMessagesHandler,
    InlineQueryHandler,
    MessageHandler,
)
from pyrogram.types import CallbackQuery, InlineQuery, Message

from ..custom_filter import chat_action
from ..util import BotConfig, config, tg, time
from .base import Base

if TYPE_CHECKING:
    from .bot import Bot

handler = Union[CallbackQueryHandler, DeletedMessagesHandler,
                InlineQueryHandler, MessageHandler]
update = Union[CallbackQuery, InlineQuery, Message]


class TelegramBot(Base):
    bot_client: Client
    client: Client
    getConfig: config.BotConfig
    prefix: str
    user: pyrogram.types.User
    uid: int
    start_time_us: int

    bot_user: pyrogram.types.User
    bot_uid: int

    _is_running: bool

    def __init__(self: "Bot", **kwargs: Any) -> None:
        self.loaded = False
        self.getConfig = BotConfig

        self._mevent_handlers = {}

        super().__init__(**kwargs)

    async def init_client(self: "Bot") -> None:
        api_id = self.getConfig["api_id"]
        if api_id == 0:
            raise ValueError("API ID is invalid nor empty.")

        api_hash = self.getConfig["api_hash"]
        if not isinstance(api_hash, str):
            raise TypeError("API HASH must be a string")

        string_session = self.getConfig["string_session"]

        if isinstance(string_session, str):
            mode = string_session
        else:
            mode = ":memory:"
        self.client = Client(api_id=api_id,
                             api_hash=api_hash,
                             session_name=mode)

        bot_token = self.getConfig["bot_token"]
        if bot_token is not None:
            if not isinstance(bot_token, str):
                raise TypeError("Bot token must be a string")

            self.bot_client = Client(api_id=api_id,
                                     api_hash=api_hash,
                                     bot_token=bot_token,
                                     session_name=":memory:")

    async def start(self: "Bot") -> None:
        self.log.info("Starting")
        await self.init_client()

        # Load prefix
        db = self.get_db("core")
        try:
            self.prefix = (await db.find_one({"_id": "Core"}))["prefix"]
        except TypeError:
            self.prefix = "."  # Default is '.'-dot you can change later

            await db.find_one_and_update({"_id": "Core"},
                                         {"$set": {
                                             "prefix": self.prefix
                                         }},
                                         upsert=True)

        self.client.add_handler(
            MessageHandler(self.on_command,
                           filters=(self.command_predicate() & filters.me &
                                    filters.outgoing)), 0)

        self.client.add_handler(
            MessageHandler(self.on_conversation,
                           filters=self.conversation_predicate()), 0)

        # Load modules
        self.load_all_modules()
        await self.dispatch_event("load")
        self.loaded = True

        await self.client.start()
        if self.has_bot:
            await self.bot_client.start()

        user = await self.client.get_me()
        if not isinstance(user, pyrogram.types.User):
            raise TypeError("Missing full self user information")
        self.user = user
        self.uid = user.id

        if self.has_bot:
            bot = await self.bot_client.get_me()
            if not isinstance(user, pyrogram.types.User):
                raise TypeError("Missing full self bot user information")
            self.bot_user = bot
            self.bot_uid = bot.id

        self.start_time_us = time.usec()
        await self.dispatch_event("start", self.start_time_us)

        self.log.info("Bot is ready")
        await self.dispatch_event("started")

    async def idle(self: "Bot") -> None:
        signals = {
            k: v
            for v, k in signal.__dict__.items()
            if v.startswith("SIG") and not v.startswith("SIG_")
        }

        def signal_handler(signum, __):

            self.log.info(f"Stop signal received ('{signals[signum]}').")
            self._is_running = False

        for name in (signal.SIGINT, signal.SIGTERM, signal.SIGABRT):
            signal.signal(name, signal_handler)

        self._is_running = True

        while self._is_running:
            await asyncio.sleep(1)

    async def run(self: "Bot") -> None:
        try:
            await self.start()

            self.log.info("Gathering dust")
            await self.idle()
        finally:
            if not self.stop_manual:
                await self.stop()

    def update_module_event(self: "Bot",
                            name: str,
                            event_type: Type[handler],
                            flt: Optional[filters.Filter] = None,
                            group: int = 0) -> None:
        if name in self.listeners:
            if name not in self._mevent_handlers:

                async def update_event(_: Client, event: Type[update]) -> None:
                    await self.dispatch_event(name, event)

                event_info = self.client.add_handler(  # skipcq: PYL-E1111
                    event_type(update_event, flt), group)
                self._mevent_handlers[name] = event_info
        elif name in self._mevent_handlers:
            self.client.remove_handler(*self._mevent_handlers[name])
            del self._mevent_handlers[name]

    def update_bot_module_event(self: "Bot",
                                name: str,
                                event_type: Type[handler],
                                flt: Optional[filters.Filter] = None,
                                group: int = 0) -> None:
        if name in self.listeners:
            if name not in self._mevent_handlers:

                async def update_event(_: Client, event: Type[update]) -> None:
                    await self.dispatch_event(name, event)

                event_info = self.bot_client.add_handler(  # skipcq: PYL-E1111
                    event_type(update_event, flt), group)
                self._mevent_handlers[name] = event_info
        elif name in self._mevent_handlers:
            self.bot_client.remove_handler(*self._mevent_handlers[name])
            del self._mevent_handlers[name]

    def update_module_events(self: "Bot") -> None:
        self.update_module_event("message", MessageHandler, ~filters.edited)
        self.update_module_event("message_edit", MessageHandler, filters.edited)
        self.update_module_event("message_delete", DeletedMessagesHandler)
        self.update_module_event("chat_action", MessageHandler, chat_action())
        if self.has_bot:
            self.update_bot_module_event("callback_query", CallbackQueryHandler)
            self.update_bot_module_event("inline_query", InlineQueryHandler)

    @property
    def events_activated(self: "Bot") -> int:
        return len(self._mevent_handlers)

    @property
    def has_bot(self: "Bot") -> bool:
        return hasattr(self, "bot_client") and isinstance(
            self.bot_client, Client)

    def redact_message(self: "Bot", text: str) -> str:
        redacted = "[REDACTED]"

        api_id = str(self.getConfig["api_id"])
        api_hash = self.getConfig["api_hash"]
        bot_token = self.getConfig["bot_token"]
        db_uri = self.getConfig["db_uri"]
        gdrive_secret = self.getConfig["gdrive_secret"]
        string_session = self.getConfig["string_session"]

        if api_id in text:
            text = text.replace(api_id, redacted)
        if api_hash in text:
            text = text.replace(api_hash, redacted)
        if bot_token is not None and bot_token in text:
            text = text.replace(bot_token, redacted)
        if db_uri in text:
            text = text.replace(db_uri, redacted)
        if gdrive_secret is not None:
            client_id = gdrive_secret["installed"].get("client_id")
            client_secret = gdrive_secret["installed"].get("client_secret")

            if client_id in text:
                text = text.replace(client_id, redacted)
            if client_secret in text:
                text = text.replace(client_secret, redacted)
        if string_session in text:
            text = text.replace(string_session, redacted)

        return text

    async def respond(
        self: "Bot",
        msg: pyrogram.types.Message,
        text: Optional[str] = None,
        *,
        input_arg: Optional[str] = None,
        mode: Optional[str] = None,
        redact: Optional[bool] = True,
        response: Optional[pyrogram.types.Message] = None,
        **kwargs: Any,
    ) -> pyrogram.types.Message:
        if text is not None:

            if redact:
                text = self.redact_message(text)

            # send as file if text > 4096
            if len(str(text)) > tg.MESSAGE_CHAR_LIMIT:
                await msg.edit("Sending output as a file.")
                response = await tg.send_as_document(text, msg, input_arg)

                await msg.delete()
                return response

        # Default to disabling link previews in responses
        if "disable_web_page_preview" not in kwargs:
            kwargs["disable_web_page_preview"] = True

        # Use selected response mode if not overridden by invoker
        if mode is None:
            mode = "edit"

        if mode == "edit":
            return await msg.edit(text=text, **kwargs)

        if mode == "reply":
            if response is not None:
                # Already replied, so just edit the existing reply to reduce spam
                return await response.edit(text=text, **kwargs)

            # Reply since we haven't done so yet
            return await msg.reply(text, **kwargs)

        if mode == "repost":
            if response is not None:
                # Already reposted, so just edit the existing reply to reduce spam
                return await response.edit(text=text, **kwargs)

            # Repost since we haven't done so yet
            if kwargs.get("document"):
                del kwargs["disable_web_page_preview"]
                response = await msg.reply_document(**kwargs)
            else:
                response = await msg.reply(text,
                                           reply_to_message_id=msg.message_id,
                                           **kwargs)
            await msg.delete()
            return response

        raise ValueError(f"Unknown response mode '{mode}'")
