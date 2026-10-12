"""Phase 0：临时标签打开 edge://extensions 截图（看插件状态），然后关掉标签回到原页面。"""
import sys
import time
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

from pywinauto.keyboard import send_keys

import winutil
from shot import screenshot
from input import type_keys


def main():
    win = winutil.default_window()
    if not win:
        raise SystemExit("无可见 Edge 窗口")
    print(f"window: {win.window_text()!r}")

    win.set_focus()
    time.sleep(0.3)
    type_keys("^t")
    time.sleep(0.8)
    type_keys("edge://extensions", pause=0.02)
    time.sleep(0.2)
    type_keys("{ENTER}")
    time.sleep(3.5)

    path = screenshot(win, "extensions")
    print("shot:", path)

    type_keys("^w")  # 关闭临时标签，回到原页面
    print("tab closed")


if __name__ == "__main__":
    main()
