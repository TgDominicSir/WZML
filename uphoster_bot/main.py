import os
import sys
import time
import re
import asyncio
import logging
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from pyrogram.errors import FloodWait

from .bot_config import Config
from .database import db
from .utils import get_readable_file_size, get_readable_time
from .uploaders.multi_upload import MultiUphosterUpload

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
LOGGER = logging.getLogger("UphosterBot")

# Global dictionaries
active_tasks = {}  # Task ID -> Task info dict

class CustomFilters:
    @staticmethod
    def authorized(client, message: Message):
        user = message.from_user
        if not user:
            return False

        # Owner is always authorized
        if user.id == Config.OWNER_ID:
            return True

        # Sudo users are always authorized
        sudo_list = [int(x.strip()) for x in Config.SUDO_USERS.split() if x.strip().isdigit()]
        if user.id in sudo_list:
            return True

        # Private chats are authorized for any user if no general auth chat is configured
        if message.chat.type.name == "PRIVATE":
            if not Config.AUTHORIZED_CHATS.strip():
                return True

        # Authorized chats filter
        auth_chats = [int(x.strip()) for x in Config.AUTHORIZED_CHATS.split() if x.strip().isdigit()]
        if message.chat.id in auth_chats:
            return True

        return False

    @staticmethod
    def sudo(client, message: Message):
        user = message.from_user
        if not user:
            return False
        if user.id == Config.OWNER_ID:
            return True
        sudo_list = [int(x.strip()) for x in Config.SUDO_USERS.split() if x.strip().isdigit()]
        return user.id in sudo_list

def get_progress_bar(percentage):
    completed = int(percentage / 10)
    remaining = 10 - completed
    return "█" * completed + "░" * remaining

class StandaloneListener:
    """Standalone listener implementing the required callbacks for MultiUphosterUpload."""
    def __init__(self, bot, message, name, user_id, size):
        self.bot = bot
        self.message = message
        self.name = name
        self.user_id = user_id
        self.size = size
        self.is_cancelled = False
        self.task_id = str(message.id)

        # Status variables
        self.status = "Initializing..."
        self.processed_bytes = 0
        self.speed = 0
        self.eta_seconds = 0
        self.link = None
        self.done = False
        self.error_msg = None

        # For speed calculation
        self.start_time = time.time()
        self.last_update_time = time.time()
        self.last_bytes = 0

    async def update_progress(self, current, total):
        if self.is_cancelled:
            raise asyncio.CancelledError()

        self.processed_bytes = current
        self.size = total

        now = time.time()
        interval = now - self.last_update_time
        if interval >= 1.0 or current == total:
            chunk = current - self.last_bytes
            self.speed = chunk / interval if interval > 0 else 0
            self.last_bytes = current
            self.last_update_time = now

            # Calculate ETA
            remaining_bytes = total - current
            self.eta_seconds = remaining_bytes / self.speed if self.speed > 0 else 0

            # Edit message to show live progress
            percentage = (current / total) * 100 if total > 0 else 0
            bar = get_progress_bar(percentage)

            text = (
                f"📥 <b>Downloading:</b> {self.name}\n"
                f"<code>[{bar}]</code> {percentage:.2f}%\n"
                f"• <b>Size:</b> {get_readable_file_size(current)} / {get_readable_file_size(total)}\n"
                f"• <b>Speed:</b> {get_readable_file_size(self.speed)}/s\n"
                f"• <b>ETA:</b> {get_readable_time(self.eta_seconds)}\n"
            )
            try:
                await self.message.edit_text(text)
            except FloodWait as f:
                await asyncio.sleep(f.value)
            except Exception:
                pass

    async def on_upload_complete(self, link, files, folders, mime_type, dir_id=""):
        self.done = True
        self.link = link

        # Build nice results message
        dest_links = []
        if isinstance(link, dict):
            for s, res in link.items():
                if "error" in res:
                    dest_links.append(f"• <b>{s.capitalize()}</b>: ❌ Error: {res['error']}")
                elif "link" in res:
                    dest_links.append(f"• <b>{s.capitalize()}</b>: <a href='{res['link']}'>Link</a>")
        else:
            dest_links.append(f"• <b>Link</b>: <a href='{link}'>Link</a>")

        results_str = "\n".join(dest_links)

        success_text = (
            f"✅ <b>Upload Complete!</b>\n\n"
            f"<b>File Name:</b> <code>{self.name}</code>\n"
            f"<b>File Size:</b> {get_readable_file_size(self.size)}\n\n"
            f"<b>Destinations:</b>\n{results_str}"
        )
        try:
            await self.message.edit_text(success_text, disable_web_page_preview=True)
        except Exception as e:
            LOGGER.error(f"Error editing complete message: {e}")

        active_tasks.pop(self.task_id, None)

    async def on_upload_error(self, error):
        self.done = True
        self.error_msg = error

        error_text = (
            f"❌ <b>Upload Failed!</b>\n\n"
            f"<b>File Name:</b> <code>{self.name}</code>\n"
            f"<b>Error:</b> <code>{error}</code>"
        )
        try:
            await self.message.edit_text(error_text)
        except Exception:
            pass

        active_tasks.pop(self.task_id, None)

def get_authorized_filter():
    return filters.create(lambda _, __, msg: CustomFilters.authorized(_, msg))

def get_sudo_filter():
    return filters.create(lambda _, __, msg: CustomFilters.sudo(_, msg))

# Create the pyrogram/wzgram Bot client
app = Client(
    "uphoster_bot",
    api_id=Config.TELEGRAM_API,
    api_hash=Config.TELEGRAM_HASH,
    bot_token=Config.BOT_TOKEN,
    workdir="uphoster_bot"
)

@app.on_message(filters.command("start") & get_authorized_filter())
async def start_handler(client, message: Message):
    welcome_text = (
        "👋 <b>Welcome to the Standalone Uphosters Upload Bot (Powered by wzgram)!</b>\n\n"
        "Configure your API keys in <code>/usetting</code>, then send any direct download link or reply to any Telegram file with the <code>/uphoster</code> command to download and upload to GoFile, PixelDrain, BuzzHeavier, DevUploads, or VikingFile!"
    )
    await message.reply_text(welcome_text)

@app.on_message(filters.command("usetting") & get_authorized_filter())
async def usetting_handler(client, message: Message):
    user_id = message.from_user.id
    user_dict = db.get_user_data(user_id)

    # Get user choices
    selected_service = user_dict.get("UPHOSTER_SERVICE", "gofile")

    text = (
        f"⚙️ <b>User Settings :</b>\n"
        f"• <b>Name:</b> {message.from_user.mention}\n"
        f"• <b>User ID:</b> <code>{user_id}</code>\n"
        f"• <b>Current Destination(s):</b> <code>{selected_service}</code>\n\n"
        f"Click the buttons below to toggle your preferred upload destinations or configure keys!"
    )

    # Build settings keyboard
    keyboard = []
    # Toggle Buttons for Destinations
    services = ["gofile", "buzzheavier", "pixeldrain", "devuploads", "vikingfile"]
    selected_list = [s.strip().lower() for s in selected_service.split(",") if s.strip()]

    row = []
    for s in services:
        status_marker = "✅" if s in selected_list else "❌"
        row.append(InlineKeyboardButton(f"{status_marker} {s.capitalize()}", callback_data=f"toggle_dest:{s}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    # Set key buttons
    keyboard.append([
        InlineKeyboardButton("🔑 Config Keys", callback_data="show_keys_menu"),
        InlineKeyboardButton("❌ Close", callback_data="close_settings")
    ])

    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

@app.on_callback_query(filters.regex(r"^toggle_dest:(.*)"))
async def toggle_dest_callback(client, query):
    user_id = query.from_user.id
    user_dict = db.get_user_data(user_id)
    selected_service = user_dict.get("UPHOSTER_SERVICE", "gofile")
    selected_list = [s.strip().lower() for s in selected_service.split(",") if s.strip()]

    service_to_toggle = query.matches[0].group(1)

    if service_to_toggle in selected_list:
        if len(selected_list) > 1:
            selected_list.remove(service_to_toggle)
        else:
            await query.answer("At least one upload destination must remain active!", show_alert=True)
            return
    else:
        selected_list.append(service_to_toggle)

    new_dest = ",".join(selected_list)
    db.update_user_data(user_id, "UPHOSTER_SERVICE", new_dest)
    await query.answer(f"Toggled {service_to_toggle.capitalize()}!")

    # Refresh settings message
    user_dict = db.get_user_data(user_id)
    text = (
        f"⚙️ <b>User Settings :</b>\n"
        f"• <b>Name:</b> {query.from_user.mention}\n"
        f"• <b>User ID:</b> <code>{user_id}</code>\n"
        f"• <b>Current Destination(s):</b> <code>{new_dest}</code>\n\n"
        f"Click the buttons below to toggle your preferred upload destinations or configure keys!"
    )

    keyboard = []
    services = ["gofile", "buzzheavier", "pixeldrain", "devuploads", "vikingfile"]
    row = []
    for s in services:
        status_marker = "✅" if s in selected_list else "❌"
        row.append(InlineKeyboardButton(f"{status_marker} {s.capitalize()}", callback_data=f"toggle_dest:{s}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("🔑 Config Keys", callback_data="show_keys_menu"),
        InlineKeyboardButton("❌ Close", callback_data="close_settings")
    ])

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

@app.on_callback_query(filters.regex(r"^show_keys_menu$"))
async def show_keys_menu_callback(client, query):
    user_id = query.from_user.id
    user_dict = db.get_user_data(user_id)

    text = (
        "🔐 <b>Service Credentials Settings :</b>\n\n"
        f"• <b>GoFile Token:</b> <code>{user_dict.get('GOFILE_TOKEN') or 'Not Set'}</code>\n"
        f"• <b>GoFile Folder ID:</b> <code>{user_dict.get('GOFILE_FOLDER_ID') or 'Not Set'}</code>\n"
        f"• <b>PixelDrain Key:</b> <code>{user_dict.get('PIXELDRAIN_KEY') or 'Not Set'}</code>\n"
        f"• <b>BuzzHeavier Token:</b> <code>{user_dict.get('BUZZHEAVIER_TOKEN') or 'Not Set'}</code>\n"
        f"• <b>BuzzHeavier Folder ID:</b> <code>{user_dict.get('BUZZHEAVIER_FOLDER_ID') or 'Not Set'}</code>\n"
        f"• <b>DevUploads Key:</b> <code>{user_dict.get('DEVUPLOADS_KEY') or 'Not Set'}</code>\n"
        f"• <b>DevUploads Folder ID:</b> <code>{user_dict.get('DEVUPLOADS_FOLDER') or 'Not Set'}</code>\n"
        f"• <b>VikingFile Hash:</b> <code>{user_dict.get('VIKINGFILE_HASH') or 'Not Set'}</code>\n"
        f"• <b>VikingFile Folder ID/Path:</b> <code>{user_dict.get('VIKINGFILE_FOLDER') or 'Not Set'}</code>\n\n"
        "To update any key or folder, use: <code>/setkey [key_name] [value]</code>\n"
        "Example: <code>/setkey gofile_token YOUR_TOKEN</code>\n"
        "Supported keys:\n"
        "<code>gofile_token</code>, <code>gofile_folder_id</code>, <code>pixeldrain_key</code>, <code>buzzheavier_token</code>, <code>buzzheavier_folder_id</code>, <code>devuploads_key</code>, <code>devuploads_folder</code>, <code>vikingfile_hash</code>, <code>vikingfile_folder</code>"
    )

    keyboard = [[
        InlineKeyboardButton("⬅️ Back to Main Settings", callback_data="back_to_settings_main"),
        InlineKeyboardButton("❌ Close", callback_data="close_settings")
    ]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

@app.on_callback_query(filters.regex(r"^back_to_settings_main$"))
async def back_to_settings_main_callback(client, query):
    user_id = query.from_user.id
    user_dict = db.get_user_data(user_id)
    selected_service = user_dict.get("UPHOSTER_SERVICE", "gofile")
    selected_list = [s.strip().lower() for s in selected_service.split(",") if s.strip()]

    text = (
        f"⚙️ <b>User Settings :</b>\n"
        f"• <b>Name:</b> {query.from_user.mention}\n"
        f"• <b>User ID:</b> <code>{user_id}</code>\n"
        f"• <b>Current Destination(s):</b> <code>{selected_service}</code>\n\n"
        f"Click the buttons below to toggle your preferred upload destinations or configure keys!"
    )

    keyboard = []
    services = ["gofile", "buzzheavier", "pixeldrain", "devuploads", "vikingfile"]
    row = []
    for s in services:
        status_marker = "✅" if s in selected_list else "❌"
        row.append(InlineKeyboardButton(f"{status_marker} {s.capitalize()}", callback_data=f"toggle_dest:{s}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("🔑 Config Keys", callback_data="show_keys_menu"),
        InlineKeyboardButton("❌ Close", callback_data="close_settings")
    ])

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

@app.on_callback_query(filters.regex(r"^close_settings$"))
async def close_settings_callback(client, query):
    await query.message.delete()

@app.on_message(filters.command("setkey") & get_authorized_filter())
async def setkey_handler(client, message: Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply_text("⚠️ <b>Usage:</b> <code>/setkey [key_name] [value]</code>\ne.g., <code>/setkey gofile_token XYZ_ABC</code>")
        return

    key_name = parts[1].strip().upper()
    value = parts[2].strip()

    valid_keys = {
        "GOFILE_TOKEN": "GOFILE_TOKEN",
        "GOFILE_FOLDER_ID": "GOFILE_FOLDER_ID",
        "PIXELDRAIN_KEY": "PIXELDRAIN_KEY",
        "BUZZHEAVIER_TOKEN": "BUZZHEAVIER_TOKEN",
        "BUZZHEAVIER_FOLDER_ID": "BUZZHEAVIER_FOLDER_ID",
        "DEVUPLOADS_KEY": "DEVUPLOADS_KEY",
        "DEVUPLOADS_FOLDER": "DEVUPLOADS_FOLDER",
        "VIKINGFILE_HASH": "VIKINGFILE_HASH",
        "VIKINGFILE_FOLDER": "VIKINGFILE_FOLDER"
    }

    if key_name not in valid_keys:
        await message.reply_text(f"❌ <b>Invalid Key!</b> Supported keys:\n<code>" + "\n".join(valid_keys.keys()) + "</code>")
        return

    db.update_user_data(message.from_user.id, valid_keys[key_name], value)
    await message.reply_text(f"✅ Successfully updated <code>{key_name}</code>!")

@app.on_message(filters.command("bsetting") & get_sudo_filter())
async def bsetting_handler(client, message: Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) >= 3:
        # Dynamic update of config
        var_name = parts[1].strip().upper()
        var_value = parts[2].strip()

        if var_name in ("BOT_MAX_TASKS", "DIRECT_LIMIT", "LEECH_LIMIT"):
            try:
                if var_name == "BOT_MAX_TASKS":
                    db.update_bot_settings(var_name, int(var_value))
                else:
                    db.update_bot_settings(var_name, float(var_value))
                await message.reply_text(f"✅ Successfully updated global bot settings: <code>{var_name}</code> = <code>{var_value}</code>")
                return
            except Exception as e:
                await message.reply_text(f"❌ Failed to parse value: {e}")
                return

    text = (
        f"⚙️ <b>Global Bot Settings (Sudo Only) :</b>\n\n"
        f"• <b>BOT_MAX_TASKS:</b> <code>{Config.BOT_MAX_TASKS}</code>\n"
        f"• <b>DIRECT_LIMIT (GB):</b> <code>{Config.DIRECT_LIMIT}</code>\n"
        f"• <b>LEECH_LIMIT (GB):</b> <code>{Config.LEECH_LIMIT}</code>\n\n"
        f"• <b>GoFile API Fallback:</b> <code>{Config.GOFILE_API or 'Not Set'}</code>\n"
        f"• <b>PixelDrain Key Fallback:</b> <code>{Config.PIXELDRAIN_KEY or 'Not Set'}</code>\n"
        f"• <b>BuzzHeavier API Fallback:</b> <code>{Config.BUZZHEAVIER_API or 'Not Set'}</code>\n"
        f"• <b>DevUploads Key Fallback:</b> <code>{Config.DEVUPLOADS_KEY or 'Not Set'}</code>\n"
        f"• <b>VikingFile Hash Fallback:</b> <code>{Config.VIKINGFILE_HASH or 'Not Set'}</code>\n\n"
        "To update limits via command: <code>/bsetting [BOT_MAX_TASKS/DIRECT_LIMIT/LEECH_LIMIT] [value]</code>"
    )
    await message.reply_text(text)

@app.on_message(filters.command("status") & get_authorized_filter())
async def status_handler(client, message: Message):
    if not active_tasks:
        await message.reply_text("💤 <b>No active upload tasks currently running.</b>")
        return

    text = "📊 <b>Active Tasks Status:</b>\n\n"
    for task_id, t in active_tasks.items():
        percentage = (t.processed_bytes / t.size) * 100 if t.size > 0 else 0
        bar = get_progress_bar(percentage)
        text += (
            f"📦 <b>{t.name}</b>\n"
            f"• <b>Status:</b> {t.status}\n"
            f"<code>[{bar}]</code> {percentage:.2f}%\n"
            f"• <b>Size:</b> {get_readable_file_size(t.processed_bytes)} / {get_readable_file_size(t.size)}\n"
            f"• <b>Speed:</b> {get_readable_file_size(t.speed)}/s\n"
            f"• <b>ETA:</b> {get_readable_time(t.eta_seconds)}\n\n"
        )
    await message.reply_text(text)

@app.on_message(filters.command("cancel") & get_authorized_filter())
async def cancel_handler(client, message: Message):
    if not active_tasks:
        await message.reply_text("⚠️ No running tasks to cancel.")
        return

    # Cancel the most recent or matching user task
    user_id = message.from_user.id
    target_task = None
    for task_id, t in active_tasks.items():
        if t.user_id == user_id:
            target_task = t
            break

    if target_task:
        target_task.is_cancelled = True
        await message.reply_text(f"🛑 Cancelling upload task for: <code>{target_task.name}</code>")
    else:
        await message.reply_text("❌ No active task found for you.")

@app.on_message(filters.command("uphoster") & get_authorized_filter())
@app.on_message(filters.regex(r"^/up\s(.*)") & get_authorized_filter())
async def uphoster_main_handler(client, message: Message):
    # Check concurrent task limits
    if Config.BOT_MAX_TASKS > 0 and len(active_tasks) >= Config.BOT_MAX_TASKS:
        await message.reply_text(f"⚠️ <b>Limit Breached:</b> Maximum concurrent bot tasks limit ({Config.BOT_MAX_TASKS}) reached!")
        return

    # Determine the file source: Reply to media or a link
    media = (
        message.reply_to_message.document or
        message.reply_to_message.video or
        message.reply_to_message.audio or
        message.reply_to_message.photo or
        message.reply_to_message.animation or
        message.reply_to_message.voice or
        message.reply_to_message.video_note
        if message.reply_to_message else None
    )

    url = None
    file_name = None
    file_size = 0

    # Check if there is an explicit link in the command text
    text_parts = message.text.split(maxsplit=1)
    if len(text_parts) > 1:
        potential_url = text_parts[1].strip()
        if potential_url.startswith(("http://", "https://")):
            url = potential_url
            file_name = os.path.basename(potential_url).split("?")[0] or "downloaded_file"

    # Check if reply message has a URL
    if not url and message.reply_to_message and message.reply_to_message.text:
        reply_text = message.reply_to_message.text.strip()
        if reply_text.startswith(("http://", "https://")):
            url = reply_text
            file_name = os.path.basename(reply_text).split("?")[0] or "downloaded_file"

    if not media and not url:
        await message.reply_text(
            "⚠️ <b>How to Use:</b>\n"
            "1. Reply to any Telegram file/media with <code>/uphoster</code>\n"
            "2. Send command with a direct link: <code>/uphoster https://example.com/file.zip</code>\n"
            "3. Reply to any message containing a link with <code>/uphoster</code>"
        )
        return

    status_msg = await message.reply_text("⏳ <b>Initializing task...</b>")

    # Retrieve user config
    user_id = message.from_user.id
    user_dict = db.get_user_data(user_id)
    uphoster_service = user_dict.get("UPHOSTER_SERVICE", "gofile")
    services = [s.strip() for s in uphoster_service.split(",") if s.strip()]

    os.makedirs("downloads", exist_ok=True)
    task_id = str(status_msg.id)

    if media:
        # Check Leech Size limit for Telegram downloads
        if hasattr(media, "file_size") and Config.LEECH_LIMIT > 0:
            limit_bytes = Config.LEECH_LIMIT * 1024 * 1024 * 1024
            if media.file_size > limit_bytes:
                await status_msg.edit_text(f"⚠️ <b>Limit Breached:</b> File size ({get_readable_file_size(media.file_size)}) exceeds Telegram Leech limit ({Config.LEECH_LIMIT} GB)!")
                return

        # It is a Telegram file
        if hasattr(media, "file_name") and media.file_name:
            file_name = media.file_name
        elif hasattr(media, "mime_type"):
            ext = media.mime_type.split("/")[-1]
            file_name = f"telegram_file_{time.time():.0f}.{ext}"
        else:
            file_name = f"telegram_file_{time.time():.0f}"

        file_size = media.file_size if hasattr(media, "file_size") else 0
        local_path = os.path.join("downloads", f"{time.time():.0f}_{file_name}")

        listener = StandaloneListener(client, status_msg, file_name, user_id, file_size)
        active_tasks[task_id] = listener
        listener.status = "Downloading from Telegram..."

        # Download the Telegram media
        try:
            await client.download_media(
                media,
                file_name=local_path,
                progress=listener.update_progress
            )
        except asyncio.CancelledError:
            if os.path.exists(local_path):
                os.remove(local_path)
            await listener.on_upload_error("Task cancelled by user.")
            return
        except Exception as e:
            if os.path.exists(local_path):
                os.remove(local_path)
            await listener.on_upload_error(f"Telegram Download Error: {e}")
            return

    elif url:
        # Check Direct URL size limit
        listener = StandaloneListener(client, status_msg, file_name, user_id, 0)
        active_tasks[task_id] = listener
        listener.status = "Checking URL size..."

        local_path = os.path.join("downloads", f"{time.time():.0f}_{file_name}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        raise Exception(f"HTTP Error {resp.status}")

                    file_size = int(resp.headers.get("content-length", 0))
                    listener.size = file_size

                    if Config.DIRECT_LIMIT > 0 and file_size > (Config.DIRECT_LIMIT * 1024 * 1024 * 1024):
                        active_tasks.pop(task_id, None)
                        await status_msg.edit_text(f"⚠️ <b>Limit Breached:</b> File size ({get_readable_file_size(file_size)}) exceeds direct URL limit ({Config.DIRECT_LIMIT} GB)!")
                        return

                    listener.status = "Downloading from URL..."
                    downloaded = 0
                    with open(local_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(1024 * 1024):
                            if listener.is_cancelled:
                                raise asyncio.CancelledError()
                            f.write(chunk)
                            downloaded += len(chunk)
                            await listener.update_progress(downloaded, file_size)
        except asyncio.CancelledError:
            if os.path.exists(local_path):
                os.remove(local_path)
            await listener.on_upload_error("Task cancelled by user.")
            return
        except Exception as e:
            if os.path.exists(local_path):
                os.remove(local_path)
            await listener.on_upload_error(f"URL Download Error: {e}")
            return

    # Phase 2: Uploading
    listener.status = "Uploading to Uphoster(s)..."
    try:
        ddl = MultiUphosterUpload(listener, local_path, services)
        await ddl.upload()
    except Exception as e:
        await listener.on_upload_error(f"Upload Error: {e}")
    finally:
        # Clean up the downloaded file
        if os.path.exists(local_path):
            try:
                os.remove(local_path)
            except Exception:
                pass

@app.on_message(filters.command("restart") & get_sudo_filter())
async def restart_handler(client, message: Message):
    await message.reply_text("🔄 <b>Restarting Bot...</b>")
    os.execl(sys.executable, sys.executable, "-m", "uphoster_bot.main")

async def main():
    LOGGER.info("Starting Standalone Uphosters Bot (wzgram)...")
    Config.load()

    # Sync bot settings from MongoDB
    bot_settings = db.get_bot_settings()
    for k, v in bot_settings.items():
        if hasattr(Config, k):
            setattr(Config, k, v)

    # Register/Set bot commands
    await app.start()
    try:
        await app.set_bot_commands([
            BotCommand("start", "Start the bot"),
            BotCommand("uphoster", "Download and Upload file to Uphosters"),
            BotCommand("usetting", "User settings / upload destinations"),
            BotCommand("setkey", "Set user API keys"),
            BotCommand("bsetting", "Bot limits & fallbacks settings"),
            BotCommand("status", "Show active tasks status"),
            BotCommand("cancel", "Cancel current active task"),
            BotCommand("restart", "Restart the bot (Sudo only)")
        ])
        LOGGER.info("Bot commands successfully registered.")
    except Exception as e:
        LOGGER.warning(f"Failed to set bot commands: {e}")

    LOGGER.info("Bot is running!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
