"""Temu 滑块拼图验证码求解（纯几何，物体无关）。

几何事实（2026-10-17 实测）：
- 拼图块固定在拼图图左侧近顶处，带白色描边，约 47x50，相对拼图区 bbox 偏移 ~(11,17)
- 缺口 = 拼图区内比周围暗的块（th<62 可分离），与拼图块尺寸接近者为目标
- 滑块手柄 = 拼图区下方的橙色圆；手柄位移 ≈ 拼图块位移（1:1）
- 拖动用 SendInput 绝对移动；轨迹快→慢+过冲回拉；失败点「刷新」重试
"""
import os
import random
import sys
import time

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import winutil
from input import _send_mouse, _send_move_abs, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, human_click
from shot import screenshot, ocr, _load_last_shot

PIECE_OFF = (11, 17)
PIECE_W, PIECE_H = 47, 50
IMG_BOX = (1104, 651, 375, 188)   # 拼图区 bbox（2582x1550 窗口实测，Chrome 同布局）


def shot(w, tag):
    return screenshot(w, f"hs-{tag}")


def find_image_box(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    nw = (g < 238).astype(np.uint8)
    nw[:560, :] = 0
    nw[900:, :] = 0
    nw[:, :1020] = 0
    nw[:, 1620:] = 0
    nw = cv2.morphologyEx(nw, cv2.MORPH_CLOSE, np.ones((21, 21), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(nw)
    if n < 2:
        return None
    i = 1 + int(np.argmax(stats[1:, 4]))
    x, y, w2, h2, _ = stats[i]
    return (x, y, w2, h2)


def find_gap(img, box):
    """返回缺口中心（相对整窗坐标）；找不到返回 None。"""
    x0, y0, w, h = box
    sub = img[y0 + 6:y0 + h - 6, x0 + 6:x0 + w - 6]
    g = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
    best = None
    for th in (55, 65, 75):
        dark = (g < th).astype(np.uint8)
        dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
        n, lab, stats, _ = cv2.connectedComponentsWithStats(dark)
        for i in range(1, n):
            x, y, ww, hh, a = stats[i]
            if 34 <= ww <= 120 and 36 <= hh <= 120 and a > 800:
                sc = abs(ww - PIECE_W) + abs(hh - PIECE_H)
                cand = dict(x=x0 + 6 + x, y=y0 + 6 + y, w=ww, h=hh, sc=sc)
                if best is None or sc < best["sc"]:
                    best = cand
        if best:   # 低阈值已找到就不升
            break
    if best:
        best["cx"] = best["x"] + best["w"] // 2
        best["cy"] = best["y"] + best["h"] // 2
    return best


def find_handle(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    orange = (h > 8) & (h < 25) & (s > 150) & (v > 180)
    orange[:850, :] = False
    orange[1030:, :] = False
    ys, xs = np.where(orange)
    if len(ys) < 300:
        return None
    return int(xs.mean()), int(ys.mean())


def human_slide(w, sx, sy, dx_total):
    ls = _load_last_shot()
    X, Y = ls["left"] + sx, ls["top"] + sy
    TX, TY = X + dx_total, Y
    _send_move_abs(X, Y)
    time.sleep(random.uniform(0.25, 0.4))
    _send_mouse(MOUSEEVENTF_LEFTDOWN)
    time.sleep(random.uniform(0.25, 0.35))
    for k in range(1, 8):
        _send_move_abs(X + int(k * 4), Y + int(k * 1.2))
        time.sleep(0.04)
    cx, cy = X + 28, Y + 8
    pts = []
    for i in range(1, 21):
        t = i / 20
        e = t * t * (3 - 2 * t)
        pts.append((cx + (TX - cx) * e * 0.55, cy + (TY - cy) * e * 0.55,
                    0.006, 0.014))
    pts.append((cx + (TX - cx) * 0.72, cy + (TY - cy) * 0.72, 0.15, 0.25))
    for i in range(15):
        t = 0.72 + 0.24 * (i / 15)
        e = 1 - (1 - t) ** 2
        pts.append((cx + (TX - cx) * e + random.uniform(-1.5, 1.5),
                    cy + (TY - cy) * e + random.uniform(-1.5, 1.5), 0.02, 0.05))
    for i in range(6):
        t = 0.96 + 0.04 * (i / 6)
        e = 1 - (1 - t) ** 2
        pts.append((cx + (TX - cx) * e, cy + (TY - cy) * e, 0.03, 0.06))
    for (X2, Y2, a, b) in pts:
        _send_move_abs(int(X2), int(Y2))
        time.sleep(random.uniform(a, b))
    _send_move_abs(TX + 3, TY + 2)
    time.sleep(0.1)
    _send_move_abs(TX, TY)
    time.sleep(random.uniform(0.4, 0.55))
    _send_mouse(MOUSEEVENTF_LEFTUP)
    time.sleep(2.0)


def on_captcha(w):
    t = "".join(l.get("text", "") for l in ocr(shot(w, "chk")).get("lines", [])).replace(" ", "")
    return ("滑动即可完成拼图" in t) or ("安全验证" in t and "拖动" not in t)


def click_refresh(w):
    p = shot(w, "rf")
    for l in ocr(p).get("lines", []):
        if "刷新" in (l.get("text") or "").replace(" ", ""):
            ls = _load_last_shot()
            human_click(ls["left"] + l["x"] + l["w"] // 2,
                        ls["top"] + l["y"] + l["h"] // 2, activate_window=w)
            time.sleep(2.5)
            return True
    return False


def solve_once(w, attempt):
    png = shot(w, f"a{attempt}")
    img = cv2.imread(png)
    box = find_image_box(img) or IMG_BOX
    gap = find_gap(img, box)
    hd = find_handle(img)
    if not gap or not hd:
        print(f"  [{attempt}] 识别失败: gap={gap} handle={hd}")
        return False
    pcx = box[0] + PIECE_OFF[0] + PIECE_W // 2
    delta = gap["cx"] - pcx
    print(f"  [{attempt}] 缺口({gap['cx']},{gap['cy']}) {gap['w']}x{gap['h']}  "
          f"拼图块({pcx},{box[1] + PIECE_OFF[1] + PIECE_H // 2})  位移 {delta}  手柄 {hd}")
    if abs(delta) < 20 or abs(delta) > 340:
        print(f"  [{attempt}] 位移异常，刷新")
        return False
    human_slide(w, hd[0], hd[1], delta)
    time.sleep(1.0)
    t = "".join(l.get("text", "") for l in ocr(shot(w, f"b{attempt}")).get("lines", [])).replace(" ", "")
    return "滑动即可完成拼图" not in t and "安全验证" not in t


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    w = winutil.chrome_window()
    w.set_focus()
    time.sleep(0.4)
    for i in range(1, rounds + 1):
        if not on_captcha(w):
            print("✓ 验证已通过")
            return 0
        print(f"第 {i} 次尝试")
        if solve_once(w, i):
            time.sleep(2)
            if not on_captcha(w):
                print("✓ 验证通过")
                return 0
        click_refresh(w)
        time.sleep(2)
    print("✗ 多次未通过")
    return 3


if __name__ == "__main__":
    sys.exit(main())
