"""批量调价驱动：读工单 CSV（按倍数降序），逐个跑 grind_one.py，断点续跑。

用法：python grind_batch.py <worklist.csv> [--limit N]
- done 文件 research/store-data/adjust-done-<日期>.txt 记录 skc/rc/说明/输出尾行
- rc=0 提交成功；rc=3 表示 0 行可调（现价已被 Temu 自动调平/作废），均算完成
- 连续 8 个失败（rc=1/2）自动停止——大概率浏览器状态坏了（弹窗/登录/佳同开关）
- 每个超时 600s；CSV 无关键字列，grind_one 靠弹窗 SKC-ID 匹配
"""
import csv
import os
import subprocess
import sys
import time
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")
BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, ".."))
DATA = os.path.join(ROOT, "research", "store-data")
LAUNCH_URL = "https://agentseller.temu.com/newon/product-select"


def relaunch_edge():
    """Edge 窗口消失时普通参数拉起（手册允许），等窗口+页面就绪"""
    subprocess.Popen(f'start msedge "{LAUNCH_URL}"', shell=True)
    for _ in range(10):
        time.sleep(6)
        try:
            p = subprocess.run(
                [sys.executable, "-c",
                 f"import sys;sys.path.insert(0,r'{BASE}');"
                 "import winutil;print(1 if winutil.default_window() else 0)"],
                capture_output=True, text=True, timeout=30)
            if p.stdout.strip() == "1":
                return True
        except Exception:
            pass
    return False


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def main():
    wl = sys.argv[1]
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 10 ** 9
    done_path = os.path.join(DATA, f"adjust-done-{date.today()}.txt")
    done = set()
    try:
        for line in open(done_path, encoding="utf-8"):
            parts = line.strip().split("\t")
            # 只有 0（提交成功）/3（0行可调）算完成；1/2/9 失败下轮重试
            if parts and parts[1] in ("0", "3"):
                done.add(parts[0])
    except FileNotFoundError:
        pass
    rows = list(csv.DictReader(open(wl, encoding="utf-8-sig")))
    skcs = []
    for r in rows:
        s = str(r["SKC"])
        if s not in skcs:
            skcs.append(s)
    todo = [s for s in skcs if s not in done]
    log(f"工单共 {len(skcs)} SKC，已完成 {len(skcs) - len(todo)}，本次待跑 {min(len(todo), limit)}")
    consec_fail = 0
    ran = ok = noop = fail = 0
    with open(done_path, "a", encoding="utf-8") as df:
        for s in todo:
            if ran >= limit:
                log(f"达到本次 limit={limit}，停止")
                break
            if consec_fail >= 8:
                log("连续 8 次失败，停止（人工检查浏览器状态）")
                break
            log(f"== [{ran + 1}/{len(todo)}] SKC {s}")
            try:
                p = subprocess.run(
                    [sys.executable, os.path.join(BASE, "grind_one.py"), s, "派对餐巾"],
                    capture_output=True, text=True, encoding="utf-8",
                    cwd=BASE, timeout=600)
                rc, out = p.returncode, (p.stdout or "") + (p.stderr or "")
            except subprocess.TimeoutExpired:
                rc, out = 9, "(timeout 600s)"
            tail = " | ".join(l.strip() for l in out.strip().splitlines()[-2:]) if out.strip() else ""
            note = {0: "OK", 2: "未找到目标", 3: "0行可调"}.get(rc, f"rc={rc}")
            df.write(f"{s}\t{rc}\t{note}\t{tail[:150]}\n")
            df.flush()
            log(f"   -> {note}  {tail[:110]}")
            ran += 1
            if rc in (0, 3):
                consec_fail = 0
                ok += rc == 0
                noop += rc == 3
            else:
                consec_fail += 1
                fail += 1
                if "无窗口" in tail:
                    log("   Edge 窗口丢失，重新拉起…")
                    if relaunch_edge():
                        log("   ✓ Edge 已恢复")
                        consec_fail = 0
                    else:
                        log("   ✗ Edge 拉起失败，停止")
                        break
    log(f"批次结束：成功 {ok}，0行可调 {noop}，失败 {fail}")


if __name__ == "__main__":
    main()
