from asyncio import create_subprocess_shell, gather, sleep
from importlib import import_module
from os import environ, path as ospath, getenv

from aiofiles import open as aiopen
from aiofiles.os import makedirs, remove, path as aiopath
from aioshutil import rmtree


from .. import (
    LOGGER,
    bot_loop,
    auth_chats,
    var_list,
    user_data,
    excluded_extensions,
    sudo_users,
)
from ..helper.ext_utils.bot_utils import cmd_exec
from ..helper.ext_utils.db_handler import database
from .config_manager import Config, BinConfig
from .tg_client import TgClient, db_partition_id


async def load_settings():
    if not Config.DATABASE_URL:
        return
    for p in ["thumbnails", "tokens"]:
        if await aiopath.exists(p):
            await rmtree(p, ignore_errors=True)
    await database.connect()
    if database.db is not None:
        if TgClient.PARTITION:
            PART = str(TgClient.PARTITION)
        else:
            BOT_ID = Config.BOT_TOKEN.split(":", 1)[0]
            PART = db_partition_id(BOT_ID)
            TgClient.PARTITION = PART
        deploy_filter = {"_id": PART}
        try:
            settings = import_module("config")
            config_file = {
                key: value.strip() if isinstance(value, str) else value
                for key, value in vars(settings).items()
                if not key.startswith("__")
            }
        except ModuleNotFoundError:
            config_file = {}
        config_file.update(
            {
                key: value.strip() if isinstance(value, str) else value
                for key, value in environ.items()
                if key in var_list
            }
        )

        old_config = await database.db.settings.deployConfig.find_one(
            deploy_filter, {"_id": 0}
        )

        results = await gather(
            database.db.settings.config.find_one(deploy_filter, {"_id": 0}),
            database.db.settings.files.find_one(deploy_filter, {"_id": 0}),
            database.db.users[PART].find_one(),
        )

        (
            config_dict,
            pf_dict,
            user_exists,
        ) = results

        if old_config is None:
            await database.db.settings.deployConfig.replace_one(
                deploy_filter, config_file, upsert=True
            )
            config_dict = config_dict or {}
            for k, v in config_file.items():
                if v is not None:
                    config_dict.setdefault(k, v)
        elif old_config != config_file:
            LOGGER.info(
                "Updating.. Deploy Config changed, merging new config.py values"
            )
            config_dict = config_dict or {}
            for k, v in config_file.items():
                if k not in old_config or old_config.get(k) != v:
                    if v is not None:
                        config_dict[k] = v
            await database.db.settings.deployConfig.replace_one(
                deploy_filter, config_file, upsert=True
            )
        else:
            LOGGER.info("Updating.. Saved Config imported from MongoDB")
            config_dict = config_dict or {}

        if config_dict:
            Config.load_dict(config_dict)

        if pf_dict:
            for key, value in pf_dict.items():
                if value:
                    file_ = key.replace("__", ".")
                    async with aiopen(file_, "wb+") as f:
                        await f.write(value)

        if user_exists:
            rows = database.db.users[PART].find({})
            async for row in rows:
                uid = row["_id"]
                del row["_id"]
                paths = {
                    "THUMBNAIL": f"thumbnails/{uid}.jpg",
                    "USER_COOKIE_FILE": f"cookies/{uid}/cookies.txt",
                }

                async def save_file(file_path, content):
                    dir_path = ospath.dirname(file_path)
                    if not await aiopath.exists(dir_path):
                        await makedirs(dir_path)
                    if file_path.startswith("cookies/") and file_path.endswith(".txt"):
                        async with aiopen(file_path, "wb") as f:
                            if isinstance(content, str):
                                content = content.encode("utf-8")
                            await f.write(content)
                    else:
                        async with aiopen(file_path, "wb+") as f:
                            if isinstance(content, str):
                                content = content.encode("utf-8")
                            await f.write(content)

                for key, path in paths.items():
                    if row.get(key):
                        await save_file(path, row[key])
                        row[key] = path
                user_data[uid] = row
            LOGGER.info("Users Data has been imported from MongoDB")

async def save_settings():
    if database.db is None:
        return
    config_file = Config.get_all()
    if TgClient.PARTITION:
        PART = str(TgClient.PARTITION)
    else:
        PART = db_partition_id(TgClient.ID)
        TgClient.PARTITION = PART
    deploy_filter = {"_id": PART}
    await database.db.settings.config.update_one(
        deploy_filter, {"$set": config_file}, upsert=True
    )


async def update_variables():
    if (
        Config.LEECH_SPLIT_SIZE > TgClient.MAX_SPLIT_SIZE
        or Config.LEECH_SPLIT_SIZE == 2097152000
        or not Config.LEECH_SPLIT_SIZE
    ):
        Config.LEECH_SPLIT_SIZE = TgClient.MAX_SPLIT_SIZE

    if Config.AUTHORIZED_CHATS:
        aid = Config.AUTHORIZED_CHATS.split()
        for id_ in aid:
            chat_id, *thread_ids = id_.split("|")
            chat_id = int(chat_id.strip())
            if thread_ids:
                thread_ids = list(map(lambda x: int(x.strip()), thread_ids))
                auth_chats[chat_id] = thread_ids
            else:
                auth_chats[chat_id] = []

    if Config.SUDO_USERS:
        aid = Config.SUDO_USERS.split()
        for id_ in aid:
            sudo_users.append(int(id_.strip()))

    if Config.EXCLUDED_EXTENSIONS:
        fx = Config.EXCLUDED_EXTENSIONS.split()
        for x in fx:
            x = x.lstrip(".")
            excluded_extensions.append(x.strip().lower())



async def load_configurations():
    if not await aiopath.exists(".netrc"):
        async with aiopen(".netrc", "w"):
            pass


    PORT = getenv("PORT", "") or "8080"
    if PORT:
        access_pwd = getenv("WEB_ACCESS_PASSWORD", "") or Config.WEB_ACCESS_PASSWORD
        if not access_pwd:
            from secrets import token_bytes

            access_pwd = token_bytes(32).hex()
            Config.WEB_ACCESS_PASSWORD = access_pwd
        env = f"WEB_ACCESS_PASSWORD={access_pwd} "
        bot_loop.create_task(cmd_exec(
            f"{env}gunicorn -k uvicorn.workers.UvicornWorker -w 1 web.wserver:app --bind 0.0.0.0:{PORT}",
            shell=True,
        ))
        bot_loop.create_task(cmd_exec("python3 cron_boot.py", shell=True))

    if Config.DISABLE_STREAM:
        LOGGER.info("Streaming is disabled. Skipping stream server.")
    else:
        from .stream_server import spawn_stream_server

        spawn_stream_server()

    from ..helper.ext_utils.tunnel_monitor import apply_tunnel_url_once

    await apply_tunnel_url_once()
