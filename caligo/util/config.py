import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


class BotConfig:

    def __init__(self) -> None:
        if os.path.isfile("config.env"):
            load_dotenv("config.env")

        config = {
            "api_id": os.environ.get("API_ID"),
            "api_hash": os.environ.get("API_HASH"),
            "bot_token": os.environ.get("BOT_TOKEN"),
            "container": os.environ.get("CONTAINER") == "True",
            "db_uri": os.environ.get("DB_URI"),
            "download_path": os.environ.get("DOWNLOAD_PATH"),
            "gdrive_folder_id": os.environ.get("G_DRIVE_FOLDER_ID"),
            "gdrive_index_link": os.environ.get("G_DRIVE_INDEX_LINK"),
            "gdrive_secret": os.environ.get("G_DRIVE_SECRET"),
            "github_repo": os.environ.get("GITHUB_REPO"),
            "github_token": os.environ.get("GITHUB_TOKEN"),
            "heroku_api_key": os.environ.get("HEROKU_API_KEY"),
            "heroku_app_name": os.environ.get("HEROKU_APP"),
            "mirror_enabled": os.environ.get("MIRROR_MODULE") == "enable",
            "string_session": os.environ.get("STRING_SESSION"),
        }

        for key, value in config.items():
            if value == "" and key == "api_id":
                value = 0
            elif value == "":
                value = None

            setattr(self, key, value)

    def __getattr__(self, name: str) -> Any:
        val = self.__getattribute__(name)
        if name == "download_path":
            return Path(val) if val is not None else Path.home() / "downloads"
        if name == "gdrive_index_link":
            return val.rstrip("/") if val is not None else val
        if name == "gdrive_secret":
            return json.loads(val) if val is not None else val
        if name == "github_repo":
            return val if val is not None else "adekmaulana/caligo"

        return val

    def __getitem__(self, item: str) -> Any:
        return self.__getattr__(item)
