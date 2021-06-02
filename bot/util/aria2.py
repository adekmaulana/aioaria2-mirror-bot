import json
import re
import socket
from datetime import datetime, timedelta
from mimetypes import guess_type
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib import parse

import aiohttp
from aioaria2 import Aria2WebsocketTrigger
from async_property import async_property
from bs4 import BeautifulSoup


def get_free_port():
    sock = socket.socket()
    sock.bind(('', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class BitTorrent:

    def __init__(self, data: Dict[str, Any]) -> None:
        self._data = data or {}

    def __str__(self):
        return self.info["name"]

    @property
    def announce_list(self) -> Optional[List[List[str]]]:
        return self._data.get("announceList")

    @property
    def comment(self) -> Optional[str]:
        return self._data.get("comment")

    @property
    def creation_date(self) -> datetime:
        return datetime.fromtimestamp(self._data["creationDate"])

    @property
    def mode(self) -> Optional[str]:
        return self._data.get("mode")

    @property
    def info(self) -> Optional[dict]:
        return self._data.get("info")


class File:

    def __init__(self, data: Dict[str, Any]) -> None:
        self._data = data or {}

    def __str__(self):
        return str(self.path)

    def __eq__(self, other):
        return self.path == other.path

    @property
    def index(self) -> int:
        return int(self._data["index"])

    @property
    def path(self) -> Path:
        return Path(self._data["path"])

    @property
    def mime_type(self) -> Optional[str]:
        return guess_type(self.path)[0]

    @property
    def metadata(self) -> bool:
        return str(self.path).startswith("[METADATA]")

    @property
    def length(self) -> int:
        return int(self._data["length"])

    @property
    def completed_length(self) -> int:
        return int(self._data["completedLength"])

    @property
    def selected(self) -> bool:
        return self._data.get("selected") == "true"

    @property
    def uris(self) -> Optional[List[Dict[str, Any]]]:
        return self._data.get("uris")


class Download:

    _bittorrent: Optional[BitTorrent]
    _files: List[File]
    _name: str

    def __init__(self, client: Aria2WebsocketTrigger, data: Dict[str,
                                                                 Any]) -> None:
        self.client = client
        self._data = data or {}

        self._name = ""
        self._files: List[File] = []
        self._bittorrent = None

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return self.gid == other.gid

    @async_property
    async def update(self) -> "Download":
        self._data = await self.client.tellStatus(self.gid)

        self._name = ""
        self._files = []
        self._bittorrent = None

        return self

    @property
    def name(self) -> str:
        if not self._name:
            if self.bittorrent and self.bittorrent.info:
                self._name = self.bittorrent.info["name"]
            elif self.files[0].metadata:
                self._name = str(self.files[0].path)
            else:
                file_path = str(self.files[0].path.absolute())
                dir_path = str(self.dir.absolute())
                if file_path.startswith(dir_path):
                    start_pos = len(dir_path) + 1
                    self._name = Path(file_path[start_pos:]).parts[0]
                else:
                    try:
                        self._name = self.files[0].uris[0]["uri"].split("/")[-1]
                    except IndexError:
                        pass
        return self._name

    @property
    def gid(self) -> str:
        return self._data["gid"]

    @property
    def status(self) -> str:
        return self._data["status"]

    @property
    def active(self) -> bool:
        return self.status == "active"

    @property
    def waiting(self) -> bool:
        return self.status == "waiting"

    @property
    def paused(self) -> bool:
        return self.status == "paused"

    @property
    def failed(self) -> bool:
        return self.status == "error"

    @property
    def complete(self) -> bool:
        return self.status == "complete"

    @property
    def removed(self) -> bool:
        return self.status == "removed"

    @property
    def total_length(self) -> int:
        return int(self._data["totalLength"])

    @property
    def completed_length(self) -> float:
        return float(self._data["completedLength"])

    @property
    def download_speed(self) -> int:
        return int(self._data["downloadSpeed"])

    @property
    def info_hash(self) -> Optional[str]:
        return self._data.get("infoHash")

    @property
    def num_seeders(self) -> Optional[int]:
        try:
            return int(self._data["numSeeders"])
        except ValueError:
            return None

    @property
    def seeder(self) -> bool:
        return self._data["seeder"] == "true"

    @property
    def connections(self) -> int:
        return int(self._data["connections"])

    @property
    def error_code(self) -> Optional[int]:
        try:
            return int(self._data["errorCode"])
        except ValueError:
            return None

    @property
    def error_message(self) -> Optional[str]:
        return self._data.get("errorMessage")

    @property
    def dir(self) -> Path:
        return Path(self._data["dir"])

    @property
    def is_file(self) -> bool:
        return (self.dir / self.name).is_file()

    @property
    def is_dir(self) -> bool:
        return (self.dir / self.name).is_dir()

    @property
    def path(self) -> Path:
        return self.files[0].path

    @property
    def mime_type(self) -> Optional[str]:
        return self.files[0].mime_type

    @property
    def files(self) -> List[File]:
        if not self._files:
            self._files = [File(data) for data in self._data.get("files", [])]

        return self._files

    @property
    def bittorrent(self) -> Optional[BitTorrent]:
        if not self._bittorrent and "bittorrent" in self._data:
            self._bittorrent = BitTorrent(self._data["bittorrent"])
        return self._bittorrent

    @property
    def metadata(self) -> bool:
        return bool(self.followed_by)

    @property
    def followed_by(self) -> List[str]:
        return self._data.get("followedBy", [])

    @property
    def progress(self) -> float:
        try:
            return self.completed_length / self.total_length
        except ZeroDivisionError:
            return 0.0

    @property
    def eta(self) -> float:
        try:
            return round((self.total_length - self.completed_length) /
                         self.download_speed)
        except ZeroDivisionError:
            return 0.0

    @property
    def eta_formatted(self) -> timedelta:
        try:
            return timedelta(seconds=int(self.eta))
        except ZeroDivisionError:
            return timedelta.max

    @async_property
    async def remove(self, force: bool = False) -> bool:
        if force is True:
            func = self.client.forceRemove
        else:
            func = self.client.remove

        res = await func(self.gid)
        if isinstance(res, str):
            return True

        return False

    @async_property
    async def pause(self, force: bool = False) -> bool:
        if force is True:
            func = self.client.forcePause
        else:
            func = self.client.pause

        res = await func(self.gid)
        if isinstance(res, str):
            return True

        return False

    @async_property
    async def resume(self) -> bool:
        res = await self.client.unpause(self.gid)
        if isinstance(res, str):
            return True

        return False


class DirectLinks:

    http: aiohttp.ClientSession

    def __init__(self, http: aiohttp.ClientSession) -> None:
        self.http = http

        self.useragent = (
            "Mozilla/5.0 (Linux; Android 11; SM-G975F) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/90.0.4430.210 Mobile Safari/537.36"
        )

    async def __call__(self, mode: str, url: str) -> Any:
        try:
            func = getattr(self, mode)
        except AttributeError:
            return None

        return await func(url)

    async def androidfilehost(self, url: str) -> List[Dict[str, str]]:
        fid = re.compile(r"\?fid=(\d+)").search(url).group(1)
        uri = "https://androidfilehost.com/libs/otf/mirrors.otf.php"
        async with self.http.get(url, headers={"user-agent": self.useragent},
                                 allow_redirects=True) as r:
            headers = {"origin": "https://androidfilehost.com",
                       "accept-encoding": "gzip, deflate, br",
                       "accept-language": "en-US,en;q=0.9",
                       "user-agent": self.useragent,
                       "content-type": "application/x-www-form-urlencoded; "
                                       "charset=UTF-8",
                       "x-mod-sbb-ctype": "xhr",
                       "accept": "*/*",
                       "referer": url,
                       "authority": "androidfilehost.com",
                       "x-requested-with": "XMLHttpRequest"}
            data = {"submit": "submit", "action": "getdownloadmirrors",
                    "fid": fid}

            async with self.http.post(uri, headers=headers, data=data,
                                      cookies=r.cookies) as resp:
                result = json.loads(await resp.text())
                return result["MIRRORS"]

    async def mediafire(self, url: str) -> Optional[str]:
        async with self.http.get(url) as resp:
            page = BeautifulSoup(await resp.text(), "lxml")
            info = page.find("a", {"aria-label": "Download file"})

            return info["href"]

    async def zippyshare(self, url: str) -> Optional[str]:
        www = re.match(r"https://([\w\d]+).zippyshare", url).group(1)
        async with self.http.get(url) as resp:
            page = BeautifulSoup(await resp.text(), "lxml")
            try:
                js_script = page.find("div", {"class": "center"}
                                      ).find_all("script")[1]
            except IndexError:
                js_script = page.find("div", {"class": "right"}
                                      ).find_all("script")[0]

            for tag in js_script:
                if "document.getElementById('dlbutton')" in tag:
                    url_raw = re.search(r'= (?P<url>\".+\" \+ '
                                        r'(?P<math>\(.+\)) .+);', tag
                                        ).group('url')
                    math = re.search(r'= (?P<url>\".+\" \+ '
                                     r'(?P<math>\(.+\)) .+);', tag
                                     ).group('math')
                    numbers = []
                    expression = []
                    for e in math.strip("()").split():
                        try:
                            numbers.append(int(e))
                        except ValueError:
                            expression.append(e)

                    try:
                        result = None
                        if expression[0] == "%" and expression[2] == "%":
                            first_result = numbers[0] % numbers[1]
                            second_result = numbers[2] % numbers[3]
                            if expression[1] == "+":
                                result = str(first_result + second_result)
                            elif expression[1] == "-":
                                result = str(first_result - second_result)
                            else:
                                raise ValueError("Unexpected value to calculate")
                        else:
                            raise ValueError("Unexpected results of expression")
                    except IndexError:
                        raise ValueError("Unexpected results of array")
                    else:
                        url_raw = url_raw.replace(math, result)
                        link = f"https://{www}.zippyshare.com"

                    if result is None:
                        raise ValueError("Unexpected response, result is empty")

                    for i in url_raw.split("+"):
                        link += i.strip().strip('"')

                    return link

                raise ValueError("Unexpected response, can't find download url")
