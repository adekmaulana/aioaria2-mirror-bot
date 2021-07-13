from typing import TYPE_CHECKING, Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from bot import util

from .bot_mixin_base import BotMixinBase

if TYPE_CHECKING:
    from .bot import Bot


class DataBase(BotMixinBase):
    db: AsyncIOMotorDatabase
    _db: AsyncIOMotorClient

    def __init__(self: "Bot", **kwargs: Any):
        self._init_db()

        self.db = self._db.get_database("bot")

        super().__init__(**kwargs)

    def _init_db(self: "Bot") -> None:
        self._db = AsyncIOMotorClient(self.config["db_uri"], connect=False)

    async def close_db(self: "Bot") -> None:
        await util.run_sync(self._db.close)