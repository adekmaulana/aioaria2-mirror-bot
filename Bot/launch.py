import asyncio
import logging
import sys

import aiorun
from pyrogram.session import Session

from .core import Bot

log = logging.getLogger("Launch")
aiorun.logger.disabled = True
Session.notice_displayed = True


def main() -> None:
    """Main entry point for the default bot launcher."""

    if sys.platform == "win32":
        policy = asyncio.WindowsProactorEventLoopPolicy()
        asyncio.set_event_loop_policy(policy)
    else:
        try:
            import uvloop
        except ImportError:
            pass
        else:
            uvloop.install()
            log.info("Using uvloop event loop")

    log.info("Initializing bot")
    loop = asyncio.new_event_loop()
    aiorun.run(Bot.create_and_run(loop=loop), loop=loop)
