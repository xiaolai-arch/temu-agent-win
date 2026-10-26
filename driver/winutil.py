"""Win32 公共层：DPI 感知、浏览器窗口枚举（UIA 壳层，只读）。

2026-10-26 起同步流程的目标浏览器改为 ego 浏览器（Chromium 内核 fork）。
窗口类名与 Edge 同为 Chrome_WidgetWin_1，故 OCR/像素/UIA 引擎可原样复用；
差异仅在进程名（ego.exe vs msedge.exe）、启动命令、profile 路径三处。
BROWSER 环境变量可切回 Edge：TEMU_BROWSER=edge
"""
import ctypes
import os
import subprocess
import time

ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_DPI_AWARE：一切坐标=物理像素

from pywinauto import Desktop  # noqa: E402

EDGE_CLASS = "Chrome_WidgetWin_1"

# 目标浏览器：ego（默认）或 edge。决定进程名过滤、启动命令、插件检查路径。
BROWSER = os.environ.get("TEMU_BROWSER", "ego").strip().lower()
if BROWSER not in ("ego", "edge"):
    BROWSER = "ego"

# ego 的 profile 目录（活动 profile = Profile 1，有 TEMU 登录态与解压插件）
EGO_PROFILE_DIR = os.path.expandvars(
    r"%LOCALAPPDATA%\Citro Labs\ego lite\User Data\Profile 1")
EDGE_PROFILE_DIR = os.path.expandvars(
    r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default")


def profile_dir() -> str:
    """当前目标浏览器的 profile 目录（doctor / restore 读插件注册用）。"""
    return EGO_PROFILE_DIR if BROWSER == "ego" else EDGE_PROFILE_DIR


def is_browser(pid: int) -> bool:
    """pid 是否属于当前目标浏览器进程（ego.exe / msedge.exe）。
    保留旧名 is_msedge 作为别名，避免旧调用点失效。"""
    want = "ego.exe" if BROWSER == "ego" else "msedge.exe"
    out = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True, text=True,
    ).stdout.strip()
    return out.lower().startswith(f'"{want}"')


is_msedge = is_browser  # 向后兼容别名


def edge_windows() -> list:
    """桌面顶层、可见、属于当前目标浏览器（ego.exe/msedge.exe）的窗口（UIA 元素）。"""
    result = []
    for w in Desktop(backend="uia").windows(class_name=EDGE_CLASS):
        try:
            if w.is_visible() and is_browser(w.process_id()):
                result.append(w)
        except Exception:
            continue
    return result


def find_window(hwnd: int):
    for w in edge_windows():
        if w.handle == hwnd:
            return w
    return None


def default_window():
    """当前唯一的 Edge 窗口；多个时取最上层（Z 序第一个）。"""
    wins = edge_windows()
    return wins[0] if wins else None


def launch_edge(url: str, timeout: float = 40) -> object:
    """普通用户级启动（绝不带调试/注入参数）。复用现有实例开窗口。
    2026-10-26：ego 改用 ego-browser.exe（带 URL 参数直接开窗并导航，
    实测可用）；Edge 保持 start msedge。"""
    if BROWSER == "ego":
        exe = (r"C:\Users\34191\.local\share\ego\active_version_dir"
               r"\ego-browser.exe")
        subprocess.Popen([exe, url])
    else:
        subprocess.run(f'start msedge "{url}"', shell=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(2)
        wins = edge_windows()
        if wins:
            time.sleep(3)  # 给首窗一点初始化时间
            return wins[0]
    raise RuntimeError("等待 Edge 窗口超时")


def window_summary(w) -> dict:
    r = w.rectangle()
    return {
        "hwnd": w.handle,
        "title": w.window_text(),
        "rect": {"left": r.left, "top": r.top, "right": r.right, "bottom": r.bottom},
        "w": r.right - r.left,
        "h": r.bottom - r.top,
        "minimized": w.is_minimized(),
    }


# ---------- Chrome 支持（2026-10-17 加：插件安装 + 采集实验用） ----------

def _proc_name(pid: int) -> str:
    out = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True, text=True,
    ).stdout.strip()
    return out.split(",")[0].strip('"').lower() if out else ""


def is_chrome(pid: int) -> bool:
    return _proc_name(pid).startswith("chrome.exe")


def chrome_windows() -> list:
    result = []
    for w in Desktop(backend="uia").windows(class_name=EDGE_CLASS):
        try:
            if w.is_visible() and is_chrome(w.process_id()):
                result.append(w)
        except Exception:
            continue
    return result


def chrome_window():
    wins = chrome_windows()
    return wins[0] if wins else None


def launch_chrome(url: str, timeout: float = 40) -> object:
    """普通用户级启动（绝不带调试/注入参数）。"""
    subprocess.run(f'start chrome "{url}"', shell=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(2)
        wins = chrome_windows()
        if wins:
            time.sleep(3)
            return wins[0]
    raise RuntimeError("等待 Chrome 窗口超时")
