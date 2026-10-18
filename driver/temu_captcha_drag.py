"""Temu 拖拽类验证码求解：把上方 4 个物体拖进下方对应方框。

物体无关解法：
1) 检测上方 tile 行（4 个 ~99px 方形）与下方目标方框（黑色长边框配对）
2) 每个 tile 内部图与每个方框内部图做多尺度模板匹配 → 各自配到最像的方框
3) human_drag 逐个拖入（SendInput 绝对移动，已验证能触发 dragstart）
4) 自动定位橙色提交按钮并提交
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
from shot import screenshot, _load_last_shot

AREA = (950, 1750, 400, 1320)   # x0,x1,y0,y1 验证卡片区域


def shot(w, tag):
    return screenshot(w, f"drag-{tag}")


def find_tiles(img):
    """上方 tile 行：Canny 轮廓里的近似方形，按 y 聚成一行取 4 个。"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    cnts, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    sq = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if 70 < w < 140 and 70 < h < 140 and 0.8 < w / h < 1.25:
            sq.append((x, y, w, h))
    # 去重
    uniq = []
    for s in sorted(sq, key=lambda t: (t[1], t[0])):
        if not any(abs(s[0] - u[0]) < 20 and abs(s[1] - u[1]) < 20 for u in uniq):
            uniq.append(s)
    if len(uniq) < 3:
        return []
    # 取 y 最靠上的一组（同一行、y 差 < 15）
    y0 = min(s[1] for s in uniq)
    row = [s for s in uniq if abs(s[1] - y0) < 15]
    return sorted(row, key=lambda s: s[0])


def find_boxes(img):
    """下方方框：黑色长横线（>150px）按 x 区间分组、按 y 配对。"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    x0a, x1a, y0a, y1a = AREA
    dark = (gray < 120).astype(np.uint8)
    runs = []
    for y in range(y0a, y1a):
        x = x0a
        while x < x1a:
            if dark[y, x]:
                s = x
                while x < x1a and dark[y, x]:
                    x += 1
                if x - s > 150:
                    runs.append((y, s, x))
            else:
                x += 1
    lines = []
    for (y, s, e) in runs:
        for L in lines:
            if abs(L[1] - s) < 25 and abs(L[2] - e) < 25 and y - L[3] <= 2:
                L[3] = y
                break
        else:
            lines.append([y, s, e, y])
    # 按 x 区间分组，组内按 y 配对（间距 150~400 视为一个框）
    lines.sort(key=lambda L: (L[1], L[0]))
    boxes = []
    i = 0
    while i < len(lines):
        grp = [lines[i]]
        j = i + 1
        while j < len(lines) and abs(lines[j][1] - lines[i][1]) < 25 \
                and abs(lines[j][2] - lines[i][2]) < 25:
            grp.append(lines[j])
            j += 1
        grp.sort(key=lambda L: L[0])
        k = 0
        while k + 1 < len(grp):
            gap = grp[k + 1][0] - grp[k][3]
            if 150 < gap < 400:
                bx0, bx1 = grp[k][1], grp[k][2]
                by0, by1 = grp[k][3], grp[k + 1][0]
                boxes.append((bx0, by0, bx1 - bx0, by1 - by0))
                k += 2
            else:
                k += 1
        i = j
    return boxes


def inner(img, rect, inset):
    x, y, w, h = rect
    return img[y + inset:y + h - inset, x + inset:x + w - inset]


def score(box_img, tile_img):
    """多尺度模板匹配，返回最高相关分。"""
    best = -1.0
    bg = cv2.cvtColor(box_img, cv2.COLOR_BGR2GRAY)
    for sc in (0.7, 0.85, 1.0, 1.15, 1.3):
        tw = int(tile_img.shape[1] * sc)
        th = int(tile_img.shape[0] * sc)
        if tw < 20 or th < 20 or tw >= bg.shape[1] or th >= bg.shape[0]:
            continue
        tg = cv2.cvtColor(cv2.resize(tile_img, (tw, th)), cv2.COLOR_BGR2GRAY)
        r = cv2.matchTemplate(bg, tg, cv2.TM_CCOEFF_NORMED)
        best = max(best, float(r.max()))
    return best


def find_submit(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    orange = (h > 8) & (h < 25) & (s > 150) & (v > 180)
    orange[:900, :] = False
    ys, xs = np.where(orange)
    if len(ys) < 500:
        return None
    return int(xs.mean()), int(ys.mean())


def main():
    w = winutil.default_window()
    img = cv2.imread(shot(w, "a"))
    tiles = find_tiles(img)
    boxes = find_boxes(img)
    print("tiles:", tiles)
    print("boxes:", boxes)
    if len(tiles) < 3 or len(boxes) < 2:
        print("✗ 检测失败")
        return 1

    tiles_img = [inner(img, t, 8) for t in tiles]
    boxes_img = [inner(img, b, 8) for b in boxes]
    # 每个 tile 配到最像的方框
    assign = []
    for ti, t in enumerate(tiles_img):
        sc = [score(b, t) for b in boxes_img]
        bi = int(np.argmax(sc))
        assign.append(bi)
        print(f"  tile{ti} -> box{bi}  分数={[round(x,2) for x in sc]}")
    if len(set(assign)) < min(3, len(boxes)):
        print("⚠ 有方框未被匹配到，仍按最高分配对继续")

    # 拖拽（同一方框多个 tile 时在框内错开落点）
    used = {}
    for ti, bi in enumerate(assign):
        bx, by, bw, bh = boxes[bi]
        n = used.get(bi, 0)
        used[bi] = n + 1
        tx = bx + bw // 2 + (0 if n == 0 else (30 if n % 2 else -30))
        ty = by + bh // 2 + (0 if n == 0 else (30 if n > 1 else 0))
        sx = tiles[ti][0] + tiles[ti][2] // 2
        sy = tiles[ti][1] + tiles[ti][3] // 2
        drag_window_coords(sx, sy, tx, ty, activate_window=w)
        print(f"  drag tile{ti}({sx},{sy}) -> box{bi}({tx},{ty})")

    time.sleep(0.8)
    img2 = cv2.imread(shot(w, "b"))
    pos = find_submit(img2)
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
