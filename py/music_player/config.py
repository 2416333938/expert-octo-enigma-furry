"""统一配置管理"""
import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

DEFAULT_CONFIG = {
    "netease": {
        "cookie": "",          # 浏览器登录后复制 MUSIC_U 值
        "phone": "",
        "password": ""
    },
    "qqmusic": {
        "cookie": "",          # Q_H_L_ 开头的 QQ 登录凭证
        "phone": ""
    },
    "kugou": {
        "cookie": ""
    },
    "qishui": {
        "cookie": ""           # 汽水音乐 Cookie
    },
    "bilibili": {
        "sessdata": "",        # B站 SESSDATA
        "bili_jct": ""
    }
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)