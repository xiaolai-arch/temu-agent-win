"""报告/状态（沿用旧项目格式，时间戳改本地时间）。"""
import json
import os
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, ".."))
LOG_DIR = os.path.join(ROOT, "logs")


def write_report(task: str, ok: bool, lines: list, shots: list | None = None) -> str:
    """写 logs/report-latest.md（覆盖）+ logs/<task>-<date>.md（追加历史）。"""
    os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.now().isoformat(timespec="seconds")
    body = [f"# {task} 报告", f"- 时间: {ts}", f"- 结果: {'✅ 成功' if ok else '❌ 失败'}"]
    body += [f"- {l}" for l in lines]
    if shots:
        body += [f"- 截图: {s}" for s in shots]
    text = "\n".join(body) + "\n"

    latest = os.path.join(LOG_DIR, "report-latest.md")
    with open(latest, "w", encoding="utf-8") as f:
        f.write(text)
    history = os.path.join(LOG_DIR, f"{task}-{datetime.now().strftime('%Y-%m-%d')}.md")
    with open(history, "a", encoding="utf-8") as f:
        f.write(text + "\n")

    status = {
        "task": task,
        "ts": ts,
        "ok": ok,
        "summary": lines[-1] if lines else "",
        "report": latest,
        "shots": shots or [],
    }
    with open(os.path.join(LOG_DIR, "last-status.json"), "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
    return latest


def read_latest() -> str:
    p = os.path.join(LOG_DIR, "report-latest.md")
    if not os.path.exists(p):
        return "(尚无报告)"
    with open(p, encoding="utf-8") as f:
        return f.read()
