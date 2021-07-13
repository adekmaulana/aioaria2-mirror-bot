from typing import TYPE_CHECKING, Any

BotMixinBase: Any
if TYPE_CHECKING:
    from .bot import Bot

    BotMixinBase = Bot
else:
    import abc

    BotMixinBase = abc.ABC