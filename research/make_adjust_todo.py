"""从商品导出表生成调价工单 CSV（按倍数降序）。
用法：python make_adjust_todo.py <store> [xlsx路径]
默认读 research/store-data/<store>-goods-<最新日期>.xlsx，
产出 research/store-data/adjust-todo-<store>-<日期>.csv
规则与 grind_one 一致：保本价=(成本×数量+9)/0.8，建议价=(成本×数量+9)/0.5，
只收在售中+已生效价格+数量可解析的 SKU，倍数=现价/建议价>1.05。
"""
import csv
import math
import os
import re
import sys

import openpyxl

sys.stdout.reconfigure(encoding="utf-8")
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "store-data")

COST = {"派对餐巾": 0.16, "餐巾": 0.16, "餐巾纸": 0.16, "儿童派对餐巾": 0.16, "身份腕带": 0.33, "压花机": 25}  # 压花机=钢印 25元/个（2026-10-24 用户确认）
QTY_RE = re.compile(r"(\d+)\s*(?:pcs|件|张|片|个|台|只)", re.I)


def sug(cat, q):
    return math.ceil((COST[cat] * q + 9) / 0.5 * 2) / 2


def main():
    store = sys.argv[1]
    fp = sys.argv[2] if len(sys.argv) > 2 else None
    if not fp:
        cands = sorted(f for f in os.listdir(DATA)
                       if f.startswith(f"{store}-goods-") and f.endswith(".xlsx"))
        if not cands:
            print(f"✗ 无 {store} 导出文件")
            return 1
        fp = os.path.join(DATA, cands[-1])
    print("读", os.path.basename(fp))

    wb = openpyxl.load_workbook(fp, read_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    hdr = [str(h or "") for h in next(rows)]
    idx = {h: i for i, h in enumerate(hdr)}
    g = lambda r, k: r[idx[k]] if idx.get(k, -1) < len(r) else None

    skc_info = {}   # skc -> dict(title, cat)
    over = {}       # skc -> [(mult, price, qty)]
    n_sku = n_skip_cat = n_skip_qty = 0
    for r in rows:
        if g(r, "SKC ID") is None:
            continue
        status = str(g(r, "商品状态") or "")
        pstat = str(g(r, "申报价格状态") or "")
        try:
            price = float(g(r, "申报价格(CNY)"))
        except (TypeError, ValueError):
            continue
        if status != "在售中" or pstat != "已生效":
            continue
        skc = str(g(r, "SKC ID"))
        cat = str(g(r, "叶子类目名称") or "")
        title = str(g(r, "商品标题") or "")
        skc_info.setdefault(skc, {"title": title, "cat": cat})
        n_sku += 1
        if cat not in COST:
            n_skip_cat += 1
            continue
        spec = " ".join(str(g(r, k) or "") for k in ("规格1名称", "规格2名称"))
        m = QTY_RE.search(spec)
        if m:
            qty = int(m.group(1))
        elif cat == "压花机":
            qty = 1  # 钢印规格无数量字段（颜色/风格），每个 SKU 即 1 台
        else:
            n_skip_qty += 1
            continue
        if qty < 10 and cat != "压花机":
            n_skip_qty += 1
            continue
        mult = price / sug(cat, qty)
        if mult > 1.05:
            over.setdefault(skc, []).append((mult, price, qty))

    out = []
    for skc, items in over.items():
        items.sort(reverse=True)
        out.append({
            "SKC": skc,
            "倍数": round(items[0][0], 2),
            "超标SKU数": len(items),
            "类目": skc_info[skc]["cat"],
            "标题": skc_info[skc]["title"][:60],
        })
    out.sort(key=lambda x: -x["倍数"])

    day = os.path.basename(fp).split("-goods-")[-1].replace(".xlsx", "")
    dest = os.path.join(DATA, f"adjust-todo-{store}-{day}.csv")
    with open(dest, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["SKC", "倍数", "超标SKU数", "类目", "标题"])
        w.writeheader()
        w.writerows(out)
    print(f"在售有效 SKU {n_sku}，跳过未知类目 {n_skip_cat}、数量不可解析 {n_skip_qty}")
    print(f"超标 SKC {len(out)} → {os.path.basename(dest)}")
    for x in out[:10]:
        print(f"  {x['SKC']} x{x['倍数']} ({x['超标SKU数']}SKU) {x['类目']} {x['标题'][:30]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
