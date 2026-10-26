"""选品调研：速卖通搜索页只读扫描 v2（不点任何商品/采集按钮，不关标签）。

用法：python scan_keywords.py [起始索引]
每词：导航搜索 URL → 等9s → 截图×(1屏+滚1屏) → OCR → 解析
输出：select/data/scan_results.json（逐词落盘，可断点续跑）
OCR 价格噪声处理：容忍全角 · ． 。 ℃ 与 s→$ 误读；每行只取第一个价格（促销价）
"""
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
BASE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.abspath(os.path.join(BASE, "..", "core"))
sys.path.insert(0, CORE)

import winutil
import uia_shell
from input import _send_move_abs
from shot import screenshot, ocr, _load_last_shot

OUT = os.path.join(BASE, "data", "scan_results.json")

KEYWORDS = [
    ("custom napkins", "基线-旧池"),
    ("custom wedding napkins", "基线-旧池"),
    ("custom christmas napkins", "季节-圣诞"),
    ("personalized christmas napkins", "季节-圣诞"),
    ("custom thanksgiving napkins", "季节-感恩节"),
    ("personalized holiday napkins", "季节-节日通用"),
    ("custom valentines day napkins", "季节-情人节(12月上架)"),
    ("custom new years eve napkins", "季节-跨年"),
    ("custom birthday napkins", "场合-生日"),
    ("custom bridal shower napkins", "场合-新娘派对"),
    ("custom baby shower napkins", "场合-宝宝宴"),
    ("custom bachelorette party napkins", "场合-单身派对"),
    ("personalized engagement napkins", "场合-订婚"),
    ("custom anniversary napkins", "场合-周年"),
    ("custom graduation napkins", "场合-毕业"),
    ("personalized baptism napkins", "场合-洗礼(小众)"),
    ("custom retirement napkins", "场合-退休(小众)"),
    ("quinceanera napkins personalized", "场合-十五岁(西语市场)"),
    ("boho wedding napkins", "风格-波西米亚"),
    ("sage green wedding napkins", "风格-鼠尾草绿"),
    ("rustic wedding napkins personalized", "风格-乡村风"),
    ("custom disco napkins", "风格-迪斯科"),
    ("custom cowgirl napkins", "风格-西部牛仔女"),
    ("custom linen napkins", "类型-亚麻质感"),
    ("monogram napkins", "类型-字母组合"),
    ("custom napkins bulk", "B2B-批量"),
]

SEP = "[·.．。,，℃:;]"          # OCR 把小数点读成各种东西
PRICE_RE = re.compile(rf"[sS$￥$]\s*(\d{{1,3}})\s*{SEP}\s*(\d{{1,2}})")
SOLD_RE = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*([KkMm万])?\+?\s*sold")
SOLD_CN_RE = re.compile(r"已售\s*(\d{1,3}(?:[.,]\d+)?)\s*([万KkMm])?")
PROMO_WORDS = ("save", "offwith", "shopper", "coupon", "节省", "零售", "each", "piece")
NAPKIN_WORDS = ("napkin", "serviette", "餐巾", "纸巾", "napki")


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def load_results():
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    return []


def save(results):
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)


def parse_page(png):
    """单页 OCR → {prices:[(v,x,y)], solds:[(v,x,y)], badges, lines}"""
    data = ocr(png)
    out = {"prices": [], "solds": [], "choice": 0, "customizable": 0,
           "napkin_lines": 0, "custom_lines": 0, "total_lines": 0,
           "titles": []}
    for l in data.get("lines", []):
        t = (l.get("text") or "").strip()
        if not t:
            continue
        tl = t.lower().replace(" ", "")
        out["total_lines"] += 1
        if any(w in tl for w in PROMO_WORDS):
            continue
        m = PRICE_RE.search(t)
        if m:
            try:
                v = float(f"{m.group(1)}.{m.group(2)}")
                if 0.3 <= v <= 200:
                    out["prices"].append((v, l["x"], l["y"]))
            except ValueError:
                pass
        ms = SOLD_RE.search(t) or SOLD_CN_RE.search(t)
        if ms:
            try:
                v = float(ms.group(1).replace(",", "."))
                unit = ms.group(2) or ""
                v *= 10000 if unit in ("万",) else 1000 if unit.lower() == "k" else 1000000 if unit.lower() == "m" else 1
                out["solds"].append((int(v), l["x"], l["y"]))
            except ValueError:
                pass
        if "choice" in tl and len(tl) < 12:
            out["choice"] += 1
        if "customiz" in tl:
            out["customizable"] += 1
        if any(k in tl for k in NAPKIN_WORDS):
            out["napkin_lines"] += 1
        if any(k in tl for k in ("custom", "personali", "logo", "monogram", "定制")):
            out["custom_lines"] += 1
        if 400 < l["y"] < 1200 and l["w"] > 150 and not PRICE_RE.search(t) and not ms:
            out["titles"].append(t)
    return out


def merge_pages(pages):
    prices = [p for pg in pages for p in pg["prices"]]
    solds_unpaired = [s for pg in pages for s in pg["solds"]]
    # 价格配对去重：同列(x差<90)且 y 差<170 的 sold 归给最近 price，一 sold 只配一 price
    used = set()
    paired_solds = []
    for v, px, py in prices:
        best, bd = None, 1e9
        for i, (s, sx, sy) in enumerate(solds_unpaired):
            if i in used:
                continue
            if abs(sx - px) < 110 and abs(sy - py) < 170:
                d = abs(sx - px) * 2 + abs(sy - py)
                if d < bd:
                    best, bd = i, d
        if best is not None:
            used.add(best)
            paired_solds.append(solds_unpaired[best][0])
    return {
        "prices": sorted(round(v, 2) for v, _, _ in prices),
        "solds": sorted(paired_solds, reverse=True),
        "choice": sum(pg["choice"] for pg in pages),
        "customizable": sum(pg["customizable"] for pg in pages),
        "napkin_lines": sum(pg["napkin_lines"] for pg in pages),
        "custom_lines": sum(pg["custom_lines"] for pg in pages),
        "total_lines": sum(pg["total_lines"] for pg in pages),
        "titles": [t for pg in pages for t in pg["titles"]][:40],
    }


def scroll_down(notches=11):
    ls = _load_last_shot()
    _send_move_abs(ls["left"] + 1290, ls["top"] + 800)
    time.sleep(0.3)
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

    for _ in range(notches):
        inp = _INP(type=0)
        inp.mi = _MI(0, 0, 4294967176, 0x0800, 0, None)
        ctypes.windll.user32.SendInput(1, (_INP * 1)(inp), ctypes.sizeof(_INP))
        time.sleep(0.09)
    time.sleep(3)


def is_captcha(text_joined):
    t = text_joined.replace(" ", "")
    if "访问此设备" in t or ("想要" in t and "允许" in t):
        return "perm"
    if "滑动即可完成拼图" in t or ("安全验证" in t and "拖动" not in t and "朝向" not in t):
        return "slide"
    if "安全验证" in t or "朝向" in t or "拖动" in t:
        return "hard"
    return None


def ensure_non_miaoshou_tab(w):
    items = uia_shell.tab_items(win=w)
    for t in items:
        if "妙手" in (t.window_text() or ""):
            continue
        try:
            t.select()
            time.sleep(1.0)
            return
        except Exception:
            continue
    from input import type_keys
    type_keys("^t")
    time.sleep(1.2)


def scan_keyword(w, kw, dim, results):
    ensure_non_miaoshou_tab(w)
    q = kw.replace(" ", "+")
    uia_shell.navigate(w, f"https://www.aliexpress.us/wholesale?SearchText={q}")
    time.sleep(9)
    png = screenshot(w, f"scan-{q}")
    pg0 = parse_page(png)
    cap = is_captcha("".join(t for t in pg0["titles"]))
    if cap:
        log(f"  {kw}: 验证码/弹框({cap})")
        if cap == "perm":
            from input import type_keys
            type_keys("{ESC}")
            time.sleep(1.5)
            png = screenshot(w, f"scan-{q}-r")
            pg0 = parse_page(png)
        elif cap == "slide":
            import temu_captcha_slide
            temu_captcha_slide.main()
            time.sleep(2.5)
            png = screenshot(w, f"scan-{q}-r")
            pg0 = parse_page(png)
        else:
            results.append({"keyword": kw, "dim": dim, "error": "hard_captcha"})
            save(results)
            return
    # 滚一屏取第二屏样本
    scroll_down()
    png2 = screenshot(w, f"scan-{q}-s2")
    pg1 = parse_page(png2)
    m = merge_pages([pg0, pg1])
    m.update(keyword=kw, dim=dim, shots=[os.path.basename(png), os.path.basename(png2)])
    results.append(m)
    save(results)
    pr = m["prices"]
    med = pr[len(pr) // 2] if pr else None
    log(f"  {kw}: 价{len(pr)}个 中位≈{med} 售出TOP5={m['solds'][:5]} "
        f"定制标={m['customizable']} Choice={m['choice']} 餐巾行={m['napkin_lines']}/{m['total_lines']}")


def main():
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    results = load_results()
    done_kw = {r["keyword"] for r in results if "error" not in r}
    w = winutil.chrome_window()
    if not w:
        log("✗ 无 Chrome 窗口，请先开 Chrome")
        return 1
    w.set_focus()
    time.sleep(0.5)
    log(f"=== 续跑 from {KEYWORDS[start][0]}（已完成 {len(done_kw)} 词）===")
    for kw, dim in KEYWORDS[start:]:
        if kw in done_kw:
            continue
        try:
            scan_keyword(w, kw, dim, results)
        except Exception as e:
            log(f"  {kw}: ✗ {type(e).__name__}: {e}")
            results.append({"keyword": kw, "dim": dim, "error": str(e)[:200]})
            save(results)
        time.sleep(2)
    log("=== 全部完成 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
