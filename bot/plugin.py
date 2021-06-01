import inspect
import logging
import os.path
from typing import TYPE_CHECKING, ClassVar, Optional

if TYPE_CHECKING:
    from .core import Bot


class Plugin:
    # Class variables
    name: ClassVar[str] = "Unnamed"
    disabled: ClassVar[bool] = False

    # Instance variables
    bot: "Bot"
    log: logging.Logger
    comment: Optional[str]

    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        self.log = logging.getLogger(type(self).name.lower().replace(" ", "_"))
        self.comment = None

    @classmethod
    def format_desc(cls, comment: Optional[str] = None):
        _comment = comment + " " if comment else ""
        return f"{_comment}plugin '{cls.name}' ({cls.__name__}) from '{os.path.relpath(inspect.getfile(cls))}'"

    def __repr__(self):
        return "<" + self.format_desc(self.comment) + ">"
