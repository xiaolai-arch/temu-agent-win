"""明星商品扫描：头部词按订单排序，提取 爆款卡片（标题+销量+价格）。
只读，不点击。输出 select/data/stars.json
"""
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(BASE, "..", "core")))
sys.path.insert(0, BASE)

import winutil
import uia_shell
from shot import screenshot
from scan_keywords import parse_page, scroll_down, ensure_non_miaoshou_tab, log

OUT = os.path.join(BASE, "data", "stars.json")
WORDS = [
    "custom thanksgiving napkins",
    "custom christmas napkins",
    "custom bachelorette party napkins",
    "custom disco napkins",
    "custom cowgirl napkins",
    "custom baby shower napkins",
]


def cluster_cards(page):
    """按列x聚类：标题行(上方) + 价格 + sold(下方) 组成卡片"""
    cards = []
    solds = page["solds"]
    prices = page["prices"]
    for sv, sx, sy in solds:
        # 同列价格（y在sold上方0-160）
        pv = None
        for v, px, py in prices:
            if abs(px - sx) < 110 and -10 <= (sy - py) <= 160:
                pv = v if pv is None else min(pv, v)
        cards.append({"sold": sv, "x": sx, "y": sy, "price": pv})
    cards.sort(key=lambda c: -c["sold"])
    # 标题配对：parse_page 的 titles 不带坐标，这里重新带坐标解析
    return cards


def parse_page_titled(png):
    """parse_page 增强版：标题行保留坐标，卡片级配对"""
    page = parse_page(png)
    from shot import ocr
    data = ocr(png)
    tlines = []
    for l in data.get("lines", []):
        t = (l.get("text") or "").strip()
        if not t or len(t) < 8:
            continue
        low = t.lower().replace(" ", "")
        if any(k in low for k in ("napkin", "serviette", "餐巾", "纸巾")) and l["w"] > 120:
            tlines.append((t, l["x"], l["y"]))
    page["tlines"] = tlines
    return page


def main():
    results = []
    w = winutil.chrome_window()
    if not w:
        log("✗ 无 Chrome 窗口")
        return 1
    w.set_focus()
    time.sleep(0.5)
    for kw in WORDS:
        ensure_non_miaoshou_tab(w)
        q = kw.replace(" ", "+")
        url = f"https://www.aliexpress.us/wholesale?SearchText={q}&sortType=total_tranpro"
        uia_shell.navigate(w, url)
        time.sleep(9)
        png = screenshot(w, f"star-{q}")
        p0 = parse_page_titled(png)
        scroll_down()
        png2 = screenshot(w, f"star-{q}-s2")
        p1 = parse_page_titled(png2)
        cards = cluster_cards(p0) + cluster_cards(p1)
        tlines = p0["tlines"] + p1["tlines"]
        for c in cards:
            # 标题 = 同列、sold 上方 40-260 的餐巾标题行（取最长一条）
            cands = [t for t, tx, ty in tlines
                     if abs(tx - c["x"]) < 120 and 40 <= (c["y"] - ty) <= 260]
            c["title"] = max(cands, key=len) if cands else ""
        cards = [c for c in cards if c["sold"] >= 30][:10]
        results.append({"keyword": kw, "cards": cards})
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=1)
        log(f"  {kw}: {len(cards)} 张卡 TOP={cards[0] if cards else None}")
        time.sleep(2)
    log("=== 完成 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
