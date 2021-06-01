from . import (
    aria2,
    async_helpers,
    config,
    error,
    file,
    git,
    image,
    misc,
    system,
    text,
    tg,
    time,
    version,
)

BotConfig = config.BotConfig()
File = file.File

run_sync = async_helpers.run_sync
