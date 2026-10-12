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


def human_click(x: int, y: int, activate_window=None):
    """移动到 (x,y) 屏幕物理像素 → 左键点击。可先激活目标窗口。"""
    if activate_window is not None:
        activate_window.set_focus()
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
