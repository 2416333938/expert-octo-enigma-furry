"""主程序 —— 命令行交互"""
import asyncio
from config import load_config, save_config
from platforms.netease import NeteaseClient
from platforms.qqmusic import QQMusicClient
from platforms.kugou import KugouClient
from platforms.qishui import QishuiClient
from platforms.bilibili import BilibiliClient
from player import MusicPlayer


class MusicApp:
    def __init__(self):
        self.cfg = load_config()
        self.player = MusicPlayer()
        self.clients = {}
        self._init_clients()

    def _init_clients(self):
        if self.cfg["netease"]["cookie"]:
            self.clients["netease"] = NeteaseClient(self.cfg["netease"]["cookie"])
        else:
            self.clients["netease"] = NeteaseClient()

        self.clients["qqmusic"] = QQMusicClient(
            self.cfg["qqmusic"].get("cookie") or None
        )
        self.clients["kugou"] = KugouClient(
            self.cfg["kugou"].get("cookie") or None
        )
        self.clients["qishui"] = QishuiClient(
            self.cfg["qishui"].get("cookie") or None
        )
        self.clients["bilibili"] = BilibiliClient(
            self.cfg["bilibili"].get("sessdata"),
            self.cfg["bilibili"].get("bili_jct")
        )

    def search_all(self, keyword: str, limit: int = 5):
        """跨平台搜索"""
        print(f"\n🔍 搜索: {keyword}\n")
        results = {}

        # 网易云
        try:
            netease_songs = self.clients["netease"].search(keyword, limit)
            results["netease"] = netease_songs
            print(f"【网易云】共 {len(netease_songs)} 条")
            for i, s in enumerate(netease_songs):
                print(f"  {i}. {s['name']} - {s['artists']}")
        except Exception as e:
            print(f"【网易云】搜索失败: {e}")

        # QQ音乐
        try:
            qq_songs = asyncio.run(self.clients["qqmusic"].search(keyword, limit))
            results["qqmusic"] = qq_songs
            print(f"\n【QQ音乐】共 {len(qq_songs)} 条")
            for i, s in enumerate(qq_songs):
                print(f"  {i}. {s['name']} - {s['artists']}")
        except Exception as e:
            print(f"【QQ音乐】搜索失败: {e}")

        # 酷狗
        try:
            kg_songs = self.clients["kugou"].search(keyword, limit)
            results["kugou"] = kg_songs
            print(f"\n【酷狗】共 {len(kg_songs)} 条")
            for i, s in enumerate(kg_songs):
                print(f"  {i}. {s['name']} - {s['artists']}")
        except Exception as e:
            print(f"【酷狗】搜索失败: {e}")

        # 汽水音乐
        try:
            qs_songs = self.clients["qishui"].search(keyword, limit)
            results["qishui"] = qs_songs
            print(f"\n【汽水音乐】共 {len(qs_songs)} 条")
            for i, s in enumerate(qs_songs):
                print(f"  {i}. {s['name']} - {s['artists']}")
        except Exception as e:
            print(f"【汽水音乐】搜索失败: {e}")

        return results

    def search_bilibili(self, keyword: str, limit: int = 5):
        """搜索 B 站视频"""
        print(f"\n📺 B站搜索: {keyword}\n")
        try:
            videos = asyncio.run(
                self.clients["bilibili"].search_videos(keyword, limit)
            )
            for i, v in enumerate(videos):
                print(f"  {i}. {v['title']}  UP: {v['author']}  [{v['bvid']}]")
            return videos
        except Exception as e:
            print(f"B站搜索失败: {e}")
            return []

    def play_bilibili(self, bvid: str):
        """播放 B 站视频的音频"""
        try:
            url = asyncio.run(
                self.clients["bilibili"].get_audio_url(bvid)
            )
            if url:
                print(f"▶ 正在播放 B站音频: {bvid}")
                self.player.play_url(url)
            else:
                print("无法获取音频地址")
        except Exception as e:
            print(f"播放失败: {e}")


def main():
    app = MusicApp()
    print("=" * 50)
    print("  多平台音乐播放器")
    print("=" * 50)

    while True:
        print("\n命令:")
        print("  search <关键词>        —— 跨平台搜索音乐")
        print("  bili <关键词>          —— 搜索 B 站视频")
        print("  playbili <bvid>        —— 播放 B 站视频音频")
        print("  play <平台> <索引>     —— 播放搜索结果")
        print("  login                  —— 配置登录信息")
        print("  quit                   —— 退出")

        cmd = input("\n> ").strip()
        if not cmd:
            continue
        if cmd == "quit":
            break
        if cmd == "login":
            configure_login(app.cfg)
            continue

        parts = cmd.split(maxsplit=2)
        if parts[0] == "search" and len(parts) > 1:
            app.search_all(parts[1])
        elif parts[0] == "bili" and len(parts) > 1:
            app.search_bilibili(parts[1])
        elif parts[0] == "playbili" and len(parts) > 1:
            app.play_bilibili(parts[1])


def configure_login(cfg):
    """交互式配置登录信息"""
    print("\n选择平台: netease / qqmusic / kugou / qishui / bilibili")
    platform = input("平台: ").strip().lower()
    if platform == "bilibili":
        cfg["bilibili"]["sessdata"] = input("SESSDATA: ").strip()
        cfg["bilibili"]["bili_jct"] = input("bili_jct: ").strip()
    elif platform in cfg:
        cfg[platform]["cookie"] = input("Cookie: ").strip()
    save_config(cfg)
    print("✅ 已保存，重启程序生效")


if __name__ == "__main__":
    main()