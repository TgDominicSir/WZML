from secrets import token_hex

from .... import task_dict, task_dict_lock, LOGGER
from ...ext_utils.bot_utils import sync_to_async
from ...ext_utils.task_manager import (
    check_running_tasks,
    stop_duplicate_check,
    limit_checker,
)
from ...mirror_leech_utils.gdrive_utils.download import GoogleDriveDownload
from ...mirror_leech_utils.status_utils.gdrive_status import GoogleDriveStatus
from ...mirror_leech_utils.status_utils.queue_status import QueueStatus
from ...telegram_helper.message_utils import send_status_message


async def add_gd_download(listener, path):
    gid = token_hex(5)

    if limit_exceeded := await limit_checker(listener):
        await listener.on_download_error(limit_exceeded, is_limit=True)
        return

    add_to_queue, event = await check_running_tasks(listener)
    if add_to_queue:
        LOGGER.info(f"Added to Queue/Download: {listener.name or 'GDrive Download'}")
        async with task_dict_lock:
            task_dict[listener.mid] = QueueStatus(listener, gid, "dl")
        await listener.on_download_start()
        if listener.multi <= 1:
            await send_status_message(listener.message)
        await event.wait()
        if listener.is_cancelled:
            return

    drive = GoogleDriveDownload(listener, path)
    async with task_dict_lock:
        task_dict[listener.mid] = GoogleDriveStatus(listener, drive, gid, "dl")

    if add_to_queue:
        LOGGER.info(f"Start Queued Download from GDrive: {listener.name or 'GDrive Download'}")
    else:
        LOGGER.info(f"Download from GDrive: {listener.name or 'GDrive Download'}")
        await listener.on_download_start()
        if listener.multi <= 1:
            await send_status_message(listener.message)

    await sync_to_async(drive.download)
