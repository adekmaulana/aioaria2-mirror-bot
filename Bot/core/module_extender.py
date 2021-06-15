import importlib
import inspect
from types import ModuleType
from typing import TYPE_CHECKING, Any, Iterable, MutableMapping, Optional, Type

from .. import module, modules, util
from .base import Base

if TYPE_CHECKING:
    from .bot import Bot


class ModuleExtender(Base):
    # Initialized during instantiation
    modules: MutableMapping[str, module.Module]

    def __init__(self: "Bot", **kwargs: Any) -> None:
        self.modules = {}

        super().__init__(**kwargs)

    def load_module(self: "Bot",
                    cls: Type[module.Module],
                    *,
                    comment: Optional[str] = None) -> None:
        self.log.info(f"Loading {cls.format_desc(comment)}")

        if cls.name in self.modules:
            old = type(self.modules[cls.name])
            raise module.ExistingModuleError(old, cls)

        mod = cls(self)
        mod.comment = comment
        self.register_listeners(mod)
        self.register_commands(mod)
        self.modules[cls.name] = mod

    def unload_module(self: "Bot", mod: module.Module) -> None:
        cls = type(mod)
        self.log.info(f"Unloading {mod.format_desc(mod.comment)}")

        self.unregister_listeners(mod)
        self.unregister_commands(mod)
        del self.modules[cls.name]

    def _load_all_from_metamod(self: "Bot",
                               submodules: Iterable[ModuleType],
                               *,
                               comment: str = None) -> None:
        for module_mod in submodules:
            for sym in dir(module_mod):
                cls = getattr(module_mod, sym)
                if (inspect.isclass(cls) and issubclass(cls, module.Module) and
                        not cls.disabled):
                    self.load_module(cls, comment=comment)

    def load_all_modules(self: "Bot") -> None:
        self.log.info("Loading modules")
        self._load_all_from_metamod(modules.submodules)
        self.log.info("All modules loaded.")

    def unload_all_modules(self: "Bot") -> None:
        self.log.info("Unloading modules...")

        for mod in list(self.modules.values()):
            self.unload_module(mod)

        self.log.info("All modules unloaded.")

    async def reload_module_pkg(self: "Bot") -> None:
        self.log.info("Reloading base module class...")
        await util.run_sync(importlib.reload, module)

        self.log.info("Reloading master module...")
        await util.run_sync(importlib.reload, modules)
