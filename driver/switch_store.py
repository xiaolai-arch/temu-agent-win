"""TEMU 店铺切换（账号切换式）— 确定性脚本版，流程来自 2026-10-12/13 发现会话实测。

用法：python switch_store.py <store-id>          # 切店 + 定制商品页双按钮验证
      python switch_store.py <store-id> --check  # 只检查当前在哪店（不登录）
      python switch_store.py --doctor            # 环境自检（OCR/窗口/凭据，不登录）
      python switch_store.py --verify-all        # 所有配置店铺轮回切换实测（加新店后跑这个）

凭据：D:\\temu-agent\\local.config.json 的 accounts.<id>（手机号+密码，绝不打印）。

流程（每步 OCR 实时定位，坐标漂移免疫）：
  1. 确保窗口（无则普通参数拉起）→ 导航干净 /login（已登录也直接出登录页）
  2. 「手机号登录」tab → 「密码登录」子模式（如需要）
  3. 手机号框 ^a 重打 → 点手机号框→Tab→^a→输密码（Tab 法，密码框无法坐标点击）
  4. 点「登录」→ 处理「同意并登录」确认弹层（布局左移，按钮在左侧）
  5. seller 落地 site-main → Agent Center 联动（导航 customize-goods 验证账号+双按钮）
  6. 不联动时的补救（2026-10-13 定稿）：seller 主页 → 侧边栏 商品管理 → 定制商品内容
     → 授权卡（勾协议→确认授权并前往→「确认切换」）→ 定制商品内容页

退出码：0=成功 1=环境/页面异常 2=需要人工（验证码/密码错）3=切换后验证失败
"""
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

import winutil
import uia_shell
from input import human_click, type_keys
from shot import screenshot, ocr
import report

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, ".."))
LOGIN_URL = "https://seller.kuajingmaihuo.com/login"
SELLER_MAIN_URL = "https://seller.kuajingmaihuo.com/site-main"
TARGET_URL = "https://agentseller.temu.com/main/customize-goods"

ACCOUNT_NAME = {"main": "hpoiZee", "store-b": "boliooZ"}  # 首登后自动学习补写
FALLBACK_LOGIN_BTN = (1876, 859)  # 布局漂移兜底（正常布局实测）
CAPTCHA_WORDS = ["验证码", "滑块", "拖动", "下方", "拼图"]
AUTHFAIL_WORDS = ["密码错误", "不正确", "账号或密码", "失败"]


def _load_names():
    """从 local.config.json accounts.<id>.name 加载已学习的店名（不打印任何凭据）。"""
    global ACCOUNT_NAME
    try:
        d = json.load(open(os.path.join(ROOT, "local.config.json"), encoding="utf-8"))
        for sid, acc in d.get("accounts", {}).items():
            if isinstance(acc, dict) and acc.get("name"):
                ACCOUNT_NAME[sid] = str(acc["name"])
    except Exception:
        pass


def _learn_name(store_id, name):
    """首登成功后把店名写回 local.config.json（下次运行即可严格校验）。"""
    if not name:
        return
    p = os.path.join(ROOT, "local.config.json")
    try:
        d = json.load(open(p, encoding="utf-8"))
        if store_id in d.get("accounts", {}) and d["accounts"][store_id].get("name") != name:
            d["accounts"][store_id]["name"] = name
            json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        ACCOUNT_NAME[store_id] = name
        log(f"→ 已学习店名 {store_id}={name}（写入配置，下次严格校验）")
    except Exception as e:
        log(f"⚠ 店名写入失败: {type(e).__name__}")


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def creds(store_id):
    d = json.load(open(os.path.join(ROOT, "local.config.json"), encoding="utf-8"))
    acc = d["accounts"].get(store_id)
    if not acc:
        raise SystemExit(f"local.config.json 无 {store_id} 凭据")
    return str(acc["phone"]), str(acc["password"])


def shot(w, tag):
    return screenshot(w, f"sw-{tag}")


def ocr_lines(path):
    for i in range(3):
        try:
            return ocr(path)["lines"]
        except Exception:
            time.sleep(1.5)
    return []


def find(lines, kw, exact=False, xmin=800):
    """OCR 行找关键词（kw 可为 str 或 list，任一命中即可），返回屏幕点击坐标（窗口相对）。
    xmin=800：排除登录页左侧营销文案。子串匹配对 OCR 截断（如「手机号登」）免疫。"""
    kws = kw if isinstance(kw, list) else [kw]
    for l in lines:
        t = l["text"].replace(" ", "")
        if l["x"] < xmin:
            continue
        for k in kws:
            k = k.replace(" ", "")
            if (t == k if exact else k in t):
                return (l["x"] + l["w"] // 2, l["y"] + l["h"] // 2)
    return None


def click(w, pos):
    r = w.rectangle()
    human_click(r.left + pos[0], r.top + pos[1], activate_window=w)


def wait_window():
    w = winutil.default_window()
    if not w:
        log("无窗口，普通参数拉起 Edge…")
        w = winutil.launch_edge(LOGIN_URL)
    w.set_focus()
    time.sleep(0.5)
    # 根治布局漂移：还原→移到主屏→最大化（直接对最大化窗口 SetWindowPos 会被 Snap 管理
    # 吞掉；副屏最大化只有 2392x1048，登录页会自适应成第三种布局，坐标全漂）
    import ctypes
    user32 = ctypes.windll.user32
    user32.ShowWindow(w.handle, 9)            # SW_RESTORE
    time.sleep(0.5)
    user32.SetWindowPos(w.handle, 0, 0, 0, 2560, 1400, 0x0040)  # SWP_SHOWWINDOW，移到主屏
    time.sleep(0.6)
    user32.ShowWindow(w.handle, 3)            # SW_MAXIMIZE
    time.sleep(1.0)
    r = w.rectangle()
    log(f"窗口 rect=({r.left},{r.top},{r.right - r.left}x{r.bottom - r.top})")
    if r.right - r.left < 2500:
        log("⚠ 主屏最大化未生效，坐标体系可能与验证布局有偏差")
    return w


def ensure_phone_pwd_mode(w):
    """确保处于 手机号+密码 模式。返回 True/False。"""
    lines = ocr_lines(shot(w, "mode"))
    if find(lines, ["密码登录", "密码登"], exact=True):
        log("→ 验证码模式，切「密码登录」子模式")
        click(w, find(lines, ["密码登录", "密码登"], exact=True))
        time.sleep(1.2)
        lines = ocr_lines(shot(w, "mode2"))
    has_phone_tab = find(lines, ["手机号登录", "手机号登"], exact=True)
    if has_phone_tab and not find(lines, "+86"):
        log("→ 点「手机号登录」tab")
        click(w, has_phone_tab)
        time.sleep(1.2)
        lines = ocr_lines(shot(w, "mode3"))
    return bool(find(lines, "+86"))


def detect_block(lines):
    """验证码 / 账密错误检测（红线：验证码绝不自动碰）。"""
    text = " ".join(l["text"].replace(" ", "") for l in lines)
    if any(k in text for k in CAPTCHA_WORDS) and "无法收到验证码" not in text:
        # 「无法收到验证码」是登录页固有链接，排除；真验证码会有其它特征词
        for k in ["滑块", "拖动", "拼图"]:
            if k in text:
                return "captcha"
        if "请输入验证码" in text or "发送验证码" in text:
            return "captcha"
    if any(k in text for k in AUTHFAIL_WORDS):
        return "authfail"
    return None


def agent_account(lines):
    """定制商品页右上角账号名（小字 OCR 易漏，支持右上角区域拉丁词兜底）。"""
    text = " ".join(l["text"] for l in lines)
    for name in ["hpoiZee", "bolioo"]:
        if name in text:
            return name
    import re
    for l in lines:  # 右上角区域的拉丁词（账号名如 hpoiZee/boliooZ）
        if l["x"] > 2150 and l["y"] < 260:
            m = re.search(r"[a-z][A-Za-z0-9]{4,}", l["text"])
            if m and m.group(0).lower() not in ("seller", "temu", "beta"):
                return m.group(0)
    return None


def sync_buttons(lines):
    """双同步按钮存在性 + 坐标。"""
    b1 = next((l for l in lines if "按勾选" in l["text"].replace(" ", "")), None)
    b2 = next((l for l in lines if "忆托ERP" in l["text"].replace(" ", "")), None)
    return b1, b2


def _dismiss_save_pwd(w, lines):
    """Edge「保存密码？」气泡（登录成功后弹出，盖住页面右侧干扰 OCR/点击）：
    点「以后再说」关掉。不保存、不改任何浏览器设置。返回 True 若关掉了。"""
    if not find_line(lines, ["保存密码", "更新密码"]):
        return False
    btn = find_line(lines, ["以后再说", "一律拒绝", "不保存"])
    if btn:
        log("→ 关闭 Edge「保存密码」气泡")
        click(w, (btn["x"] + btn["w"] // 2, btn["y"] + btn["h"] // 2))
        time.sleep(1)
        return True
    log("⚠ 保存密码气泡在但没找到关闭按钮")
    return False


def do_login(w, phone, password):
    """登录流程主体。返回 None(成功) / 'captcha' / 'authfail' / 'failpage'。"""
    # 1) 模式
    if not ensure_phone_pwd_mode(w):
        return "failpage"
    # 2) 手机号
    lines = ocr_lines(shot(w, "form"))
    box = find(lines, "+86") or find(lines, ["手机号登录", "手机号登"], exact=True) or (1877, 631)
    click(w, (box[0] + (135 if find(lines, "+86") else 0), box[1]))
    time.sleep(0.3)
    type_keys("^a")
    type_keys(phone, pause=0.03)
    time.sleep(0.3)
    # 3) 密码（Tab 法：点手机号框→Tab 焦点进密码框）
    type_keys("{TAB}")
    time.sleep(0.2)
    type_keys("^a")
    type_keys(password, pause=0.05)
    time.sleep(0.4)
    # 4) 登录按钮
    lines = ocr_lines(shot(w, "btn"))
    pos = find(lines, ["登录", "登 录"], exact=True) or FALLBACK_LOGIN_BTN
    click(w, pos)
    time.sleep(3)
    # 5) 「同意并登录」弹层
    lines = ocr_lines(shot(w, "consent"))
    c = find(lines, "同意并登录", exact=True, xmin=1200)
    if c:
        log("→ 处理「同意并登录」确认层")
        click(w, c)
    time.sleep(8)
    # 6) 结果判定（先关掉「保存密码」气泡再截图判定）
    lines = ocr_lines(shot(w, "result"))
    if _dismiss_save_pwd(w, lines):
        time.sleep(1)
        lines = ocr_lines(shot(w, "result2"))
    blocked = detect_block(lines)
    if blocked:
        return blocked
    url = next((l["text"].replace(" ", "") for l in lines if "http" in l["text"].lower()), "")
    if "/login" in url and "redirectUrl" not in url:
        return "failpage"
    return None


def check_target(w, navigate=True):
    """验证定制商品页。正常链路优先：切「定制商品内容」标签 → F5 刷新
    （标签可能是上一店的旧标签，刷新后按当前授权重载）；无标签才导航 URL 兜底。
    右上角账号名漏读时裁剪放大重读两轮。"""
    try:
        uia_shell.switch_tab(w, "定制商品")
        time.sleep(1)
        from input import type_keys as _tk
        w.set_focus()
        _tk("{F5}")
        time.sleep(6)
    except RuntimeError:
        if navigate:
            uia_shell.navigate(w, TARGET_URL)
            time.sleep(6)
    path = shot(w, "target")
    lines = ocr_lines(path)
    _dismiss_save_pwd(w, lines)  # 气泡可能盖住按钮/账号区
    acc = agent_account(lines)
    if acc is None and (sync_buttons(lines)[0] or sync_buttons(lines)[1]):
        from PIL import Image
        for _ in range(2):
            img = Image.open(path)
            crop = img.crop((2150, 110, 2582, 250))
            crop = crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS)
            zp = path.replace(".png", "_acc.png")
            crop.save(zp)
            acc = agent_account(ocr(zp)["lines"])
            if acc:
                break
            time.sleep(2)
            path = shot(w, "target2")
            lines = ocr_lines(path)
            acc = agent_account(lines)
    return acc, sync_buttons(lines), lines


def wait_customize_tab(w, timeout=30, tabs_before=None, allow_any=False):
    """正常链路通过后，系统会自动开「定制商品内容」标签——等它出现并切换。
    （2026-10-13 用户指点的正确逻辑：不直接输 URL，跟随点击流进主页/开标签。）
    成功判定（2026-10-14 修复）：allow_any=True（本轮真点过授权卡/确认切换/侧边栏
    入口）时，新旧定制标签都算数（授权后旧标签会按新授权重载）；否则必须是
    **新出现**的标签——上一店遗留的旧标签绝不能当成功（06:56 误判事故根因）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            tabs_now = uia_shell.tabs(w)
            fresh = [t for t in tabs_now if "定制商品" in (t or "") and
                     (tabs_before is None or allow_any or t not in tabs_before)]
            if fresh:
                uia_shell.switch_tab(w, "定制商品")
                return True
        except RuntimeError:
            pass
        except Exception:
            pass
        time.sleep(2)
    return False


def find_line(lines, kw, xmin=0):
    """返回 OCR 行对象（含 x/y/w/h），找不到返回 None。弹窗文字用 xmin=0。"""
    kws = kw if isinstance(kw, list) else [kw]
    for l in lines:
        t = l["text"].replace(" ", "")
        if l["x"] < xmin:
            continue
        for k in kws:
            if k.replace(" ", "") in t:
                return l
    return None


def find_line_fuzzy(lines, kw, xmin=0, ratio=0.8):
    """find_line 的 OCR 容错版：子串不中时按相似度兜底
    （实测「商品管理」会被误读成「商管理」，掉一个字整条联动链路就断）。"""
    hit = find_line(lines, kw, xmin=xmin)
    if hit:
        return hit
    from difflib import SequenceMatcher
    kws = kw if isinstance(kw, list) else [kw]
    best, best_r = None, 0.0
    for l in lines:
        if l["x"] < xmin:
            continue
        t = l["text"].replace(" ", "")
        for k in kws:
            r = SequenceMatcher(None, k.replace(" ", ""), t).ratio()
            if r > best_r:
                best, best_r = l, r
    return best if best_r >= ratio else None


def _has_captcha(lines):
    text = " ".join(l["text"].replace(" ", "") for l in lines)
    return any(k in text for k in ["滑块", "拼图", "请向右滑"])


def _click_blue_left_of(w, ref_line):
    """点 ref_line（如「不切换」）左侧的蓝色实心按钮（白字蓝底 OCR 读不出文字，
    用像素级蓝色块检测）。2026-10-13 实测：确认切换按钮在「不切换」左侧 ~150px。"""
    from PIL import Image
    path = shot(w, "bluebtn")
    img = Image.open(path).convert("RGB")
    px = img.load()
    y0, y1 = max(0, ref_line["y"] - 45), ref_line["y"] + ref_line["h"] + 45
    x1 = ref_line["x"] - 5
    cols = {}
    for x in range(700, x1, 3):
        cnt = sum(1 for y in range(y0, y1, 3)
                  if px[x, y][2] > 170 and px[x, y][2] - px[x, y][0] > 60 and px[x, y][2] - px[x, y][1] > 30)
        if cnt >= 5:
            cols[x] = cnt
    blocks, xs = [], sorted(cols)
    if xs:
        cur = [xs[0], xs[0]]
        for x in xs[1:]:
            if x - cur[1] <= 6:
                cur[1] = x
            else:
                blocks.append(tuple(cur))
                cur = [x, x]
        blocks.append(tuple(cur))
    cands = [b for b in blocks if 60 <= b[1] - b[0] <= 420]
    if not cands:
        return False
    b = max(cands, key=lambda t: t[1])  # 离「不切换」最近的块
    cx, cy = (b[0] + b[1]) // 2, ref_line["y"] + ref_line["h"] // 2
    log(f"→ 蓝色按钮像素定位 x{b[0]}-{b[1]} → 点击 ({cx},{cy})")
    click(w, (cx, cy))
    return True


def _seller_name(lines):
    """seller 主页右上角的当前卖家账号名（大字，OCR 稳定可读；比授权卡标题可靠）。"""
    import re
    for l in lines:
        if l["x"] > 2200 and 100 < l["y"] < 250:
            m = re.search(r"[A-Za-z][A-Za-z0-9]{4,}", l["text"])
            if m and m.group(0).lower() not in ("seller", "temu", "beta"):
                return m.group(0)
    return None


def _norm_name(s):
    """账号名 OCR 归一化：№→li（boliooZ 常被读成 bo№oZ）、I/1→l、0→o，去非字母数字。"""
    import re
    t = s.replace("№", "li").replace("I", "l").replace("1", "l").replace("0", "o")
    return re.sub(r"[^a-z]", "", t.lower())


def _name_eq(a, b):
    if not a or not b:
        return False
    na, nb = _norm_name(a), _norm_name(b)
    if na == nb:
        return True
    import difflib
    return difflib.SequenceMatcher(None, na, nb).ratio() >= 0.8


def _store_name_from(lines):
    """从授权卡/确认切换弹窗的 OCR 里抓目标店名（兜底，主源是 seller 主页头部）。
    OCR 会把「」读成 f/J 等，正则容忍各种括号字形。"""
    import re
    text = "".join(l["text"].replace(" ", "") for l in lines)
    m = re.search(r"的[「fF\[\(\{]([A-Za-z0-9№lI]{2,12})[」jJ\]\)\}]店", text)
    if m:
        return m.group(1)
    for i, l in enumerate(lines):
        if "即将切换为" in l["text"].replace(" ", ""):
            for l2 in lines[i + 1:]:
                m2 = re.search(r"[A-Za-z0-9№][A-Za-z0-9№lI]{4,}", l2["text"])
                if m2 and m2.group(0).lower() not in ("seller", "temu"):
                    return m2.group(0)
    return None


def _find_checkbox(w, policy_line):
    """授权卡协议勾选框像素定位：政策行上方的浅灰描边空心方框（10-26px 宽，
    上下边沿成对）。2026-10-14 教训：框相对文字行首的偏移会漂（-28px 经验值在
    store-b 卡上点在框外 19px，勾选失败 → 按钮点了没反应）。找不到返回 None
    （调用方回退 -28px 老经验值——10-13 与 07:21 两张卡实测该值有效）。"""
    from PIL import Image
    path = shot(w, "cbx")
    img = Image.open(path).convert("RGB")
    px = img.load()
    ty = policy_line["y"] + policy_line["h"] // 2
    tx = policy_line["x"]

    def edge(x, y):
        v = (px[x, y][0] + px[x, y][1] + px[x, y][2]) // 3
        return 195 < v < 247  # 浅灰描边（219-233 实测）；白底 251+，正文/遮罩更深

    runs = []
    x = max(760, tx - 110)
    while x < tx + 30:
        if edge(x, ty - 11):
            xa = x
            while x < tx + 30 and edge(x, ty - 11):
                x += 1
            runs.append((xa, x - 1))
        else:
            x += 1
    for xa, xb in runs:
        width = xb - xa + 1
        if not (10 <= width <= 26):
            continue
        bot = sum(1 for xx in range(xa, xb + 1) if edge(xx, ty + 6))
        if bot >= max(5, width - 4):
            return ((xa + xb) // 2, ty - 2)
    return None


def link_agent_center(w):
    """Agent Center 联动/重授权（2026-10-13 用户流程实测定稿，全程程序可操作）：
    seller 主页 → 侧边栏「商品管理」展开 →「定制商品内容」→ 页面弹授权卡
    「即将前往 SellerCentral（全球）的「X」店铺」（勾协议 →「确认授权并前往」）
    →（Agent Center 挂着别店时）「确认切换」弹窗 → 定制商品内容页打开。
    坐标全部 OCR 实时定位；「不切换」绝不点。
    返回 (状态, 店名)：状态 'ok'/'captcha'/'fail'；店名从授权卡/切换弹窗抓取
    （右上角账号名小字 OCR 常漏读，以链路上读到的名字为兜底真值）。
    成功判定（2026-10-14 修复）：必须「执行过授权动作」或「出现了新的定制商品标签」——
    上一店留下的旧标签绝不算成功（否则误判后 F5 仍是旧店，白跑一次登录）。
    （旧 settle/seller-login 表单路径已废弃：其提交按钮对合成输入免疫，2026-10-13 实测。）"""
    log("→ Agent Center 联动链路：seller 主页 → 商品管理 → 定制商品内容")
    try:
        tabs_before = set(uia_shell.tabs(w))
        n_before = len(uia_shell.tab_items(w))
    except Exception:
        tabs_before, n_before = set(), 1
    uia_shell.navigate(w, SELLER_MAIN_URL)
    time.sleep(6)
    consent_done = False
    acted = False  # 本轮链路是否真的点了授权卡/确认切换（成功判定的必要条件之一）
    entered = False  # 点过侧边栏「定制商品内容」（Agent Center 已授权时直达，无授权卡）
    dialog_done = False  # 「确认切换」弹窗已处理
    auth_clicks = 0
    store_name = None
    gm_clicks = 0
    esc_tries = 0
    for i in range(10):
        # ⓪ 新后台标签检查：「确认切换」弹窗常开在授权后新开的标签里（2026-10-14
        #    main 实测：对着 seller 页连点授权卡毫无用处，弹窗其实在后台等人确认）
        if acted and not dialog_done:
            try:
                n_now = len(uia_shell.tab_items(w))
            except Exception:
                n_now = n_before
            if n_now > n_before:
                log(f"→ 出现新标签（{n_before}→{n_now}），切过去找「确认切换」弹窗")
                uia_shell.switch_tab_index(w, -1)
                time.sleep(2)
                lines2 = ocr_lines(shot(w, f"sw{i}"))
                sw_line = find_line(lines2, "不切换")
                if sw_line and find_line(lines2, "确认切换"):
                    log("→ 后台标签里的「确认切换」弹窗，像素定位蓝色确认按钮")
                    if _click_blue_left_of(w, sw_line):
                        dialog_done = True
                    time.sleep(8)
                    continue
                uia_shell.switch_tab_index(w, 0)  # 不是弹窗 → 回 seller 页继续
                time.sleep(1.5)
        lines = ocr_lines(shot(w, f"link{i}"))
        if _dismiss_save_pwd(w, lines):
            time.sleep(1)
            continue  # 关掉气泡后重新观察
        if _has_captcha(lines):
            log("✋ 出现滑块验证码（红线：不自动处理）")
            return "captcha", store_name
        # 消息面板下拉会遮挡右上角 → 尝试 Esc 关闭。注意（2026-10-14 教训）：
        # ① 面板对 Esc 可能无反应，所以最多按 2 次就放弃；
        # ② 绝不因它 continue——侧边栏在左侧不被遮挡，链路必须继续走，
        #    否则 8 轮循环全耗在按 Esc 上，商品管理永远点不到（07:13 事故根因）。
        if esc_tries < 2 and find_line(lines, ["全部消息", "标记为已读"]):
            log("→ 消息面板开着，按 Esc 尝试关闭（不阻塞链路）")
            w.set_focus()
            type_keys("{ESC}")
            esc_tries += 1
            time.sleep(1.0)
        if store_name is None:
            nm = _seller_name(lines) or _store_name_from(lines)
            if nm:
                store_name = nm
                log(f"→ 链路读到目标店名: {store_name}")
        # ① 「确认切换」弹窗（出现在当前页时）：按钮是白字蓝底（OCR 只能读到标题
        #    「…确认切换吗」和深色的「不切换」）→ 用「不切换」行定位，点其左侧蓝色
        #    按钮。绝不点「不切换」。
        if find_line(lines, "确认切换") and find_line(lines, "不切换"):
            log("→ 「确认切换」弹窗，像素定位蓝色确认按钮")
            if not _click_blue_left_of(w, find_line(lines, "不切换")):
                log("⚠ 未定位到确认切换按钮")
            acted = True
            dialog_done = True
            time.sleep(8)
            continue
        # ② 授权卡（勾协议 → 确认授权并前往）。最多点 2 次：点过后弹窗/新标签需要
        #    时间出现，连点只会开一堆后台标签（2026-10-14 main 实测连点 ×6 无效）
        btn = find_line(lines, "确认授权并前往")
        if btn and auth_clicks < 2:
            cb = find_line(lines, ["板块共享", "已阅读并同意"])
            if cb and not consent_done:
                pos = _find_checkbox(w, cb) or (cb["x"] - 28, cb["y"] + cb["h"] // 2)
                log(f"→ 勾选授权协议（框像素定位 {pos}）")
                click(w, pos)
                consent_done = True
                time.sleep(2)
            log("→ 点「确认授权并前往」")
            click(w, (btn["x"] + btn["w"] // 2, btn["y"] + btn["h"] // 2))
            acted = True
            auth_clicks += 1
            time.sleep(8)
            continue
        # ③ 侧边栏「定制商品内容」入口（fuzzy：OCR 常掉字，如「定制商品内空」）
        side = find_line_fuzzy(lines, "定制商品内容")
        if side and side["x"] < 300:
            log("→ 侧边栏点「定制商品内容」")
            click(w, (side["x"] + 70, side["y"] + side["h"] // 2))
            entered = True
            time.sleep(5)
            continue
        # ④ 侧边栏「商品管理」未展开 → 先展开（最多 2 次，防后台开标签后死循环点）
        #    fuzzy：实测 OCR 把「商品管理」读成「商管理」，硬匹配整条链路就断在这
        gm = find_line_fuzzy(lines, "商品管理")
        if gm and gm["x"] < 300 and gm_clicks < 2:
            log("→ 侧边栏点「商品管理」展开")
            click(w, (gm["x"] + 45, gm["y"] + gm["h"] // 2))
            gm_clicks += 1
            time.sleep(2)
            continue
        break  # 无可操作元素 → 等定制商品标签
    # 兜底：全标签扫一遍「确认切换」（双击开的多个新标签里可能还藏着弹窗）
    if acted and not dialog_done:
        try:
            items = uia_shell.tab_items(w)
        except Exception:
            items = []
        for idx in range(len(items) - 1, -1, -1):
            try:
                uia_shell.switch_tab_index(w, idx)
            except Exception:
                continue
            time.sleep(1.2)
            lines2 = ocr_lines(shot(w, f"sweep{idx}"))
            sw_line = find_line(lines2, "不切换")
            if sw_line and find_line(lines2, "确认切换"):
                log(f"→ 标签[{idx}] 有「确认切换」弹窗，确认")
                _click_blue_left_of(w, sw_line)
                dialog_done = True
                time.sleep(8)
                break
    if wait_customize_tab(w, timeout=30, tabs_before=tabs_before,
                          allow_any=(acted or entered)):
        log("→ 「定制商品内容」标签已打开，切换验证")
        _close_extra_tabs(w, n_before)
        return "ok", store_name
    if not acted and not entered:
        log("→ 联动链路未执行任何授权动作（侧边栏定位失败？），判失败")
    else:
        log("→ 未等到定制商品标签")
    return "fail", store_name


def _close_extra_tabs(w, n_before, rounds=6):
    """收掉本轮联动多开的重复「定制商品内容」标签（只留一个）。
    只关标题完全重复的定制页——绝不碰 seller 页和唯一的那张定制页。"""
    from input import type_keys as _tk
    for _ in range(rounds):
        try:
            items = uia_shell.tab_items(w)
        except Exception:
            return
        titles = [t.window_text() or "" for t in items]
        if len(items) <= n_before or len(titles) <= 1:
            return
        dup = None
        for idx in range(len(titles) - 1, -1, -1):
            if "定制商品" in titles[idx] and titles.count(titles[idx]) > 1:
                dup = idx
                break
        if dup is None:
            return
        log(f"→ 关掉多余的定制页标签[{dup}]")
        try:
            uia_shell.switch_tab_index(w, dup)
            time.sleep(0.8)
            w.set_focus()
            _tk("^w")
            time.sleep(1.2)
        except Exception:
            return


def check_only():
    w = wait_window()
    acc, (b1, b2), lines = check_target(w)
    print(f"当前 Agent Center 账号: {acc or '未识别'}")
    print(f"按勾选同步: {'✅' if b1 else '❌'}  忆托ERP同步: {'✅' if b2 else '❌'}")
    if acc is None and not (b1 or b2):
        print("(可能未登录或页面未加载)")
    return 0


def doctor():
    """环境自检（不登录、不点页面）：OCR 管线 / Edge 窗口 / 各店凭据与已学店名 /
    同步插件在位。加新店后先跑这个，全绿再切。"""
    print("== 环境自检 ==")
    problems = 0
    # 1) OCR 管线端到端（合成图片，不碰浏览器）
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (600, 120), "white")
        d = ImageDraw.Draw(img)
        d.text((20, 40), "TEST 151 OK", fill="black")
        p = os.path.join(os.environ.get("TEMP", "."), "sw-doctor.png")
        img.save(p)
        out = ocr(p)["lines"]
        text = " ".join(l["text"] for l in out)
        ok = "151" in text.replace(" ", "")
        print(f"OCR 管线: {'✅' if ok else '❌'}（读到: {text!r}）")
        if not ok:
            problems += 1
            print("  → 修复线索：driver/shot.py 需用 PowerShell 全路径 + 反斜杠 + UTF-8 解码")
    except Exception as e:
        problems += 1
        print(f"OCR 管线: ❌ {type(e).__name__}: {e}")
    # 2) Edge 窗口
    w = winutil.default_window()
    print(f"Edge 窗口: {'✅ hwnd=' + str(w.handle) if w else '⚠ 未找到（切店时会自动拉起）'}")
    # 3) 各店凭据
    try:
        d = json.load(open(os.path.join(ROOT, "local.config.json"), encoding="utf-8"))
        for sid, acc in d.get("accounts", {}).items():
            if not isinstance(acc, dict):
                continue
            has = bool(acc.get("phone")) and bool(acc.get("password"))
            nm = acc.get("name") or ACCOUNT_NAME.get(sid) or "（首登时自动学习）"
            print(f"店铺 {sid}: 凭据 {'✅' if has else '❌ 缺 phone/password'} · 店名 {nm}")
            if not has:
                problems += 1
    except Exception as e:
        problems += 1
        print(f"local.config.json: ❌ {type(e).__name__}: {e}")
    # 4) 同步插件在位（2026-10-14 事故：Edge 大版本更新把解压插件整批卸了，
    #    双按钮全消失 → 所有店验证必失败）。恢复：python driver/restore_extensions.py
    try:
        pref_dir = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default")
        blob = ""
        for fn in ("Preferences", "Secure Preferences"):
            try:
                blob += open(os.path.join(pref_dir, fn), encoding="utf-8").read()
            except OSError:
                pass
        need = [("佳同TEMU助手", "jiatong-temu"), ("忆托工具箱", "yishu-plugin"), ("妙手ERP", "miaoshou")]
        have = [label for label, key in need if key in blob]
        missing = [label for label, key in need if key not in blob]
        if not missing:
            print("同步插件: ✅ 佳同/忆托/妙手 全部在位")
        else:
            problems += 1
            print(f"同步插件: ❌ 缺 {'/'.join(missing)} → 跑 python driver/restore_extensions.py 恢复")
    except Exception as e:
        print(f"同步插件: ⚠ 检查失败 {type(e).__name__}")
    print(f"== 自检结束：{'✅ 全部通过' if problems == 0 else f'❌ {problems} 项异常'} ==")
    return 0 if problems == 0 else 1


def verify_all():
    """全店轮回实测：按配置顺序切换到每一家并验证，输出矩阵报告。
    加新店后跑这个，全 ✅ 才算接入完成。"""
    d = json.load(open(os.path.join(ROOT, "local.config.json"), encoding="utf-8"))
    stores = list(d.get("accounts", {}).keys())
    log(f"== 全店轮回实测：{' → '.join(stores)} ==")
    results, times = [], []
    for sid in stores:
        t0 = time.time()
        rc = run_store(sid)
        dt = time.time() - t0
        results.append((sid, rc, dt))
        log(f"── {sid}: exit={rc}（{dt:.0f}s）")
        time.sleep(3)
    lines = [f"{sid}: {'✅ 成功' if rc == 0 else '❌ exit=' + str(rc)}（{dt:.0f}s）"
             for sid, rc, dt in results]
    ok = all(rc == 0 for _, rc, _ in results)
    lines.append("结论: " + ("所有店铺切换+验证全部通过 ✅" if ok else "存在失败店铺，见上 ❌"))
    report.write_report("store-verify-all", ok, lines)
    print("\n".join(lines))
    return 0 if ok else 3


def run_store(store_id):
    """切到指定店 + 双按钮验证。返回退出码（0 成功）。"""
    phone, password = creds(store_id)
    log(f"== 切换到 {store_id}（手机号 {phone[:3]}****{phone[-2:]}）==")
    t0 = time.time()

    w = wait_window()
    time.sleep(1)

    # 已经在目标店？直接验证（流畅度优化：免登录）
    acc, (b1, b2), _ = check_target(w)
    expected = ACCOUNT_NAME.get(store_id)
    if expected and _name_eq(acc, expected) and b1 and b2:
        log(f"已在目标店（{acc}，双按钮✅），免登录直达")
        report.write_report("store-switch", True,
                            [f"店铺: {store_id}（已在目标店，未重新登录）",
                             f"账号: {acc}", "双按钮: 按勾选同步✅ 忆托ERP同步✅",
                             "未执行任何同步点击"])
        print("OK already-on-target")
        return 0
    log(f"当前 Agent Center 账号: {acc or '未识别'} → 开始登录切换")

    # seller 登录
    uia_shell.navigate(w, LOGIN_URL)
    time.sleep(4)
    w.set_focus()
    rc = do_login(w, phone, password)
    if rc == "captcha":
        log("✋ 出现验证码（红线：不自动处理）")
        report.write_report("store-switch", False,
                            [f"店铺: {store_id}", "结果: 登录出现验证码，需人工",
                             "截图已存，请人工完成后重跑"])
        return 2
    if rc == "authfail":
        log("✋ 账号或密码错误")
        report.write_report("store-switch", False, [f"店铺: {store_id}", "结果: 账号或密码错误"])
        return 2
    if rc:
        log(f"✋ 登录未成功（{rc}），截图取证")
        report.write_report("store-switch", False, [f"店铺: {store_id}", f"结果: 登录异常({rc})"])
        return 1
    log(f"seller 登录成功（{time.time()-t0:.0f}s）")

    # Agent Center 验证 + 联动（按页面状态判断，不依赖已知账号名——新店首登时名字未知）
    acc, (b1, b2), lines = check_target(w)
    on_auth = find(lines, ["中国地区", "商家中心"], xmin=600) is not None and b1 is None
    # 未知店（expected=None）读到的是别家已知店名 → 同样必须联动，防跑错店
    known_others = {v for k, v in ACCOUNT_NAME.items() if k != store_id}
    need = on_auth or (expected is not None and not _name_eq(acc, expected)) \
        or (expected is None and any(_name_eq(acc, o) for o in known_others))
    linked_name = None
    if need:
        log(f"→ 需要联动（on_auth={on_auth}, acc={acc}, expected={expected}），走联动链路…")
        rc, linked_name = link_agent_center(w)
        if rc == "captcha":
            report.write_report("store-switch", False,
                                [f"店铺: {store_id}", "结果: 重授权出现滑块验证码，需人工滑一次",
                                 "人工在浏览器完成滑块后重跑本任务即可（红线：程序绝不碰验证码）"])
            return 2
        if rc == "fail":
            # 自动重试一次（2026-10-14：OCR 偶发掉字断链，重跑成功率实测高；
            # 第二次全新导航，页面状态常已不同）
            log("→ 联动失败，自动重试一次")
            rc, ln2 = link_agent_center(w)
            linked_name = linked_name or ln2
            if rc == "captcha":
                report.write_report("store-switch", False,
                                    [f"店铺: {store_id}", "结果: 重授权出现滑块验证码，需人工滑一次"])
                return 2
        time.sleep(2)
        acc, (b1, b2), lines = check_target(w)
        if acc is None and linked_name:
            acc = linked_name  # 右上角小字漏读 → 用授权链路上读到的店名
    if expected is not None and not _name_eq(acc, expected):
        report.write_report("store-switch", False,
                            [f"店铺: {store_id}",
                             f"结果: seller 已登录但 Agent Center 仍为 {acc or '未知'}（预期 {expected}）",
                             "请看截图核对页面状态；重跑一次本任务通常可恢复"])
        return 3

    ok = bool(b1 and b2)
    if not ok:
        report.write_report("store-switch", False,
                            [f"店铺: {store_id}", "结果: 双按钮未出现（页面状态异常，见截图）"])
        return 3
    if expected is None and store_id not in ACCOUNT_NAME:
        _learn_name(store_id, acc or linked_name)  # 首登学习店名（下次严格校验）
    lines = [
        f"店铺: {store_id}",
        f"账号: {acc or (expected or '新店（账号名已记录在截图）')}",
        f"双按钮: 按勾选同步{'✅' if b1 else '❌'} 忆托ERP同步{'✅' if b2 else '❌'}",
        f"耗时: {time.time()-t0:.0f}s",
        "未执行任何同步点击（只读验证）",
    ]
    report.write_report("store-switch", ok, lines)
    log(f"== 完成 ok={ok} 账号={acc} 耗时 {time.time()-t0:.0f}s ==")
    return 0 if ok else 3


LOCK_FILE = os.path.join(BASE, ".switch-lock")


def _acquire_lock():
    """同一时刻只允许一个切店进程（2026-10-14 事故：工作台残留任务与新任务
    并发抢浏览器窗口，互相把对方的页面导航走，全部失败）。锁 15 分钟自动过期。"""
    import atexit
    if os.path.exists(LOCK_FILE):
        try:
            age = time.time() - os.path.getmtime(LOCK_FILE)
        except OSError:
            age = 1e9
        if age < 900:
            raise SystemExit("⚠ 已有另一个切店进程在运行（工作台任务？），为避免抢浏览器窗口已退出。"
                             "确认没有后在等 15 分钟，或删除 driver/.switch-lock")
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    atexit.register(lambda: os.path.exists(LOCK_FILE) and os.remove(LOCK_FILE))


def main():
    _acquire_lock()
    if "--check" in sys.argv:
        raise SystemExit(check_only())
    if "--doctor" in sys.argv:
        raise SystemExit(doctor())
    if "--verify-all" in sys.argv:
        raise SystemExit(verify_all())
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    raise SystemExit(run_store(sys.argv[1]))


if __name__ == "__main__":
    _load_names()
    main()
