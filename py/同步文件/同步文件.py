#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文件夹同步工具（GUI 版 · 多任务 · 只复制 · Git 源 · 系统托盘 · 独立设置窗口）

界面：
  - 三块区域均可拖拽分隔线调整大小：任务列表 / 任务配置 / 日志
  - 高级选项集中在“设置”窗口里（Toplevel），主界面保持简洁
  - 支持系统托盘（需 pip install pystray Pillow）

同步模式：
  - 单向增量 / 单向镜像 / 双向同步 / 只复制（双向补齐，同名跳过）

Git 源：
  源输入 Git 仓库地址时，先拉取到本地缓存再同步；只保留单向增量 / 单向镜像。
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

CHUNK_SIZE = 1 << 20
APP_TITLE = "文件夹同步工具"

CONFIG_FILENAME = "sync_config.json"
CONFIG_VERSION = 2


# =========================================================================== #
# Git 支持
# =========================================================================== #

_GIT_URL_PATTERNS = [
    re.compile(r"^https?://.+\.git/?$", re.I),
    re.compile(r"^https?://(github\.com|gitlab\.com|gitee\.com|bitbucket\.org|codeberg\.org)/[\w.\-]+/[\w.\-]+/?$", re.I),
    re.compile(r"^git@[\w.\-]+:[\w./\-]+(\.git)?$", re.I),
    re.compile(r"^ssh://[\w@.\-:]+/[\w./\-]+(\.git)?$", re.I),
    re.compile(r"^git://[\w.\-:]+/[\w./\-]+$", re.I),
    re.compile(r"^file://.+\.git/?$", re.I),
]


def is_git_url(s: str) -> bool:
    s = (s or "").strip()
    if not s or " " in s:
        return False
    if re.match(r"^[A-Za-z]:[\\/]", s):
        return False
    return any(p.match(s) for p in _GIT_URL_PATTERNS)


def run_git(args: list[str], cwd=None, timeout: int = 300):
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = 0x08000000
    try:
        r = subprocess.run(
            ["git"] + args, cwd=cwd, capture_output=True, text=True,
            timeout=timeout, **kwargs,
        )
        return r.returncode, r.stdout or "", r.stderr or ""
    except FileNotFoundError:
        return 127, "", "未找到 git 命令，请安装 Git 并加入 PATH"
    except subprocess.TimeoutExpired:
        return 124, "", f"git 操作超时（>{timeout}s）"
    except Exception as exc:
        return 1, "", str(exc)


def git_available() -> bool:
    return shutil.which("git") is not None


def git_cache_dir(url: str) -> Path:
    h = hashlib.md5(url.encode("utf-8")).hexdigest()[:12]
    name = url.rstrip("/").split("/")[-1].split(":")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    name = re.sub(r"[^\w.\-]", "_", name) or "repo"
    base = Path(tempfile.gettempdir()) / "folder_sync_git_cache"
    return base / f"{name}_{h}"


def ensure_git_repo(url: str, cache_dir: Path, log) -> tuple[bool, str]:
    cache_dir.parent.mkdir(parents=True, exist_ok=True)

    if not (cache_dir / ".git").exists():
        if cache_dir.exists():
            try:
                shutil.rmtree(cache_dir)
            except OSError as exc:
                return False, f"无法清理缓存目录：{exc}"
        log(f"[GIT]    正在克隆 {url} …")
        rc, out, err = run_git(["clone", url, str(cache_dir)], timeout=900)
        if rc != 0:
            return False, f"git clone 失败：{(err or out).strip()}"
        log("[GIT]    克隆完成")
        return True, ""

    log("[GIT]    拉取更新 …")
    rc, out, err = run_git(["-C", str(cache_dir), "pull", "--ff-only"], timeout=600)
    if rc != 0:
        log("[GIT]    pull --ff-only 失败，尝试强制同步 …")
        rc2, _o2, _e2 = run_git(
            ["-C", str(cache_dir), "fetch", "--all", "--prune"], timeout=600
        )
        if rc2 != 0:
            return False, f"git fetch 失败：{(err or out).strip()}"

        target = None
        rc3, out3, _e3 = run_git(
            ["-C", str(cache_dir), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
            timeout=30,
        )
        if rc3 == 0 and out3.strip():
            target = out3.strip()
        else:
            for b in ("origin/main", "origin/master"):
                rc4, _o4, _e4 = run_git(
                    ["-C", str(cache_dir), "rev-parse", "--verify", b], timeout=30
                )
                if rc4 == 0:
                    target = b
                    break
        if target is None:
            return False, f"git 更新失败，无法确定远程分支：{(err or out).strip()}"

        rc5, out5, err5 = run_git(
            ["-C", str(cache_dir), "reset", "--hard", target], timeout=120
        )
        if rc5 != 0:
            return False, f"git reset 失败：{(err5 or out5).strip()}"

    log("[GIT]    更新完成")
    return True, ""


# =========================================================================== #
# 配置文件读写
# =========================================================================== #

def get_config_path() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent
    return base / CONFIG_FILENAME


def load_config() -> dict:
    path = get_config_path()
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        print(f"[警告] 读取配置文件失败：{exc}")
        return {}


def save_config(data: dict) -> None:
    path = get_config_path()
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception as exc:
        print(f"[警告] 写入配置文件失败：{exc}")


# --------------------------------------------------------------------------- #
# 任务配置
# --------------------------------------------------------------------------- #

VALID_MODES = ("one_way", "mirror", "two_way", "copy_only")


def default_profile(name: str = "新任务") -> dict:
    return {
        "name": name,
        "src": "",
        "dst": "",
        "mode": "one_way",
        "dry_run": False,
        "fast": False,
        "clean_empty_dirs": True,
        "conflict": "skip",
        "tolerance": "2",
        "excludes": "",
        "auto_sync": False,
        "auto_interval": "5",
    }


def _as_bool(v, default=False) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(v, (int, float)):
        return bool(v)
    return default


def _as_float_str(v, default: str, min_value: float = 0.0) -> str:
    try:
        x = float(v)
        if x < min_value:
            raise ValueError
        return f"{x:g}"
    except (TypeError, ValueError):
        return default


def normalize_profile(raw: dict, fallback_name: str = "未命名任务") -> dict:
    p = default_profile()
    if not isinstance(raw, dict):
        return p

    p["name"] = str(raw.get("name") or fallback_name).strip() or fallback_name
    p["src"] = str(raw.get("src", "") or "")
    p["dst"] = str(raw.get("dst", "") or "")

    mode = raw.get("mode", "one_way")
    if mode not in VALID_MODES:
        mode = "one_way"
    p["mode"] = mode

    p["dry_run"] = _as_bool(raw.get("dry_run", False))
    p["fast"] = _as_bool(raw.get("fast", False))
    p["clean_empty_dirs"] = _as_bool(raw.get("clean_empty_dirs", True))

    conflict = raw.get("conflict", "skip")
    if conflict not in ("skip", "keep-both"):
        conflict = "skip"
    p["conflict"] = conflict

    p["tolerance"] = _as_float_str(raw.get("tolerance", 2), "2", 0.0)
    p["excludes"] = str(raw.get("excludes", "") or "")

    p["auto_sync"] = _as_bool(raw.get("auto_sync", False))
    p["auto_interval"] = _as_float_str(raw.get("auto_interval", 5), "5", 1.0)

    return p


def normalize_config(cfg: dict) -> tuple[list[dict], int]:
    profiles_raw = cfg.get("profiles")
    profiles: list[dict] = []

    if isinstance(profiles_raw, list):
        for i, item in enumerate(profiles_raw):
            if isinstance(item, dict):
                profiles.append(normalize_profile(item, f"任务 {i + 1}"))

    if not profiles and ("src" in cfg or "dst" in cfg):
        profiles = [normalize_profile(cfg, "默认任务")]

    if not profiles:
        profiles = [default_profile("默认任务")]

    try:
        last = int(cfg.get("last_selected", 0))
    except (TypeError, ValueError):
        last = 0
    if not (0 <= last < len(profiles)):
        last = 0

    return profiles, last


# --------------------------------------------------------------------------- #
# 工具函数
# --------------------------------------------------------------------------- #

def file_hash(path: Path) -> str:
    h = hashlib.blake2b(digest_size=16)
    with open(path, "rb") as f:
        while True:
            block = f.read(CHUNK_SIZE)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def human_time(sec: float) -> str:
    sec = max(0, int(sec))
    if sec < 60:
        return f"{sec} 秒"
    m, s = divmod(sec, 60)
    if m < 60:
        return f"{m} 分 {s} 秒"
    h, m = divmod(m, 60)
    return f"{h} 小时 {m} 分"


def is_subpath(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def build_excluder(patterns: list[str]):
    if not patterns:
        return lambda rel: False

    def excluded(rel: Path) -> bool:
        posix = rel.as_posix()
        name = rel.name
        return any(
            fnmatch.fnmatch(posix, p) or fnmatch.fnmatch(name, p)
            for p in patterns
        )

    return excluded


# --------------------------------------------------------------------------- #
# 扫描 / 比较
# --------------------------------------------------------------------------- #

@dataclass
class Entry:
    size: int
    mtime: float


def scan(root: Path, excluded) -> dict[Path, Entry]:
    result: dict[Path, Entry] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        cur = Path(dirpath)
        dirnames[:] = [
            d for d in dirnames
            if not excluded((cur / d).relative_to(root))
        ]
        for name in filenames:
            full = cur / name
            rel = full.relative_to(root)
            if excluded(rel) or full.is_symlink():
                continue
            try:
                st = full.stat()
            except OSError:
                continue
            result[rel] = Entry(st.st_size, st.st_mtime)
    return result


def is_same_file(p1: Path, p2: Path, e1: Entry, e2: Entry,
                 tolerance: float, fast: bool) -> bool:
    if e1.size != e2.size:
        return False
    if abs(e1.mtime - e2.mtime) <= tolerance:
        return True
    if fast:
        return False
    return file_hash(p1) == file_hash(p2)


def folder_signature(root: Path, excluded) -> str:
    entries = scan(root, excluded)
    h = hashlib.md5()
    for rel in sorted(entries):
        e = entries[rel]
        h.update(f"{rel}|{e.size}|{int(e.mtime)}".encode())
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# 执行计划
# --------------------------------------------------------------------------- #

@dataclass
class Op:
    kind: str
    src: Path | None
    dst: Path | None
    reason: str


@dataclass
class Plan:
    ops: list[Op] = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    skipped: int = 0
    clean_dirs_root: Path | None = None

    @property
    def total_units(self) -> int:
        return len(self.ops) + len(self.conflicts)


def plan_mirror(src: Path, dst: Path, ctx: "Ctx", excluded) -> Plan:
    plan = Plan()
    src_map = scan(src, excluded)
    dst_map = scan(dst, excluded)

    for rel in sorted(src_map):
        if ctx._stopped():
            return plan
        s, d = src / rel, dst / rel
        if rel not in dst_map:
            plan.ops.append(Op("copy", s, d, "目标缺失"))
        elif not is_same_file(s, d, src_map[rel], dst_map[rel],
                              ctx.tolerance, ctx.fast):
            plan.ops.append(Op("copy", s, d, "内容不同"))
        else:
            plan.skipped += 1

    if ctx.delete:
        for rel in sorted(dst_map):
            if ctx._stopped():
                return plan
            if rel not in src_map:
                plan.ops.append(Op("delete", None, dst / rel, "源中已不存在"))
        plan.clean_dirs_root = dst

    return plan


def plan_copy_only(a: Path, b: Path, ctx: "Ctx", excluded) -> Plan:
    plan = Plan()
    a_map = scan(a, excluded)
    b_map = scan(b, excluded)

    for rel in sorted(a_map):
        if ctx._stopped():
            return plan
        if rel not in b_map:
            plan.ops.append(Op("copy", a / rel, b / rel, "B 中不存在"))
        else:
            plan.skipped += 1

    for rel in sorted(b_map):
        if ctx._stopped():
            return plan
        if rel not in a_map:
            plan.ops.append(Op("copy", b / rel, a / rel, "A 中不存在"))

    return plan


def plan_two_way(a: Path, b: Path, ctx: "Ctx", excluded) -> Plan:
    plan = Plan()
    a_map = scan(a, excluded)
    b_map = scan(b, excluded)

    for rel in sorted(set(a_map) | set(b_map)):
        if ctx._stopped():
            return plan
        pa, pb = a / rel, b / rel

        if rel not in b_map:
            plan.ops.append(Op("copy", pa, pb, "仅存在于 A"))
            continue
        if rel not in a_map:
            plan.ops.append(Op("copy", pb, pa, "仅存在于 B"))
            continue

        ea, eb = a_map[rel], b_map[rel]
        if is_same_file(pa, pb, ea, eb, ctx.tolerance, ctx.fast):
            plan.skipped += 1
            continue

        if abs(ea.mtime - eb.mtime) <= ctx.tolerance:
            plan.conflicts.append((rel, pa, pb, a, b))
            if ctx.on_conflict == "keep-both":
                stamp = time.strftime("%Y%m%d-%H%M%S")
                for src_file, dst_dir, tag in ((pa, b, "A"), (pb, a, "B")):
                    target = (dst_dir / rel.parent /
                              f"{rel.stem}.conflict-{tag}-{stamp}{rel.suffix}")
                    plan.ops.append(Op("copy", src_file, target,
                                       f"冲突副本（来自 {tag}）"))
        elif ea.mtime > eb.mtime:
            plan.ops.append(Op("copy", pa, pb, "A 较新"))
        else:
            plan.ops.append(Op("copy", pb, pa, "B 较新"))

    return plan


# --------------------------------------------------------------------------- #
# 统计 / 上下文
# --------------------------------------------------------------------------- #

@dataclass
class Stats:
    copied: int = 0
    deleted: int = 0
    skipped: int = 0
    conflicts: int = 0
    errors: int = 0
    bytes_copied: int = 0


@dataclass
class Ctx:
    dry_run: bool = False
    delete: bool = False
    fast: bool = False
    tolerance: float = 2.0
    on_conflict: str = "skip"
    clean_empty_dirs: bool = True
    stats: Stats = field(default_factory=Stats)
    log: callable = print
    stop_flag: callable = None

    def _stopped(self) -> bool:
        return self.stop_flag is not None and self.stop_flag()

    def copy(self, src: Path, dst: Path, reason: str) -> None:
        self.stats.copied += 1
        try:
            self.stats.bytes_copied += src.stat().st_size
        except OSError:
            pass
        self.log(f"[COPY]   {src}  ->  {dst}   ({reason})")
        if self.dry_run:
            return
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        except OSError as exc:
            self.stats.errors += 1
            self.log(f"[ERROR]  复制失败 {src} -> {dst}: {exc}")

    def delete(self, path: Path, reason: str = "") -> None:
        self.stats.deleted += 1
        self.log(f"[DELETE] {path}" + (f"   ({reason})" if reason else ""))
        if self.dry_run:
            return
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            self.stats.errors += 1
            self.log(f"[ERROR]  删除失败 {path}: {exc}")


def clean_empty_dirs(root: Path, ctx: Ctx) -> None:
    for dirpath, _dirnames, _filenames in os.walk(root, topdown=False):
        p = Path(dirpath)
        if p == root:
            continue
        try:
            if next(p.iterdir(), None) is None:
                ctx.log(f"[RMDIR]  {p}")
                if not ctx.dry_run:
                    p.rmdir()
        except OSError:
            pass


def execute_plan(plan: Plan, ctx: Ctx, progress_callback=None) -> None:
    total = plan.total_units
    done = 0

    def step():
        nonlocal done
        done += 1
        if progress_callback:
            progress_callback(done, total)

    for op in plan.ops:
        if ctx._stopped():
            ctx.log("[STOP]   已被用户停止")
            return
        if op.kind == "copy":
            ctx.copy(op.src, op.dst, op.reason)
        elif op.kind == "delete":
            ctx.delete(op.dst, op.reason)
        step()

    for rel, pa, pb, a, b in plan.conflicts:
        if ctx._stopped():
            ctx.log("[STOP]   已被用户停止")
            return
        ctx.stats.conflicts += 1
        if ctx.on_conflict == "skip":
            ctx.log(f"[冲突]   {pa}  <->  {pb}   "
                    f"（内容不同且时间接近，已跳过）")
            step()

    if plan.clean_dirs_root and ctx.clean_empty_dirs:
        clean_empty_dirs(plan.clean_dirs_root, ctx)


# =========================================================================== #
# GUI
# =========================================================================== #

MODE_SHORT = {"one_way": "增量", "mirror": "镜像", "two_way": "双向", "copy_only": "只复制"}
MODE_LONG = {
    "one_way": "单向增量",
    "mirror": "单向镜像",
    "two_way": "双向同步（较新覆盖较旧）",
    "copy_only": "只复制（双向补齐，同名跳过，不删除、不覆盖）",
}


class SyncApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title(APP_TITLE)

        self.config_path = get_config_path()
        cfg = load_config()
        self.profiles, last_selected = normalize_config(cfg)

        # ---------- 运行时状态 ----------
        self.current_index: int | None = None
        self._suppress_select = False
        self._suppress_src_check = False
        self.msg_queue: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.monitor_thread: threading.Thread | None = None
        self.stop_requested = False
        self.monitor_stop = True
        self.monitor_reset = False
        self.auto_busy = False
        self.sync_done_event = threading.Event()
        self.sync_done_event.set()

        # ---------- 托盘 ----------
        self.tray_icon = None
        self._allow_real_exit = False
        self._tray_hint_shown = False
        self.tray_enabled_var = tk.BooleanVar(
            value=bool(cfg.get("tray_enabled", True))
        )

        # ---------- 设置窗口 ----------
        self.settings_window: tk.Toplevel | None = None

        # ---------- 变量 ----------
        self.name_var = tk.StringVar()
        self.src_var = tk.StringVar()
        self.dst_var = tk.StringVar()
        self.mode_var = tk.StringVar(value="one_way")
        self.dry_run_var = tk.BooleanVar()
        self.fast_var = tk.BooleanVar()
        self.clean_empty_var = tk.BooleanVar(value=True)
        self.conflict_var = tk.StringVar(value="skip")
        self.tolerance_var = tk.StringVar(value="2")
        self.exclude_var = tk.StringVar()
        self.auto_sync_var = tk.BooleanVar()
        self.auto_interval_var = tk.StringVar(value="5")

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_label = tk.StringVar(value="")
        self.auto_status = tk.StringVar(value="未开启")
        self.git_hint_var = tk.StringVar(value="")

        self.mode_buttons: dict[str, ttk.Radiobutton] = {}

        self._build_ui()

        geom = cfg.get("window_geometry")
        if isinstance(geom, str) and geom.strip():
            try:
                root.geometry(geom)
            except tk.TclError:
                root.geometry("1120x830")
        else:
            root.geometry("1120x830")
        root.minsize(900, 640)

        self.src_var.trace_add("write", self._on_src_var_changed)

        self._refresh_task_list()
        self._select_task(last_selected, force=True)

        self._poll_queue()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ==================================================================== UI ==
    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 6}

        # 主横向 PanedWindow：左（任务列表） | 右（配置 + 日志）
        self.main_paned = ttk.PanedWindow(self.root, orient="horizontal")
        self.main_paned.pack(fill="both", expand=True, **pad)

        # ---------------- 左侧：任务列表 ----------------
        left = ttk.Frame(self.main_paned)
        self.main_paned.add(left, weight=0)
        self._build_task_list_panel(left)

        # ---------------- 右侧：纵向 PanedWindow ----------------
        self.right_paned = ttk.PanedWindow(self.main_paned, orient="vertical")
        self.main_paned.add(self.right_paned, weight=1)

        # 右上：任务配置
        config_panel = ttk.Frame(self.right_paned)
        self.right_paned.add(config_panel, weight=3)
        self._build_config_panel(config_panel)

        # 右下：日志
        log_panel = ttk.LabelFrame(self.right_paned, text="日志")
        self.right_paned.add(log_panel, weight=2)
        self._build_log_panel(log_panel)

        # ---------------- 底部：按钮 + 进度 ----------------
        self._build_bottom_bar()

        # ---------------- 状态栏 ----------------
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(self.root, textvariable=self.status_var, anchor="w",
                  relief="sunken").pack(fill="x", side="bottom")

    # ------------------------------------------------------- 左侧：任务列表 --
    def _build_task_list_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="同步任务", font=("", 10, "bold")) \
            .pack(anchor="w", padx=4, pady=(2, 4))

        tree_wrap = ttk.Frame(parent)
        tree_wrap.pack(fill="both", expand=True)

        self.task_tree = ttk.Treeview(
            tree_wrap, columns=("mode",), height=20, selectmode="browse"
        )
        self.task_tree.heading("#0", text="任务名")
        self.task_tree.heading("mode", text="模式")
        self.task_tree.column("#0", width=160, stretch=True, minwidth=110)
        self.task_tree.column("mode", width=64, anchor="center", stretch=False)

        tsb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=tsb.set)
        self.task_tree.pack(side="left", fill="both", expand=True)
        tsb.pack(side="right", fill="y")

        self.task_tree.tag_configure("auto", foreground="#2471a3")
        self.task_tree.tag_configure("git", foreground="#8e44ad")

        btn_row = ttk.Frame(parent)
        btn_row.pack(fill="x", pady=(6, 0))
        ttk.Button(btn_row, text="新建", width=6, command=self._new_task).pack(side="left")
        ttk.Button(btn_row, text="复制", width=6, command=self._duplicate_task).pack(side="left", padx=2)
        ttk.Button(btn_row, text="改名", width=6, command=self._rename_task).pack(side="left", padx=2)
        ttk.Button(btn_row, text="删除", width=6, command=self._delete_task).pack(side="left", padx=2)

        self.task_tree.bind("<<TreeviewSelect>>", self._on_task_select)
        self.task_tree.bind("<Double-1>", lambda e: self._rename_task())

    # ------------------------------------------------------- 右上：任务配置 --
    def _build_config_panel(self, parent: ttk.Frame) -> None:
        # 任务名
        nf = ttk.LabelFrame(parent, text="任务")
        nf.pack(fill="x", padx=4, pady=(0, 4))
        nf.columnconfigure(1, weight=1)
        ttk.Label(nf, text="名称：").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(nf, textvariable=self.name_var).grid(
            row=0, column=1, sticky="ew", padx=(0, 6), pady=6
        )

        # 源 / 目标
        pf = ttk.LabelFrame(parent, text="源 / 目标")
        pf.pack(fill="x", padx=4, pady=4)
        pf.columnconfigure(1, weight=1)

        ttk.Label(pf, text="源 A：").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(pf, textvariable=self.src_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(pf, text="浏览…", command=lambda: self._pick_dir(self.src_var)) \
            .grid(row=0, column=2, padx=6)

        ttk.Label(pf, textvariable=self.git_hint_var,
                  foreground="#8e44ad", wraplength=560, justify="left") \
            .grid(row=1, column=1, columnspan=2, sticky="w", padx=6, pady=(0, 4))

        ttk.Label(pf, text="目标 B：").grid(row=2, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(pf, textvariable=self.dst_var).grid(row=2, column=1, sticky="ew")
        ttk.Button(pf, text="浏览…", command=lambda: self._pick_dir(self.dst_var)) \
            .grid(row=2, column=2, padx=6)

        ttk.Button(pf, text="A、B 互换", command=self._swap) \
            .grid(row=3, column=2, sticky="e", padx=6, pady=(0, 6))

        # 同步模式
        mf = ttk.LabelFrame(parent, text="同步模式")
        mf.pack(fill="x", padx=4, pady=4)

        rb = ttk.Radiobutton(mf, text="单向增量（A → B，只补新增/更新）",
                             variable=self.mode_var, value="one_way")
        rb.pack(anchor="w", padx=8, pady=2)
        self.mode_buttons["one_way"] = rb

        rb = ttk.Radiobutton(mf, text="单向镜像（A → B，B 中多余文件会被删除）",
                             variable=self.mode_var, value="mirror")
        rb.pack(anchor="w", padx=8, pady=2)
        self.mode_buttons["mirror"] = rb

        rb = ttk.Radiobutton(mf, text="双向同步（A ↔ B，较新覆盖较旧）",
                             variable=self.mode_var, value="two_way")
        rb.pack(anchor="w", padx=8, pady=2)
        self.mode_buttons["two_way"] = rb

        rb = ttk.Radiobutton(
            mf,
            text="只复制（A ↔ B 双向补齐：把彼此缺失的文件复制给对方；同名一律跳过）",
            variable=self.mode_var, value="copy_only",
        )
        rb.pack(anchor="w", padx=8, pady=2)
        self.mode_buttons["copy_only"] = rb

        # 自动同步
        af = ttk.LabelFrame(parent, text="自动同步（仅对当前任务生效）")
        af.pack(fill="x", padx=4, pady=4)
        arow = ttk.Frame(af); arow.pack(fill="x", padx=8, pady=6)
        ttk.Checkbutton(arow, text="开启自动同步",
                        variable=self.auto_sync_var,
                        command=self._on_auto_toggle).pack(side="left")
        ttk.Label(arow, text="   扫描间隔(秒)：").pack(side="left")
        ttk.Entry(arow, textvariable=self.auto_interval_var, width=6).pack(side="left")
        ttk.Label(arow, textvariable=self.auto_status,
                  foreground="#555").pack(side="left", padx=12)

        # 一行小提示：其它高级选项已收进设置
        hint = ttk.Frame(parent)
        hint.pack(fill="x", padx=4, pady=(2, 0))
        ttk.Label(hint,
                  text="ⓘ 预览模式、快速比较、清理空目录、时间容差、冲突处理、排除规则、托盘开关均在「设置」里",
                  foreground="#7f8c8d").pack(anchor="w")

    # ------------------------------------------------------- 右下：日志 --
    def _build_log_panel(self, parent: ttk.LabelFrame) -> None:
        self.log_text = tk.Text(parent, wrap="none", height=10)
        self.log_text.pack(side="left", fill="both", expand=True)
        lsb = ttk.Scrollbar(parent, orient="vertical", command=self.log_text.yview)
        lsb.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=lsb.set)

        self.log_text.tag_configure("error", foreground="#c0392b")
        self.log_text.tag_configure("copy", foreground="#1e8449")
        self.log_text.tag_configure("delete", foreground="#c0392b")
        self.log_text.tag_configure("conflict", foreground="#b9770e")
        self.log_text.tag_configure("auto", foreground="#2471a3")
        self.log_text.tag_configure("git", foreground="#8e44ad")
        self.log_text.tag_configure("tray", foreground="#16a085")
        self.log_text.tag_configure("info", foreground="#7f8c8d")

    # ------------------------------------------------------- 底部按钮栏 --
    def _build_bottom_bar(self) -> None:
        pad = {"padx": 8, "pady": 6}
        bf = ttk.Frame(self.root)
        bf.pack(fill="x", **pad)

        self.start_btn = ttk.Button(bf, text="开始同步", command=self._start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(bf, text="停止", command=self._stop, state="disabled")
        self.stop_btn.pack(side="left", padx=6)

        ttk.Button(bf, text="设置…", command=self._open_settings).pack(side="left", padx=6)
        ttk.Button(bf, text="保存设置", command=self._save_settings_clicked).pack(side="left", padx=6)
        ttk.Button(bf, text="清空日志", command=self._clear_log).pack(side="left", padx=6)
        ttk.Button(bf, text="隐藏到托盘", command=self._hide_to_tray).pack(side="left", padx=6)

        self.progress = ttk.Progressbar(bf, mode="determinate",
                                        maximum=1, variable=self.progress_var)
        self.progress.pack(side="right", fill="x", expand=True, padx=6)

        # 进度文字单独一行
        pfl = ttk.Frame(self.root)
        pfl.pack(fill="x", padx=10)
        ttk.Label(pfl, textvariable=self.progress_label,
                  anchor="w", foreground="#333").pack(side="left")

        # 配置文件路径
        ttk.Label(self.root, text=f"配置文件：{self.config_path}",
                  anchor="w", foreground="#7f8c8d").pack(fill="x", padx=10, pady=(2, 0))

    # ================================================== 设置窗口（Toplevel） ==
    def _open_settings(self) -> None:
        # 已经打开 → 提到前面
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.lift()
            self.settings_window.focus_force()
            return

        win = tk.Toplevel(self.root)
        win.title(f"{APP_TITLE} · 设置")
        win.transient(self.root)
        win.resizable(True, True)
        self.settings_window = win
        win.protocol("WM_DELETE_WINDOW", self._close_settings)

        self._build_settings_ui(win)

        # 打开时保存当前 UI 到 profile，确保设置里显示的与主界面一致
        if self.current_index is not None:
            self._save_ui_to_profile(self.current_index)
            self._refresh_task_item(self.current_index)

        # 计算窗口位置：贴主窗口右侧
        win.update_idletasks()
        w, h = 560, 580
        x = self.root.winfo_x() + self.root.winfo_width() - w - 60
        y = self.root.winfo_y() + 80
        # 若超出屏幕右侧，则居中显示
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        if x + w > sw - 20:
            x = max(20, (sw - w) // 2)
        if y + h > sh - 40:
            y = max(20, (sh - h) // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")

        # 聚焦设置窗口
        win.focus_force()

    def _close_settings(self) -> None:
        # 保存
        if self.current_index is not None:
            self._refresh_task_item(self.current_index)
        self._save_settings()

        # 销毁窗口
        if self.settings_window is not None:
            try:
                self.settings_window.destroy()
            except tk.TclError:
                pass
            self.settings_window = None

    def _build_settings_ui(self, win: tk.Toplevel) -> None:
        pad = {"padx": 12, "pady": 8}

        # ---------------- 全局设置 ----------------
        gf = ttk.LabelFrame(win, text="全局设置")
        gf.pack(fill="x", **pad)

        ttk.Checkbutton(
            gf, text="关闭窗口时最小化到系统托盘",
            variable=self.tray_enabled_var,
        ).pack(anchor="w", padx=10, pady=(8, 2))

        if self._pystray_available():
            ttk.Label(
                gf,
                text="勾选后，点击主窗口右上角的 × 会隐藏到系统托盘；\n"
                     "托盘图标：双击恢复窗口，右键菜单可立即同步 / 退出。",
                foreground="#666", justify="left",
            ).pack(anchor="w", padx=10, pady=(0, 8))
        else:
            ttk.Label(
                gf,
                text="⚠ 未检测到 pystray / Pillow，托盘功能不可用。\n"
                     "  安装命令：pip install pystray Pillow",
                foreground="#c0392b", justify="left",
            ).pack(anchor="w", padx=10, pady=(0, 8))

        # ---------------- 当前任务选项 ----------------
        tf = ttk.LabelFrame(win, text="当前任务的同步选项")
        tf.pack(fill="both", expand=True, **pad)

        # 复选框
        cb = ttk.Frame(tf)
        cb.pack(fill="x", padx=10, pady=(8, 4))
        ttk.Checkbutton(cb, text="预览模式（不实际修改文件）",
                        variable=self.dry_run_var).pack(anchor="w", pady=2)
        ttk.Checkbutton(cb, text="快速比较（只比大小和时间，不做内容哈希）",
                        variable=self.fast_var).pack(anchor="w", pady=2)
        ttk.Checkbutton(cb, text="删除文件后清理空目录",
                        variable=self.clean_empty_var).pack(anchor="w", pady=2)

        ttk.Separator(tf, orient="horizontal").pack(fill="x", padx=10, pady=8)

        # 时间容差
        r1 = ttk.Frame(tf); r1.pack(fill="x", padx=10, pady=4)
        ttk.Label(r1, text="时间容差(秒)：").pack(side="left")
        ttk.Entry(r1, textvariable=self.tolerance_var, width=8).pack(side="left")
        ttk.Label(r1, text="  （兼容 FAT 等低精度文件系统，默认 2）",
                  foreground="#888").pack(side="left")

        # 冲突处理
        r2 = ttk.Frame(tf); r2.pack(fill="x", padx=10, pady=4)
        ttk.Label(r2, text="冲突处理：").pack(side="left")
        ttk.Radiobutton(r2, text="跳过", variable=self.conflict_var,
                        value="skip").pack(side="left", padx=(0, 8))
        ttk.Radiobutton(r2, text="保留双方", variable=self.conflict_var,
                        value="keep-both").pack(side="left")
        ttk.Label(tf,
                  text="（仅双向同步遇到“时间相同但内容不同”时生效）",
                  foreground="#888").pack(anchor="w", padx=10)

        # 排除规则
        r3 = ttk.Frame(tf); r3.pack(fill="x", padx=10, pady=(8, 4))
        ttk.Label(r3, text="排除规则：").pack(side="left")
        ttk.Entry(r3, textvariable=self.exclude_var).pack(
            side="left", fill="x", expand=True
        )
        ttk.Label(tf,
                  text="多个用空格分隔，glob 语法：*.tmp  .git  __pycache__",
                  foreground="#888").pack(anchor="w", padx=10)

        # ---------------- 底部按钮 ----------------
        bf = ttk.Frame(win)
        bf.pack(fill="x", pady=10)

        ttk.Button(bf, text="关闭", command=self._close_settings) \
            .pack(side="right", padx=12)

    # ====================================================== Git 源检测 ==
    def _on_src_var_changed(self, *_args) -> None:
        if self._suppress_src_check:
            return
        self._update_git_mode_lock()

    def _update_git_mode_lock(self) -> None:
        src_text = self.src_var.get().strip()
        is_url = is_git_url(src_text)

        for key in ("two_way", "copy_only"):
            btn = self.mode_buttons.get(key)
            if btn is not None:
                try:
                    btn.configure(state="disabled" if is_url else "normal")
                except tk.TclError:
                    pass

        if is_url:
            if not git_available():
                self.git_hint_var.set(
                    "⚠ 检测到 Git 仓库地址，但系统未找到 git 命令。\n"
                    "  请安装 Git 并将其加入 PATH 后再试。"
                )
            else:
                self.git_hint_var.set(
                    "ⓘ 检测到 Git 仓库地址：会先拉取到本地缓存再同步。\n"
                    "  该来源只支持「单向增量 / 单向镜像」。"
                )
            if self.mode_var.get() in ("two_way", "copy_only"):
                self.mode_var.set("one_way")
        else:
            self.git_hint_var.set("")

    # ====================================================== 托盘功能 ==
    @staticmethod
    def _pystray_available() -> bool:
        try:
            import pystray  # noqa: F401
            from PIL import Image  # noqa: F401
            return True
        except ImportError:
            return False

    def _tray_should_enable(self) -> bool:
        return bool(self.tray_enabled_var.get()) and self._pystray_available()

    @staticmethod
    def _make_tray_image():
        from PIL import Image, ImageDraw
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        main = (41, 128, 185, 255)
        d.rounded_rectangle([6, 10, 30, 24], radius=3, fill=main)
        d.rounded_rectangle([6, 18, size - 6, size - 8], radius=5, fill=main)
        return img

    def _ensure_tray(self) -> bool:
        if self.tray_icon is not None:
            return True
        if not self._pystray_available():
            return False
        try:
            import pystray
        except ImportError:
            return False

        try:
            image = self._make_tray_image()
        except Exception:
            return False

        menu = pystray.Menu(
            pystray.MenuItem("显示主窗口", self._tray_on_show, default=True),
            pystray.MenuItem("立即同步", self._tray_on_sync),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", self._tray_on_quit),
        )
        try:
            icon = pystray.Icon("folder_sync", image, APP_TITLE, menu)
            threading.Thread(target=icon.run, daemon=True).start()
            self.tray_icon = icon
            self.msg_queue.put("[托盘]   已启动系统托盘图标")
        except Exception as exc:
            self.msg_queue.put(f"[托盘]  创建托盘图标失败：{exc}")
            self.tray_icon = None
            return False
        return True

    def _hide_to_tray(self) -> None:
        if not self.tray_enabled_var.get():
            self.msg_queue.put("[托盘]  未开启“关闭时最小化到托盘”，无法隐藏")
            return
        if not self._ensure_tray():
            messagebox.showwarning(
                APP_TITLE,
                "未安装 pystray / Pillow，无法使用系统托盘。\n\n"
                "请执行：pip install pystray Pillow"
            )
            return

        self._save_settings()
        self.root.withdraw()

        if not self._tray_hint_shown and self.tray_icon is not None:
            self._tray_hint_shown = True
            try:
                self.tray_icon.notify(
                    "程序已最小化到托盘。双击图标可恢复窗口。", APP_TITLE
                )
            except Exception:
                pass

        self.msg_queue.put("[托盘]   窗口已隐藏到系统托盘")

    def _restore_window(self) -> None:
        try:
            self.root.deiconify()
            self.root.state("normal")
            self.root.lift()
            self.root.focus_force()
        except tk.TclError:
            pass

    def _tray_on_show(self, icon=None, item=None) -> None:
        self.root.after(0, self._restore_window)

    def _tray_on_sync(self, icon=None, item=None) -> None:
        def _do():
            self._restore_window()
            if self.worker and self.worker.is_alive():
                self.msg_queue.put("[托盘]   已有同步在运行，忽略本次请求")
                return
            self._start(from_auto=False)
        self.root.after(0, _do)

    def _tray_on_quit(self, icon=None, item=None) -> None:
        self._allow_real_exit = True
        self.root.after(0, self._on_close)

    def _stop_tray(self) -> None:
        icon = self.tray_icon
        self.tray_icon = None
        if icon is None:
            return
        try:
            icon.stop()
        except Exception:
            pass

    # ====================================================== 任务列表操作 ==
    def _refresh_task_list(self) -> None:
        self.task_tree.delete(*self.task_tree.get_children())
        for i, p in enumerate(self.profiles):
            self._insert_task_item(i, p)

    def _insert_task_item(self, i: int, p: dict) -> None:
        name = p.get("name") or f"任务 {i + 1}"
        prefix = "● " if p.get("auto_sync") else ""
        if is_git_url(p.get("src", "")):
            prefix += "⎇ "
        display = prefix + name
        tags = []
        if p.get("auto_sync"):
            tags.append("auto")
        if is_git_url(p.get("src", "")):
            tags.append("git")
        self.task_tree.insert(
            "", "end", iid=str(i),
            text=display, values=(MODE_SHORT.get(p.get("mode"), "增量"),),
            tags=tuple(tags),
        )

    def _refresh_task_item(self, idx: int) -> None:
        if not self.task_tree.exists(str(idx)):
            return
        p = self.profiles[idx]
        name = p.get("name") or f"任务 {idx + 1}"
        prefix = "● " if p.get("auto_sync") else ""
        if is_git_url(p.get("src", "")):
            prefix += "⎇ "
        display = prefix + name
        tags = []
        if p.get("auto_sync"):
            tags.append("auto")
        if is_git_url(p.get("src", "")):
            tags.append("git")
        self.task_tree.item(str(idx), text=display,
                            values=(MODE_SHORT.get(p.get("mode"), "增量"),),
                            tags=tuple(tags))

    def _on_task_select(self, _event=None) -> None:
        if self._suppress_select:
            return
        sel = self.task_tree.selection()
        if not sel:
            return
        try:
            idx = int(sel[0])
        except (ValueError, IndexError):
            return
        if idx == self.current_index:
            return
        self._select_task(idx)

    def _select_task(self, idx: int, force: bool = False) -> None:
        if not (0 <= idx < len(self.profiles)):
            idx = 0
        if not force and idx == self.current_index:
            return

        if self.current_index is not None:
            self._save_ui_to_profile(self.current_index)
            self._refresh_task_item(self.current_index)

        self.current_index = idx
        self._load_profile_to_ui(idx)

        self._suppress_select = True
        try:
            self.task_tree.selection_set(str(idx))
            self.task_tree.focus(str(idx))
            self.task_tree.see(str(idx))
        finally:
            self._suppress_select = False

        self.monitor_reset = True
        p = self.profiles[idx]
        if p.get("auto_sync"):
            self._ensure_monitor_running()
        else:
            self._stop_monitor()

    # ------------------------------------------------------ 新建 / 复制 / 删除 --
    def _new_task(self) -> None:
        name = simpledialog.askstring(
            APP_TITLE, "新任务名称：",
            initialvalue=f"任务 {len(self.profiles) + 1}",
            parent=self.root,
        )
        if name is None:
            return
        name = name.strip() or f"任务 {len(self.profiles) + 1}"
        if self.current_index is not None:
            self._save_ui_to_profile(self.current_index)
        self.profiles.append(default_profile(name))
        new_idx = len(self.profiles) - 1
        self._refresh_task_list()
        self._select_task(new_idx, force=True)

    def _duplicate_task(self) -> None:
        if self.current_index is None:
            return
        self._save_ui_to_profile(self.current_index)
        src = dict(self.profiles[self.current_index])
        base = src.get("name") or "任务"
        src["name"] = self._unique_name(f"{base} 副本")
        self.profiles.append(src)
        new_idx = len(self.profiles) - 1
        self._refresh_task_list()
        self._select_task(new_idx, force=True)

    def _unique_name(self, base: str) -> str:
        existing = {p.get("name", "") for p in self.profiles}
        if base not in existing:
            return base
        i = 2
        while f"{base} {i}" in existing:
            i += 1
        return f"{base} {i}"

    def _rename_task(self) -> None:
        if self.current_index is None:
            return
        cur = self.profiles[self.current_index].get("name", "")
        name = simpledialog.askstring(
            APP_TITLE, "重命名任务：", initialvalue=cur, parent=self.root
        )
        if name is None:
            return
        name = name.strip()
        if not name:
            return
        self.profiles[self.current_index]["name"] = name
        self.name_var.set(name)
        self._refresh_task_item(self.current_index)
        self._save_settings()

    def _delete_task(self) -> None:
        if self.current_index is None:
            return
        name = self.profiles[self.current_index].get("name", "")
        if not messagebox.askyesno(APP_TITLE, f"确定删除任务「{name}」？"):
            return

        del self.profiles[self.current_index]
        if not self.profiles:
            self.profiles = [default_profile("默认任务")]
            self.current_index = None
            self._refresh_task_list()
            self._select_task(0, force=True)
            self._save_settings()
            return

        self.current_index = None
        new_idx = min(self.current_index or 0, len(self.profiles) - 1)
        self._refresh_task_list()
        self._select_task(max(0, new_idx), force=True)
        self._save_settings()

    # ====================================================== Profile <-> UI ==
    def _load_profile_to_ui(self, idx: int) -> None:
        p = self.profiles[idx]
        self._suppress_src_check = True
        try:
            self.name_var.set(p.get("name", ""))
            self.src_var.set(p.get("src", ""))
            self.dst_var.set(p.get("dst", ""))
            self.mode_var.set(p.get("mode", "one_way"))
            self.dry_run_var.set(bool(p.get("dry_run", False)))
            self.fast_var.set(bool(p.get("fast", False)))
            self.clean_empty_var.set(bool(p.get("clean_empty_dirs", True)))
            self.conflict_var.set(p.get("conflict", "skip"))
            self.tolerance_var.set(p.get("tolerance", "2"))
            self.exclude_var.set(p.get("excludes", ""))
            self.auto_sync_var.set(bool(p.get("auto_sync", False)))
            self.auto_interval_var.set(p.get("auto_interval", "5"))
        finally:
            self._suppress_src_check = False
        self._update_git_mode_lock()

    def _save_ui_to_profile(self, idx: int) -> None:
        p = self.profiles[idx]
        p["name"] = self.name_var.get().strip() or f"任务 {idx + 1}"
        p["src"] = self.src_var.get()
        p["dst"] = self.dst_var.get()
        p["mode"] = self.mode_var.get()
        p["dry_run"] = bool(self.dry_run_var.get())
        p["fast"] = bool(self.fast_var.get())
        p["clean_empty_dirs"] = bool(self.clean_empty_var.get())
        p["conflict"] = self.conflict_var.get()
        p["tolerance"] = self.tolerance_var.get()
        p["excludes"] = self.exclude_var.get()
        p["auto_sync"] = bool(self.auto_sync_var.get())
        p["auto_interval"] = self.auto_interval_var.get()

    # ====================================================== 配置读写 ==
    def _collect_config(self) -> dict:
        if self.current_index is not None:
            self._save_ui_to_profile(self.current_index)
        try:
            geom = self.root.winfo_geometry()
        except tk.TclError:
            geom = ""
        return {
            "version": CONFIG_VERSION,
            "last_selected": self.current_index if self.current_index is not None else 0,
            "window_geometry": geom,
            "tray_enabled": bool(self.tray_enabled_var.get()),
            "profiles": self.profiles,
        }

    def _save_settings(self) -> None:
        save_config(self._collect_config())

    def _save_settings_clicked(self) -> None:
        self._save_settings()
        if self.current_index is not None:
            self._refresh_task_item(self.current_index)
        self.status_var.set(f"设置已保存到 {self.config_path.name}")
        self.msg_queue.put(f"[信息]   设置已保存：{self.config_path}")

    # ====================================================== 基本操作 ==
    def _pick_dir(self, var: tk.StringVar) -> None:
        p = filedialog.askdirectory(title="选择文件夹")
        if p:
            var.set(p)

    def _swap(self) -> None:
        s, d = self.src_var.get(), self.dst_var.get()
        self.src_var.set(d)
        self.dst_var.set(s)

    def _clear_log(self) -> None:
        self.log_text.delete("1.0", "end")

    # ====================================================== 日志 ==
    def _append_log(self, text: str) -> None:
        tag = None
        if "[ERROR]" in text:
            tag = "error"
        elif "[COPY]" in text:
            tag = "copy"
        elif "[DELETE]" in text or "[RMDIR]" in text:
            tag = "delete"
        elif "[冲突]" in text:
            tag = "conflict"
        elif "[自动]" in text:
            tag = "auto"
        elif "[GIT]" in text:
            tag = "git"
        elif "[托盘]" in text:
            tag = "tray"
        elif "[信息]" in text or "[准备]" in text:
            tag = "info"
        self.log_text.insert("end", text + "\n", tag or ())
        self.log_text.see("end")

    def _poll_queue(self) -> None:
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                self._append_log(msg)
        except queue.Empty:
            pass
        self.root.after(80, self._poll_queue)

    # ====================================================== 校验 ==
    def _validate_inputs(self):
        src_text = self.src_var.get().strip()
        dst_text = self.dst_var.get().strip()
        if not src_text:
            messagebox.showwarning(APP_TITLE, "请选择源文件夹或输入 Git 地址")
            return None
        if not dst_text:
            messagebox.showwarning(APP_TITLE, "请选择目标文件夹")
            return None

        is_url = is_git_url(src_text)

        if is_url:
            if not git_available():
                messagebox.showerror(
                    APP_TITLE,
                    "检测到 Git 仓库地址，但系统未找到 git 命令。\n"
                    "请安装 Git 并确保它在 PATH 中。"
                )
                return None
            if self.mode_var.get() in ("two_way", "copy_only"):
                self.mode_var.set("one_way")
            src = src_text
        else:
            src = Path(src_text).expanduser().resolve()
            if not src.exists() or not src.is_dir():
                messagebox.showerror(APP_TITLE, f"源文件夹不存在或不是文件夹：\n{src}")
                return None

        dst = Path(dst_text).expanduser().resolve()
        if dst.exists() and not dst.is_dir():
            messagebox.showerror(APP_TITLE, f"目标路径已存在但不是文件夹：\n{dst}")
            return None

        if not is_url:
            if src == dst:
                messagebox.showerror(APP_TITLE, "两个路径不能相同")
                return None
            if is_subpath(src, dst) or is_subpath(dst, src):
                messagebox.showerror(APP_TITLE, "两个文件夹不能互相包含")
                return None

        try:
            tolerance = float(self.tolerance_var.get())
            if tolerance < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(APP_TITLE, "时间容差必须是 ≥ 0 的数字（可在「设置」里修改）")
            return None

        excludes = self.exclude_var.get().split()
        return src, dst, tolerance, excludes, is_url

    # ====================================================== 开始同步 ==
    def _start(self, from_auto: bool = False) -> bool:
        if self.worker and self.worker.is_alive():
            return False

        result = self._validate_inputs()
        if result is None:
            if from_auto:
                self.msg_queue.put("[自动]  参数无效，自动同步已跳过")
            return False

        src, dst, tolerance, excludes, is_url = result
        mode = self.mode_var.get()
        dry_run = self.dry_run_var.get()

        if mode == "mirror" and not dry_run and not from_auto:
            if not messagebox.askyesno(
                APP_TITLE,
                f"镜像模式会删除目标文件夹中多余的文件：\n{dst}\n\n确认继续？"
            ):
                return False

        if not dst.exists():
            if dry_run:
                self.msg_queue.put(f"[MKDIR]  {dst}")
            else:
                try:
                    dst.mkdir(parents=True, exist_ok=True)
                except OSError as exc:
                    if not from_auto:
                        messagebox.showerror(APP_TITLE, f"无法创建目标文件夹：{exc}")
                    return False

        self._save_settings()
        if self.current_index is not None:
            self._refresh_task_item(self.current_index)

        excluded = build_excluder(excludes)

        self.stop_requested = False
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress.configure(maximum=1)
        self.progress_var.set(0)
        self.progress_label.set("正在准备…")
        self.status_var.set("同步中…")

        task_name = self.name_var.get() or "当前任务"
        self.msg_queue.put("=" * 60)
        self.msg_queue.put(f"任务      : {task_name}")
        if is_url:
            self.msg_queue.put(f"源仓库    : {src}")
        else:
            self.msg_queue.put(f"源文件夹  : {src}")
        self.msg_queue.put(f"目标文件夹: {dst}")
        self.msg_queue.put(f"同步模式  : {MODE_LONG.get(mode, mode)}"
                           + ("  （自动触发）" if from_auto else ""))
        if excludes:
            self.msg_queue.put(f"排除规则  : {', '.join(excludes)}")
        if dry_run:
            self.msg_queue.put(">>> 预览模式：不会修改任何文件 <<<")
        self.msg_queue.put("-" * 60)

        self.sync_done_event.clear()

        ctx = Ctx(
            dry_run=dry_run,
            delete=(mode == "mirror"),
            fast=self.fast_var.get(),
            tolerance=tolerance,
            on_conflict=self.conflict_var.get(),
            clean_empty_dirs=self.clean_empty_var.get(),
            log=self.msg_queue.put,
            stop_flag=lambda: self.stop_requested,
        )

        self.worker = threading.Thread(
            target=self._run_sync,
            args=(mode, src, dst, ctx, excluded, is_url),
            daemon=True,
        )
        self.worker.start()
        return True

    # ====================================================== 后台执行 ==
    def _run_sync(self, mode: str, src_arg, dst: Path,
                  ctx: Ctx, excluded, is_url: bool) -> None:
        progress_state = {"t0": time.time()}

        def progress_cb(done: int, total: int) -> None:
            if total <= 0:
                self.root.after(0, self._set_progress, 0, 0, None)
                return
            elapsed = time.time() - progress_state["t0"]
            eta = elapsed / done * (total - done) if 0 < done < total else 0.0
            self.root.after(0, self._set_progress, done, total, eta)

        try:
            if is_url:
                url = str(src_arg)
                cache = git_cache_dir(url)
                self.msg_queue.put(f"[GIT]    仓库缓存目录：{cache}")
                ok, err = ensure_git_repo(url, cache, self.msg_queue.put)
                if not ok:
                    ctx.stats.errors += 1
                    self.msg_queue.put(f"[ERROR]  {err}")
                    return
                actual_src = cache
            else:
                actual_src = Path(src_arg)

            self.msg_queue.put("[准备]   正在扫描并比较文件…")
            t_plan = time.time()

            if mode == "two_way":
                plan = plan_two_way(actual_src, dst, ctx, excluded)
            elif mode == "copy_only":
                plan = plan_copy_only(actual_src, dst, ctx, excluded)
            else:
                plan = plan_mirror(actual_src, dst, ctx, excluded)

            plan_ms = (time.time() - t_plan) * 1000

            self.msg_queue.put(
                f"[准备]   计划完成：{len(plan.ops)} 个操作，"
                f"{len(plan.conflicts)} 个冲突，"
                f"{plan.skipped} 个相同，耗时 {plan_ms:.0f} ms"
            )

            if plan.ops or plan.conflicts:
                self.root.after(0, self.progress.configure,
                                "maximum", max(plan.total_units, 1))
                progress_state["t0"] = time.time()
                execute_plan(plan, ctx, progress_cb)
            else:
                self.root.after(0, self._set_progress, 0, 0, None)
                self.msg_queue.put("[信息]   没有需要同步的内容")

        except Exception as exc:
            ctx.stats.errors += 1
            self.msg_queue.put(f"[ERROR]  同步异常：{exc}")
        finally:
            self.root.after(0, self._on_finish, ctx)
            self.sync_done_event.set()

    # ====================================================== 进度显示 ==
    def _set_progress(self, done: int, total: int, eta: float | None) -> None:
        self.progress.configure(maximum=max(total, 1))
        self.progress_var.set(done)
        if total <= 0:
            self.progress_label.set("")
            return
        pct = done / total * 100
        text = f"进度：{done}/{total}（{pct:.0f}%）"
        if eta is not None and done < total:
            text += f"   预计剩余：{human_time(eta)}"
        elif done >= total:
            text += "   已完成"
        self.progress_label.set(text)

    # ====================================================== 完成 ==
    def _on_finish(self, ctx: Ctx) -> None:
        s = ctx.stats
        prefix = "将" if ctx.dry_run else "已"
        self.msg_queue.put("-" * 60)
        self.msg_queue.put(
            f"{prefix}复制 {s.copied} 个文件（{human_size(s.bytes_copied)}）"
        )
        self.msg_queue.put(f"{prefix}删除 {s.deleted} 个文件")
        tail = f"跳过 {s.skipped} 个相同文件"
        if s.conflicts:
            tail += f"，发现 {s.conflicts} 个冲突"
        if s.errors:
            tail += f"，{s.errors} 个操作失败"
        self.msg_queue.put(tail)
        self.msg_queue.put("=" * 60)

        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.status_var.set("完成" if s.errors == 0 else f"完成（{s.errors} 个错误）")
        self.progress_label.set("已完成")

        if self.tray_icon is not None and not self.root.winfo_viewable():
            try:
                if s.errors:
                    self.tray_icon.notify(
                        f"同步完成，{s.errors} 个操作失败", APP_TITLE
                    )
                else:
                    self.tray_icon.notify(
                        f"同步完成：复制 {s.copied}，删除 {s.deleted}", APP_TITLE
                    )
            except Exception:
                pass

    def _stop(self) -> None:
        if self.worker and self.worker.is_alive():
            self.stop_requested = True
            self.status_var.set("正在停止…")

    # ====================================================== 自动同步 ==
    def _ensure_monitor_running(self) -> None:
        self.monitor_stop = False
        if self.monitor_thread is None or not self.monitor_thread.is_alive():
            self.monitor_thread = threading.Thread(
                target=self._auto_sync_loop, daemon=True
            )
            self.monitor_thread.start()
        self.auto_status.set("监控中…")

    def _stop_monitor(self) -> None:
        self.monitor_stop = True
        self.auto_status.set("未开启")

    def _on_auto_toggle(self) -> None:
        if self.auto_sync_var.get():
            self.monitor_reset = True
            self._ensure_monitor_running()
        else:
            self._stop_monitor()
        if self.current_index is not None:
            self._save_ui_to_profile(self.current_index)
            self._refresh_task_item(self.current_index)
        self._save_settings()

    def _read_interval(self) -> float:
        try:
            v = float(self.auto_interval_var.get())
            return max(1.0, v)
        except ValueError:
            return 5.0

    def _combined_signature(self) -> str | None:
        src_text = self.src_var.get().strip()
        dst_text = self.dst_var.get().strip()
        if not src_text or not dst_text:
            return None
        if is_git_url(src_text):
            return None
        try:
            a = Path(src_text).expanduser().resolve()
            b = Path(dst_text).expanduser().resolve()
        except Exception:
            return None
        if not a.is_dir() or not b.is_dir():
            return None
        if is_subpath(a, b) or is_subpath(b, a) or a == b:
            return None

        excluded = build_excluder(self.exclude_var.get().split())
        try:
            return f"{folder_signature(a, excluded)}|{folder_signature(b, excluded)}"
        except Exception:
            return None

    def _trigger_and_wait(self, reason: str) -> None:
        self.msg_queue.put(f"[自动]   {reason}")
        self.sync_done_event.clear()

        def _trigger():
            ok = self._start(from_auto=True)
            if not ok:
                self.sync_done_event.set()

        self.root.after(0, _trigger)

        t0 = time.time()
        while not self.sync_done_event.is_set():
            if self.monitor_stop:
                break
            if time.time() - t0 > 1800:
                self.msg_queue.put("[自动]  同步超过 30 分钟，放弃本次等待")
                break
            time.sleep(0.3)

        time.sleep(0.5)

    def _auto_sync_loop(self) -> None:
        last_sig: str | None = None
        last_tick = 0.0

        while not self.monitor_stop:
            if self.monitor_reset:
                last_sig = None
                self.monitor_reset = False

            interval = self._read_interval()
            src_text = self.src_var.get().strip()
            is_url = is_git_url(src_text)

            if self.worker and self.worker.is_alive():
                time.sleep(0.4)
                continue

            now = time.time()
            if now - last_tick < interval:
                time.sleep(0.4)
                continue
            last_tick = now

            if is_url:
                self.auto_status.set(f"Git 源：每 {interval:g} 秒拉取一次")
                self._trigger_and_wait("定时拉取 Git 仓库并同步…")
                if self.monitor_stop:
                    break
                self.auto_status.set("监控中…")
                continue

            sig = self._combined_signature()
            if sig is None:
                self.auto_status.set("等待有效路径…")
                time.sleep(interval)
                continue

            if last_sig is None:
                last_sig = sig
                self.auto_status.set("监控中…（已建立基线）")
                time.sleep(interval)
                continue

            if sig != last_sig:
                last_sig = sig
                self.auto_status.set("检测到更改，触发同步")
                self._trigger_and_wait("检测到文件夹变化，开始同步…")
                if self.monitor_stop:
                    break
                last_sig = self._combined_signature()
                self.auto_status.set("监控中…")

            time.sleep(interval)

        self.auto_status.set("未开启")

    # ====================================================== 关闭 ==
    def _on_close(self) -> None:
        # 先关闭设置窗口（如果开着）
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self._close_settings()

        # 托盘可用 + 开关打开 + 不是托盘“退出”菜单 → 隐藏到托盘
        if self._tray_should_enable() and not self._allow_real_exit:
            self._save_settings()
            self._hide_to_tray()
            return

        # 真正退出
        self._save_settings()
        self.monitor_stop = True
        self.stop_requested = True
        self._stop_tray()
        self.root.after(150, self.root.destroy)


def main() -> None:
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    SyncApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()