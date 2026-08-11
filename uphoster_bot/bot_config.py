import os
from logging import getLogger

LOGGER = getLogger(__name__)

class Config:
    # Core Bot Credentials (mandatory)
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    TELEGRAM_API = int(os.getenv("TELEGRAM_API", "0"))
    TELEGRAM_HASH = os.getenv("TELEGRAM_HASH", "")
    OWNER_ID = int(os.getenv("OWNER_ID", "0"))

    # Authorized Chats & Sudo Users (space-separated IDs)
    AUTHORIZED_CHATS = os.getenv("AUTHORIZED_CHATS", "")
    SUDO_USERS = os.getenv("SUDO_USERS", "")

    # MongoDB URL (Mandatory as per user instruction: Use mongodb only)
    DATABASE_URL = os.getenv("DATABASE_URL", "")

    # Global/Fallback Upload Credentials
    GOFILE_API = os.getenv("GOFILE_API", "")
    GOFILE_FOLDER_ID = os.getenv("GOFILE_FOLDER_ID", "")
    GOFILE_AUTO_CREATE_FOLDER = os.getenv("GOFILE_AUTO_CREATE_FOLDER", "False").lower() in ("true", "1", "yes")

    PIXELDRAIN_KEY = os.getenv("PIXELDRAIN_KEY", "")

    BUZZHEAVIER_API = os.getenv("BUZZHEAVIER_API", "")

    DEVUPLOADS_KEY = os.getenv("DEVUPLOADS_KEY", "")
    DEVUPLOADS_FOLDER = os.getenv("DEVUPLOADS_FOLDER", "")

    VIKINGFILE_HASH = os.getenv("VIKINGFILE_HASH", "")
    VIKINGFILE_FOLDER = os.getenv("VIKINGFILE_FOLDER", "")

    # Admin Controls (from leech code)
    BOT_MAX_TASKS = int(os.getenv("BOT_MAX_TASKS", "0"))
    DIRECT_LIMIT = float(os.getenv("DIRECT_LIMIT", "0.0"))
    LEECH_LIMIT = float(os.getenv("LEECH_LIMIT", "0.0"))

    # Command Suffix (Optional)
    CMD_SUFFIX = os.getenv("CMD_SUFFIX", "")

    # Telegraph Author Details
    AUTHOR_NAME = os.getenv("AUTHOR_NAME", "Uphoster Upload Bot")
    AUTHOR_URL = os.getenv("AUTHOR_URL", "https://t.me/WZML_X")

    @classmethod
    def load(cls):
        # Load from config.py file if it exists
        try:
            from . import config
            for attr in dir(config):
                if attr.isupper() and hasattr(cls, attr):
                    setattr(cls, attr, getattr(config, attr))
            LOGGER.info("Config loaded from local config.py")
        except ImportError:
            try:
                import config
                for attr in dir(config):
                    if attr.isupper() and hasattr(cls, attr):
                        setattr(cls, attr, getattr(config, attr))
                LOGGER.info("Config loaded from local config.py")
            except ImportError:
                LOGGER.info("Local config.py not found. Using environment variables.")
