import math
from typing import Any, AsyncIterator, ClassVar, Dict, Optional, Tuple

import aiohttp

from .. import command, module, util


class HerokuManager(module.Module):
    name: ClassVar[str] = "Heroku"

    api_key: str
    app_name: str

    apps: Dict[str, Any]
    account: Dict[str, Any]
    http: aiohttp.ClientSession

    uri: str
    useragent: str

    async def on_load(self) -> None:
        self.api_key = self.bot.getConfig["heroku_api_key"]
        self.app_name = self.bot.getConfig["heroku_app_name"]
        if self.api_key is None or self.app_name is None:
            self.log.warning("Heroku module credential not satisfy.")
            self.bot.unload_module(self)
            return

        self.http = self.bot.http

        self.uri = "https://api.heroku.com"
        self.useragent = (
            "Mozilla/5.0 (Linux; Android 11; SM-G975F) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/90.0.4430.210 Mobile Safari/537.36"
        )
        self.account = await self.get_account()

        self.apps = {}
        async for app_name, app_id in self.get_account_apps():
            self.apps[app_name] = app_id

    async def request(
        self, path: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[Any, Any]:
        headers = {
            "User-Agent": self.useragent,
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/vnd.heroku+json; version=3",
        }

        if options is not None:
            headers.update(options)

        async with self.http.get(path, headers=headers) as resp:
            if resp.status != 200:
                ret = {"status": resp.status, "error": {"reason": resp.reason}}
                self.log.info(util.tg.pretty_print_entity(ret))
                return ret

            return await resp.json()

    async def get_account(self) -> Dict[Any, Any]:
        path = self.uri + "/account"
        return await self.request(path)

    async def get_account_quota(self) -> Dict[str, Any]:
        options = {
            "Accept": "application/vnd.heroku+json; version=3.account-quotas"
        }
        path = self.uri + f"/accounts/{self.account['id']}/actions/get-quota"

        return await self.request(path, options)

    async def get_account_apps(self) -> AsyncIterator[Tuple[str, int]]:
        path = self.uri + "/apps"
        apps = await self.request(path)
        for app in apps:
            yield app["name"], app["id"]

    @command.desc("Check your Free Dyno hours quota you've used this month.")
    @command.alias("dyno")
    async def cmd_dynousage(self, ctx: command.Context) -> Optional[str]:
        await ctx.respond("Pulling information...")

        ret = await self.get_account_quota()

        quota = ret["account_quota"]
        quota_used = ret["quota_used"]

        # Account quota remaining this month
        remaining_quota = quota - quota_used
        percentage = math.floor(remaining_quota / quota * 100)
        minutes_remaining = remaining_quota / 60
        hours = math.floor(minutes_remaining / 60)
        minutes = math.floor(minutes_remaining % 60)

        # Account apps quota used this month
        apps = ret["apps"]
        for app in apps:
            if app["app_uuid"] == self.apps.get(self.app_name):
                appQuota = app.get("quota_used")
                appQuotaUsed = appQuota / 60
                appPercentage = math.floor(appQuota * 100 / quota)
                break
        else:
            appQuotaUsed = 0
            appPercentage = 0

        appHours = math.floor(appQuotaUsed / 60)
        appMinutes = math.floor(appQuotaUsed % 60)

        head = util.text.join_map(
            {
                 "Hours": f"{hours}h",
                 "Minutes": f"{minutes}m"
            },
            heading=f"Account remaining ({percentage}%) this month"
        )
        body = util.text.join_map(
            {
                "Hours": f"{appHours}h",
                "Minutes": f"{appMinutes}m",
            },
            heading=f"App[{self.app_name}] usage ({appPercentage}%) this month"
        )

        return head + "\n\n" + body
