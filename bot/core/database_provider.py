from typing import TYPE_CHECKING, Any

from .bot_mixin_base import BotMixinBase

from bot import util

if TYPE_CHECKING:
    from .bot import Bot


class DatabaseProvider(BotMixinBase):
    db: util.db.AsyncDB

    def __init__(self: "Bot", **kwargs: Any):
        client = util.db.AsyncClient(self.config["db_uri"], connect=False)
        self.db = client.get_database("bot")

        super().__init__(**kwargs)
