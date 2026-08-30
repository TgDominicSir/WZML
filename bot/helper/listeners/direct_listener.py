from time import time
from aiofiles import open as aiopen
from aiofiles.os import makedirs, path as aiopath
from aiohttp import ClientSession, ClientError

from ... import LOGGER


class DirectListener:
    def __init__(self, path, listener, a2c_opt=None):
        self.listener = listener
        self._path = path
        self._proc_bytes = 0
        self._curr_downloaded = 0
        self._curr_speed = 0
        self._failed = 0
        self._start_time = time()
        self.name = self.listener.name
        self.is_downloading = False

    @property
    def processed_bytes(self):
        return self._proc_bytes + self._curr_downloaded

    @property
    def speed(self):
        if self._curr_speed > 0:
            return self._curr_speed
        return self.processed_bytes / max(time() - self._start_time, 1)

    async def download(self, contents):
        self.is_downloading = True
        async with ClientSession() as session:
            for content in contents:
                if self.listener.is_cancelled:
                    break
                dir_path = f"{self._path}/{content['path']}" if content.get("path") else self._path
                filename = content.get("filename", "file")
                file_path = f"{dir_path}/{filename}"
                url = content.get("url")

                if not url:
                    self._failed += 1
                    continue

                try:
                    await makedirs(dir_path, exist_ok=True)
                    self._curr_downloaded = 0
                    last_time = time()
                    last_bytes = 0

                    headers = content.get("headers") or {}
                    async with session.get(url, headers=headers) as response:
                        if response.status >= 400:
                            raise ClientError(f"HTTP {response.status}")
                        async with aiopen(file_path, "wb") as f:
                            async for chunk in response.content.iter_chunked(128 * 1024):
                                if self.listener.is_cancelled:
                                    break
                                await f.write(chunk)
                                self._curr_downloaded += len(chunk)
                                now = time()
                                dt = now - last_time
                                if dt >= 1.0:
                                    self._curr_speed = (self._curr_downloaded - last_bytes) / dt
                                    last_time = now
                                    last_bytes = self._curr_downloaded

                    self._proc_bytes += self._curr_downloaded
                    self._curr_downloaded = 0
                    self._curr_speed = 0

                except Exception as e:
                    self._failed += 1
                    LOGGER.error(f"Unable to download {filename} due to: {e}")
                    if await aiopath.exists(file_path):
                        from aiofiles.os import remove
                        await remove(file_path)

        if self.listener.is_cancelled:
            return
        if self._failed == len(contents):
            await self.listener.on_download_error("All files failed to download!")
            return
        await self.listener.on_download_complete()

    async def cancel_task(self):
        self.listener.is_cancelled = True
        LOGGER.info(f"Cancelling Download: {self.listener.name}")
        await self.listener.on_download_error("Download Cancelled by User!")
