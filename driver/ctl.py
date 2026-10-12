"""driver 小控制台：Bash 里一步一动作，computer-use 交互调试用。

用法：
  python ctl.py shot <name>              # 截图（建立 click 坐标系）
  python ctl.py click <x> <y>            # 点击截图坐标
  python ctl.py keys "<keys>"            # 按键 ^t ^w {ENTER} {ESC}
  python ctl.py type "<text>"            # 输入文本
  python ctl.py newtab <url>             # Ctrl+T 开临时标签并导航
  python ctl.py focus                    # 激活 Edge 窗口
  python ctl.py ocr [name]               # 最近/指定截图 OCR
  python ctl.py dialog <path>            # 原生文件夹对话框：填路径+确定（pick_folder4.ps1）
"""
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

import winutil
from input import human_click, type_keys
from shot import screenshot
from uia_shell import navigate


def win():
    w = winutil.default_window()
    if not w:
        raise SystemExit("无可见 Edge 窗口")
    return w


def main():
    cmd = sys.argv[1]
    if cmd == "shot":
        print(screenshot(win(), sys.argv[2] if len(sys.argv) > 2 else "ctl"))
    elif cmd == "click":
        from shot import _load_last_shot
        LAST_SHOT = _load_last_shot()
        if LAST_SHOT["hwnd"] is None:
            raise SystemExit("先 shot 建立坐标系")
        x, y = int(sys.argv[2]), int(sys.argv[3])
        human_click(LAST_SHOT["left"] + x, LAST_SHOT["top"] + y, activate_window=win())
        print(f"clicked ({x},{y})")
    elif cmd == "keys":
        type_keys(sys.argv[2])
        print("ok")
    elif cmd == "type":
        type_keys(sys.argv[2], pause=0.02)
        print("ok")
    elif cmd == "newtab":
        w = win()
        w.set_focus()
        type_keys("^t")
        time.sleep(0.8)
        navigate(w, sys.argv[2])
        time.sleep(3.5)
        print("tab opened:", sys.argv[2])
    elif cmd == "focus":
        win().set_focus()
        print("ok")
    elif cmd == "ocr":
        import glob
        import json
        import os
        if len(sys.argv) > 2:
            cands = sorted(glob.glob(os.path.join(r"D:\temu-agent\screenshots", f"*-{sys.argv[2]}.png")))
        else:
            cands = sorted(glob.glob(os.path.join(r"D:\temu-agent\screenshots", "*.png")))
        from shot import ocr
        result = ocr(cands[-1])
        for l in result["lines"]:
            print(f"({l['x']},{l['y']},{l['w']}x{l['h']}) {l['text']}")
    elif cmd == "dialog":
        ps = r"D:\temu-agent\scripts\pick_folder4.ps1"
        import subprocess as sp
        p = sp.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                      "-File", ps, "-TargetPath", sys.argv[2]],
                     stdout=sp.PIPE, stderr=sp.STDOUT)
        try:
            out, _ = p.communicate(timeout=60)
        except sp.TimeoutExpired:
            p.kill()
            out, _ = p.communicate()
        print(out.decode("gbk", "replace").strip() or "(no output)")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
