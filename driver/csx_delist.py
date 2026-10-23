"""客服自助工具批量下架：python csx_delist.py <type:SKU|SKC> <id> [<id> ...]

复用 2026-10-22/23 验证过的流程：
  客服图标 → 联系官方客服 → 自助工具 → 商品下架 → 发商品 →
  表单(类型/ID/亏损下架) → 申请下架 → 确认 → 等机器人回复
每个 ID 间隔 SPACING 秒（限流），「操作失败」自动重试最多 2 次。
结果追加写入 research/store-data/delist-log.txt。
前提：浏览器已登录目标店铺。只读其余页面内容，仅提交下架申请。
"""
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, ".."))
sys.path.insert(0, BASE)

import winutil
import uia_shell
from input import human_click, type_keys
from shot import screenshot, ocr

SPACING = 50
LOG = os.path.join(ROOT, "research", "store-data", "delist-log.txt")

# 稳定坐标（2582x1550 实测多轮验证）
POS = {
    "kf_icon": (2077, 185),
    "lianxi": None,          # OCR 定位 联系官方客服
    "tools": (1546, 983),    # 自助工具
    "menu_item": (1553, 552),  # 商品下架
    "fg_link": None,         # OCR 定位 发商品
    "type_dd": (1841, 671),
    "type_sku": (1820, 763),
    "type_skc": (1820, 720),
    "input": (2047, 671),
    "reason_dd": (1993, 737),
    "reason_opt": (1831, 787),
    "submit": (2030, 804),
    "confirm": (1544, 958),
    "cancel": (2161, 805),
    "panel_x": (2370, 262),
}


def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def shot_lines(w, tag):
    for _ in range(3):
        try:
            return ocr(screenshot(w, tag))["lines"]
        except Exception:
            time.sleep(1)
    return []


def click(w, pos, wait=1.0):
    r = w.rectangle()
    human_click(r.left + pos[0], r.top + pos[1], activate_window=w)
    time.sleep(wait)


def open_dialog(w):
    """打开 发送下架商品信息 表单。返回 True/False。"""
    for attempt in range(2):
        # 佳同推广浮层可能挡住客服图标 → 先关
        lines = shot_lines(w, "popup")
        for kw in ("今日不再提示", "10分钟后再提醒"):
            hit = next(((l["x"]+l["w"]//2, l["y"]+l["h"]//2) for l in lines
                        if kw in l["text"].replace(" ", "")), None)
            if hit:
                log("  → 关佳同浮层")
                click(w, hit, 1.5)
                break
        click(w, POS["kf_icon"], 3.5)                    # 客服图标
        lines = shot_lines(w, "kf")
        btn = next(((l["x"]+l["w"]//2, l["y"]+l["h"]//2) for l in lines
                    if "联系官方客服" in l["text"].replace(" ", "")), None)
        if btn:
            click(w, btn, 3.5)                           # 联系官方客服
        else:
            log("  ⚠ 未见联系官方客服（可能已在聊天）")
        lines = shot_lines(w, "chat")
        tool = next(((l["x"]+l["w"]//2, l["y"]+l["h"]//2) for l in lines
                     if l["text"].replace(" ", "") == "自助工具"), None)
        if not tool:
            log("  ⚠ 未见自助工具，重开面板")
            click(w, POS["kf_icon"], 2)
            continue
        click(w, tool, 1.5)                              # 自助工具
        click(w, POS["menu_item"], 3)                    # 商品下架（发聊天）
        lines = shot_lines(w, "fg")
        fg = next(((l["x"]+l["w"]//2, l["y"]+l["h"]//2) for l in lines
                   if l["text"].replace(" ", "").startswith("发商品")), None)
        if not fg:
            log("  ⚠ 未见发商品链接")
            continue
        click(w, fg, 3)                                  # 发商品 → 表单
        lines = shot_lines(w, "dlg")
        if any("发送下架商品信息" in l["text"].replace(" ", "") for l in lines):
            return True
    return False


def submit_one(w, id_type, pid):
    """提交单个下架。返回 'ok' / 'fail' / 'already' / 'disabled'。"""
    # 表单必为全新打开状态
    if id_type == "SKU":
        click(w, POS["type_dd"], 1.2)
        click(w, POS["type_sku"], 0.8)
    human_click(*_abs(w, POS["input"]), activate_window=w)
    time.sleep(0.4)
    from switch_store import _clear_input
    _clear_input(w)
    type_keys(str(pid), pause=0.03)
    time.sleep(0.4)
    click(w, POS["reason_dd"], 1.2)
    lines = shot_lines(w, "rs")
    hit = next(((l["x"]+l["w"]//2, l["y"]+l["h"]//2) for l in lines
                if l["text"].replace(" ", "") == "亏损下架"), None)
    from input import human_click
    r = w.rectangle()
    pos = hit or POS["reason_opt"]
    human_click(r.left + pos[0], r.top + pos[1], activate_window=w)
    time.sleep(1.0)
    human_click(r.left + POS["submit"][0], r.top + POS["submit"][1], activate_window=w)
    time.sleep(3.5)
    lines = shot_lines(w, "cf")
    if not any("确认下架" in l["text"].replace(" ", "") for l in lines):
        return "disabled"
    time.sleep(2)
    human_click(r.left + POS["confirm"][0], r.top + POS["confirm"][1], activate_window=w)
    # 等机器人回复（已下架 / 操作失败）
    for _ in range(10):
        time.sleep(6)
        lines = shot_lines(w, "rp")
        text = "".join(l["text"].replace(" ", "") for l in lines)
        if "该商品已下架" in text:
            return "ok"
        if "操作失败" in text or "系统繁忙" in text:
            return "fail"
    return "unknown"


def _abs(w, pos):
    r = w.rectangle()
    return (r.left + pos[0], r.top + pos[1])


def main():
    id_type = sys.argv[1].upper()
    ids = [int(x) for x in sys.argv[2:]]
    w = winutil.default_window()
    if not w:
        print("✗ 无窗口")
        return 1
    w.set_focus()
    for i, pid in enumerate(ids):
        log(f"== [{i+1}/{len(ids)}] {id_type} {pid}")
        ok = False
        for att in range(3):
            if not open_dialog(w):
                log("  ✗ 表单打不开，60s 后重试")
                time.sleep(60)
                continue
            res = submit_one(w, id_type, pid)
            log(f"  → {res}（第{att+1}次）")
            if res == "ok":
                ok = True
                break
            if res == "disabled":
                # 表单卡死 → 取消重开
                click(w, POS["cancel"], 1.5)
                time.sleep(30)
                continue
            if res == "fail":
                time.sleep(150)   # 系统繁忙 → 长歇
                continue
            time.sleep(20)
        log(f"== {pid}: {'✅' if ok else '❌'}")
        if i < len(ids) - 1:
            time.sleep(SPACING)
    return 0


if __name__ == "__main__":
    sys.exit(main())
