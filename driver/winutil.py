"""Win32 公共层：DPI 感知、Edge 窗口枚举（UIA 壳层，只读）。"""
import ctypes
import subprocess
import time

ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_DPI_AWARE：一切坐标=物理像素

from pywinauto import Desktop  # noqa: E402

EDGE_CLASS = "Chrome_WidgetWin_1"


def is_msedge(pid: int) -> bool:
    out = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        capture_output=True, text=True,
    ).stdout.strip()
    return out.lower().startswith('"msedge.exe"')


def edge_windows() -> list:
    """桌面顶层、可见、属于 msedge.exe 的窗口（UIA 元素）。"""
    result = []
    for w in Desktop(backend="uia").windows(class_name=EDGE_CLASS):
        try:
            if w.is_visible() and is_msedge(w.process_id()):
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
    """普通用户级启动（绝不带调试/注入参数）。复用现有实例开窗口。"""
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
