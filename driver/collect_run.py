"""速卖通无人值守长跑采集：自动搜词 → 自动定位网格 → 逐格采集 → 触底自动换词。

用法：python collect_run.py <目标点击数> [已累计点击]
  例：python collect_run.py 2000 100

网格定位：OCR 价格行（含"美元"且同排 >=3 项、x>400）→ 格中心 = (价格x+146, 价格y-250)
流：点格 → 新详情标签 → teal「采集此商品」→ 5s → ^w 回列表 → 1.5s
异常：滑块自动解；拖拽/旋转/超时类 → 退出码 3 停止并等人工
进度：每屏写日志 logs/collect_run.log
"""
import os
import random
import re
import sys
import time

import cv2

sys.stdout.reconfigure(encoding="utf-8")
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import winutil
import uia_shell
from input import human_click, type_keys, alt_left, _send_move_abs
from shot import screenshot, ocr, _load_last_shot

LOG = os.path.abspath(os.path.join(BASE, "..", "logs", "collect_run.log"))
MIAOSHOU_MARK = "妙手"
ERP_URL = "https://erp.91miaoshou.com/pddkj/collect_box/items"
LOGGED_MARKS = ("未发布", "采集箱", "待办事项", "常用功能")
LOGIN_MARKS = ("立即登录", "忘记密码", "请输入验证码")
KEYWORDS = [
    # 2026-10-22 选品调研换池（数据/依据：research/reports/2026-10-22-选品报告.md，26词实测销量）
    # 季节窗口优先（感恩节 11/26、圣诞采购季 10-12 月，错过等一年）
    "custom thanksgiving napkins", "custom christmas napkins",
    "personalized christmas napkins", "personalized holiday napkins",
    "custom new years eve napkins",
    # 常青主力：首页 TOP5 销量 1412-2150，超过旧池王牌 custom wedding napkins(1923)
    "custom bachelorette party napkins", "custom disco napkins",
    "custom cowgirl napkins", "custom anniversary napkins",
    "custom baby shower napkins", "custom birthday napkins",
    "custom bridal shower napkins", "quinceanera napkins personalized",
    "rustic wedding napkins personalized",
    # 补充位：B2B / 低竞争小众
    "custom napkins bulk", "monogram napkins", "personalized baptism napkins",
    "custom graduation napkins",
]
# 12月上架位：custom valentines day napkins（TOP5=1629，情人节 2/14，12月再入池）
# 已排除：retirement(需求≈0)/engagement(375)/boho+sage green(成品印花为主，定制标0-1)
# 旧池(2026-10-18，已饱和)：custom/personalized/paper/logo/cocktail/wedding napkins
CELL_DX, CELL_DY = 146, -250   # 价格文本 → 卡片图片中心
NAPKIN_KW = ("napkin", "serviette", "餐巾", "纸巾")   # 详情页标题白名单（2026-10-18：混入泡泡机后加）


def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def shot(w, tag):
    return screenshot(w, f"rn-{tag}")


def text_of(png):
    return "".join(l.get("text", "") for l in ocr(png).get("lines", [])).replace(" ", "")


def detect_grid(png):
    """返回 [(cell_x, cell_y)]，按行排序。兼容中文页（美元）与英文页（$）。"""
    rows = []
    for l in ocr(png).get("lines", []):
        t = l.get("text", "").replace(" ", "")
        # 只认价格行：$/美元 开头数字；排除节省/save/each 等副行（会伪造出第二排格）
        tl = t.lower()
        if (("$" in t or "美元" in t) and l["x"] > 400 and l["w"] < 260
                and t.lstrip("$￥")[:1].isdigit()
                and not any(w in tl for w in ("节省", "零售", "save", "each", "piece"))):
            rows.append((l["x"], l["y"]))
    if not rows:
        return []
    rows.sort(key=lambda r: r[1])
    groups = []
    for (x, y) in rows:
        if groups and abs(y - groups[-1][-1][1]) <= 60:
            groups[-1].append((x, y))
        else:
            groups.append([(x, y)])
    cells = []
    for g in groups:
        if len(g) < 3:
            continue
        ym = sum(y for _, y in g) / len(g)
        cells.extend((x + CELL_DX, int(ym) + CELL_DY) for x, _ in g)
    return cells


def ensure_search(w, keyword):
    """确保当前窗口停在搜索结果页；否则用直达 URL 重搜。
    2026-10-18 改直达：首页 Dollar Express 弹窗的 X 会把页面导航进 BundleDeals
    促销落地页（"关弹窗"反而被劫持），且首页占位符/工具条会骗过 OCR 结果页判定。
    /wholesale?SearchText= 会自动重定向到真实结果页，无弹窗。"""
    ensure_ali_tab(w)                    # 绝不在妙手标签上导航
    url = uia_shell.current_url(w)
    png = shot(w, "ens")
    t = text_of(png)
    tl = t.lower()
    if ("wholesale" in url) and ("$" in t or "美元" in t) and ("napkin" in tl or "serviette" in tl):
        return True
    q = keyword.replace(" ", "+")
    uia_shell.navigate(w, f"https://www.aliexpress.us/wholesale?SearchText={q}")
    time.sleep(9)
    url = uia_shell.current_url(w)
    t = text_of(shot(w, "ens3"))
    ok = ("wholesale" in url) and ("$" in t or "美元" in t)
    log(f"  搜索「{keyword}」→ wholesale_url:{'wholesale' in url} 结果页:{ok}")
    return ok


def miaoshou_tab(w):
    """返回妙手标签元素（找不到= None）。妙手标签全程保留，绝不关闭。"""
    try:
        for t in uia_shell.tab_items(win=w):
            if MIAOSHOU_MARK in (t.window_text() or ""):
                return t
    except Exception:
        pass
    return None


def ensure_miaoshou_tab(w):
    """确保妙手标签存在且已登录（2026-10-18 用户要求：采集必须登录妙手，标签不许关）。
    掉登录时自动跑 miaoshou_login.py（含验证码 OCR 重试）。"""
    if miaoshou_tab(w) is None:
        log("  妙手标签缺失 → 新开并登录采集箱")
        type_keys("^t")
        time.sleep(1.2)
        uia_shell.navigate(w, ERP_URL)
        time.sleep(10)
    else:
        return True                      # 标签在 = 会话在（cookie 持久），不额外折腾
    # 新开/复开后核验登录态
    png = shot(w, "ms-login")
    t = text_of(png)
    if any(m in t for m in LOGGED_MARKS):
        log("  ✓ 妙手已登录，标签保留")
        return True
    if any(m in t for m in LOGIN_MARKS):
        log("  ⚠ 妙手掉登录 → 自动登录…")
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(BASE, "miaoshou_login.py"), "--chrome"],
                           capture_output=True, text=True, encoding="utf-8", errors="ignore")
        tail = (r.stdout or "").strip().splitlines()[-3:]
        log("  login >> " + " | ".join(tail))
        return r.returncode == 0
    log("  ⚠ 妙手页面状态不明，继续采集（插件登录态独立于网页会话）")
    return True


def ensure_ali_tab(w):
    """把激活标签切到非妙手标签；没有就新开。保证导航永不落在妙手标签上。"""
    try:
        items = uia_shell.tab_items(win=w)
    except Exception:
        return False
    for t in items:
        if MIAOSHOU_MARK in (t.window_text() or ""):
            continue
        try:
            t.select()
            time.sleep(1.0)
            return True
        except Exception:
            continue
    type_keys("^t")
    time.sleep(1.2)
    return True


def handle_captcha(w):
    """返回 True=处理后可继续，False=需人工停止。"""
    t = text_of(shot(w, "cap"))
    if "访问此设备" in t or ("想要" in t and "允许" in t):   # 浏览器权限弹框（COMError 元凶）
        log("  ⚠ 浏览器权限弹框，ESC 消除…")
        type_keys("{ESC}")
        time.sleep(1.5)
        t = text_of(shot(w, "cap2"))
    if ("滑动即可完成拼图" in t) or ("安全验证" in t and "拖动" not in t and "朝向" not in t):
        log("  ⚠ 滑块验证，自动求解…")
        import temu_captcha_slide
        ok = temu_captcha_slide.main()
        time.sleep(2)
        return ok == 0
    if "安全验证" in t or "朝向" in t or "拖动" in t:
        log("  ✗ 出现拖拽/旋转类验证，需人工处理后重跑")
        return False
    return True


def scroll(w, notches=13):
    ls = _load_last_shot()
    _send_move_abs(ls["left"] + 1290, ls["top"] + 800)
    time.sleep(0.3)
    import ctypes

    class _MI(ctypes.Structure):
        _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                    ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_void_p)]

    class _U(ctypes.Union):
        _fields_ = [("mi", _MI)]

    class _INP(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", ctypes.c_ulong), ("u", _U)]
    for _ in range(notches):
        inp = _INP(type=0)
        inp.mi = _MI(0, 0, 4294967176, 0x0800, 0, None)
        ctypes.windll.user32.SendInput(1, (_INP * 1)(inp), ctypes.sizeof(_INP))
        time.sleep(0.09)
    time.sleep(3)


def close_extra_tabs(w):
    """关闭多余 AliExpress 标签，只留激活的那个 + 非 AliExpress 标签。"""
    items = uia_shell.tab_items(win=w)
    ali = [t for t in items if "AliExpress" in (t.window_text() or "")]
    if len(ali) <= 1:
        return
    for t in ali:
        if t.window_text() and not t.is_selected():
            t.select()
            time.sleep(0.7)
            type_keys("^w")
            time.sleep(1.0)
            items = uia_shell.tab_items(win=w)
            ali = [x for x in items if "AliExpress" in (x.window_text() or "")]
            if len(ali) <= 1:
                return


def collect_cell(w, cx, cy, idx):
    ls = _load_last_shot()
    tabs_before = len(uia_shell.tab_items(win=w))
    human_click(ls["left"] + cx, ls["top"] + cy, activate_window=w)
    time.sleep(7)
    if not handle_captcha(w):
        return "captcha_stop"
    tabs_after = len(uia_shell.tab_items(win=w))
    if tabs_after > tabs_before:          # 详情开了新标签（可能在后台）
        items = uia_shell.tab_items(win=w)
        ali = [t for t in items if "AliExpress" in (t.window_text() or "")]
        if ali:
            ali[-1].select()
            time.sleep(1.2)
    png = shot(w, f"d{idx}")
    t = text_of(png)
    if "全选" in t and "采集" in t:
        log(f"  #{idx} 点击未进详情，跳过")
        return "miss"
    if not title_is_napkin(png):        # 标题不含餐巾词 = 点错商品/被促销弹层劫持，绝不点采集
        log(f"  #{idx} 标题非餐巾，跳过")
        if tabs_after > tabs_before:
            type_keys("^w")
            time.sleep(1.4)
        else:
            alt_left()                   # 同标签被劫持（BundleDeals 弹层）→ 返回列表
            time.sleep(2.5)
        return "miss"
    btn = teal_button(png)
    if not btn:
        log(f"  #{idx} 详情无采集按钮，跳过")
        if tabs_after > tabs_before:
            type_keys("^w")
            time.sleep(1.4)
        else:
            alt_left()                   # 店铺页/异常页同标签劫持 → 返回列表
            time.sleep(2.5)
        return "miss"
    human_click(ls["left"] + btn[0], ls["top"] + btn[1], activate_window=w)
    time.sleep(5)
    if tabs_after > tabs_before:
        type_keys("^w")
        time.sleep(1.5)
    return "ok"


def title_is_napkin(png):
    """详情页标题区（y200-520）OCR 须含餐巾词。
    只看标题区：整页 OCR 会被推荐位的餐巾词污染（泡泡机页面下方就推餐巾）。"""
    img = cv2.imread(png)
    if img is None:
        return False
    crop = img[200:520, 540:2450]
    p = png.replace(".png", "-title.png")
    cv2.imwrite(p, crop)
    t = "".join(l.get("text", "") for l in ocr(p).get("lines", [])).replace(" ", "").lower()
    return any(k in t for k in NAPKIN_KW)


def teal_button(png):
    img = cv2.imread(png)
    strip = img[1470:1525, 1000:1350]
    hsv = cv2.cvtColor(strip, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    mask = (h > 75) & (h < 95) & (s > 90) & (v > 150)
    col = mask.sum(axis=0)
    runs = []
    x = 0
    while x < len(col):
        if col[x] > 20:
            s0 = x
            while x < len(col) and col[x] > 20:
                x += 1
            runs.append((1000 + s0, 1000 + x))
        else:
            x += 1
    if not runs:
        return None
    r = max(runs, key=lambda t: t[1] - t[0])
    return ((r[0] + r[1]) // 2, 1499) if r[1] - r[0] >= 60 else None


def main():
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    done = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    w = winutil.chrome_window()
    if not w:
        log("✗ 无 Chrome 窗口")
        return 1
    w.set_focus()
    time.sleep(0.5)
    ki = KEYWORDS.index("wedding napkins") if "wedding napkins" in KEYWORDS else 0
    screen = 0
    seen_sigs = set()
    miss_streak = 0          # 连续 miss 熔断：页面被劫持/坐标失效时强制重搜
    log(f"=== 开跑 目标={target} 已完成={done} ===")
    ensure_miaoshou_tab(w)   # 采集前置：妙手标签在 + 已登录（用户要求，标签全程保留）
    while done < target:
        screen += 1
        if miaoshou_tab(w) is None:      # 妙手标签被意外关闭 → 立即重建
            log("  ⚠ 妙手标签消失 → 重建")
            ensure_miaoshou_tab(w)
        if not ensure_search(w, KEYWORDS[ki]):
            ki = (ki + 1) % len(KEYWORDS)
            continue
        png = shot(w, f"s{screen}")
        cells = detect_grid(png)
        if not cells:
            log(f"  屏{screen} 无网格行 → 换词")
            ki = (ki + 1) % len(KEYWORDS)
            scroll(w, 26)
            continue
        sig = tuple(cells)
        if sig in seen_sigs:
            log(f"  屏{screen} 网格未变化（可能触底）→ 换词 + 回顶")
            ki = (ki + 1) % len(KEYWORDS)
            uia_shell.navigate(w, "https://www.aliexpress.us/?gatewayAdapt=glo2usa")
            time.sleep(6)
            continue
        seen_sigs.add(sig)
        log(f"  屏{screen} 检出 {len(cells)} 格，关键词={KEYWORDS[ki]}")
        for (cx, cy) in cells:
            if done >= target:
                break
            if miss_streak >= 4:        # 连续 4 格全 miss = 页面/坐标已不可信
                log("  连续 miss≥4 → 放弃本屏，强制重搜")
                miss_streak = 0
                break
            try:
                r = collect_cell(w, cx, cy, done + 1)
            except Exception as e:      # COMError/窗口句柄失效 → 重取窗口继续，不崩整轮
                log(f"  #{done + 1} 异常 {type(e).__name__}，重取窗口后继续")
                w = winutil.chrome_window()
                if not w:
                    log("✗ Chrome 窗口丢失，停止")
                    return 1
                w.set_focus()
                time.sleep(2)
                continue
            if r == "captcha_stop":
                return 3
            if r == "ok":
                done += 1
                miss_streak = 0
                if done % 10 == 0:
                    log(f"  —— 累计 {done}/{target} ——")
            elif r == "miss":
                miss_streak += 1
        close_extra_tabs(w)
        scroll(w, 13)
    log(f"=== 完成 {done}/{target} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
