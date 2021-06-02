from typing import TYPE_CHECKING, Any

from motor.core import AgnosticCollection
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .base import Base

if TYPE_CHECKING:
    from .bot import Bot


class DataBase(Base):
    db: AsyncIOMotorDatabase
    db_client: AsyncIOMotorClient

    def __init__(self: "Bot", **kwargs: Any):
        self._init_db()

        self.db = self.db_client.get_database("caligo")

        super().__init__(**kwargs)

    def _init_db(self) -> None:
        self.db_client = AsyncIOMotorClient(self.getConfig["db_uri"], connect=False)

    async def close_db(self) -> None:
        self.db_client.close()

    def get_db(self: "Bot", name: str) -> AgnosticCollection:
        return self.db.get_collection(name)
