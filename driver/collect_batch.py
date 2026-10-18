"""Temu 搜索结果页批量采集（单商品流程：进详情 → 采集此商品 → 关标签）。

用法：python collect_batch.py <卡片x,y 空格分隔...>
例：  python collect_batch.py 518,430 778,430 1037,430
"""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import winutil
import uia_shell
from input import human_click, type_keys
from shot import screenshot, ocr

SEARCH_TAB_KEYS = ["定制餐巾", "Temu"]


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def shot(w, tag):
    return screenshot(w, f"cb-{tag}")


def click_xy(w, x, y):
    from shot import _load_last_shot
    ls = _load_last_shot()
    human_click(ls["left"] + x, ls["top"] + y, activate_window=w)


def find_line(png, *words):
    for l in ocr(png).get("lines", []):
        t = (l.get("text") or "").replace(" ", "")
        if any(wd in t for wd in words):
            return l
    return None


def open_search(w):
    items = uia_shell.tab_items(win=w)
    for key in SEARCH_TAB_KEYS:
        for t in items:
            if key in (t.window_text() or ""):
                t.select()
                time.sleep(1.2)
                return True
    return False


def collect_one(w, x, y, idx):
    if not open_search(w):
        log("✗ 找不到搜索标签")
        return False
    click_xy(w, x, y)
    time.sleep(6.5)
    png = shot(w, f"d{idx}")
    stop = find_line(png, "停用插件")
    if not stop:
        log(f"  #{idx} 详情页工具条未出现，跳过")
        # 关掉可能新开的标签
        type_keys("^w")
        time.sleep(1.0)
        return False
    cx = stop["x"] + stop["w"] // 2 - 90   # 「采集此商品」在「停用插件」左侧
    cy = stop["y"] + stop["h"] // 2
    click_xy(w, cx, cy)
    log(f"  #{idx} 已点采集此商品 ({cx},{cy})")
    time.sleep(4.5)
    shot(w, f"a{idx}")
    type_keys("^w")          # 关详情标签
    time.sleep(1.5)
    return True


def main():
    specs = sys.argv[1:]
    if not specs:
        print(__doc__)
        return 1
    w = winutil.default_window()
    ok = 0
    for i, s in enumerate(specs, 1):
        x, y = (int(v) for v in s.split(","))
        if collect_one(w, x, y, i):
            ok += 1
        log(f"进度 {i}/{len(specs)}")
    log(f"完成：{ok}/{len(specs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
