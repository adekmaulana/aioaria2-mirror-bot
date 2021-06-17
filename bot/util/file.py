import asyncio
from datetime import datetime, timedelta
from mimetypes import guess_type
from os.path import join
from urllib import parse
from typing import Any, Optional, Tuple

from aiopath import AsyncPath
from pyrogram.types import Message

from .async_helpers import run_sync
from .misc import human_readable_bytes as human
from .time import format_duration_td as time, sec


class File:

    _content: Any
    _index_link: Optional[str]
    _invoker: Any
    _name: str
    _path: AsyncPath
    _start_time: Any

    def __init__(self, path: AsyncPath) -> None:
        self._path = path

        self._name = ""
        self._content = None
        self._invoker = None
        self._index_link = None
        self._start_time = None

    @property
    def name(self) -> str:
        if not self._name:
            filePath = str(self._path.absolute())
            dirPath = str(self._path.parent.absolute())
            if filePath.startswith(dirPath):
                start = len(dirPath) + 1
                self._name = AsyncPath(filePath[start:]).parts[0]
            else:
                self._name = self._path.parts[-1]

        return self._name

    @property
    def path(self) -> AsyncPath:
        return self._path

    @property
    def dir(self) -> AsyncPath:
        return self.path.parent.absolute()

    @property
    def mime_type(self) -> Optional[str]:
        return guess_type(self.path)[0]

    @property
    def content(self) -> Any:
        return self._content

    @content.setter
    def content(self, val) -> None:
        self._content = val

    @property
    def invoker(self) -> Message:
        return self._invoker

    @invoker.setter
    def invoker(self, val) -> None:
        self._invoker = val

    @property
    def index_link(self) -> Optional[str]:
        link = None
        if self._index_link is not None:
            link = join(self._index_link, parse.quote(self.name))

        return self._index_link if self._index_link is None else link

    @index_link.setter
    def index_link(self, val) -> None:
        self._index_link = val

    @property
    def start_time(self) -> int:
        return self._start_time

    @start_time.setter
    def start_time(self, val) -> None:
        self._start_time = val

    async def progress_string(self) -> Tuple[Optional[str], bool, Optional[str]]:
        file = self.content
        progress = None
        status, response = await run_sync(file.next_chunk, num_retries=5)
        if status:
            after = sec() - self.start_time
            size = status.total_size
            current = status.resumable_progress
            percent = current / size
            speed = round(current / after, 2)
            eta = timedelta(seconds=int(round((size - current) / speed)))
            bullets = "●" * int(round(percent * 10)) + "○"
            if len(bullets) > 10:
                bullets = bullets.replace("○", "")

            space = '    ' * (10 - len(bullets))
            progress = (
                f"`{self.name}`\n"
                f"Status: **Uploading**\n"
                f"Progress: [{bullets + space}] {round(percent * 100)}%\n"
                f"__{human(current)} of {human(size)} @ "
                f"{human(speed, postfix='/s')}\neta - {time(eta)}__\n\n")

        if response is None and progress is not None:
            return progress, False, None

        size = response.get("size")
        mirrorLink = response.get("webContentLink")
        text = (f"**GoogleDrive Link**: [{self.name}]({mirrorLink}) "
                f"(__{human(int(size))}__)")
        if self.index_link is not None:
            text += f"\n\n__Shareable link__: [Here]({self.index_link})."

        return None, True, text

    async def progress(self, update: Optional[bool] = True) -> None:
        invoker = self.invoker

        done = False
        last_update_time = None
        link = None
        while not done:
            progress, done, link = await self.progress_string()
            now = datetime.now()
            if invoker is not None and progress is not None and (
                    last_update_time is None or (now - last_update_time
                                                 ).total_seconds() >= 5):
                await invoker.edit(progress)

                last_update_time = now

            await asyncio.sleep(0.1)

        if invoker is not None and update is True and link is not None:
            await invoker.reply(link)
            await invoker.delete()
