"""temu-driver — MCP server（stdio）：UIA 壳层 + 视觉/OCR 内容层 + 报告。

坐标约定：screenshot 返回的图片坐标 = 物理像素，原点=窗口左上角；
click_point(x, y) 接受同一坐标系（基于最近一次截图的窗口原点自动换算屏幕坐标）。
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")

from mcp.server.mcpserver import MCPServer, Image

import report
import shot
import uia_shell
import winutil
from input import human_click, type_keys

mcp = MCPServer(name="temu-driver")


def _win(hwnd: int | None = None):
    if hwnd:
        w = winutil.find_window(hwnd)
        if not w:
            raise RuntimeError(f"hwnd={hwnd} 已失效，请重新 edge_windows()")
        return w
    w = winutil.default_window()
    if not w:
        raise RuntimeError("无可见 Edge 窗口；先 edge_navigate(url) 拉起")
    return w


# ---------- 只读：窗口与导航 ----------

@mcp.tool()
def edge_windows() -> str:
    """列出可见 Edge 窗口（hwnd/title/rect/最小化）。只读。"""
    return "\n".join(
        f"hwnd={s['hwnd']} title={s['title']!r} rect=({s['rect']['left']},{s['rect']['top']},{s['w']}x{s['h']}) min={s['minimized']}"
        for s in (winutil.window_summary(w) for w in winutil.edge_windows())
    ) or "(无)"


@mcp.tool()
def edge_focus(hwnd: int) -> str:
    """激活指定 Edge 窗口。"""
    _win(hwnd).set_focus()
    return f"ok hwnd={hwnd}"


@mcp.tool()
def edge_navigate(url: str, hwnd: int | None = None) -> str:
    """导航到 URL（必要时普通参数拉起 Edge，绝不带调试/注入 flag）。"""
    if hwnd is None and not winutil.edge_windows():
        w = winutil.launch_edge(url)
        return f"launched hwnd={w.handle}"
    w = _win(hwnd)
    uia_shell.navigate(w, url)
    import time
    time.sleep(4)
    return f"navigated hwnd={w.handle} url={url}"


@mcp.tool()
def edge_tabs(hwnd: int | None = None) -> str:
    """列出窗口的标签页标题。只读。"""
    return "\n".join(uia_shell.tabs(_win(hwnd))) or "(无标签)"


@mcp.tool()
def edge_tab_select(title_contains: str, hwnd: int | None = None) -> str:
    """切换到标题包含指定文本的标签页。"""
    return f"selected: {uia_shell.switch_tab(_win(hwnd), title_contains)}"


@mcp.tool()
def uia_dump(depth: int = 8, name_contains: str | None = None, hwnd: int | None = None) -> str:
    """dump UIA 树（壳层可靠；网页内容默认不在树里，除非 Edge 开了 renderer accessibility）。只读。"""
    return uia_shell.dump(_win(hwnd), depth=depth, name_contains=name_contains)


# ---------- 感知：截图与 OCR ----------

@mcp.tool()
def screenshot(name: str = "shot", hwnd: int | None = None) -> Image:
    """截当前/指定 Edge 窗口，返回图片供视觉分析（模型直接看图找元素）。
    图片坐标=物理像素、原点=窗口左上角；后续 click_point 用同一坐标系。"""
    path = shot.screenshot(_win(hwnd), name)
    return Image(path=path)


@mcp.tool()
def ocr_last(name: str | None = None) -> str:
    """对最近一张截图（或指定文件名）做 OCR，返回文本行+坐标（JSON）。
    适合精确文本定位（如「按勾选同步」按钮）；视觉模型看不出小字时用它。"""
    import glob
    import os
    if name:
        cands = sorted(glob.glob(os.path.join(shot.SHOT_DIR, f"*-{name}.png")), key=os.path.getmtime)
        if not cands:
            return f"未找到 *-{name}.png"
        path = cands[-1]
    else:
        cands = sorted(glob.glob(os.path.join(shot.SHOT_DIR, "*.png")), key=os.path.getmtime)
        if not cands:
            return "screenshots/ 为空，先 screenshot()"
        path = cands[-1]
    return str(shot.ocr(path))


# ---------- 动作：点击/输入/滚动（改页面状态，任务层负责门禁） ----------

@mcp.tool()
def click_point(x: int, y: int) -> str:
    """人类化点击截图坐标 (x,y)（物理像素，原点=最近一次截图的窗口左上角）。"""
    last = shot._load_last_shot()
    if last["hwnd"] is None:
        raise RuntimeError("先 screenshot() 建立坐标系")
    w = winutil.find_window(last["hwnd"]) or _win()
    human_click(last["left"] + x, last["top"] + y, activate_window=w)
    return f"clicked ({x},{y}) -> screen ({last['left'] + x},{last['top'] + y})"


@mcp.tool()
def click_element(name: str, control_type: str | None = None) -> str:
    """按名称点击 UIA 元素（仅壳层/a11y 树内元素有效；网页元素优先 click_point+视觉）。"""
    return str(uia_shell.find_and_click(_win(), name, control_type))


@mcp.tool()
def type_text(text: str) -> str:
    """输入文本（真实键盘事件；支持中文）。"""
    type_keys(text, pause=0.02)
    return f"typed {len(text)} chars"


@mcp.tool()
def press_keys(keys: str) -> str:
    """按键组合，pywinauto 语法：{ENTER} {ESC} {TAB} ^l ^a ^t ^w +f 等。"""
    type_keys(keys)
    return f"keys {keys}"


@mcp.tool()
def scroll(dy: int = -300) -> str:
    """滚轮滚动（负=向上，正=向下），作用于当前鼠标位置。"""
    import ctypes
    import random
    import time as _t
    MOUSEEVENTF_WHEEL = 0x0800
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, -dy * 120, 0)
    _t.sleep(random.uniform(0.2, 0.4))
    return f"scrolled {dy}"


# ---------- 报告 ----------

@mcp.tool()
def write_report(task: str, ok: bool, lines: list[str]) -> str:
    """写中文报告（logs/report-latest.md + 历史 + last-status.json），lines 逐条为要点。"""
    import glob
    import os
    cands = sorted(glob.glob(os.path.join(shot.SHOT_DIR, "*.png")), key=os.path.getmtime)
    shots_recent = [os.path.abspath(p) for p in cands[-3:]]
    return "report: " + report.write_report(task, ok, lines, shots_recent)


@mcp.tool()
def read_report() -> str:
    """读最近一次报告。"""
    return report.read_latest()


if __name__ == "__main__":
    mcp.run()
