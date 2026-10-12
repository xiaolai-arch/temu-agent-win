"""Phase 0 冒烟：找到（或拉起）日常 Edge → UIA 地址栏导航 → DPI-aware 截图。

红线：不点任何东西、不带任何自动化启动参数（只用 start msedge <url> 这种普通用户级启动）。
"""
import ctypes
import os
import subprocess
import sys
import time
from datetime import datetime

# 让 stdout 在 Git Bash / 任意控制台下都能打中文
sys.stdout.reconfigure(encoding="utf-8")

# DPI 感知：物理像素坐标（本机 150% 缩放，双 2560x1600）
ctypes.windll.shcore.SetProcessDpiAwareness(2)

from pywinauto import Desktop
from pywinauto.keyboard import send_keys

TARGET_URL = "https://agentseller.temu.com/main/customize-goods"
SHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "screenshots")


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def is_msedge(pid):
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True, text=True,
        ).stdout.strip()
        return out.lower().startswith('"msedge.exe"')
    except Exception:
        return False


def find_edge_windows():
    """返回桌面上属于 msedge.exe 的可见顶层窗口列表。"""
    wins = Desktop(backend="uia").windows(class_name="Chrome_WidgetWin_1")
    result = []
    for w in wins:
        try:
            if w.is_visible() and is_msedge(w.process_id()):
                result.append(w)
        except Exception:
            continue
    return result


def wait_edge_window(timeout=40):
    """找 Edge 可见窗口；没有则普通参数拉起（无任何自动化 flag）。"""
    wins = find_edge_windows()
    if wins:
        return wins[0], False
    log(f"无可见 Edge 窗口，普通参数拉起: start msedge {TARGET_URL}")
    subprocess.run(f'start msedge "{TARGET_URL}"', shell=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(2)
        wins = find_edge_windows()
        if wins:
            return wins[0], True
    raise RuntimeError("等待 Edge 窗口超时")


def navigate(win, url):
    """UIA 找地址栏 → Ctrl+L → 输入 URL → Enter。"""
    edits = [e for e in win.descendants(control_type="Edit")
             if "地址" in (e.element_info.name or "")]
    if not edits:
        raise RuntimeError("UIA 未找到地址栏 Edit（'地址和搜索栏'）")
    addr = edits[0]
    log(f"地址栏已定位: name={addr.element_info.name!r}")
    addr.set_focus()
    time.sleep(0.3)
    send_keys("^l")
    time.sleep(0.2)
    send_keys("^a")
    time.sleep(0.1)
    send_keys(url, with_spaces=True)
    time.sleep(0.2)
    send_keys("{ENTER}")
    log("已回车导航")


def main():
    os.makedirs(SHOT_DIR, exist_ok=True)
    win, launched = wait_edge_window()
    log(f"Edge 窗口: hwnd={win.handle} title={win.window_text()!r} launched={launched}")
    if not launched:
        navigate(win, TARGET_URL)
    log("等待页面加载…")
    time.sleep(8)

    win.set_focus()
    time.sleep(0.5)
    img = win.capture_as_image()
    ts = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    path = os.path.abspath(os.path.join(SHOT_DIR, f"{ts}-smoke.png"))
    img.save(path)
    log(f"截图已存: {path} size={img.size}")

    tabs = [t.window_text() for t in win.descendants(control_type="TabItem")]
    log(f"标签页: {tabs}")
    log("SMOKE OK — 请人工确认截图中有「按勾选同步」「忆托ERP同步」按钮")


if __name__ == "__main__":
    main()
