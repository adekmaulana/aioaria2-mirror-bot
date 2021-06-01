import asyncio
import bisect
from typing import TYPE_CHECKING, Any, MutableMapping, MutableSequence

from pyrogram.filters import Filter
from pyrogram.types import Update

from bot import plugin, util
from bot.listener import Listener, ListenerFunc

from .bot_mixin_base import MixinBase

if TYPE_CHECKING:
    from .bot import Bot


class EventDispatcher(MixinBase):
    # Initialized during instantiation
    listeners: MutableMapping[str, MutableSequence[Listener]]

    def __init__(self: "Bot", **kwargs: Any) -> None:
        # Initialize listener map
        self.listeners = {}

        # Propagate initialization to other mixins
        super().__init__(**kwargs)

    def register_listener(
        self: "Bot",
        plug: plugin.Plugin,
        event: str,
        func: ListenerFunc,
        priority: int = 100,
        filters: Filter = None
    ) -> None:
        listener = Listener(event, func, plug, priority, filters)

        if event in self.listeners:
            bisect.insort(self.listeners[event], listener)
        else:
            self.listeners[event] = [listener]

        self.update_plugin_events()

    def unregister_listener(self: "Bot", listener: Listener) -> None:
        self.listeners[listener.event].remove(listener)
        # Remove list if empty
        if not self.listeners[listener.event]:
            del self.listeners[listener.event]

        self.update_plugin_events()

    def register_listeners(self: "Bot", plug: plugin.Plugin) -> None:
        for event, func in util.misc.find_prefixed_funcs(plug, "on_"):
            done = True
            try:
                self.register_listener(
                    plug, event, func,
                    priority=getattr(func, "_listener_priority", 100),
                    filters=getattr(func, "_listener_filters", None)
                )
                done = True
            finally:
                if not done:
                    self.unregister_listeners(plug)

    def unregister_listeners(self: "Bot", plug: plugin.Plugin) -> None:
        for lst in list(self.listeners.values()):
            for listener in lst:
                if listener.plugin == plug:
                    self.unregister_listener(listener)

    async def dispatch_event(
        self: "Bot", event: str, *args: Any, wait: bool = True, **kwargs: Any
    ) -> None:
        tasks = set()

        try:
            listeners = self.listeners[event]
        except KeyError:
            return None

        if not listeners:
            return

        for lst in listeners:
            if lst.filters:
                for arg in args:
                    if isinstance(arg, Update):
                        permitted: bool = await lst.filters(self.client, arg)
                        if permitted:
                            break

                        continue
                else:
                    continue

            task = self.loop.create_task(lst.func(*args, **kwargs))
            tasks.add(task)

        if not tasks:
            return

        self.log.debug("Dispatching event '%s' with data %s", event, args)
        if wait:
            await asyncio.wait(tasks)