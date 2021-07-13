import inspect
from types import ModuleType as PluginType
from typing import TYPE_CHECKING, Any, Iterable, MutableMapping, Optional, Type

from bot import plugin, plugins
from bot.error import ExistingPluginError

from .bot_mixin_base import BotMixinBase

if TYPE_CHECKING:
    from .bot import Bot


class PluginExtender(BotMixinBase):
    # Initialized during instantiation
    plugins: MutableMapping[str, plugin.Plugin]

    def __init__(self: "Bot", **kwargs: Any) -> None:
        # Initialize plugin map
        self.plugins = {}

        # Propagate initialization to other mixins
        super().__init__(**kwargs)

    def load_plugin(
        self: "Bot", cls: Type[plugin.Plugin], *, comment: Optional[str] = None
    ) -> None:
        self.log.info(f"Loading {cls.format_desc(comment)}")

        if cls.name in self.plugins:
            old = type(self.plugins[cls.name])
            raise ExistingPluginError(old, cls)

        plug = cls(self)
        plug.comment = comment
        self.register_listeners(plug)
        self.register_commands(plug)
        self.plugins[cls.name] = plug

    def unload_plugin(self: "Bot", plug: plugin.Plugin) -> None:
        cls = type(plug)
        self.log.info(f"Unloading {plug.format_desc(plug.comment)}")

        self.unregister_listeners(plug)
        self.unregister_commands(plug)
        del self.plugins[cls.name]

    def _load_all_from_metaplug(
        self: "Bot", subplugins: Iterable[PluginType], *, comment: str = None
    ) -> None:
        for plug in subplugins:
            for sym in dir(plug):
                cls = getattr(plug, sym)
                if inspect.isclass(cls) and issubclass(cls, plugin.Plugin) and not cls.disabled:
                    self.load_plugin(cls, comment=comment)

    # noinspection PyTypeChecker,PyTypeChecker
    def load_all_plugins(self: "Bot") -> None:
        self.log.info("Loading plugins")
        self._load_all_from_metaplug(plugins.subplugins)
        self.log.info("All plugins loaded.")

    def unload_all_pluginss(self: "Bot") -> None:
        self.log.info("Unloading plugins...")

        # Can't modify while iterating, so collect a list first
        for plug in list(self.plugins.values()):
            self.unload_plugin(plug)

        self.log.info("All plugins unloaded.")