import re
import aiohttp
from logging import getLogger
from .bot_config import Config

LOGGER = getLogger(__name__)

class TelegraphHelper:
    def __init__(self, author_name=None, author_url=None):
        self.access_token = None
        self.author_name = author_name or "Uphoster Upload Bot"
        self.author_url = author_url or "https://t.me/WZML_X"

    async def create_account(self):
        LOGGER.info("Creating Telegraph Account...")
        url = "https://api.telegra.ph/createAccount"
        params = {
            "short_name": "UphosterBot",
            "author_name": self.author_name,
            "author_url": self.author_url
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    res = await resp.json()
                    if res.get("ok"):
                        self.access_token = res["result"].get("access_token")
                        LOGGER.info("Telegraph Account created successfully.")
                    else:
                        LOGGER.error(f"Failed to create Telegraph Account: {res}")
        except Exception as e:
            LOGGER.error(f"Error creating Telegraph Account: {e}")

    def _html_to_nodes(self, content_str):
        nodes = []
        # Support basic parsing of: <p>{i}. <a href="{url}">{name}</a></p>
        paragraphs = re.findall(r'<p>(.*?)</p>', content_str, re.DOTALL)
        if not paragraphs:
            paragraphs = [content_str]

        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            # Check if paragraph contains an anchor link
            match = re.search(r'(.*?)(?:<a\s+href=["\'](.*?)["\']>(.*?)</a>)', p, re.DOTALL)
            if match:
                prefix = match.group(1).strip()
                url = match.group(2).strip()
                name = match.group(3).strip()

                children = []
                if prefix:
                    children.append(prefix + " ")
                children.append({
                    "tag": "a",
                    "attrs": {"href": url},
                    "children": [name]
                })
                nodes.append({
                    "tag": "p",
                    "children": children
                })
            else:
                nodes.append({
                    "tag": "p",
                    "children": [p]
                })
        return nodes

    async def create_page(self, title, content):
        if not self.access_token:
            await self.create_account()
            if not self.access_token:
                # Dummy response fallback
                return {"path": "error"}

        url = "https://api.telegra.ph/createPage"
        import json
        nodes = self._html_to_nodes(content)
        data = {
            "access_token": self.access_token,
            "title": title,
            "author_name": self.author_name,
            "author_url": self.author_url,
            "content": json.dumps(nodes),
            "return_content": "false"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as resp:
                    res = await resp.json()
                    if res.get("ok"):
                        return res["result"]
                    else:
                        LOGGER.error(f"Telegraph createPage failed: {res}")
        except Exception as e:
            LOGGER.error(f"Telegraph API Error: {e}")
        return {"path": "error"}

telegraph = TelegraphHelper(Config.AUTHOR_NAME, Config.AUTHOR_URL)
