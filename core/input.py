"""人类化输入：鼠标分步移动（随机速度/抖动）、按下/释放有间隔；键盘复用 pywinauto（内部 SendInput）。

所有鼠标坐标 = 屏幕物理像素（DPI-aware 进程，无虚拟化）。
"""
import ctypes
import ctypes.wintypes
import math
import random
import time

user32 = ctypes.windll.user32

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
INPUT_MOUSE = 0


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", _MOUSEINPUT)]
    _anonymous_ = ("u",)
    _fields_ = [("type", ctypes.c_ulong), ("u", _U)]


def _send_mouse(flags, dx=0, dy=0):
    inp = _INPUT(type=INPUT_MOUSE)
    inp.mi = _MOUSEINPUT(dx=dx, dy=dy, mouseData=0, dwFlags=flags,
                         time=0, dwExtraInfo=None)
    arr = (_INPUT * 1)(inp)
    user32.SendInput(1, arr, ctypes.sizeof(_INPUT))


def cursor_pos() -> tuple:
    pt = ctypes.wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def _move_to(x: int, y: int, steps: int | None = None):
    """分步移动 + 抖动，模拟人手；先快后慢（ease-out）。"""
    cx, cy = cursor_pos()
    dist = math.hypot(x - cx, y - cy)
    if dist < 2:
        return
    steps = steps or max(6, min(40, int(dist / 25)))
    for i in range(1, steps + 1):
        t = i / steps
        ease = 1 - (1 - t) ** 2  # ease-out quad
        nx = cx + (x - cx) * ease + random.uniform(-1.5, 1.5)
        ny = cy + (y - cy) * ease + random.uniform(-1.5, 1.5)
        user32.SetCursorPos(int(nx), int(ny))
        time.sleep(random.uniform(0.008, 0.02))
    user32.SetCursorPos(x, y)


def _safe_focus(w):
    """set_focus 带 COMError 容错：UIA 句柄失效时退化为 Win32 前台激活。"""
    if w is None:
        return
    try:
        w.set_focus()
    except Exception:
        try:
            user32.SetForegroundWindow(w.handle)
        except Exception:
            pass


def human_click(x: int, y: int, activate_window=None):
    """移动到 (x,y) 屏幕物理像素 → 左键点击。可先激活目标窗口。"""
    if activate_window is not None:
        _safe_focus(activate_window)
        time.sleep(random.uniform(0.15, 0.3))
    _move_to(x, y)
    time.sleep(random.uniform(0.06, 0.15))
    _send_mouse(MOUSEEVENTF_LEFTDOWN)
    time.sleep(random.uniform(0.05, 0.09))
    _send_mouse(MOUSEEVENTF_LEFTUP)
    time.sleep(random.uniform(0.1, 0.25))


def type_keys(keys: str, pause: float | None = None):
    """pywinauto 键盘语法：{ENTER} {ESC} ^l ^a，中文文本直接传。"""
    from pywinauto.keyboard import send_keys
    send_keys(keys, with_spaces=True, pause=pause if pause is not None else 0.03)


MOUSEEVENTF_MOVE_ABS = MOUSEEVENTF_MOVE | 0x8000  # + MOUSEEVENTF_ABSOLUTE


def _send_move_abs(x: int, y: int):
    """绝对坐标移动（归一化到 0..65535）。必须用 SendInput 绝对移动事件——
    SetCursorPos 的移动不触发网页 dragstart（2026-10-17 拖拽验证码实测）。"""
    sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    _send_mouse(MOUSEEVENTF_MOVE_ABS, int(x * 65535 / (sw - 1)), int(y * 65535 / (sh - 1)))


def human_drag(sx: int, sy: int, tx: int, ty: int, activate_window=None):
    """人类化拖拽（屏幕物理像素）。按下→停顿→起步小步→缓动 42 步→停顿→抬起。
    专治需要 dragstart 的网页拖拽（Temu 拖拽类验证码已验证）。"""
    if activate_window is not None:
        _safe_focus(activate_window)
        time.sleep(random.uniform(0.3, 0.5))
    _send_move_abs(sx, sy)
    time.sleep(random.uniform(0.2, 0.35))
    _send_mouse(MOUSEEVENTF_LEFTDOWN)
    time.sleep(random.uniform(0.24, 0.32))
    # 起步小步：触发 dragstart
    for k in range(1, 7):
        _send_move_abs(sx + int(k * 3), sy + int(k))
        time.sleep(0.03)
    cx, cy = sx + 18, sy + 6
    steps = 42
    for i in range(1, steps + 1):
        t = i / steps
        ease = 1 - (1 - t) ** 2  # ease-out
        _send_move_abs(int(cx + (tx - cx) * ease + random.uniform(-2, 2)),
                       int(cy + (ty - cy) * ease + random.uniform(-2, 2)))
        time.sleep(random.uniform(0.012, 0.032))
    _send_move_abs(tx, ty)
    time.sleep(random.uniform(0.35, 0.5))
    _send_mouse(MOUSEEVENTF_LEFTUP)
    time.sleep(random.uniform(0.7, 0.9))


def drag_window_coords(sx: int, sy: int, tx: int, ty: int, activate_window=None):
    """窗口坐标系（与 ctl.py shot/click 同一坐标系）拖拽。"""
    from shot import _load_last_shot
    ls = _load_last_shot()
    human_drag(ls["left"] + sx, ls["top"] + sy,
               ls["left"] + tx, ls["top"] + ty, activate_window=activate_window)


VK_MENU = 0x12
VK_LEFT = 0x25
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.wintypes.WORD), ("wScan", ctypes.wintypes.WORD),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _KU(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT)]


class _KINP(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", ctypes.c_ulong), ("u", _KU)]


def _key(vk, up=False):
    inp = _KINP(type=INPUT_KEYBOARD)
    inp.ki = _KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP if up else 0, 0, None)
    arr = (_KINP * 1)(inp)
    user32.SendInput(1, arr, ctypes.sizeof(_KINP))


def alt_left():
    """SendInput 直发 Alt+←（浏览器后退）。pywinauto 的 %{LEFT} 实测不可靠。"""
    _key(VK_MENU)
    time.sleep(0.05)
    _key(VK_LEFT)
    time.sleep(0.05)
    _key(VK_LEFT, up=True)
    time.sleep(0.05)
    _key(VK_MENU, up=True)
    time.sleep(1.2)
