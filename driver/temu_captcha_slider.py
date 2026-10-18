"""Temu 滑块拼图验证码求解（一条龙，避免超时）。

几何事实（2026-10-17 实测）：
- 拼图块固定在拼图区左上角：相对拼图区 bbox 约 (11, 17) 起、约 47x50
- 缺口是拼图区里的暗色块；按「尺寸最接近拼图块」挑选
- 滑块手柄 = 拼图区下方的橙色圆
- 拖动用 SendInput 绝对移动（能触发 dragstart），慢速缓动
"""
import os
import sys
import time

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import winutil
from input import human_click, drag_window_coords
from shot import screenshot, ocr, _load_last_shot

PIECE_OFF = (11, 17)      # 拼图块相对拼图区 bbox 的偏移
PIECE_SIZE = (47, 50)     # 拼图块近似尺寸
W, H = 2582, 1550


def shot(w, tag):
    return screenshot(w, f"sl-{tag}")


def find_image_box(img):
    """拼图区：验证卡片里最大的「非纯白」矩形块。"""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    notwhite = (g < 238).astype(np.uint8)
    notwhite[:560, :] = 0
    notwhite[900:, :] = 0
    notwhite[:, :1020] = 0
    notwhite[:, 1620:] = 0
    notwhite = cv2.morphologyEx(notwhite, cv2.MORPH_CLOSE, np.ones((21, 21), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(notwhite)
    if n < 2:
        return None
    # 取最大的一块，再取它的水平投影宽度最大的行来定宽（抗缺口让块分裂）
    i = 1 + int(np.argmax(stats[1:, 4]))
    x, y, w, h, a = stats[i]
    return (x, y, w, h)


def find_gaps(img, box):
    x0, y0, w, h = box
    sub = img[y0:y0 + h, x0:x0 + w]
    g = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
    dark = (g < 62).astype(np.uint8)
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(dark)
    out = []
    for i in range(1, n):
        x, y, ww, hh, a = stats[i]
        if 30 < ww < 130 and 30 < hh < 130 and a > 800:
            out.append(dict(x=x0 + x, y=y0 + y, w=ww, h=hh,
                            cx=x0 + x + ww // 2, cy=y0 + y + hh // 2))
    return out


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


def dismiss_timeout(w):
    """若出现「验证过程耗时过长」弹窗，点确定。"""
    png = shot(w, "chk")
    t = "".join(l.get("text", "") for l in ocr(png).get("lines", []))
    if "耗时过长" not in t.replace(" ", ""):
        return False
    for l in ocr(png).get("lines", []):
        if "确定" in (l.get("text") or "").replace(" ", ""):
            ls = _load_last_shot()
            human_click(ls["left"] + l["x"] + l["w"] // 2,
                        ls["top"] + l["y"] + l["h"] // 2, activate_window=w)
            time.sleep(1.5)
            print("✓ 已关超时弹窗")
            return True
    return False


def main():
    w = winutil.chrome_window()
    w.set_focus()
    time.sleep(0.4)
    dismiss_timeout(w)
    time.sleep(2.0)

    png = shot(w, "a")
    img = cv2.imread(png)
    box = find_image_box(img)
    if not box:
        print("✗ 未找到拼图区")
        return 1
    px, py = box[0] + PIECE_OFF[0], box[1] + PIECE_OFF[1]
    pcx, pcy = px + PIECE_SIZE[0] // 2, py + PIECE_SIZE[1] // 2
    gaps = find_gaps(img, box)
    print(f"拼图区 {box}  拼图块@({pcx},{pcy})  缺口 {[(g['x'],g['y'],g['w'],g['h']) for g in gaps]}")
    if not gaps:
        print("✗ 未找到缺口")
        return 1
    gap = min(gaps, key=lambda g: abs(g["w"] - PIECE_SIZE[0]) + abs(g["h"] - PIECE_SIZE[1]))
    delta = gap["cx"] - pcx
    print(f"目标缺口 {gap['w']}x{gap['h']} @({gap['cx']},{gap['cy']})  位移 {delta}")

    hd = find_handle(img)
    if not hd:
        print("✗ 未找到滑块手柄")
        return 1
    print("手柄:", hd)
    drag_window_coords(hd[0], hd[1], hd[0] + delta, hd[1], activate_window=w)
    time.sleep(4.5)
    png2 = shot(w, "b")
    t = "".join(l.get("text", "") for l in ocr(png2).get("lines", []))
    still = "安全验证" in t.replace(" ", "")
    print(("✗ 仍在验证页" if still else "✓ 已通过验证"), png2)
    return 3 if still else 0


if __name__ == "__main__":
    sys.exit(main())
