"""单 SKC 调价：python price_one.py <SKC-ID>
流程：上新生命周期 → 商品ID查询 → 发起调价 → 弹窗内逐行
（数量→建议价映射，>5% 才填，餐巾 0.16/件、腕带 0.33/件，30% 净利率）
→ 内部滚动条翻页 → 确认调价（蓝块定位）→ 验证提示。
"""
import math
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import winutil
import uia_shell
from input import human_click, human_drag, type_keys
from shot import screenshot, ocr
from switch_store import _clear_input

COST = {"派对餐巾": 0.16, "餐巾": 0.16, "餐巾纸": 0.16, "身份腕带": 0.33}


def sug(cat, q):
    c = COST.get(cat, 0.16)
    return math.ceil((c * q + 9) / 0.5 * 2) / 2


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def ocr_lines(w, tag):
    for _ in range(3):
        try:
            return ocr(screenshot(w, tag))["lines"]
        except Exception:
            time.sleep(1)
    return []


def main():
    skc = sys.argv[1]
    cat = sys.argv[2] if len(sys.argv) > 2 else "派对餐巾"
    w = winutil.default_window()
    if not w:
        print("✗ 无窗口")
        return 1
    w.set_focus()
    time.sleep(0.5)
    r = w.rectangle()

    uia_shell.navigate(w, "https://agentseller.temu.com/newon/product-select")
    time.sleep(10)
    inp = q = None
    for i in range(3):
        lines = ocr_lines(w, f"q{i}")
        inp = next(((l["x"]+60, l["y"]+l["h"]//2) for l in lines
                    if "多个查询" in l["text"].replace(" ", "")
                    or "依次输入" in l["text"].replace(" ", "")), None)
        q = next(((l["x"]+l["w"]//2, l["y"]+l["h"]//2) for l in lines
                  if l["text"].replace(" ", "") == "查询"), None)
        if inp and q:
            break
        time.sleep(3)
    if not (inp and q):
        log("⚠ OCR 定位失败，用固定坐标（input 1850,752 / 查询 1559,962）")
        inp, q = (1850, 752), (1559, 962)
    human_click(r.left + inp[0], r.top + inp[1], activate_window=w)
    time.sleep(0.5)
    _clear_input(w)
    type_keys(skc, pause=0.03)
    time.sleep(0.6)
    human_click(r.left + q[0], r.top + q[1], activate_window=w)
    time.sleep(8)
    # 关可能出现的待办/满意度浮窗
    lines = ocr_lines(w, "pop")
    x = next(((l["x"]+l["w"]//2, l["y"]+l["h"]//2) for l in lines
              if l["text"].replace(" ", "") == "×"), None)
    if x:
        human_click(r.left + x[0], r.top + x[1], activate_window=w)
        time.sleep(1.5)
    # 遍历结果里每个 发起调价：打开弹窗 → 核对 SKC ID → 匹配才填，不匹配取消换下一个

    def read_dialog_title():
        """裁剪弹窗标题区放大 OCR。"""
        from PIL import Image
        p = screenshot(w, "hdr")
        img = Image.open(p)
        crop = img.crop((900, 240, 2400, 480))
        crop = crop.resize((int(crop.width * 1.5), int(crop.height * 1.5)), Image.LANCZOS)
        zp = p.replace(".png", "-hdr.png")
        crop.save(zp)
        text = "".join(l["text"].replace(" ", "") for l in ocr(zp)["lines"])
        return text

    matched = False
    kw = sys.argv[3] if len(sys.argv) > 3 else None
    tried = set()
    for scroll_round in range(5):
        lines = ocr_lines(w, f"t{scroll_round}")
        tjs = sorted((l["y"], l["x"]+l["w"]//2) for l in lines
                     if l["text"].replace(" ", "") == "发起调价")
        fresh = [(y, x) for y, x in tjs if (y, x) not in tried]
        if not fresh:
            human_drag(r.left + 2574, r.top + 300, r.left + 2574, r.top + 800,
                       activate_window=w)
            time.sleep(2)
            continue
        for ly, lx in fresh:
            tried.add((ly, lx))
            human_click(r.left + lx, r.top + ly, activate_window=w)
            time.sleep(4)
            title = read_dialog_title()
            if kw and kw.replace(" ", "") in title.replace(" ", ""):
                matched = True
                log(f"✓ 弹窗标题含「{kw}」，开始填")
                break
            log(f"  非「{kw}」：{title[:36]}，取消")
            lines2 = ocr_lines(w, "cx")
            cx = next(((l["x"]+l["w"]//2, l["y"]+l["h"]//2) for l in lines2
                       if l["text"].replace(" ", "") == "取消"), None)
            if cx:
                human_click(r.left + cx[0], r.top + cx[1], activate_window=w)
                time.sleep(1.5)
            else:
                type_keys("{ESC}")
                time.sleep(1.5)
        if matched:
            break
    if not matched:
        log(f"✗ 结果页里没找到目标（关键词 {kw}）")
        return 2

    # 弹窗填行
    total = 0
    seen_sig = set()
    scroll_px = 0
    for rnd in range(10):
        lines = ocr_lines(w, f"d{rnd}")
        rows = {}
        for l in lines:
            t = l["text"].replace(" ", "").replace("．", ".").replace("℃", ".")
            m = re.match(r"^¥(\d+)\.(\d{1,2})$", t)
            if m and 1350 < l["x"] < 1650:
                rows[round(l["y"])] = float(m.group(1) + "." + m.group(2))
        n = 0
        for y, val in sorted(rows.items()):
            qty = None
            for l2 in lines:
                if abs(l2["y"] - (y - 15)) <= 40 and l2["x"] < 1300:
                    m2 = (re.search(r"(\d+)\s*(?:pcs|件)", l2["text"])
                       or re.match(r"(\d+)", l2["text"]))
                    if m2:
                        qty = int(m2.group(1))
                        break
            if not qty:
                continue
            # 已作废价格的行跳过（用户要求：作废的不调）
            voided = any("已作废" in l2["text"].replace(" ", "").replace("　", "")
                         and abs(l2["y"] - y) <= 60 for l2 in lines)
            if voided:
                log(f"  {qty}件 ¥{val} 已作废，跳过")
                continue
            target = sug(cat, qty)
            if val > target * 1.05:
                sig = (qty, val)
                if sig in seen_sig:
                    continue
                human_click(r.left + 1750, r.top + y - 15, activate_window=w)
                time.sleep(0.4)
                _clear_input(w)
                v = int(target) if target == int(target) else target
                type_keys(str(v), pause=0.03)
                time.sleep(0.3)
                seen_sig.add(sig)
                log(f"  {qty}件 ¥{val} → {v}")
                n += 1
                total += 1
            else:
                # 现价接近/低于建议价：平台只能降不能升 → 取消勾选该行
                from PIL import Image
                p = screenshot(w, "cb")
                b = Image.open(p).convert("RGB").load()[713, y]
                if b[2] > 150 and b[2] - b[0] > 40:
                    human_click(r.left + 713, r.top + y, activate_window=w)
                    time.sleep(0.4)
                    log(f"  {qty}件 ¥{val}≈建议价，取消勾选")
        if n == 0:
            scroll_px += 150
            human_drag(r.left + 2521, r.top + 800,
                       r.left + 2521, r.top + 800 + scroll_px, activate_window=w)
            time.sleep(1.5)
            lines = ocr_lines(w, f"d{rnd}b")
            rows = {}
            for l in lines:
                t = l["text"].replace(" ", "").replace("．", ".").replace("℃", ".")
                m = re.match(r"^¥(\d+)\.(\d{1,2})$", t)
                if m and 1350 < l["x"] < 1650:
                    rows[round(l["y"])] = float(m.group(1) + "." + m.group(2))
            n = 0
            for y, val in sorted(rows.items()):
                qty = None
                for l2 in lines:
                    if abs(l2["y"] - (y - 15)) <= 40 and l2["x"] < 1300:
                        m2 = (re.search(r"(\d+)\s*(?:pcs|件)", l2["text"])
                       or re.match(r"(\d+)", l2["text"]))
                        if m2:
                            qty = int(m2.group(1))
                            break
                if not qty:
                    continue
                target = sug(cat, qty)
                if val > target * 1.05:
                    sig = (qty, val)
                    if sig in seen_sig:
                        continue
                    human_click(r.left + 1750, r.top + y - 15, activate_window=w)
                    time.sleep(0.4)
                    _clear_input(w)
                    v = int(target) if target == int(target) else target
                    type_keys(str(v), pause=0.03)
                    time.sleep(0.3)
                    seen_sig.add(sig)
                    log(f"  {qty}件 ¥{val} → {v}")
                    n += 1
                    total += 1
            if n == 0:
                break
    log(f"共填 {total} 行")
    if total == 0:
        # 空提交会把原价格作废 —— 禁止空提交
        lines = ocr_lines(w, "cx0")
        cx = next(((l["x"]+l["w"]//2, l["y"]+l["h"]//2) for l in lines
                   if l["text"].replace(" ", "") == "取消"), None)
        if cx:
            human_click(r.left + cx[0], r.top + cx[1], activate_window=w)
            time.sleep(1.5)
        log("⚠ 0 行需要调整，已取消（避免空提交作废价格）")
        return 3
    screenshot(w, "pre-submit")
    log("提交前截图已存")
    pos = None
    from export_goods import blue_button
    for _ in range(3):
        pos = blue_button(w, 700, 1100, 1420, 1540)
        if pos:
            break
        time.sleep(1.5)
    if not pos:
        log("✗ 确认调价按钮未找到")
        return 1
    human_click(r.left + pos[0], r.top + pos[1], activate_window=w)
    ok = False
    for i in range(5):
        time.sleep(2)
        text = "".join(l["text"].replace(" ", "") for l in ocr_lines(w, f"s{i}"))
        if "调价成功" in text:
            ok = True
            break
    log(f"{'✅ 调价成功' if ok else '⚠ 未捕获成功提示（需复核）'} SKC {skc}")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
