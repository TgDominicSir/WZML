from pymongo import MongoClient
from logging import getLogger
from .bot_config import Config

LOGGER = getLogger(__name__)

class Database:
    def __init__(self):
        self.client = None
        self.db = None
        self._init_db()

    def _init_db(self):
        if not Config.DATABASE_URL:
            raise ValueError("DATABASE_URL is missing in configuration! MongoDB is mandatory.")

        try:
            self.client = MongoClient(Config.DATABASE_URL)
            self.db = self.client["uphoster_bot"]
            LOGGER.info("Connected to MongoDB successfully.")
        except Exception as e:
            LOGGER.critical(f"Failed to connect to MongoDB: {e}")
            raise e

    def get_user_data(self, user_id):
        try:
            user = self.db.users.find_one({"_id": user_id})
            if user:
                return user.get("settings", {})
        except Exception as e:
            LOGGER.error(f"MongoDB get_user_data error: {e}")
        return {}

    def update_user_data(self, user_id, key, value):
        data = self.get_user_data(user_id)
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value

        try:
            self.db.users.update_one(
                {"_id": user_id},
                {"$set": {"settings": data}},
                upsert=True
            )
        except Exception as e:
            LOGGER.error(f"MongoDB update_user_data error: {e}")

    def get_bot_settings(self):
        try:
            settings = self.db.settings.find_one({"_id": "bot_config"})
            if settings:
                return settings.get("config", {})
        except Exception as e:
            LOGGER.error(f"MongoDB get_bot_settings error: {e}")
        return {}

    def update_bot_settings(self, key, value):
        data = self.get_bot_settings()
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value

        try:
            self.db.settings.update_one(
                {"_id": "bot_config"},
                {"$set": {"config": data}},
                upsert=True
            )
            # Update local config values too
            if hasattr(Config, key):
                setattr(Config, key, value)
        except Exception as e:
            LOGGER.error(f"MongoDB update_bot_settings error: {e}")

db = Database()
