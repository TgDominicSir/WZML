# ruff: noqa: E402
try:
    from uvloop import install

    install()
except ImportError:
    pass

from asyncio import new_event_loop, set_event_loop

bot_loop = new_event_loop()
set_event_loop(bot_loop)

from asyncio import Lock
from logging import (
    ERROR,
    INFO,
    WARNING,
    FileHandler,
    StreamHandler,
    basicConfig,
    getLogger,
)
from os import cpu_count
from time import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .core.config_manager import Config

getLogger("niquests").setLevel(WARNING)
getLogger("pyrogram").setLevel(ERROR)
getLogger("apscheduler").setLevel(ERROR)
getLogger("pymongo").setLevel(WARNING)
getLogger("aiohttp").setLevel(WARNING)


bot_start_time = time()

basicConfig(
    format="[%(asctime)s] [%(levelname)s] - %(message)s",
    datefmt="%d-%b-%y %I:%M:%S %p",
    handlers=[FileHandler("log.txt"), StreamHandler()],
    level=INFO,
)

LOGGER = getLogger(__name__)
cpu_no = cpu_count() or 1
threads = max(1, cpu_no // 2)
cores = ",".join(str(i) for i in range(threads))

if cpu_no <= 1 or cpu_no == 2:
    service_cores = ""
else:
    service_cores = ",".join(str(i) for i in range(threads, cpu_no))

bot_cache = {}
DOWNLOAD_DIR = "/usr/src/app/downloads/"
intervals = {"status": {}, "stopAll": False}
user_data = {}
queued_dl = {}
queued_up = {}
status_dict = {}
task_dict = {}
shortener_dict = {}
categories_dict = {}
var_list = [
    "BOT_TOKEN",
    "TELEGRAM_API",
    "TELEGRAM_HASH",
    "OWNER_ID",
    "DATABASE_URL",
    "BASE_URL",
    "UPSTREAM_REPO",
    "UPSTREAM_BRANCH",
]
auth_chats = {}
excluded_extensions = []
sudo_users = []
non_queued_dl = set()
non_queued_up = set()
multi_tags = set()
task_dict_lock = Lock()
queue_dict_lock = Lock()
same_directory_lock = Lock()

if not Config.WEB_ACCESS_PASSWORD:
    from secrets import token_hex

    Config.WEB_ACCESS_PASSWORD = token_hex(32)

scheduler = AsyncIOScheduler(event_loop=bot_loop)
