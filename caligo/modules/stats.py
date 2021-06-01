import asyncio
from typing import Any, ClassVar, Optional

import pyrogram

from .. import command, module, util

USEC_PER_HOUR = 60 * 60 * 1000000
USEC_PER_DAY = USEC_PER_HOUR * 24


def _calc_pct(num1: int, num2: int) -> str:
    if not num2:
        return "0"

    return "{:.1f}".format((num1 / num2) * 100).rstrip("0").rstrip(".")


def _calc_ph(stat: int, uptime: int) -> str:
    up_hr = max(1, uptime) / USEC_PER_HOUR
    return "{:.1f}".format(stat / up_hr).rstrip("0").rstrip(".")


def _calc_pd(stat: int, uptime: int) -> str:
    up_day = max(1, uptime) / USEC_PER_DAY
    return "{:.1f}".format(stat / up_day).rstrip("0").rstrip(".")


class StatsModule(module.Module):
    name: ClassVar[str] = "Stats"

    db: Any
    lock: asyncio.Lock

    async def get(self, key: str) -> Optional[Any]:
        collection = await self.db.find_one({"_id": self.name})
        if collection is not None:
            return collection.get(key)

        return None

    async def inc(self, key: str, value: int) -> None:
        await self.db.find_one_and_update({"_id": self.name},
                                          {"$inc": {
                                              key: value
                                          }},
                                          upsert=True)

    async def delete(self, key: str) -> None:
        await self.db.find_one_and_update({"_id": self.name},
                                          {"$unset": {
                                              key: ""
                                          }})

    async def put(self, key: str, value: int) -> None:
        await self.db.find_one_and_update({"_id": self.name},
                                          {"$set": {
                                              key: value
                                          }},
                                          upsert=True)

    async def on_load(self) -> None:
        self.db = self.bot.get_db("stats")

        if await self.get("stop_time_usec") or await self.get("uptime"):
            self.log.info("Migrating stats timekeeping format")

        last_time = await self.get("stop_time_usec")
        if last_time is not None:
            await self.inc("uptime", util.time.usec() - last_time)
            await self.delete("stop_time_usec")

        uptime = await self.get("uptime")
        if uptime is not None:
            await self.put("start_time_usec", self.bot.start_time_us - uptime)
            await self.delete("uptime")

    async def on_start(self, time_us: int) -> None:
        # Initialize start_time_usec for new instances
        if not await self.db.find_one({"_id": self.name}):
            await self.inc("start_time_usec", time_us)

    async def on_message(self, msg: pyrogram.types.Message) -> None:
        stat = "sent" if msg.outgoing else "received"
        await self.bot.log_stat(stat)

        if msg.sticker:
            sticker_stat = stat + "_stickers"
            await self.bot.log_stat(sticker_stat)

    async def on_message_edit(self, msg: pyrogram.types.Message) -> None:
        stat = "sent" if msg.outgoing else "received"
        await self.bot.log_stat(stat + "_edits")

    async def on_command(
        self,
        cmd: command.Command,  # skipcq: PYL-W0613
        msg: pyrogram.types.Message  # skipcq: PYL-W0613
    ) -> None:
        await self.bot.log_stat("processed")

    async def on_stat_event(self, key: str) -> None:
        await self.inc(key, 1)

    async def get_start_time(self) -> int:
        return await self.get("start_time_usec") or self.bot.start_time_us

    @command.desc("Show chat stats (pass `reset` to reset stats)")
    @command.usage('["reset" to reset stats?]', optional=True)
    @command.alias("stat")
    async def cmd_stats(self, ctx: command.Context) -> str:
        if ctx.input == "reset":
            await self.db.find_one_and_delete({"_id": self.name})
            await self.on_load()
            await self.on_start(util.time.usec())
            return "__All stats have been reset.__"

        start_time: Optional[int] = await self.get("start_time_usec")
        if start_time is None:
            start_time = util.time.usec()
            await self.put("start_time_usec", start_time)
        uptime = util.time.usec() - start_time

        sent: int = await self.get("sent") or 0
        sent_stickers: int = await self.get("sent_stickers") or 0
        sent_edits: int = await self.get("sent_edits") or 0
        recv: int = await self.get("received") or 0
        recv_stickers: int = await self.get("received_stickers") or 0
        recv_edits: int = await self.get("received_edits") or 0
        processed: int = await self.get("processed") or 0
        stickers: int = await self.get("stickers_created") or 0

        return util.text.join_map(
            {
                "Total time elapsed":
                    util.time.format_duration_us(uptime),
                "Messages received":
                    f"{recv} ({_calc_ph(recv, uptime)}/h) • {_calc_pct(recv_stickers, recv)}% are stickers • {_calc_pct(recv_edits, recv)}% were edited",
                "Messages sent":
                    f"{sent} ({_calc_ph(sent, uptime)}/h) • {_calc_pct(sent_stickers, sent)}% are stickers • {_calc_pct(sent_edits, sent)}% were edited",
                "Total messages sent":
                    f"{_calc_pct(sent, sent + recv)}% of all accounted messages",
                "Commands processed":
                    f"{processed} ({_calc_ph(processed, uptime)}/h) • {_calc_pct(processed, sent)}% of sent messages",
                "Stickers created":
                    f"{stickers} ({_calc_pd(stickers, uptime)}/day)",
            },
            heading="Stats since last reset",
        )
