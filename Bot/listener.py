from typing import Any, Callable, Optional

from pyrogram import filters
from pyrogram.filters import Filter

ListenerFunc = Any
Decorator = Callable[[ListenerFunc], ListenerFunc]


def priority(_prio: int) -> Decorator:
    """Sets priority on the given listener function."""

    def prio_decorator(func: ListenerFunc) -> ListenerFunc:
        setattr(func, "_listener_priority", _prio)
        return func

    return prio_decorator


def pattern(_pattern: str) -> Decorator:
    """Sets regex filters on the given listener function."""

    def regex_decorator(func: ListenerFunc) -> ListenerFunc:
        setattr(func, "_listener_regex", filters.regex(_pattern))
        return func

    return regex_decorator


class Listener:
    event: str
    func: ListenerFunc
    module: Any
    priority: int
    regex: Optional[Filter]

    def __init__(self, event: str, func: ListenerFunc, mod: Any,
                 prio: int, regex: Optional[Filter]) -> None:
        self.event = event
        self.func = func
        self.module = mod
        self.priority = prio
        self.regex = regex

    def __lt__(self, other: "Listener") -> bool:
        return self.priority < other.priority
