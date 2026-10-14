"""恢复 Edge 同步插件（2026-10-14 事故复盘：Edge 大版本更新会关闭开发人员模式并
整批卸载解压加载的插件 → 定制商品页双按钮消失 → 所有店切换验证必失败）。

做法（全部走浏览器正常 UI，符合红线：只启用开发人员模式、只读 cross 目录、
零自动化启动参数）：
  edge://extensions → 打开「开发人员模式」→「加载解压缩的扩展」→
  原生「选择要加载的扩展目录」对话框输入完整路径 → 「选择文件夹」× 3 个插件。

用法：python restore_extensions.py        # 缺哪个补哪个（doctor 会查在位状态）
对话框坐标为主屏最大化 Edge 实测（窗口 2582x1550）；异常时人工在
edge://extensions 操作一遍即可。
"""
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

import winutil
import uia_shell
from input import human_click, type_keys
from shot import screenshot, ocr
from switch_store import log, find_line

CROSS = r"C:\Users\34191\Desktop\cross"
EXTS = ["jiatong-temu-387", "yishu-plugin", "miaoshou-erp-plugin-v3"]  # 旧 profile 同款三件套
DLG_EDIT, DLG_BTN = (600, 710), (1031, 755)  # 「选择要加载的扩展目录」对话框实测坐标


def _prefs_blob() -> str:
    import os
    pref_dir = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default")
    blob = ""
    for fn in ("Preferences", "Secure Preferences"):
        try:
            blob += open(pref_dir + "\\" + fn, encoding="utf-8").read()
        except OSError:
            pass
    return blob


def _dev_mode_on(w) -> bool:
    """「开发人员模式」开关行（左下角）出现蓝色/深色实心轨道即开启。"""
    from PIL import Image
    img = Image.open(screenshot(w, "devmode")).convert("RGB")
    px = img.load()
    for x in range(380, 520, 2):
        colored = sum(1 for y in range(1425, 1475, 2)
                      if px[x, y][2] > 140 and px[x, y][2] - px[x, y][0] > 40)
        if colored >= 6:
            return True
    # 开启后该行右侧会出现「加载解压缩的扩展」等按钮，也是开启证据
    lines = ocr_lines_cached(w)
    return find_line(lines, ["加载解压缩", "解压缩的扩展"]) is not None


def ocr_lines_cached(w):
    return ocr(screenshot(w, "devmode2"))["lines"]


def _open_dev_mode(w):
    r = w.rectangle()
    for cx, cy in [(429, 1450), (435, 1451), (420, 1445), (445, 1455), (158, 1451)]:
        human_click(r.left + cx, r.top + cy, activate_window=w)
        time.sleep(1.2)
        if _dev_mode_on(w):
            log(f"→ 开发人员模式已打开（点击 {cx},{cy}）")
            return
    raise SystemExit("❌ 没能打开开发人员模式，请人工在 edge://extensions 打开后重跑")


def _load_unpacked(w, folder: str):
    r = w.rectangle()
    btn = None
    for _ in range(3):
        lines = ocr(screenshot(w, "lb"))["lines"]
        btn = find_line(lines, ["加载解压缩的扩展", "解压缩的扩展"])
        if btn:
            break
        time.sleep(1.2)
    if not btn:
        raise RuntimeError("未找到「加载解压缩的扩展」按钮（开发人员模式没开？）")
    human_click(r.left + btn["x"] + btn["w"] // 2, r.top + btn["y"] + btn["h"] // 2,
                activate_window=w)
    time.sleep(1.8)
    # 原生「选择要加载的扩展目录」对话框：点输入框 → 敲完整路径 → 「选择文件夹」
    human_click(r.left + DLG_EDIT[0], r.top + DLG_EDIT[1], activate_window=w)
    time.sleep(0.5)
    type_keys("^a")
    type_keys(folder, pause=0.01)
    time.sleep(0.6)
    human_click(r.left + DLG_BTN[0], r.top + DLG_BTN[1], activate_window=w)
    time.sleep(3)


def main():
    blob = _prefs_blob()
    missing = [e for e in EXTS if e not in blob]
    if not missing:
        log("三个插件都在位，无需恢复 ✅")
        return 0
    w = winutil.default_window()
    if not w:
        raise SystemExit("无 Edge 窗口")
    w.set_focus()
    uia_shell.navigate(w, "edge://extensions")
    time.sleep(2.5)
    if not _dev_mode_on(w):
        log("→ 开发人员模式关闭，尝试打开…")
        _open_dev_mode(w)
        time.sleep(1)
    for name in missing:
        log(f"→ 加载插件 {name}")
        _load_unpacked(w, CROSS + "\\" + name)
        uia_shell.navigate(w, "edge://extensions")
        time.sleep(2)
    blob = _prefs_blob()
    still = [e for e in EXTS if e not in blob]
    log("恢复完成：" + ("全部在位 ✅" if not still else f"仍缺 {still}，请人工核对 edge://extensions"))
    return 0 if not still else 1


if __name__ == "__main__":
    raise SystemExit(main())
