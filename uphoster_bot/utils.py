import asyncio
from functools import partial

class SetInterval:
    def __init__(self, interval, action, *args, **kwargs):
        self.interval = interval
        self.action = action
        self.task = asyncio.create_task(self._set_interval(*args, **kwargs))

    async def _set_interval(self, *args, **kwargs):
        while True:
            await asyncio.sleep(self.interval)
            try:
                await self.action(*args, **kwargs)
            except Exception:
                pass

    def cancel(self):
        self.task.cancel()


async def sync_to_async(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(func, *args, **kwargs))


def get_readable_file_size(size_in_bytes):
    if size_in_bytes is None:
        return '0 B'
    size_in_bytes = float(size_in_bytes)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
            break
        size_in_bytes /= 1024.0
    else:
        return f"{size_in_bytes:.2f} PB"


def get_readable_time(seconds):
    if seconds is None or seconds < 0:
        return '0s'
    periods = [('d', 86400), ('h', 3600), ('m', 60), ('s', 1)]
    result = []
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            result.append(f"{int(period_value)}{period_name}")
    if not result:
        return "0s"
    return "".join(result[:3])
