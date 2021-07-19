import json
import random
import re
from typing import TYPE_CHECKING, Any, ClassVar, MutableMapping, Optional

from aiopath import AsyncPath
from Crypto.Cipher import AES
from Crypto.Util import Counter

from .. import command, plugin, util
from ..util import crypto

if TYPE_CHECKING:
    from .aria2 import Aria2


class Mega(plugin.Plugin):
    name: ClassVar[str] = "Mega"

    file: MutableMapping[str, MutableMapping[str, Any]]

    async def on_load(self) -> None:
        self.file = {}

    async def api_request(self, file_id: str) -> MutableMapping[str, Any]:
        """Make request to mega.nz API"""
        uid = random.randint(0, 0xFFFFFFFF)
        data = {
            "a": "g",
            "g": 1,
            "p": file_id
        }
        async with self.bot.http.post(
            url=f"https://g.api.mega.co.nz/cs?id={uid + 1}&amp;sid=''",
            data=json.dumps([data]),
        ) as resp:
            return (await resp.json())[0]

    async def cmd_mega(self, ctx: command.Context) -> Optional[str]:
        if not ctx.input:
            return "Mega link not provided"
        
        try:
            url = re.findall(r'\bhttps?://.*mega.*\.nz\S+', ctx.input)[0]
        except IndexError:
            return "Invalid mega link"

        if "file" in url:
            data = re.findall(r'\bfile\/\S+', url)[0].split("/")[1]
            file_id = data.split("#")[0]
            file_key = data.split("#")[1]
        elif "folder" in url or "#F" in url or "#N" in url:
            return "Mega folder download aren't support"
        else:
            data = url.split("#!")[1]
            file_id = data.split("!")[0]
            file_key = data.split("!")[1]

        key = crypto.base64_to_a32(file_key)
        k = (key[0] ^ key[4], key[1] ^ key[5], key[2] ^ key[6], key[3] ^ key[7])
        iv = key[4:6] + (0, 0)
        metaMAC = key[6:8]

        file = await self.api_request(file_id)
        att = crypto.base64_url_decode(file["at"])
        att = crypto.decrypt_attr(att, k)

        kStr = await util.run_sync(crypto.a32_to_str, k)
        counter = Counter.new(128, initial_value=((iv[0] << 32) + iv[1]) << 64)
        aes = AES.new(kStr, AES.MODE_CTR, counter=counter)

        outputFile: AsyncPath = self.bot.config["download_path"] / (att["n"] + ".temp")

        aria2: "Aria2" = self.bot.plugins["Aria2"]  # type: ignore
        gid = await aria2.addDownload(file["g"], ctx, mega=True,
                                      options={"out": att["n"]})
        if not gid:
            return "Invalid response"

        self.file[gid] = {"file": outputFile, "aes": aes}
