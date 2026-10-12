"""DPI-aware 窗口截图 + OCR（Windows 自带 Media.Ocr，中文优先）。

坐标约定（全项目统一）：截图与点击坐标都是**物理像素**，原点=窗口左上角（窗口客户区近似）。
click_point 工具把窗口坐标换算成屏幕绝对坐标再发事件。
"""
import json
import os
import subprocess
import time
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
SHOT_DIR = os.path.abspath(os.path.join(BASE, "..", "screenshots"))
OCR_PS = os.path.join(BASE, "ocr.ps1")

# 最近一次成功截图的坐标系（窗口 hwnd + 屏幕原点），click_point 用它换算
LAST_SHOT = {"hwnd": None, "left": 0, "top": 0}


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d-%H-%M-%S")  # 本地时间（修旧项目 UTC 坑）


def screenshot(win, name: str = "shot") -> str:
    """截指定窗口（前台），存 screenshots/，返回绝对路径。"""
    os.makedirs(SHOT_DIR, exist_ok=True)
    win.set_focus()
    time.sleep(0.4)
    img = win.capture_as_image()
    path = os.path.join(SHOT_DIR, f"{_timestamp()}-{name}.png")
    img.save(path)
    r = win.rectangle()
    LAST_SHOT.update(hwnd=win.handle, left=r.left, top=r.top, w=img.size[0], h=img.size[1])
    return path


def ocr(path: str) -> dict:
    """调 PowerShell Windows.Media.Ocr，返回 {lines:[{text,x,y,w,h}], width, height}。

    坐标为相对截图（物理像素）的左上/右下角框。
    """
    out = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", OCR_PS, "-ImagePath", path],
        capture_output=True, text=True, timeout=60,
    )
    if out.returncode != 0:
        raise RuntimeError(f"OCR 失败: {out.stderr.strip()[:400]}")
    return json.loads(out.stdout)
