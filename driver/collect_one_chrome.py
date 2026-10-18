"""Chrome 里单个商品采集：关旧详情标签 → 回搜索页 → 点指定卡片 → 采集此商品。

用法：python collect_one_chrome.py <卡片x> <卡片y>
坐标 = Chrome 窗口截图坐标系（ctl/shot 同一套）。
"""
import os
import sys
import time

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import winutil
import uia_shell
from input import human_click, type_keys
from shot import screenshot, ocr, _load_last_shot


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def shot(w, tag):
    return screenshot(w, f"c1-{tag}")


def click_xy(w, x, y):
    ls = _load_last_shot()
    human_click(ls["left"] + x, ls["top"] + y, activate_window=w)


def teal_button(png):
    """底部工具条的青色「采集此商品」按钮中心。"""
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
    return ((r[0] + r[1]) // 2, 1499)


def close_detail_tabs(w):
    """关闭所有 Temu 商品详情标签（标题以商品名开头且含 Temu）。"""
    n = 0
    for t in uia_shell.tab_items(win=w):
        tx = t.window_text() or ""
        if "Temu" in tx and not tx.startswith("Temu"):
            t.select()
            time.sleep(0.8)
            type_keys("^w")
            time.sleep(1.2)
            n += 1
    return n


def back_to_search(w):
    for t in uia_shell.tab_items(win=w):
        if (t.window_text() or "").startswith("Temu"):
            t.select()
            time.sleep(1.2)
            return True
    return False


def main():
    x, y = int(sys.argv[1]), int(sys.argv[2])
    w = winutil.chrome_window()
    w.set_focus()
    time.sleep(0.4)

    n = close_detail_tabs(w)
    if n:
        log(f"关闭 {n} 个旧详情标签")
    if not back_to_search(w):
        log("✗ 找不到 Temu 搜索标签")
        return 1
    type_keys("^{HOME}")          # 回到页首，卡片网格坐标才准
    time.sleep(2)

    click_xy(w, x, y)
    time.sleep(7)
    png = shot(w, "d")
    # 校验确实是详情页：有「商品ID/店铺信息」，且没有搜索页工具条特征「采集本页」
    lines = ocr(png).get("lines", [])
    t = "".join(l.get("text", "") for l in lines).replace(" ", "")
    if "商品ID" not in t and "店铺信息" not in t:
        log("✗ 打开的不是商品详情页（无商品ID），不采集")
        return 1
    if "采集本页" in t:
        log("✗ 仍在搜索页（误判），不采集")
        return 1
    btn = teal_button(png)
    if not btn:
        log("✗ 详情页未出现采集按钮（可能未打开/风控）")
        type_keys("^w")
        time.sleep(1.0)
        return 1
    click_xy(w, *btn)
    log(f"✓ 已点采集此商品 {btn}")
    time.sleep(5)
    shot(w, "after")
    return 0


if __name__ == "__main__":
    sys.exit(main())
