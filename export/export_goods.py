"""商品列表导出（只读）：当前店 goods/list 页 → 记录页面统计 → 下载查询结果 → 归档。

用法：python export_goods.py <store-id>
前置：switch_store.py <store-id> 已成功（浏览器已登录目标店）。
流程：
  1. 当前标签导航 https://agentseller.temu.com/goods/list
  2. 处理可能自动弹出的「待办任务」弹窗（点 X，只关不改任何待办）
  3. 确认右上角范围 = 全球（不是则点「全球」chip——纯视图筛选）
  4. OCR 记录 tab 计数（全部/在售中/未发布/已下架/草稿箱）与待办任务条
  5. 点「下载查询结果 N」→ 弹窗内蓝色「导出」按钮（像素级蓝块定位）
  6. 轮询 D:\Download 新增 商品基础信息*.xlsx（大小稳定）→ 拷贝
     export/data/<store-id>-goods-<date>.xlsx

只读声明：全程只 导航/关闭弹窗/切换视图范围/导出查询结果，绝不点
同步、上新、改价、批量删除等改数据按钮。导出 = 后台生成查询结果文件。
"""
import os
import re
import shutil
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, ".."))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.abspath(os.path.join(BASE, "..", "core")))

import winutil
import uia_shell
from input import human_click, type_keys
from shot import screenshot, ocr

GOODS_URL = "https://agentseller.temu.com/goods/list"
DL_DIR = r"D:\Download"
OUT_DIR = os.path.join(BASE, "data")


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def shot(w, tag):
    return screenshot(w, f"eg-{tag}")


def ocr_lines(w, tag):
    for _ in range(3):
        try:
            return ocr(shot(w, tag))["lines"]
        except Exception:
            time.sleep(1.5)
    return []


def click(w, pos):
    r = w.rectangle()
    human_click(r.left + pos[0], r.top + pos[1], activate_window=w)


def find_line(lines, kws, xmin=0, xmax=99999, ymin=0, ymax=99999):
    for l in lines:
        t = l["text"].replace(" ", "")
        if not (xmin <= l["x"] <= xmax and ymin <= l["y"] <= ymax):
            continue
        for k in kws:
            if k in t:
                return l
    return None


def blue_button(w, x0, x1, y0, y1, min_w=50):
    """区域内的蓝色实心块（白字蓝底按钮 OCR 读不出 → 像素定位）。"""
    import cv2
    p = shot(w, "blue")
    img = cv2.imread(p)
    if img is None:
        return None
    region = img[y0:y1, x0:x1]
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    mask = ((h > 100) & (h < 130) & (s > 80) & (v > 120)) | \
           ((h > 210) & (h < 250) & (s > 80) & (v > 120))
    col = mask.sum(axis=0)
    runs = []
    x = 0
    while x < len(col):
        if col[x] > 15:
            s0 = x
            while x < len(col) and col[x] > 15:
                x += 1
            runs.append((s0, x))
        else:
            x += 1
    if not runs:
        return None
    best = max(runs, key=lambda t: t[1] - t[0])
    if best[1] - best[0] < min_w:
        return None
    import numpy as np
    rows = np.where(mask[:, best[0]:best[1]].sum(axis=1) > 0)[0]
    if len(rows) == 0:
        return None
    return (x0 + (best[0] + best[1]) // 2, y0 + int(rows.mean()))


def wait_stable_file(dirl, t0, timeout=420):
    """等 DL_DIR 出现 t0 之后新建的商品基础信息*.xlsx 且大小 5s 不变。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for name in os.listdir(dirl):
            if name.startswith("商品基础信息") and name.endswith(".xlsx"):
                p = os.path.join(dirl, name)
                try:
                    mt = os.path.getmtime(p)
                except OSError:
                    continue
                if mt >= t0 - 2:
                    s1 = os.path.getsize(p)
                    time.sleep(5)
                    s2 = os.path.getsize(p)
                    if s1 == s2 and s1 > 1000:
                        return p
        time.sleep(6)
    return None


def close_todo_modal(w, lines):
    """「您有以下待办任务需要尽快处理」弹窗 → 点右上角 X（X 圆心=标题行左上 +924,-43，实测）。"""
    ttl = find_line(lines, ["待办任务需要尽快处理"])
    if ttl is None:
        return False
    pos = (ttl["x"] + 924, ttl["y"] - 43)
    log(f"→ 关闭待办任务弹窗 X {pos}")
    click(w, pos)
    time.sleep(1.5)
    return True


def ensure_global_scope(w, lines):
    """右上角范围：页面标题「商品列表·全球」即全球；否则点「全球」chip。"""
    title = find_line(lines, ["商品列表·全球", "商品列表·美区", "商品列表·欧区"], xmin=350, ymin=150, ymax=500)
    if title and "全球" in title["text"].replace(" ", ""):
        return  # 已是全球
    chip = find_line(lines, ["全球"], xmin=2150, ymin=150, ymax=450)
    if chip is None:
        log("⚠ 标题无「全球」且未找到 chip，按实测坐标点全球")
        click(w, (2300, 208))
    else:
        log(f"→ 范围非全球，点「全球」chip ({chip['x']},{chip['y']})")
        click(w, (chip["x"] + 30, chip["y"] + chip["h"] // 2))
    time.sleep(3)


def wheel(w, notches, x=1290, y=800):
    """页面滚轮（避开佳同面板按钮区，只在页面主体上滚）。"""
    try:
        w.wheel_mouse_input(x, y, -notches * 3)
    except Exception:
        import ctypes
        from input import _send_move_abs
        r = w.rectangle()
        _send_move_abs(r.left + x, r.top + y)
        time.sleep(0.3)
        for _ in range(notches):
            ctypes.windll.user32.mouse_event(0x0800, 0, 0, -120, 0)
            time.sleep(0.08)
    time.sleep(2.5)


def find_export_btn(w, tries=6):
    """滚动直到「下载查询结果」按钮可见（佳同面板会把它挤到折叠线下）。
    返回 (按钮坐标, 当前OCR行)。绝不点佳同面板里的按钮（含批量删除等危险项）。"""
    for i in range(tries):
        lines = ocr_lines(w, f"dl{ i}")
        for l in lines:
            t = l["text"].replace(" ", "")
            if ("下载查" in t or ("下载" in t and "结果" in t)) and l["x"] > 500 and l["y"] > 800:
                return (l["x"] + l["w"] // 2, l["y"] + l["h"] // 2), lines
        if find_line(lines, ["佳同跨境", "批量上架商品"]):
            log(f"→ 佳同面板占据视口，滚动…({i + 1})")
            wheel(w, 4)
        else:
            wheel(w, 3)
    return None, lines


def grab_stats(w, pre_lines=()):
    """OCR 商品列表页：tab 计数 + 待办 chips + 提示横幅，写 store-data/<sid>-page.md。"""
    lines = ocr_lines(w, "stats")
    keep = []
    for l in list(pre_lines) + list(lines):
        t = l["text"].replace(" ", "")
        if not t:
            continue
        if any(k in t for k in ("全部", "在售", "未发布", "已下架", "已删除", "草稿箱",
                                "待办", "商品信息", "商品属性", "SKU", "建议零售价",
                                "图片", "实拍", "额度", "流量", "申报价", "分类错误",
                                "发品", "热销", "视频")) and l["x"] > 300:
            keep.append(f"{l['x']},{l['y']}: {t}")
    stats = {"counts": {}, "todo": {}}
    text = " ".join(k.split(": ", 1)[1] for k in keep)
    for name, pat in [("全部", r"全部(\d+)"), ("在售中", r"在售中(\d+)"),
                      ("未发布到站点", r"未发布到站点(\d+)"),
                      ("已下架/已终止", r"已下架.?已终止(\d+)"),
                      ("已删除", r"已删除(\d+)"), ("草稿箱", r"草稿箱.(\d+)")]:
        m = re.search(pat, text)
        if m:
            stats["counts"][name] = int(m.group(1))
    for name, pat in [("商品信息", r"商品信息(\d+)"), ("商品属性", r"商品属性(\d+)"),
                      ("商品SKU", r"商品SKU(\d+)"), ("建议零售价", r"建议零售价(\d+)"),
                      ("图片/视频", r"图片.?视频(\d+)")]:
        m = re.search(pat, text)
        if m:
            stats["todo"][name] = m.group(1)
    md = os.path.join(OUT_DIR, f"{SID}-page-ocr.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write(f"# {SID} 商品列表页 OCR 快照 {time.strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write("```\n" + "\n".join(keep) + "\n```\n")
    log(f"→ 页面统计: {stats['counts']} 待办:{stats['todo']}")
    return stats


def main():
    global SID
    SID = sys.argv[1] if len(sys.argv) > 1 else "main"
    os.makedirs(OUT_DIR, exist_ok=True)
    w = winutil.default_window()
    if not w:
        log("✗ 无 Edge 窗口")
        return 1
    w.set_focus()
    time.sleep(0.5)

    # 1) 导航商品列表
    uia_shell.navigate(w, GOODS_URL)
    time.sleep(8)

    # 2) 可能的待办弹窗
    lines = ocr_lines(w, "load")
    if close_todo_modal(w, lines):
        time.sleep(2)
        lines = ocr_lines(w, "load2")
    pre_lines = lines

    # 3) 范围=全球（幂等点击）
    ensure_global_scope(w, lines)
    time.sleep(2)

    # 4) 页面统计（滚动到 tab 行后抓，弹窗信息合并）
    btn, lines = find_export_btn(w)
    if not btn:
        log("✗ 未找到「下载查询结果」按钮")
        return 1
    stats = grab_stats(w, pre_lines)
    log(f"→ 点下载查询结果 {btn}")
    before = {n for n in os.listdir(DL_DIR) if n.startswith("商品基础信息")}
    t0 = time.time()
    click(w, btn)
    time.sleep(3)

    # 弹窗确认 + 蓝色「导出」（点击后验证弹窗关闭，最多重试 2 次）
    ok_export = False
    for att in range(3):
        lines = ocr_lines(w, f"dlg{att}")
        dlg = find_line(lines, ["共查询到", "全部商品信息"], ymin=400, ymax=1100)
        if not dlg:
            ok_export = True
            break
        pos = None
        for _ in range(3):
            pos = blue_button(w, 1000, 1780, 1000, 1230)
            if pos:
                break
            time.sleep(2)
        if not pos:
            log("✗ 未定位到导出按钮")
            return 1
        log(f"→ 点导出 {pos}")
        click(w, pos)
        time.sleep(4)
    if not ok_export:
        log("✗ 导出点击后弹窗仍未关闭")
        return 1

    # 「导出成功」toast 确认（可选）
    lines = ocr_lines(w, "toast")
    if find_line(lines, ["导出成功"], ymin=150, ymax=500):
        log("→ 导出成功 toast ✅")

    # 6) 等文件落地
    log("→ 等待导出文件生成…")
    p = wait_stable_file(DL_DIR, t0)
    if not p:
        log("✗ 超时未等到导出文件")
        return 1
    name = os.path.basename(p)
    if name in before:
        # 同名旧文件还在 → 找最新 mtime 的新文件（Edge 会自动加 (1) 后缀）
        cands = [n for n in os.listdir(DL_DIR)
                 if n.startswith("商品基础信息") and n.endswith(".xlsx")
                 and n not in before]
        if cands:
            p = os.path.join(DL_DIR, max(cands, key=lambda n: os.path.getmtime(os.path.join(DL_DIR, n))))
        else:
            p = os.path.join(DL_DIR, name)
    dest = os.path.join(OUT_DIR, f"{SID}-goods-{time.strftime('%Y-%m-%d')}.xlsx")
    shutil.copy2(p, dest)
    log(f"✓ 已归档 {dest}（{os.path.getsize(dest)} bytes）")
    with open(os.path.join(OUT_DIR, f"{SID}-stats.txt"), "w", encoding="utf-8") as f:
        f.write(repr(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
