# 🤖 Standalone Uphosters Upload Bot (Powered by wzgram)

A standalone, fast, and feature-rich Telegram Bot dedicated to downloading files/media (from direct URLs or Telegram messages) and uploading them to popular file hosts: **GoFile, PixelDrain, BuzzHeavier, DevUploads, and VikingFile**.

It is fully decoupled from the core WZML-X bot, offering an extremely lightweight footprint, MongoDB-only database management, dynamic user settings, and detailed progress tracking.

---

## 🌟 Key Features

* **Multi-Host Uploads:** Upload to multiple hosts simultaneously or choose specific hosts.
* **Smart Downloads:** Direct, fast downloads from both HTTP/HTTPS direct links and Telegram media (files, videos, documents, etc.).
* **Dynamic User Settings (`/usetting`):** Users can toggle their active upload destinations and configure their own API keys, folder IDs, and user hashes.
* **Global Fallback Credentials:** Bot owners can set global fallback keys for users without personal accounts.
* **Admin Limits & Task Control (`/bsetting`):** Allows bot admins to change concurrent task limits (`BOT_MAX_TASKS`), url download limits (`DIRECT_LIMIT`), and leech upload limits (`LEECH_LIMIT`) dynamically.
* **Detailed Progress Status (`/status`):** Tracks real-time percentage, size, download/upload speed, and ETA.
* **Task Cancellation (`/cancel`):** Cancel downloading/uploading tasks dynamically.
* **MongoDB Storage:** Persists user credentials and global bot settings securely to MongoDB.
* **Heroku-Ready:** Includes full configurations (`Procfile`, `runtime.txt`, `app.json`) for instant 1-click deployment to Heroku.

---

## 🚀 Getting Started

### 📋 Prerequisites

* Python 3.9 or higher.
* Standard system packages (gcc, etc.).

### ⚙️ Installation & Deployment

1. **Clone/Extract** the files into a dedicated directory:
   ```bash
   cd uphoster_bot
   ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the Bot:**
   Copy `config_sample.py` to `config.py` and enter your credentials:
   ```bash
   cp config_sample.py config.py
   # Edit config.py with your credentials
   ```

4. **Run the Bot:**
   ```bash
   python -m uphoster_bot.main
   ```

### 💜 Heroku Deploy

To deploy instantly to Heroku, simply click the standard "Deploy to Heroku" link pointing to your repository, or use the Heroku CLI:
```bash
heroku create
heroku addons:create mongolab
git push heroku main
```

---

## 🛠️ Configuration Options

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Telegram Bot Token from `@BotFather` |
| `TELEGRAM_API` | Telegram API ID from `my.telegram.org` |
| `TELEGRAM_HASH` | Telegram API Hash from `my.telegram.org` |
| `OWNER_ID` | Telegram User ID of the bot owner |
| `AUTHORIZED_CHATS` | Space-separated chat/channel/group IDs authorized to use the bot |
| `SUDO_USERS` | Space-separated user IDs with Sudo access to view/restart bot |
| `DATABASE_URL` | Mandatory MongoDB connection string. |

---

## 🎮 Bot Commands

* `/start` - Start the bot and get a welcome message.
* `/uphoster` (or reply with `/up`) - Download and upload direct links or Telegram files.
* `/usetting` - View user settings, toggle preferred upload destinations, and check keys.
* `/setkey [key] [value]` - Configure personal service API credentials.
* `/bsetting` - View or update global bot fallback credentials and limits (Sudo only).
* `/status` - Show detailed list of active upload tasks.
* `/cancel` - Abort active tasks.
* `/restart` - Restart the bot (Sudo only).

---

## 🔑 User-Configurable Keys

Users can dynamically save their own API keys/folder IDs using the `/setkey` command:
* `gofile_token` - Gofile Account API Token.
* `gofile_folder_id` - Target Gofile Folder ID.
* `pixeldrain_key` - PixelDrain API key.
* `buzzheavier_token` - BuzzHeavier Token.
* `buzzheavier_folder_id` - Target BuzzHeavier Folder ID.
* `devuploads_key` - DevUploads API key.
* `devuploads_folder` - DevUploads Folder ID.
* `vikingfile_hash` - VikingFile User Hash.
* `vikingfile_folder` - VikingFile Folder Name/Path.
