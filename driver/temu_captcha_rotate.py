"""Temu 旋转类验证码求解：使所有物体朝向一致（点击图片每次旋转 90°）。

物体无关解法（不依赖颜色/物种）：
1) 以第 1 格为基准，对每格试 0/90/180/270 四种旋转 + 小位移搜索，
   取最匹配者 → 得到「该格需顺时针转 k×90° 才能与基准一致」
2) 点基准格一次做试验，看 k 变化方向 → 判断点击是顺时针还是逆时针
3) 闭环点击：点一轮 → 重量一轮 → 直到 6 格朝向全一致（防点击被吞）
4) 提交
"""
import os
import sys
import time

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import winutil
from input import human_click
from shot import screenshot, _load_last_shot

CELL_X = [(981, 1177), (1177, 1381), (1381, 1588)]
CELL_Y = [(585, 794), (794, 1008)]
INSET = 12
SIZE = 96
CELLS = [(r, c) for r in range(2) for c in range(3)]


def shot(w, tag):
    return screenshot(w, f"rot-{tag}")


def norm_cell(img, r, c):
    x0, x1 = CELL_X[c]
    y0, y1 = CELL_Y[r]
    sub = img[y0 + INSET:y1 - INSET, x0 + INSET:x1 - INSET]
    g = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
    return cv2.resize(g, (SIZE, SIZE), interpolation=cv2.INTER_AREA).astype(np.float32)


def _mse(a, b):
    """只在「非背景」像素上算 MSE（背景≈白），抗留白差异。"""
    mask = (a < 235) | (b < 235)
    if mask.sum() < 50:
        return 1e9
    d = (a - b)[mask]
    return float((d * d).mean())


def rot_mse(g, ref):
    """返回 [k=0,1,2,3] 各自「顺时针转 k×90° 后与 ref 的 MSE」。"""
    out = []
    for k in range(4):
        rot = np.rot90(g, -k)  # -k = 顺时针 k×90°
        best = 1e18
        for dy in (-4, -2, 0, 2, 4):
            for dx in (-4, -2, 0, 2, 4):
                m = np.roll(np.roll(rot, dy, 0), dx, 1)
                v = _mse(m, ref)
                if v < best:
                    best = v
        out.append(best)
    return out


def measure(img, ref):
    """返回 {cell: 需顺时针 k×90° 才与 ref 一致}。"""
    res = {}
    for k in CELLS:
        res[k] = int(np.argmin(rot_mse(norm_cell(img, *k), ref)))
    return res


def click_cell(w, r, c, focus=False):
    ls = _load_last_shot()
    x = (CELL_X[c][0] + CELL_X[c][1]) // 2
    y = (CELL_Y[r][0] + CELL_Y[r][1]) // 2
    human_click(ls["left"] + x, ls["top"] + y, activate_window=w if focus else None)
    time.sleep(0.85)


def find_submit(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    orange = (h > 8) & (h < 25) & (s > 150) & (v > 180)
    orange[:1000, :] = False
    ys, xs = np.where(orange)
    if len(ys) < 500:
        return None
    return int(xs.mean()), int(ys.mean())


def main():
    w = winutil.default_window()
    img = cv2.imread(shot(w, "a"))
    ref = norm_cell(img, 0, 0)
    cur = measure(img, ref)
    print("初始 k(需顺时针×90):", cur)

    # 试验点击：判断旋转方向
    probe = (0, 0)
    w.set_focus()
    time.sleep(0.4)
    click_cell(w, *probe)
    img2 = cv2.imread(shot(w, "b"))
    after = measure(img2, ref)
    d = (after[probe] - cur[probe]) % 4
    if d == 0:
        print("✗ 点击未改变朝向（点空或已超时）")
        return 1
    cw = (d == 3)   # 顺时针点击 → k 减 1
    print(f"试验：k {cur[probe]} → {after[probe]} ⇒ 点击{'顺时针' if cw else '逆时针'}")

    w.set_focus()
    time.sleep(0.3)
    ok = False
    img3 = img2
    for rnd in range(1, 8):
        img3 = cv2.imread(shot(w, f"c{rnd}"))
        m = measure(img3, ref)
        bad = [k for k in CELLS if m[k] != 0]
        print(f"  第{rnd}轮 k={m} 待修={bad}")
        if not bad:
            ok = True
            break
        for k in bad:
            click_cell(w, *k)
    if not ok:
        print("✗ 未对齐，不提交")
        return 3
    print("✓ 6 格朝向已一致")

    pos = find_submit(img3)
    if not pos:
        print("✗ 未找到提交按钮")
        return 3
    ls = _load_last_shot()
    human_click(ls["left"] + pos[0], ls["top"] + pos[1], activate_window=w)
    print("✓ 已提交", pos)
    time.sleep(6)
    print("结果图:", shot(w, "done"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
