from typing import TYPE_CHECKING, Any

Base: Any
if TYPE_CHECKING:
    from .bot import Bot

    Base = Bot
else:
    import abc

    Base = abc.ABC
