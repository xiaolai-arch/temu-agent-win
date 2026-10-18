"""Chrome 搜索结果页逐商品采集（一屏 10 个：2 行 × 5 列），采完自动下滚一屏。

用法：python collect_screen.py [y1] [y2] [scroll]
  y1/y2 = 两行卡片图片中心 y（默认 570 1045）
  scroll = 采完后是否下滚 660px（0/1，默认 1）

每件：点卡片 → 校验详情页（有商品ID、无采集本页）→ 点青色「采集此商品」→ 关标签。
风控：出现验证时自动调 temu_captcha_slide 解滑块后重试一次。
"""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import random

import winutil
import uia_shell
from input import human_click, type_keys
from input import _send_move_abs
from shot import screenshot, ocr, _load_last_shot
import temu_captcha_slide


COLS = [408, 760, 1115, 1470, 1820]
ok_count = 0


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def shot(w, tag):
    return screenshot(w, f"cs-{tag}")


def click_xy(w, x, y):
    ls = _load_last_shot()
    human_click(ls["left"] + x, ls["top"] + y, activate_window=w)


def teal_button(png):
    import cv2
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
    if r[1] - r[0] < 60:      # 按钮宽度至少 60
        return None
    return ((r[0] + r[1]) // 2, 1499)


def handle_captcha(w):
    t = "".join(l.get("text", "") for l in ocr(shot(w, "cap")).get("lines", [])).replace(" ", "")
    if ("安全验证" in t) or ("滑动即可完成拼图" in t):
        log("  ⚠ 出现验证，自动解滑块…")
        temu_captcha_slide.main()
        time.sleep(2)
        return True
    return False


def back_to_search(w):
    for t in uia_shell.tab_items(win=w):
        if (t.window_text() or "").startswith("Temu"):
            t.select()
            time.sleep(1.0)
            return True
    return False


def collect_one(w, x, y, idx):
    global ok_count
    if not back_to_search(w):
        log("  ✗ 搜索标签丢失")
        return False
    click_xy(w, x, y)
    time.sleep(7)
    if handle_captcha(w):
        # 验证过了但当前标签已刷新，重走一次
        back_to_search(w)
        click_xy(w, x, y)
        time.sleep(7)
    png = shot(w, f"d{idx}")
    lines = ocr(png).get("lines", [])
    t = "".join(l.get("text", "") for l in lines).replace(" ", "")
    if ("商品ID" not in t and "店铺信息" not in t) or "采集本页" in t:
        log(f"  #{idx} 非详情页，跳过")
        return False
    btn = teal_button(png)
    if not btn:
        log(f"  #{idx} 未找到采集按钮，跳过")
        type_keys("^w")
        time.sleep(1.0)
        return False
    click_xy(w, *btn)
    log(f"  #{idx} ✓ 采集点击 {btn}，停留 10 秒…")
    ok_count += 1
    time.sleep(10)                        # 用户要求：点完停留 10 秒
    type_keys("^w")
    time.sleep(1.4)
    return True


def main():
    y1 = int(sys.argv[1]) if len(sys.argv) > 1 else 570
    y2 = int(sys.argv[2]) if len(sys.argv) > 2 else 1045
    do_scroll = (sys.argv[3] != "0") if len(sys.argv) > 3 else True
    global COLS
    if len(sys.argv) > 4:
        COLS = [int(v) for v in sys.argv[4].split(",")]
    w = winutil.chrome_window()
    w.set_focus()
    time.sleep(0.4)
    i = 0
    for y in (y1, y2):
        for x in COLS:
            i += 1
            collect_one(w, x, y, i)
    log(f"本屏完成：{ok_count}/{len(COLS)*2}")
    if do_scroll:
        back_to_search(w)
        import ctypes
        MOUSEEVENTF_WHEEL = 0x0800

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
        _send_move_abs = getattr(__import__("input"), "_send_move_abs")
        _send_move_abs(ls["left"] + 1290, ls["top"] + 800)
        time.sleep(0.3)
        for _ in range(13):        # 13 格 × 120 ≈ 下滚 2 行
            inp = _INP(type=0)
            inp.mi = _MI(0, 0, 4294967176, MOUSEEVENTF_WHEEL, 0, None)   # -120 向下
            arr = (_INP * 1)(inp)
            ctypes.windll.user32.SendInput(1, arr, ctypes.sizeof(_INP))
            time.sleep(0.1)
        time.sleep(3)
        log("已下滚一屏")
    return 0


if __name__ == "__main__":
    sys.exit(main())
