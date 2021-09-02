from typing import TYPE_CHECKING, Any

from .bot_mixin_base import BotMixinBase

from bot import util

if TYPE_CHECKING:
    from .bot import Bot


class DatabaseProvider(BotMixinBase):
    db: util.db.AsyncDB

    def __init__(self: "Bot", **kwargs: Any):
        db_uri = self.config["db_uri"]
        if not db_uri:
            raise RuntimeError("DB_URI environment variable not set")

        client = util.db.AsyncClient(db_uri, connect=False)
        self.db = client.get_database("bot")

        super().__init__(**kwargs)
