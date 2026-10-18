"""速卖通搜索结果页逐商品采集（一屏：2 行 × 5 列，采完自动下滚）。

用法：python ali_screen.py <y1> <y2> [x1,x2,x3,x4,x5]
"""
import os
import sys
import time

import cv2

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import winutil
import uia_shell
from input import human_click, type_keys, alt_left
from shot import screenshot, ocr, _load_last_shot

COLS = [686, 1005, 1317, 1648, 1986]


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def shot(w, tag):
    return screenshot(w, f"as-{tag}")


def click_xy(w, x, y):
    ls = _load_last_shot()
    human_click(ls["left"] + x, ls["top"] + y, activate_window=w)


def teal_button(png):
    img = cv2.imread(png)
    strip = img[1470:1525, 1000:1350]
    hsv = cv2.cvtColor(strip, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    mask = (h > 75) & (h < 95) & (s > 90) & (v > 150)
    col = mask.sum(axis=0)
    runs = []
    x = 0
    while x < len(col):
        if col[x] > 20:
            s0 = x
            while x < len(col) and col[x] > 20:
                x += 1
            runs.append((1000 + s0, 1000 + x))
        else:
            x += 1
    if not runs:
        return None
    r = max(runs, key=lambda r: r[1] - r[0])
    return ((r[0] + r[1]) // 2, 1499) if r[1] - r[0] >= 60 else None


def on_list(png):
    """搜索列表页特征：工具条有 全选/采集本页。"""
    t = "".join(l.get("text", "") for l in ocr(png).get("lines", [])).replace(" ", "")
    return ("全选" in t) or ("采集本页" in t)


def main():
    y1 = int(sys.argv[1]) if len(sys.argv) > 1 else 705
    y2 = int(sys.argv[2]) if len(sys.argv) > 2 else 1230
    if len(sys.argv) > 3:
        COLS[:] = [int(v) for v in sys.argv[3].split(",")]
    w = winutil.chrome_window()
    w.set_focus()
    time.sleep(0.4)
    ok = 0
    idx = 0
    for y in (y1, y2):
        for x in COLS:
            idx += 1
            click_xy(w, x, y)
            time.sleep(8)
            png = shot(w, f"d{idx}")
            if on_list(png):
                log(f"  #{idx} 仍在列表页（点击未生效），跳过")
                continue
            btn = teal_button(png)
            if not btn:
                log(f"  #{idx} 详情页无采集按钮，跳过")
                type_keys("^w")
                time.sleep(1.4)
                continue
            click_xy(w, *btn)
            ok += 1
            log(f"  #{idx} ✓ 采集点击 {btn}，停留 5 秒")
            time.sleep(5)
            type_keys("^w")
            time.sleep(1.6)
    log(f"本屏完成：{ok}/{idx}")
    # 下滚一屏（2 行）
    back = [t for t in uia_shell.tab_items(win=w) if (t.window_text() or "").startswith("AliExpress") or "napkins" in (t.window_text() or "").lower()]
    if back:
        back[0].select()
        time.sleep(1.0)
    import ctypes

    class _MI(ctypes.Structure):
        _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                    ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_void_p)]

    class _U(ctypes.Union):
        _fields_ = [("mi", _MI)]

    class _INP(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", ctypes.c_ulong), ("u", _U)]

    ls = _load_last_shot()
    from input import _send_move_abs
    _send_move_abs(ls["left"] + 1290, ls["top"] + 800)
    time.sleep(0.3)
    for _ in range(13):
        inp = _INP(type=0)
        inp.mi = _MI(0, 0, 4294967176, 0x0800, 0, None)
        arr = (_INP * 1)(inp)
        ctypes.windll.user32.SendInput(1, arr, ctypes.sizeof(_INP))
        time.sleep(0.1)
    time.sleep(3)
    log("已下滚一屏")
    return 0


if __name__ == "__main__":
    sys.exit(main())
