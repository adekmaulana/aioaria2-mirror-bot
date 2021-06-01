import asyncio
import base64
import pickle
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, AsyncIterator, ClassVar, Dict, Iterable, List, Optional, Set, Tuple, Union

import aiofile
import pyrogram
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from oauthlib.oauth2.rfc6749.errors import InvalidGrantError

from .. import command, module, util

FOLDER = "application/vnd.google-apps.folder"
MIME_TYPE = {
    "application/gzip": "📦",
    "application/octet-stream": "⚙️",
    "application/rar": "📦",
    "application/vnd.google-apps.folder": "📁️",
    "application/vnd.rar": "📦",
    "application/x-7z-compressed": "📦",
    "application/x-bzip": "📦",
    "application/x-bzip2": "📦",
    "application/x-rar": "📦",
    "application/x-tar": "📦",
    "application/zip": "📦",
    "audio/aac": "🎵",
    "audio/mp4": "🎵",
    "audio/mpeg": "🎵",
    "audio/ogg": "🎵",
    "audio/wav": "🎵",
    "audio/x-opus+ogg": "🎵",
    "image/gif": "🖼️",
    "image/jpeg": "🖼️",
    "image/png": "🖼️",
    "video/mp4": "🎥️",
    "video/x-matroska": "🎥️"
}
PATTERN = re.compile(r"(?<=/folders/)([\w-]+)|(?<=%2Ffolders%2F)([\w-]+)|"
                     r"(?<=/file/d/)([\w-]+)|(?<=%2Ffile%2Fd%2F)([\w-]+)|"
                     r"(?<=id=)([\w-]+)|(?<=id%3D)([\w-]+)")
DOMAIN = re.compile(r"https?:\/\/(?:www\.|:?www\d+\.|(?!www))"
                    r"([a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9])\.[^\s]{2,}")


def getIdFromUrl(url: Any) -> Any:
    try:
        return PATTERN.search(url)[0]
    except (TypeError, IndexError):
        return url


class GoogleDrive(module.Module):
    name: ClassVar[str] = "GoogleDrive"
    disabled: ClassVar[bool] = not util.BotConfig.mirror_enabled

    configs: Dict[str, Any]
    creds: Optional[Credentials]
    db: Any
    service: Resource

    aria2: Any
    cache: Dict[int, int]
    copy_tasks: Set[Tuple[int, str]]
    index_link: str
    parent_id: str
    task: Set[Tuple[int, asyncio.Task]]

    getDirectLink: util.aria2.DirectLinks

    async def on_load(self) -> None:
        self.creds = None
        self.db = self.bot.get_db("gdrive")
        self.index_link = self.bot.getConfig["gdrive_index_link"]
        self.parent_id = self.bot.getConfig["gdrive_folder_id"]
        self.task = set()

        self.cache = {}
        self.copy_tasks = set()

        try:
            creds = (await self.db.find_one({"_id": self.name}))["creds"]
        except (KeyError, TypeError):
            self.configs = self.bot.getConfig["gdrive_secret"]
            if not self.configs:
                self.log.warning(f"{self.name} module secret not satisfy.")
                self.bot.unload_module(self)
                return
        else:
            self.aria2 = self.bot.modules["Aria2"]
            self.creds = await util.run_sync(pickle.loads, creds)
            # service will be overwrite if credentials is expired
            self.service = await util.run_sync(build,
                                               "drive",
                                               "v3",
                                               credentials=self.creds,
                                               cache_discovery=False)

    async def on_start(self, _: int) -> None:
        self.getDirectLink = util.aria2.DirectLinks(self.bot.http)

    @command.desc("Check your GoogleDrive credentials")
    @command.alias("gdauth")
    async def cmd_gdcheck(self, ctx: command.Context  # skipcq: PYL-W0613
                          ) -> Tuple[str, int]:
        return "You are all set.", 5

    @command.desc("Clear/Reset your GoogleDrive credentials")
    @command.alias("gdreset")
    async def cmd_gdclear(self, ctx: command.Context) -> Optional[Tuple[str,
                                                                        int]]:
        if not self.creds:
            return "__Credentials already empty.__", 5

        await self.db.delete_one({"_id": self.name})
        await asyncio.gather(self.on_load(),
                             ctx.respond("__Credentials cleared.__"))

    async def getAccessToken(self, message: pyrogram.types.Message) -> str:
        flow = InstalledAppFlow.from_client_config(
            self.configs, ["https://www.googleapis.com/auth/drive"],
            redirect_uri=self.configs["installed"]["redirect_uris"][0])
        auth_url, _ = flow.authorization_url(access_type="offline",
                                             prompt="consent")

        await self.bot.respond(message, "Check your **Saved Message.**")
        async with self.bot.conversation("me", timeout=60) as conv:
            request = await conv.send_message(
                f"Please visit the link:\n{auth_url}\n"
                "And reply the token here.\n**You have 60 seconds**.")

            try:
                response = await conv.get_response()
            except asyncio.TimeoutError:
                await request.delete()
                return "⚠️ <u>Timeout no token receive</u>"

        await self.bot.respond(message, "Token received...")
        token = response.text

        try:
            await asyncio.gather(request.delete(), response.delete(),
                                 util.run_sync(flow.fetch_token, code=token))
        except InvalidGrantError:
            return ("⚠️ **Error fetching token**\n\n"
                    "__Refresh token is invalid, expired, revoked, "
                    "or does not match the redirection URI.__")

        self.creds = flow.credentials
        credential = await util.run_sync(pickle.dumps, self.creds)

        await self.db.find_one_and_update({"_id": self.name},
                                          {"$set": {
                                              "creds": credential
                                          }},
                                          upsert=True)
        await self.on_load()

        return "Credentials created."

    async def authorize(self,
                        message: pyrogram.types.Message) -> Optional[bool]:
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.log.info("Refreshing credentials")
                await util.run_sync(self.creds.refresh, Request())

                credential = await util.run_sync(pickle.dumps, self.creds)
                await self.db.find_one_and_update(
                    {"_id": self.name}, {"$set": {
                        "creds": credential
                    }})
            else:
                await asyncio.gather(
                    self.bot.respond(message,
                                     "Credential is empty, generating..."),
                    asyncio.sleep(2.5))

                ret = await self.getAccessToken(message)

                await self.bot.respond(message, ret)
                if self.creds is None:
                    return False

            await self.on_load()

    async def getInfo(self, identifier: str,
                      fields: Iterable[str]) -> Dict[str, Any]:
        fields = ", ".join(fields)

        return await util.run_sync(self.service.files().get(
            fileId=identifier, fields=fields, supportsAllDrives=True).execute)

    async def copyFile(self, file_id: str, parent_id: Optional[str] = None) -> str:
        metadata = {}
        if parent_id is not None:
            metadata["parents"] = [parent_id]
        elif parent_id is None and self.parent_id is not None:
            metadata["parents"] = [self.parent_id]

        file = await util.run_sync(self.service.files().copy(
            body=metadata, fileId=file_id, supportsAllDrives=True).execute)
        return file["id"]

    async def copyFolder(self, target: str, *, parent_id: Optional[str] = None,
                         name: Optional[str] = None, msg_id: Optional[int] = None
                         ) -> AsyncIterator[asyncio.Task]:
        query = f"'{target}' in parents"

        async for contents in self.searchContent(query=query, limit=1000):
            if msg_id is not None:
                self.cache[msg_id] += len(contents)

            for content in contents:
                if content["mimeType"] == FOLDER:
                    # Dont count folder
                    if msg_id is not None:
                        self.cache[msg_id] -= 1
                    childFolder = await self.createFolder(content["name"],
                                                          folderId=parent_id)
                    async for task in self.copyFolder(target=content["id"],
                                                      parent_id=childFolder,
                                                      name=name, msg_id=msg_id):
                        yield task
                else:
                    yield self.bot.loop.create_task(self.copyFile(
                                                    content["id"],
                                                    parent_id=parent_id),
                                                    name=name)
                    await asyncio.sleep(0.5)

    async def createFolder(self,
                           folderName: str,
                           folderId: Optional[str] = None) -> str:
        folder_metadata: Dict[str, Any] = {
            "name": folderName,
            "mimeType": "application/vnd.google-apps.folder"
        }
        if folderId is not None:
            folder_metadata["parents"] = [folderId]
        elif folderId is None and self.parent_id is not None:
            folder_metadata["parents"] = [self.parent_id]

        folder = await util.run_sync(self.service.files().create(
            body=folder_metadata, fields="id", supportsAllDrives=True).execute)
        return folder["id"]

    async def uploadFolder(
        self,
        sourceFolder: Path,
        *,
        gid: Optional[str] = None,
        parent_id: Optional[str] = None,
        msg: Optional[pyrogram.types.Message] = None
    ) -> AsyncIterator[asyncio.Task]:
        for content in sourceFolder.iterdir():
            if content.is_dir():
                childFolder = await self.createFolder(content.name, parent_id)
                async for task in self.uploadFolder(content,
                                                    gid=gid,
                                                    parent_id=childFolder,
                                                    msg=msg):
                    yield task
            elif content.is_file():
                file = util.File(content)
                content = await self.uploadFile(file, parent_id, msg)
                if isinstance(content, str):  # Skip because file size is 0
                    continue

                yield self.bot.loop.create_task(file.progress(update=False),
                                                name=gid)
                await asyncio.sleep(0.5)

    async def uploadFile(self,
                         file: Union[util.File, util.aria2.Download],
                         parent_id: Optional[str] = None,
                         msg: Optional[pyrogram.types.Message] = None
                         ) -> Union[MediaFileUpload, str]:
        body: Dict[str, Any] = {"name": file.name, "mimeType": file.mime_type}
        if parent_id is not None:
            body["parents"] = [parent_id]
        elif parent_id is None and self.parent_id is not None:
            body["parents"] = [self.parent_id]

        if file.path.stat().st_size > 0:
            media_body = MediaFileUpload(file.path,
                                         mimetype=file.mime_type,
                                         resumable=True,
                                         chunksize=50 * 1024 * 1024)
            content = await util.run_sync(self.service.files().create,
                                          body=body,
                                          media_body=media_body,
                                          fields="id, size, webContentLink",
                                          supportsAllDrives=True)
        else:
            media_body = MediaFileUpload(file.path, mimetype=file.mime_type)
            content = await util.run_sync(self.service.files().create(
                body=body,
                media_body=media_body,
                fields="id, size, webContentLink",
                supportsAllDrives=True).execute)

            return content.get("id")

        if isinstance(file, util.aria2.Download):
            content.gid, content.name, content.start_time = (file.gid, file.name,
                                                             util.time.sec())
        elif isinstance(file, util.File):
            file.content, file.start_time, file.invoker = (content,
                                                           util.time.sec(),
                                                           msg)
            if self.index_link is not None:
                file.index_link = self.index_link

        return content

    async def downloadFile(self, ctx: command.Context,
                           msg: pyrogram.types.Message) -> Optional[Path]:
        download_path = self.bot.getConfig["download_path"]

        before = util.time.sec()
        last_update_time = None
        human = util.misc.human_readable_bytes
        time = util.time.format_duration_td
        if msg.document:
            file_name = msg.document.file_name
        elif msg.audio:
            file_name = msg.audio.file_name
        elif msg.video:
            file_name = msg.video.file_name
        elif msg.sticker:
            file_name = msg.sticker.file_name
        elif msg.photo:
            date = datetime.fromtimestamp(msg.photo.date)
            file_name = f"photo_{date.strftime('%Y-%m-%d_%H-%M-%S')}.jpg"
        elif msg.voice:
            date = datetime.fromtimestamp(msg.voice.date)
            file_name = f"audio_{date.strftime('%Y-%m-%d_%H-%M-%S')}.ogg"
        else:
            file_name = None

        def prog_func(current: int, total: int) -> None:
            nonlocal last_update_time

            percent = current / total
            after = util.time.sec() - before
            now = datetime.now()

            try:
                speed = round(current / after, 2)
                eta = timedelta(seconds=int(round((total - current) / speed)))
            except ZeroDivisionError:
                speed = 0
                eta = timedelta(seconds=0)
            bullets = "●" * int(round(percent * 10)) + "○"
            if len(bullets) > 10:
                bullets = bullets.replace("○", "")

            space = '    ' * (10 - len(bullets))
            progress = (
                f"`{file_name}`\n"
                f"Status: **Downloading**\n"
                f"Progress: [{bullets + space}] {round(percent * 100)}%\n"
                f"__{human(current)} of {human(total)} @ "
                f"{human(speed, postfix='/s')}\neta - {time(eta)}__\n\n")
            # Only edit message once every 5 seconds to avoid ratelimits
            if last_update_time is None or (
                    now - last_update_time).total_seconds() >= 5:
                self.bot.loop.create_task(ctx.respond(progress))

                last_update_time = now

        file_path = download_path / file_name
        file_path = await ctx.bot.client.download_media(msg,
                                                        file_name=file_path,
                                                        progress=prog_func)

        return Path(file_path) if file_path is not None else file_path

    async def searchContent(self, query: str,
                            limit: int) -> AsyncIterator[List[Dict[str, Any]]]:
        fields = "nextPageToken, files(name, id, mimeType, webViewLink)"
        pageToken = None

        while True:
            response = await util.run_sync(self.service.files().list(
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                q=query,
                spaces="drive",
                corpora="allDrives",
                fields=fields,
                pageSize=limit,
                orderBy="folder, modifiedTime desc, name asc",
                pageToken=pageToken).execute)

            yield response.get("files", [])

            pageToken = response.get("nextPageToken", None)
            if pageToken is None:
                break

    @command.desc("Delete your GoogleDrive file/folder")
    @command.usage("[file id or folder id]")
    @command.alias("gdrm", "gddel", "gddelete")
    async def cmd_gdremove(self, ctx: command.Context, *,
                           identifier: Optional[str] = None
                           ) -> Union[str, Tuple[str, int]]:
        if not ctx.input and not identifier:
            return "__Pass the id of content to delete it__", 5
        if ctx.input and not identifier:
            identifier = getIdFromUrl(ctx.input)

        await util.run_sync(self.service.files().delete(
                            fileId=identifier, supportsAllDrives=True).execute)

        return f"__Deleted:__ `{identifier}`"

    @command.desc("Copy public GoogleDrive folder/file into your own")
    @command.usage("[file id or folder id]")
    @command.alias("gdcp")
    async def cmd_gdcopy(self, ctx: command.Context) -> Union[str,
                                                              Tuple[str, int]]:
        if not ctx.input and not ctx.msg.reply_to_message:
            return "__Input the id of the file/folder or reply with abort__", 5
        if ctx.msg.reply_to_message and ctx.input != "abort":
            return "__Replying to message only for aborting task__", 5

        if ctx.msg.reply_to_message:
            reply_msg_id = ctx.msg.reply_to_message.message_id
            for msg_id, identifier in self.copy_tasks.copy():
                if msg_id == reply_msg_id:
                    await self.cmd_gdremove(ctx, identifier=identifier)
                    break
            else:
                return "__Replied message is not task__", 5

            return "__Aborted__", 1

        await ctx.respond("Gathering...")
        identifier = getIdFromUrl(ctx.input)

        try:
            content = await self.getInfo(identifier, ["id", "name", "mimeType"])
        except HttpError as e:
            content = None
            if "'location': 'fileId'" in str(e):
                return "__Invalid input of id.__", 5

        if content["mimeType"] == FOLDER:
            cancelled = False
            counter = 0
            progress_string = ""
            last_update_time = None
            self.cache[ctx.msg.message_id] = 0

            self.copy_tasks.add((ctx.msg.message_id, content["id"]))
            parentFolder = await self.createFolder(content["name"])
            async for task in self.copyFolder(target=content["id"],
                                              parent_id=parentFolder,
                                              name=content["name"],
                                              msg_id=ctx.msg.message_id):
                try:
                    await task
                except HttpError as e:
                    if "'reason': 'notFound'" in str(e):
                        cancelled = True
                        break

                    raise
                else:
                    counter += 1
                    now = datetime.now()
                    length = self.cache[ctx.msg.message_id]
                    percent = round(((counter / length) * 100), 2)
                    progress_string = (f"__Copying {content['name']}"
                                       f": [{counter}/{length}] {percent}%__")
                    if last_update_time is None or (now - last_update_time
                                                    ).total_seconds() >= 5 and (
                                                    progress_string != ""):
                        await ctx.respond(progress_string)
                        last_update_time = now

            del self.cache[ctx.msg.message_id]
            if cancelled:
                self.copy_tasks.remove((ctx.msg.message_id, content["id"]))
                try:
                    await self.cmd_gdremove(ctx, identifier=parentFolder)
                except Exception:  # skipcq: PYL-W0703
                    return "__Aborted, but failed to delete the content__", 5

                return "__Transmission aborted__", 5

            ret = await self.getInfo(parentFolder, ["webViewLink"])
        else:
            task = self.bot.loop.create_task(self.copyFile(content["id"]))
            self.copy_tasks.add((ctx.msg.message_id, content["id"]))
            try:
                await task
            except asyncio.CancelledError:
                return "__Transmission aborted__", 5

            file_id = task.result()
            ret = await self.getInfo(file_id, ["webViewLink"])

        self.copy_tasks.remove((ctx.msg.message_id, content["id"]))

        return f"Copying success: [{content['name']}]({ret['webViewLink']})"

    @command.desc("Mirror Magnet/Torrent/Link/Message Media into GoogleDrive")
    @command.usage("[Magnet/Torrent/Link or reply to message]")
    async def cmd_gdmirror(self, ctx: command.Context) -> Optional[str]:
        if not ctx.input and not ctx.msg.reply_to_message:
            return "__Either link nor media found.__"
        if ctx.input and ctx.msg.reply_to_message:
            return "__Can't pass link while replying to message.__"

        if ctx.msg.reply_to_message:
            reply_msg = ctx.msg.reply_to_message

            if reply_msg.media:
                task = self.bot.loop.create_task(
                    self.downloadFile(ctx, reply_msg))
                self.task.add((ctx.msg.message_id, task))
                try:
                    await task
                except asyncio.CancelledError:
                    return "__Transmission aborted.__"
                else:
                    path = task.result()
                    self.task.remove((ctx.msg.message_id, task))
                    if path is None:
                        return "__Something went wrong, file probably corrupt__"

                if path.suffix == ".torrent":
                    async with aiofile.async_open(path, "rb") as afp:
                        types = base64.b64encode(await afp.read())
                else:
                    file = util.File(path)
                    await self.uploadFile(file, msg=ctx.msg)

                    task = self.bot.loop.create_task(file.progress())
                    self.task.add((ctx.msg.message_id, task))
                    try:
                        await task
                    except asyncio.CancelledError:
                        return "__Transmission aborted.__"
                    else:
                        self.task.remove((ctx.msg.message_id, task))

                    return
            elif reply_msg.text:
                types = reply_msg.text
            else:
                return "__Unsupported types of download.__"
        else:
            types = ctx.input

        if isinstance(types, str):
            match = DOMAIN.match(types)
            if match:
                await ctx.respond("Generating direct link...")

                direct = await self.getDirectLink(match.group(1), types)
                if direct is not None and isinstance(direct, list):
                    if len(direct) == 1:
                        types = direct[0]["url"]
                    elif len(direct) > 1:
                        text = "Multiple links found, choose one of the following:\n\n"
                        for index, mirror in enumerate(direct):
                            text += f"`{index + 1}`. {mirror['name']}\n"
                        text += "\nSend only the number here."
                        async with self.bot.conversation(ctx.msg.chat.id,
                                                         timeout=60) as conv:
                            request = await conv.send_message(text)

                            try:
                                response = await conv.get_response(
                                    filters=pyrogram.filters.me)
                            except asyncio.TimeoutError:
                                await request.delete()
                                types = direct[0]["url"]
                            else:
                                await asyncio.gather(request.delete(),
                                                     response.delete())
                                index = int(response.text) - 1
                                types = direct[index]["url"]
                elif direct is not None:
                    types = direct

        try:
            ret = await self.aria2.addDownload(types, ctx.msg)
            return ret
        except NameError:
            return "__Mirroring torrent file/url needs Aria2 loaded.__"

    @command.pattern(r"(parent)=(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')|"
                     r"(limit)=(\d+)|(filter)=(file|folder)|"
                     r"(name)=(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')|"
                     r"(q)=(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')")
    @command.usage("[parent=\"folderId\"] [name=\"file/folder name\"] "
                   "[limit=number] [filter=file/folder]"
                   "[q=\"search query\"], **single/double quote important for "
                   "parent, name and q parameters**",
                   optional=True)
    @command.desc("Search through all Google Drive by given query/parent/name")
    @command.alias("gdlist", "gdls")
    async def cmd_gdsearch(self,
                           ctx: command.Context) -> Union[str, Tuple[str, int]]:
        if ctx.input and not ctx.matches:
            return "__Invalid parameters of input.__", 5

        options: Dict[str, Any] = {}
        for match in ctx.matches:
            for index, option in enumerate(match.groups()):
                if option is not None and match.group(index + 2) is not None:
                    match = match.group(index + 2)
                    options[option] = match

                    # Remove quote/double quote and override
                    if option not in ("limit", "filter"):
                        options[option] = match.removesuffix(
                            match[0]).removeprefix(match[0])

                    break

        await ctx.respond("Collecting...")

        filters = options.get("filter")
        limit = int(options.get("limit", 15))
        name = options.get("name")
        parent = getIdFromUrl(options.get("parent"))
        if limit > 1000:
            return "__Can't use limit more than 1000.__", 5
        if filters is not None:
            filters = (f"mimeType = '{FOLDER}'" if filters == "folder" else
                       f"mimeType != '{FOLDER}'")

        if all(x is not None for x in [parent, name, filters]):
            query = f"'{parent}' in parents and (name contains '{name}' and {filters})"
        elif parent is not None and name is not None and filters is None:
            query = f"'{parent}' in parents and (name contains '{name}')"
        elif parent is not None and name is None and filters is not None:
            query = f"'{parent}' in parents and ({filters})"
        elif parent is not None and name is None and filters is None:
            query = f"'{parent}' in parents"
        elif parent is None and name is not None and filters is not None:
            query = f"name contains '{name}' and {filters}"
        elif parent is None and name is not None and filters is None:
            query = f"name contains '{name}'"
        elif parent is None and name is None and filters is not None:
            query = filters
        else:
            query = ""

        try:
            # Ignore given parent, name, filter options if q present
            query = options["q"]
        except KeyError:
            pass

        output = ""
        count = 0

        try:
            async for contents in self.searchContent(query=query, limit=limit):
                for content in contents:
                    if count >= limit:
                        break

                    count += 1
                    output += (
                        MIME_TYPE.get(content["mimeType"], "📄") +
                        f" [{content['name']}]({content['webViewLink']})\n")

                if count >= limit:
                    break
        except HttpError as e:
            if "'location': 'q'" in str(e):
                return "__Invalid parameters of query.__", 5
            if "'location': 'fileId'" in str(e):
                return "__Invalid parameters of parent.__", 5

            raise

        if query == "":
            query = "Not specified"

        return f"**Google Drive Search**:\n{query}\n\n**Result**\n{output}"
