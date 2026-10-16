"""蓝色块检测（白字蓝底按钮定位，OCR 读不出白字时用）。

用法:
  python scripts/find_blue.py <png> <x1> <y1> <x2> <y2> [min_w] [min_h]

输出：区域内蓝色像素簇的外接矩形（物理像素, 相对整图）+ 中心点。
判据（skill 定稿）: b>170 且 b-r>60 且 b-g>30
"""
import sys
from PIL import Image


def main():
    src = sys.argv[1]
    x1, y1, x2, y2 = map(int, sys.argv[2:6])
    min_w = int(sys.argv[6]) if len(sys.argv) > 6 else 40
    min_h = int(sys.argv[7]) if len(sys.argv) > 7 else 20
    img = Image.open(src).convert("RGB").crop((x1, y1, x2, y2))
    w, h = img.size
    px = img.load()

    # 标记蓝色像素
    mask = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if b > 170 and b - r > 60 and b - g > 30:
                mask[y][x] = True

    # 简单连通域（4 邻域，BFS）
    seen = [[False] * w for _ in range(h)]
    boxes = []
    for sy in range(h):
        for sx in range(w):
            if mask[sy][sx] and not seen[sy][sx]:
                stack = [(sx, sy)]
                seen[sy][sx] = True
                minx = maxx = sx
                miny = maxy = sy
                cnt = 0
                while stack:
                    cx, cy = stack.pop()
                    cnt += 1
                    minx, maxx = min(minx, cx), max(maxx, cx)
                    miny, maxy = min(miny, cy), max(maxy, cy)
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < w and 0 <= ny < h and mask[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx] = True
                            stack.append((nx, ny))
                boxes.append((minx, miny, maxx, maxy, cnt))

    boxes = [b for b in boxes if (b[2] - b[0]) >= min_w and (b[3] - b[1]) >= min_h]
    boxes.sort(key=lambda b: -b[4])
    if not boxes:
        print("(未发现蓝色块)")
    for bx1, by1, bx2, by2, cnt in boxes[:5]:
        print(f"bbox=({bx1 + x1},{by1 + y1})-({bx2 + x1},{by2 + y1}) "
              f"w={bx2 - bx1 + 1} h={by2 - by1 + 1} px={cnt} "
              f"center=({(bx1 + bx2) // 2 + x1},{(by1 + by2) // 2 + y1})")


if __name__ == "__main__":
    main()
