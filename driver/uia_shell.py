"""UIA 壳层操作：地址栏导航、标签切换、树 dump（只读）+ 元素点击坐标解析。"""
import time

import winutil
from input import human_click, type_keys


def _lit(s: str) -> str:
    """pywinauto send_keys 字面量转义：%^+~() 在其键盘语法里是特殊键
    （% 是 ALT 修饰符！2026-10-16 实测 percent 编码 URL 打字后变成垃圾：
    https%3A%2F%2Fagentseller… → httpsAFFagentseller…，下游 redirectUrl
    全坏、授权弹窗白屏）。花括号留给真按键使用。"""
    for ch in "^+%~()":
        s = s.replace(ch, "{" + ch + "}")
    return s


def navigate(win, url: str):
    """Ctrl+L → 输入 URL → 回车（UIA 定位地址栏获得焦点，输入走真实键盘）。"""
    edits = [e for e in win.descendants(control_type="Edit")
             if "地址" in (e.element_info.name or "")]
    if not edits:
        raise RuntimeError("UIA 未找到地址栏 Edit")
    edits[0].set_focus()
    time.sleep(0.3)
    type_keys("^l^a")
    time.sleep(0.1)
    type_keys(_lit(url), pause=0.01)
    time.sleep(0.2)
    type_keys("{ENTER}")


def tabs(win) -> list:
    return [t.window_text() for t in win.descendants(control_type="TabItem")]


def tab_items(win) -> list:
    """TabItem 元素列表（UIA 顺序 = 标签条顺序，可按索引 select）。"""
    return win.descendants(control_type="TabItem")


def switch_tab_index(win, idx: int) -> str:
    """按索引切标签（-1 = 最右/最新）。"""
    items = win.descendants(control_type="TabItem")
    t = items[idx]
    t.select()
    time.sleep(1.2)
    return t.window_text()


def switch_tab(win, title_contains: str) -> str:
    for t in win.descendants(control_type="TabItem"):
        if title_contains in (t.window_text() or ""):
            t.select()
            time.sleep(1.2)
            return t.window_text()
    raise RuntimeError(f"未找到标签页: {title_contains}")


def dump(win, depth: int = 8, name_contains: str | None = None, max_lines: int = 200) -> str:
    """UIA 树文本 dump（缩进树）。若 Edge 开了 renderer accessibility 则含网页内容。"""
    lines = []

    def walk(el, level):
        if len(lines) >= max_lines or level > depth:
            return
        try:
            name = (el.element_info.name or "").strip()
            ctype = el.element_info.control_type
        except Exception:
            return
        if not name_contains or name_contains in name:
            lines.append(f"{'  ' * level}{ctype}: {name[:60]}")
        try:
            children = el.children()
        except Exception:
            return
        if len(children) > 30:  # 剪枝：太宽的层只看前 30 个
            children = children[:30]
        for c in children:
            walk(c, level + 1)

    walk(win, 0)
    return "\n".join(lines)


def element_center(el) -> tuple:
    """UIA 元素中心（屏幕物理像素）。"""
    r = el.rectangle()
    return (r.left + r.right) // 2, (r.top + r.bottom) // 2


def find_and_click(win, name: str, control_type: str | None = None) -> dict:
    """按名称精确匹配 UIA 元素并人类化点击（仅壳层与 a11y 树内有效）。"""
    cands = []
    for el in win.descendants(title=name, control_type=control_type):
        try:
            if el.is_visible():
                cands.append(el)
        except Exception:
            continue
    if not cands:
        raise RuntimeError(f"UIA 未找到可点击元素: {name}")
    el = cands[0]
    x, y = element_center(el)
    human_click(x, y, activate_window=win)
    return {"clicked": name, "screen_x": x, "screen_y": y}
