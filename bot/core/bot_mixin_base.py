from typing import TYPE_CHECKING, Any

MixinBase: Any
if TYPE_CHECKING:
    from .bot import BotMixinBase

    MixinBase = Bot
else:
    import abc

    MixinBase = abc.ABC