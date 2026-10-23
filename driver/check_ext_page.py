"""OCR 最新截图并按关键词过滤（用于扩展页/商品页快速验证）。用法：python check_ext_page.py 关键词1 关键词2 ..."""
import glob
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
from shot import ocr

SHOTS = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "screenshots"))
cands = sorted(glob.glob(os.path.join(SHOTS, "*.png")), key=os.path.getmtime)
path = cands[-1]
print("file:", os.path.basename(path))
keys = sys.argv[1:] or ["扩展", "同步", "忆托", "yishu"]
d = ocr(path)
for l in d["lines"]:
    t = l["text"].replace(" ", "")
    if any(k.lower() in t.lower() for k in keys):
        print(f"({l['x']},{l['y']},{l['w']}x{l['h']}) {t}")
