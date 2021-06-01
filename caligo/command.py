import asyncio
import re
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    List,
    Match,
    Optional,
    Pattern,
    Sequence,
    Union,
)

import pyrogram

if TYPE_CHECKING:
    from .core import Bot

CommandFunc = Union[Callable[..., Coroutine[Any, Any, None]],
                    Callable[..., Coroutine[Any, Any, Any]]]
Decorator = Callable[[CommandFunc], CommandFunc]


def desc(_desc: str) -> Decorator:
    """Sets description on a command function."""

    def desc_decorator(func: CommandFunc) -> CommandFunc:
        setattr(func, "_cmd_description", _desc)
        return func

    return desc_decorator


def usage(_usage: str,
          optional: bool = False,
          reply: bool = False) -> Decorator:
    """Sets argument usage help on a command function."""

    def usage_decorator(func: CommandFunc) -> CommandFunc:
        setattr(func, "_cmd_usage", _usage)
        setattr(func, "_cmd_usage_optional", optional)
        setattr(func, "_cmd_usage_reply", reply)
        return func

    return usage_decorator


def alias(*aliases: str) -> Decorator:
    """Sets aliases on a command function."""

    def alias_decorator(func: CommandFunc) -> CommandFunc:
        setattr(func, "_cmd_aliases", aliases)
        return func

    return alias_decorator


def pattern(_pattern: str) -> Decorator:
    """Sets regex pattern on a command function."""

    def pattern_decorator(func: CommandFunc) -> CommandFunc:
        setattr(func, "_cmd_pattern", re.compile(_pattern))
        return func

    return pattern_decorator


class Command:
    name: str
    desc: str
    usage: str
    usage_optional: bool
    usage_reply: bool
    aliases: Sequence[str]
    pattern: Pattern[str]
    module: Any
    func: CommandFunc

    def __init__(self, name: str, mod: Any, func: CommandFunc) -> None:
        self.name = name
        self.desc = getattr(func, "_cmd_description", None)
        self.usage = getattr(func, "_cmd_usage", None)
        self.usage_optional = getattr(func, "_cmd_usage_optional", False)
        self.usage_reply = getattr(func, "_cmd_usage_reply", False)
        self.aliases = getattr(func, "_cmd_aliases", [])
        self.pattern = getattr(func, "_cmd_pattern", None)
        self.module = mod
        self.func = func


class Context:
    bot: "Bot"
    msg: pyrogram.types.Message
    segments: Sequence[str]
    cmd_len: int
    invoker: str

    response: Optional[pyrogram.types.Message]
    response_mode: Optional[str]

    input: Optional[Union[str, None]]
    args: Sequence[str]
    matches: Optional[List[Match[str]]]

    def __init__(self, bot: "Bot", msg: pyrogram.types.Message,
                 segments: Sequence[str], cmd_len: int,
                 matches: Optional[List[Match[str]]]) -> None:
        self.bot = bot
        self.msg = msg
        self.segments = segments
        self.cmd_len = cmd_len
        self.invoker = segments[0]

        self.response = None
        self.response_mode = None

        self.input = self.msg.text[self.cmd_len:]
        self.matches = matches

    def __getattr__(self, name: str) -> Any:
        if name == "args":
            return self._get_args()

        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'")

    # Argument segments
    def _get_args(self) -> Sequence[str]:
        self.args = self.segments[1:]
        return self.args

    async def respond(
        self,
        text: Optional[str] = None,
        *,
        mode: Optional[str] = None,
        redact: Optional[bool] = None,
        msg: Optional[pyrogram.types.Message] = None,
        reuse_response: bool = False,
        delete_after: Union[int, float] = 0,
        **kwargs: Any,
    ) -> pyrogram.types.Message:

        self.response = await self.bot.respond(
            msg or self.msg,
            text,
            input_arg=self.input,
            mode=mode,
            redact=redact,
            response=self.response
            if reuse_response and mode == self.response_mode else None,
            **kwargs,
        )
        self.response_mode = mode

        if delete_after != 0:

            async def delete() -> bool:
                await asyncio.sleep(delete_after)
                return await self.response.delete()

            self.bot.loop.create_task(delete())

        return self.response

    async def respond_multi(
        self,
        *args: Any,
        mode: Optional[str] = None,
        msg: Optional[pyrogram.types.Message] = None,
        reuse_response: bool = False,
        **kwargs: Any,
    ) -> pyrogram.types.Message:
        # First response is the same
        if self.response:
            # After that, force a reply to the previous response
            if mode is None:
                mode = "reply"

            if msg is None:
                msg = self.response

            if reuse_response is None:
                reuse_response = False

        return await self.respond(*args,
                                  mode=mode,
                                  msg=msg,
                                  reuse_response=reuse_response,
                                  **kwargs)
