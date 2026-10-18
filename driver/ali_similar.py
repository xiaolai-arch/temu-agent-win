"""在商品详情页的「相似商品」网格里逐个采集（点卡片→新详情→采集→Alt+←回网格）。

用法：python ali_similar.py <x1,y1> <x2,y2> ...（网格卡片中心）
"""
import os
import sys
import time

import cv2

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import winutil
from input import human_click, alt_left
from shot import screenshot, ocr, _load_last_shot


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def shot(w, tag):
    return screenshot(w, f"sim-{tag}")


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


def page_sig(png):
    img = cv2.imread(png)
    top = img[230:520, 540:2450]
    return cv2.resize(top, (64, 8)).tobytes()


def main():
    cards = [tuple(int(v) for v in a.split(",")) for a in sys.argv[1:]]
    w = winutil.chrome_window()
    w.set_focus()
    time.sleep(0.4)
    ok = 0
    for i, (cx, cy) in enumerate(cards, 1):
        sig0 = page_sig(shot(w, f"pre{i}"))
        click_xy(w, cx, cy)
        time.sleep(8)
        png = shot(w, f"d{i}")
        sig1 = page_sig(png)
        if sig0 == sig1:
            log(f"#{i} 页面未跳转，跳过")
            continue
        btn = teal_button(png)
        if not btn:
            log(f"#{i} 详情页无采集按钮，跳过")
            alt_left()
            time.sleep(3)
            continue
        click_xy(w, *btn)
        ok += 1
        log(f"#{i} ✓ 采集点击 {btn}，停留 5 秒")
        time.sleep(5)
        alt_left()
        time.sleep(3.5)
    log(f"完成 {ok}/{len(cards)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
