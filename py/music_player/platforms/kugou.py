"""酷狗音乐客户端 —— 基于 pymusiclibrary"""
from pymusiclibrary import MusicLibrary


class KugouClient:
    def __init__(self, cookie=None):
        self.lib = MusicLibrary()
        if cookie:
            self.lib.set_cookie(cookie)

    def search(self, keyword: str, limit: int = 10):
        """搜索歌曲"""
        raw = self.lib.search_song(keyword, page=1, page_size=limit, platform="kugou")
        songs = []
        for item in raw:
            songs.append({
                "hash": item.get("hash"),
                "name": item.get("songname"),
                "artists": item.get("singername"),
                "album": item.get("album_name", ""),
            })
        return songs

    def get_play_url(self, song_hash: str):
        """获取播放直链"""
        return self.lib.get_song_url(song_hash, platform="kugou")