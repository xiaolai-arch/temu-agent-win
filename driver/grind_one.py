"""单 SKC 调价全流程（自包含）：python grind_one.py <SKC> <关键词>
流程：清消息（一键已读）→ 上新生命周期 → 查询 SKC → 滚动收集 发起调价 →
逐个开弹窗核对标题关键词 → 匹配的弹窗逐行填建议价（作废行/达标行取消勾选）
→ 确认调价（弹窗关闭=成功）。
只读除提交调价外的一切操作。结果写入 stdout。
"""
import math
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import winutil
import uia_shell
from input import human_click, human_drag, type_keys
from shot import screenshot, ocr
from switch_store import _clear_input
from export_goods import blue_button

COST = {"派对餐巾": 0.16, "餐巾": 0.16, "餐巾纸": 0.16, "身份腕带": 0.33}


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def ocr_lines(w, tag):
    for _ in range(3):
        try:
            return ocr(screenshot(w, tag))["lines"]
        except Exception:
            time.sleep(1)
    return []


def cancel_modal(w):
    """关掉打开发起调价弹窗：优先点取消，OCR 不到就 ESC。"""
    for _ in range(2):
        lines = ocr_lines(w, "cancel")
        cx = next(((l["x"]+l["w"]//2, l["y"]+l["h"]//2) for l in lines
                   if l["text"].replace(" ", "") == "取消"), None)
        if cx:
            click(w, cx, 1.5)
        else:
            type_keys("{ESC}")
            time.sleep(1.2)


def click(w, pos, wait=1.0):
    r = w.rectangle()
    human_click(r.left + pos[0], r.top + pos[1], activate_window=w)
    time.sleep(wait)


def sug(cat, q):
    return math.ceil((COST.get(cat, 0.16) * q + 9) / 0.5 * 2) / 2


def main():
    skc = sys.argv[1]
    cat = sys.argv[2] if len(sys.argv) > 2 else "派对餐巾"
    kw = sys.argv[3] if len(sys.argv) > 3 else None
    w = winutil.default_window()
    if not w:
        print("✗ 无窗口")
        return 1
    w.set_focus()
    time.sleep(0.5)
    r = w.rectangle()

    uia_shell.navigate(w, "https://agentseller.temu.com/newon/product-select")
    time.sleep(10)

    # 0) 一键已读所有消息（防消息面板反复弹出）+ 关面板
    for rnd in range(2):
        lines = ocr_lines(w, f"m{rnd}")
        yidu = next(((l["x"]+l["w"]//2, l["y"]+l["h"]//2) for l in lines
                     if "一键已读所有消息" in l["text"].replace(" ", "")), None)
        if yidu:
            log("→ 一键已读所有消息")
            click(w, yidu, 2)
            break
        xx = next(((l["x"]+l["w"]//2, l["y"]+l["h"]//2) for l in lines
                   if l["text"].replace(" ", "") == "×"), None)
        if xx:
            click(w, xx, 1.5)
            break

    # 0.5) 活动邀请弹窗（黑五等）拦截：点「暂不调整」关闭，绝不点确认
    for _ in range(2):
        lines = ocr_lines(w, "promo")
        zbtz = next(((l["x"]+l["w"]//2, l["y"]+l["h"]//2) for l in lines
                     if "暂不调整" in l["text"].replace(" ", "")), None)
        if not zbtz:
            break
        click(w, zbtz, 1.5)
        log("→ 关闭活动邀请弹窗（暂不调整）")

    # 1) 查询 SKC（label 锚点 + 固定坐标兜底；轮询等页面渲染）
    inp = q = None
    for i in range(8):
        lines = ocr_lines(w, f"q{i}")
        lbl = next(((l["x"], l["y"], l["h"]) for l in lines
                    if l["text"].replace(" ", "") == "商品ID查询" and l["x"] > 350), None)
        inp = next(((l["x"]+60, l["y"]+l["h"]//2) for l in lines
                    if "多个查询" in l["text"].replace(" ", "")
                    or "依次输入" in l["text"].replace(" ", "")), None)
        q = next(((l["x"]+l["w"]//2, l["y"]+l["h"]//2) for l in lines
                  if l["text"].replace(" ", "") == "查询"), None)
        if lbl and not inp:
            inp = (lbl[0] + 330, lbl[1] + lbl[2]//2)
        if q and (inp or i >= 4):
            break
        time.sleep(2.5)
    inp = inp or (1850, 752)
    q = q or (1559, 962)
    click(w, inp, 0.5)
    _clear_input(w)
    type_keys(skc, pause=0.03)
    time.sleep(0.6)
    click(w, q, 1)
    time.sleep(8)

    # 1.5) 待办任务弹窗拦截处理（X = 标题行左上 +924,-43）
    lines = ocr_lines(w, "modal")
    if any("待办任务需要尽快处理" in l["text"].replace(" ", "") for l in lines):
        ttl = next((l for l in lines if "待办任务需要尽快处理" in l["text"].replace(" ", "")), None)
        click(w, (ttl["x"] + 924, ttl["y"] - 43), 1.5)
        log("→ 关闭待办任务弹窗")

    # 2) 收集 发起调价 链接（滚动多轮）
    tjs = []
    tried = set()
    # 结果区在筛选区下方：先点结果统计区拿焦点，再 PGDN 逐步向下收集
    lines = ocr_lines(w, "t00")
    stat = next(((l["x"]+60, l["y"]+l["h"]//2) for l in lines
                 if l["text"].replace(" ", "").startswith("全部") and l["y"] > 1100), None)
    if stat:
        click(w, stat, 0.5)
    for sr in range(8):
        lines = ocr_lines(w, f"t{sr}")
        cur = sorted((l["y"], l["x"]+l["w"]//2) for l in lines
                     if l["text"].replace(" ", "") == "发起调价")
        fresh = [(y, x) for y, x in cur if (y//60, x//60) not in tried]
        tjs.extend(fresh)
        tried.update((y//60, x//60) for y, x in cur)
        if fresh and len(tjs) >= 6:
            break
        type_keys("{PGDN}")
        time.sleep(2)
        lines = ocr_lines(w, f"t{sr}b")
        cur = sorted((l["y"], l["x"]+l["w"]//2) for l in lines
                     if l["text"].replace(" ", "") == "发起调价")
        fresh = [(y, x) for y, x in cur if (y//60, x//60) not in tried]
        tjs.extend(fresh)
        tried.update((y//60, x//60) for y, x in cur)
    # 去重相邻
    dedup = []
    for y, x in tjs:
        if not dedup or abs(y - dedup[-1][0]) > 30 or abs(x - dedup[-1][1]) > 30:
            dedup.append((y, x))
    tjs = dedup
    log(f"收集到 {len(tjs)} 个发起调价链接")
    if not tjs:
        return 2

    # 3) 逐个核对。弹窗可能未渲染（OCR 穿透看到底层列表页，其上也有 SKC 文本，
    #    文本判据必误匹配）——先等「确认调价」蓝块出现确认弹窗真打开了，再做文本匹配
    matched = False
    from PIL import Image
    for ly, lx in tjs:
        click(w, (lx, ly), 4)
        rendered = False
        for _ in range(4):
            if blue_button(w, 700, 1100, 1420, 1540):
                rendered = True
                break
            time.sleep(2)
        if not rendered:
            log("  弹窗未渲染（穿透底层页），取消")
            type_keys("{ESC}")
            time.sleep(1.5)
            continue
        # 弹窗内「我知道了」提示浮层：点掉再匹配
        for _ in range(2):
            flines = ocr_lines(w, "iknow")
            ik = next(((l["x"]+l["w"]//2, l["y"]+l["h"]//2) for l in flines
                       if l["text"].replace(" ", "") in ("我知道了", "知道了")), None)
            if not ik:
                break
            click(w, ik, 1.5)
            log("→ 关闭「我知道了」浮层")
        p = screenshot(w, "hdr")
        img = Image.open(p)
        crop = img.crop((780, 240, 2400, 480))
        crop = crop.resize((int(crop.width*1.5), int(crop.height*1.5)), Image.LANCZOS)
        zp = p.replace(".png", "-h.png")
        crop.save(zp)
        title = "".join(l["text"].replace(" ", "") for l in ocr(zp)["lines"])
        # 主判据：弹窗内任意位置的「SKC…ID数字」（长标题会把 SKC ID 行挤出
        # 固定裁剪区，整窗 OCR 才稳）；标题关键词兜底
        whole = "".join(l["text"].replace(" ", "") for l in ocr_lines(w, "whole"))
        if re.search(r"SKC.{0,4}" + skc, whole) or (kw and kw in title):
            matched = True
            log(f"✓ 匹配目标：{title[:36]}")
            break
        log(f"  非目标：{title[:36]}，取消")
        lines = ocr_lines(w, "cx")
        cx = next(((l["x"]+l["w"]//2, l["y"]+l["h"]//2) for l in lines
                   if l["text"].replace(" ", "") == "取消"), None)
        if cx:
            click(w, cx, 1.5)
        else:
            type_keys("{ESC}")
            time.sleep(1.5)
    if not matched:
        log(f"✗ 未找到目标（{kw}）")
        return 2

    # 4) 填行。弹窗表格行高随填写动态变化（空行带红色提示，填完提示消失该行变矮，
    #    下方行整体上移），缓存坐标必然失效——因此：
    #    ① 先扫描全表（自下而上当场取消勾选，勾选框点击容差大），待填行只登记
    #    ② 再自下而上逐行填写：每行填前重新 OCR 定位（锚定「请输入」占位符），
    #       填完立即 OCR 验证值真的在输入框里，没落上就重试
    def parse_price(l):
        t = l["text"].replace(" ", "").replace("．", ".").replace("℃", ".")
        # OCR 会丢小数点（¥256.38→¥25638）：≥4 位整数按两位小数还原
        m = re.match(r"^¥(\d+)(?:\.(\d{1,2}))?$", t)
        if not m:
            return None
        if m.group(2) is not None:
            return float(m.group(1) + "." + m.group(2))
        if len(m.group(1)) >= 4:
            return int(m.group(1)) / 100.0
        return float(m.group(1))

    def value_visible(lines, py, v):
        """行已填判据（相对价格行 y）：输入框出现目标值，或该行出现绿色「降价」标签
        （OCR 对 2 位短数字经常整段漏识别，标签二字识别稳定且只在有效填入后出现）"""
        for l in lines:
            if abs(l["y"] - py) > 45:
                continue
            t = l["text"].replace(" ", "").replace("．", ".")
            if 1600 < l["x"] < 2260:
                m = re.match(r"^(?:¥)?(\d+)(?:\.(\d{1,2}))?", t)
                if m:
                    try:
                        got = float(m.group(1) + "." + (m.group(2) or "0"))
                    except ValueError:
                        m = None
                    if m and abs(got - float(v)) < 0.005:
                        return True
            if t == "降价" and l["x"] >= 1900:
                return True
        return False

    def row_qty(lines, py):
        # 勾选框会被 OCR 误读成单字符"0"抢在数量行前——单字符行不参与
        zone = [l2 for l2 in lines
                if abs(l2["y"] - (py - 15)) <= 45 and l2["x"] < 1300
                and len(l2["text"].replace(" ", "")) > 1]
        for l2 in zone:
            m2 = re.search(r"(\d+)\s*(?:pcs|件|张|片)", l2["text"])
            if m2 and int(m2.group(1)) <= 999:
                return int(m2.group(1))
        for l2 in zone:
            # 兜底拒绝 "11.5cm…" 截成 11：数字后紧跟小数点/数字的一律不要
            m2 = re.match(r"(\d+)(?![.\d])", l2["text"])
            if m2 and int(m2.group(1)) <= 999:
                return int(m2.group(1))
        return None

    def sane_qty(qty):
        # 本店餐巾/腕带最小规格 20 件——识别出 <10 的数量必是 OCR 垃圾
        # （曾把 50件 认成 1件，按 sug(1) 填 18.5 低于保本价）
        return qty is not None and qty >= 10

    def scan_collect():
        """滚动扫描全表，自下而上当场取消勾选（作废/≈建议价）；返回待填 [(y,qty,val)]"""
        from PIL import Image
        fills = []
        scroll_px = 0
        idle = 0
        handled = set()
        for rnd in range(12):
            lines = ocr_lines(w, f"f{rnd}")
            rows = {}
            for l in lines:
                if 1350 < l["x"] < 1650:
                    val = parse_price(l)
                    if val is not None:
                        rows[round(l["y"])] = val
            acted = 0
            for y, val in sorted(rows.items(), reverse=True):
                qty = row_qty(lines, y)
                if not sane_qty(qty):
                    continue
                voided = any("已作废" in l2["text"].replace(" ", "")
                             and abs(l2["y"] - y) <= 60 for l2 in lines)
                # 行签名带 y 桶：同价同行数的两行是两个待办，不能按 (qty,val) 去重
                sig = (qty, val, round(y / 40))
                if sig in handled:
                    continue
                if voided or val <= sug(cat, qty) * 1.05:
                    p = screenshot(w, "cb")
                    b = Image.open(p).convert("RGB").load()[713, y]
                    if b[2] > 150 and b[2] - b[0] > 40:
                        click(w, (713, y), 0.4)
                        log(f"  {qty}件 ¥{val} {'已作废' if voided else '≈建议价'} → 取消勾选")
                    else:
                        log(f"  {qty}件 ¥{val} 勾选框未判蓝（可能已取消）")
                    handled.add(sig)
                    acted += 1
                    continue
                fills.append((y, qty, val))
                handled.add(sig)
                acted += 1
            if acted == 0:
                idle += 1
                if idle >= 2:
                    break
                scroll_px += 150
                human_drag(r.left + 2521, r.top + 820,
                           r.left + 2521, r.top + 820 + scroll_px, activate_window=w)
                time.sleep(1.5)
            else:
                idle = 0
        return sorted(fills, reverse=True)

    def fill_one(val, y_reg, seq):
        """重新 OCR 定位行（取离登记 y 最近者，同价多行时才不串行）→ 填建议价 → 立即验证"""
        for attempt in range(2):
            lines = ocr_lines(w, f"fr{seq}-{attempt}")
            cands = [l for l in lines
                     if 1350 < l["x"] < 1650
                     and (p := parse_price(l)) is not None
                     and abs(p - val) < 0.005]
            if not cands:
                time.sleep(1.5)
                continue
            py = min(cands, key=lambda l: abs(l["y"] - y_reg))["y"]
            qty = row_qty(lines, py)
            # 数量交叉验证：二次 OCR 再读一次，取位数多者（OCR 常丢行首数字，
            # 曾把 152pcs 认成 52件 → sug 差一倍）
            if sane_qty(qty):
                time.sleep(0.8)
                qty2 = row_qty(ocr_lines(w, f"fq{seq}-{attempt}"), py)
                if sane_qty(qty2) and len(str(qty2)) > len(str(qty)):
                    qty = qty2
            if not sane_qty(qty):
                time.sleep(1.5)
                continue
            target = sug(cat, qty)
            # 空行下方的红色提示把行撑高——锚定行内「请输入」占位符（其 y+h/2 ≈ 输入框中心）
            ph = next((l for l in lines
                       if "输入" in l["text"].replace(" ", "")
                       and 1600 < l["x"] < 2250
                       and abs(l["y"] - (py - 15)) <= 55), None)
            iy = (ph["y"] + ph["h"] // 2) if ph else (py - 15)
            click(w, (1750, iy), 0.4)
            _clear_input(w)
            v = int(target) if target == int(target) else target
            type_keys(str(v), pause=0.03)
            time.sleep(0.3)
            # 点申报价格类型列（惰性区域）让输入框失焦
            click(w, (1000, py - 15), 0.3)
            if value_visible(ocr_lines(w, f"fv{seq}-{attempt}"), py, v):
                log(f"  {qty}件 ¥{val} → 填 {v} ✓")
                return True
            log(f"  ⚠ {qty}件 ¥{val} 填 {v} 未落上，重试")
        return False

    todo = scan_collect()
    log(f"待填 {len(todo)} 行")
    filled_total = 0
    for seq, (y, qty, val) in enumerate(todo):
        if fill_one(val, y, seq):
            filled_total += 1
        else:
            log(f"✗ {qty}件 ¥{val} 两轮都没填上，取消提交")
            cancel_modal(w)
            return 1
    log(f"共填 {filled_total} 行")

    # 5) 提交（重试到弹窗关闭）；每次失败后自救：把「红字提示的空勾选行」强制取消勾选。
    #    纯像素操作：竖扫勾选框列找蓝块（价格 OCR 可能烂成 ¥2t23 不可依赖），
    #    蓝块行若下方有红提示条带且无绿色「降价」标签 → 空勾选行，点掉
    def rescue_empty_checked():
        from PIL import Image
        p = screenshot(w, "rescue")
        px = Image.open(p).convert("RGB").load()
        blue_ys = [yy for yy in range(740, 1420)
                   if px[713, yy][2] > 150 and px[713, yy][2] - px[713, yy][0] > 40]
        centers = []
        for yy in blue_ys:
            if centers and yy - centers[-1][-1] <= 3:
                centers[-1].append(yy)
            else:
                centers.append([yy])
        n = 0
        for grp in centers:
            cy = grp[len(grp) // 2]
            red = sum(1 for yy in range(cy + 20, cy + 54, 4)
                      for xx in range(1560, 2110, 40)
                      if px[xx, yy][0] > 170 and px[xx, yy][1] < 120 and px[xx, yy][2] < 120)
            green = any(px[xx, yy][1] > 130 and px[xx, yy][0] < 130
                        for yy in range(cy - 12, cy + 22, 4)
                        for xx in range(2050, 2170, 20))
            if red >= 3 and not green:
                click(w, (713, cy), 0.4)
                log(f"  自救：取消空勾选行（勾选框 y={cy}）")
                n += 1
        return n

    if filled_total == 0:
        log("⚠ 0 行可调，取消")
        cancel_modal(w)
        return 3
    pos = None
    for _ in range(3):
        pos = blue_button(w, 700, 1100, 1420, 1540)
        if pos:
            break
        time.sleep(1.5)
    if not pos:
        log("✗ 确认调价按钮未找到")
        cancel_modal(w)
        return 1
    for attempt in range(4):
        click(w, pos, 3)
        lines = ocr_lines(w, f"sub{attempt}")
        if not any("原申报价格" in l["text"].replace(" ", "") for l in lines):
            log("✅ 弹窗关闭，调价已提交")
            return 0
        log(f"  ⚠ 第{attempt+1}次点击弹窗未关，重试")
        rescue_empty_checked()
    log("✗ 提交失败")
    cancel_modal(w)
    return 1


if __name__ == "__main__":
    sys.exit(main())
