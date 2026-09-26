"""QQ音乐客户端 —— 基于 qqmusic-api-python"""
import asyncio
from qqmusic_api import Client, Credential


class QQMusicClient:
    def __init__(self, cookie=None):
        self.credential = None
        if cookie:
            self.credential = Credential(cookie=cookie)

    async def login_qr(self):
        """扫码登录，返回二维码 URL"""
        async with Client() as client:
            qr = await client.login.get_qr_code()
            return qr.get("qrcode_url")

    async def search(self, keyword: str, limit: int = 10):
        """搜索歌曲"""
        async with Client(credential=self.credential) as client:
            result = await client.search.search_song(keyword, page=1, num=limit)
            songs = []
            for item in result.get("list", []):
                songs.append({
                    "mid": item.get("mid"),
                    "name": item.get("name"),
                    "artists": "/".join(s.get("name", "") for s in item.get("singer", [])),
                    "album": item.get("album", {}).get("name", ""),
                })
            return songs

    async def get_play_url(self, song_mid: str):
        """获取播放直链"""
        async with Client(credential=self.credential) as client:
            urls = await client.song.get_song_urls([song_mid])
            if urls and urls[0].get("url"):
                return urls[0]["url"]
        return None