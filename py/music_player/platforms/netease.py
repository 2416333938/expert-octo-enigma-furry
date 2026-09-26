"""网易云音乐客户端 —— 基于 pyncm"""
from pyncm import apis
from pyncm.apis.login import LoginViaCellPhone, LoginViaAnonymousAccount, GetCurrentLoginSession
from pyncm import GetCurrentSession, SetCurrentSession, CreateNewSession


class NeteaseClient:
    def __init__(self, cookie=None):
        self.session = CreateNewSession()
        SetCurrentSession(self.session)
        if cookie:
            self.session.cookies["MUSIC_U"] = cookie
            self.logged_in = True
        else:
            LoginViaAnonymousAccount()
            self.logged_in = False

    def login_by_phone(self, phone: str, password: str):
        """手机号登录"""
        LoginViaCellPhone(phone=phone, password=password)
        self.logged_in = True
        return True

    def search(self, keyword: str, limit: int = 10):
        """搜索歌曲，返回 [{id, name, artists, album}]"""
        result = apis.cloudsearch.GetSearchResult(keyword, stype=1, limit=limit)
        songs = []
        for item in result["result"]["songs"]:
            songs.append({
                "id": item["id"],
                "name": item["name"],
                "artists": "/".join(a["name"] for a in item["ar"]),
                "album": item["al"]["name"],
            })
        return songs

    def get_play_url(self, song_id: int):
        """获取播放直链"""
        result = apis.track.GetTrackAudio(song_id)
        if result["data"] and result["data"][0]["url"]:
            return result["data"][0]["url"]
        return None