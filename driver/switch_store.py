"""TEMU 店铺切换（账号切换式）— 确定性脚本版，流程来自 2026-10-12/13 发现会话实测。

用法：python switch_store.py <store-id>          # 切店 + 定制商品页双按钮验证
      python switch_store.py <store-id> --check  # 只检查当前在哪店（不登录）

凭据：D:\\temu-agent\\local.config.json 的 accounts.<id>（手机号+密码，绝不打印）。

流程（每步 OCR 实时定位，坐标漂移免疫）：
  1. 确保窗口（无则普通参数拉起）→ 导航干净 /login（已登录也直接出登录页）
  2. 「手机号登录」tab → 「密码登录」子模式（如需要）
  3. 手机号框 ^a 重打 → 点手机号框→Tab→^a→输密码（Tab 法，密码框无法坐标点击）
  4. 点「登录」→ 处理「同意并登录」确认弹层（布局左移，按钮在左侧）
  5. seller 落地 site-main → Agent Center 联动（导航 customize-goods 验证账号+双按钮）
  6. 不联动时的补救：settle/seller-login?redirectUrl=… 强制重授权（2026-10-13 实测入口）

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
TARGET_URL = "https://agentseller.temu.com/main/customize-goods"
# seller-login 重授权入口（Agent Center 联动补救）
REAUTH_URL = ("https://seller.kuajingmaihuo.com/settle/seller-login?redirectUrl="
              "https%3A%2F%2Fagentseller.temu.com%2Fmain%2Fcustomize-goods")

ACCOUNT_NAME = {"main": "hpoiZee", "store-b": "boliooZ"}  # store-c 未知：记录实测
FALLBACK_LOGIN_BTN = (1876, 859)  # 布局漂移兜底（正常布局实测）
CAPTCHA_WORDS = ["验证码", "滑块", "拖动", "下方", "拼图"]
AUTHFAIL_WORDS = ["密码错误", "不正确", "账号或密码", "失败"]


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
    """定制商品页右上角账号名。"""
    text = " ".join(l["text"] for l in lines)
    for name in ["hpoiZee", "bolioo"]:
        if name in text:
            return name
    return None


def sync_buttons(lines):
    """双同步按钮存在性 + 坐标。"""
    b1 = next((l for l in lines if "按勾选" in l["text"].replace(" ", "")), None)
    b2 = next((l for l in lines if "忆托ERP" in l["text"].replace(" ", "")), None)
    return b1, b2


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
    # 6) 结果判定
    lines = ocr_lines(shot(w, "result"))
    blocked = detect_block(lines)
    if blocked:
        return blocked
    url = next((l["text"].replace(" ", "") for l in lines if "http" in l["text"].lower()), "")
    if "/login" in url and "redirectUrl" not in url:
        return "failpage"
    return None


def check_target(w, expect_old=None):
    """导航定制商品页，返回 (账号名 or None, (b1,b2), lines)。"""
    uia_shell.navigate(w, TARGET_URL)
    time.sleep(6)
    lines = ocr_lines(shot(w, "target"))
    return agent_account(lines), sync_buttons(lines), lines


def reauth_agent_center(w):
    """Agent Center 联动：settle/seller-login 重授权。
    实测链路：seller-login 页选分区「全球(除欧区、美国)」→ redirect →
    agentseller/auth/authentication 地区页点「中国地区」→ 完成授权。"""
    log("→ Agent Center 未联动，走重授权入口…")
    uia_shell.navigate(w, REAUTH_URL)
    time.sleep(5)
    # ① settle/seller-login：选分区「全球(除欧区、美国)」（OCR 有漏读波动，重试 3 轮）
    pos = None
    for _ in range(3):
        lines = ocr_lines(shot(w, "reauth"))
        for l in lines:
            t = l["text"].replace(" ", "")
            if "全球" in t and l["x"] > 900:
                pos = (l["x"] + l["w"] // 2, l["y"] + l["h"] // 2)
                break
        if pos:
            break
    if pos:
        log(f"→ seller-login 选分区「全球」@ {pos}")
        click(w, pos)
        # 轮询等页面离开"选分区"状态（redirect 链可能 >6s）
        for _ in range(4):
            time.sleep(2)
            lines = ocr_lines(shot(w, "reauth-wait"))
            if not any("全球" in l["text"].replace(" ", "") and l["x"] > 900 for l in lines):
                log("→ 选分区已通过，页面已跳转")
                break
        else:
            # 该页对鼠标合成点击免疫 → 键盘战术（2026-10-13 实测 Tab×4+Enter 有效）
            log("→ 点击无效，改键盘 Tab×4+Enter")
            r0 = w.rectangle()
            human_click(r0.left + 600, r0.top + 250, activate_window=w)
            time.sleep(0.3)
            type_keys("{TAB}" * 4)
            time.sleep(0.15)
            type_keys("{ENTER}")
            time.sleep(3)
            lines = ocr_lines(shot(w, "reauth-kb"))
            if any("全球" in l["text"].replace(" ", "") and l["x"] > 900 for l in lines):
                log("⚠ 键盘也未通过选分区（需要人工）")
    # ② 中途确认按钮
    for kw in ["确认登录", "同意并登录"]:
        p = find(lines, [kw, kw[:-1]], exact=True, xmin=900)
        if p:
            log(f"→ 点「{kw}」@ {p}")
            click(w, p)
            time.sleep(5)
            break
    # ③ auth 地区选择页：「中国地区」（轮询出现）
    for _ in range(6):
        pos = find(lines, "中国地区", xmin=400)
        if pos:
            break
        time.sleep(2)
        lines = ocr_lines(shot(w, "reauth2"))
    if pos:
        log(f"→ auth 地区页点「中国地区」@ {pos}")
        click(w, pos)
        time.sleep(8)
        return True
    log("→ 未出现地区选择页（可能已自动联动）")
    return False


def check_only():
    w = wait_window()
    acc, (b1, b2), lines = check_target(w)
    print(f"当前 Agent Center 账号: {acc or '未识别'}")
    print(f"按勾选同步: {'✅' if b1 else '❌'}  忆托ERP同步: {'✅' if b2 else '❌'}")
    if acc is None and not (b1 or b2):
        print("(可能未登录或页面未加载)")
    return 0


def main():
    if "--check" in sys.argv:
        raise SystemExit(check_only())
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    store_id = sys.argv[1]
    phone, password = creds(store_id)
    log(f"== 切换到 {store_id}（手机号 {phone[:3]}****{phone[-2:]}）==")
    t0 = time.time()

    w = wait_window()
    time.sleep(1)

    # 已经在目标店？直接验证（流畅度优化：免登录）
    acc, (b1, b2), _ = check_target(w)
    expected = ACCOUNT_NAME.get(store_id)
    if expected and acc == expected and b1 and b2:
        log(f"已在目标店（{acc}，双按钮✅），免登录直达")
        report.write_report("store-switch", True,
                            [f"店铺: {store_id}（已在目标店，未重新登录）",
                             f"账号: {acc}", "双按钮: 按勾选同步✅ 忆托ERP同步✅",
                             "未执行任何同步点击"])
        print("OK already-on-target")
        return
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
        raise SystemExit(2)
    if rc == "authfail":
        log("✋ 账号或密码错误")
        report.write_report("store-switch", False, [f"店铺: {store_id}", "结果: 账号或密码错误"])
        raise SystemExit(2)
    if rc:
        log(f"✋ 登录未成功（{rc}），截图取证")
        report.write_report("store-switch", False, [f"店铺: {store_id}", f"结果: 登录异常({rc})"])
        raise SystemExit(1)
    log(f"seller 登录成功（{time.time()-t0:.0f}s）")

    # Agent Center 验证 + 联动（按页面状态判断，不依赖已知账号名——store-c 首登时名字未知）
    acc, (b1, b2), lines = check_target(w)
    on_auth = find(lines, ["中国地区", "商家中心"], xmin=600) is not None and b1 is None
    need = on_auth or (expected is not None and acc != expected)
    if need:
        log(f"→ 需要联动（on_auth={on_auth}, acc={acc}, expected={expected}），走重授权…")
        reauth_agent_center(w)
        time.sleep(2)
        acc, (b1, b2), lines = check_target(w)
    if expected is not None and acc != expected:
        on_auth_now = find(lines, ["中国地区"], xmin=400) is not None
        report.write_report("store-switch", False,
                            [f"店铺: {store_id}",
                             "结果: ⚠️ 卡在 Agent Center 授权页（该页对自动点击免疫）" if on_auth_now
                             else f"结果: seller 已登录但 Agent Center 仍为 {acc or '未知'}",
                             "人工恢复（10 秒）: 浏览器当前页面用鼠标点「商家中心」卡片，之后重跑本任务" if on_auth_now
                             else "重授权入口未生效，需人工检查"])
        raise SystemExit(3)

    ok = bool(b1 and b2)
    on_auth_final = find(lines, ["中国地区"], xmin=400) is not None and not b1
    if not ok:
        extra = ("结果: ⚠️ 卡在 Agent Center 授权页（该页对自动操作免疫）",
                 "人工恢复（10 秒）: 在浏览器当前页面用鼠标点一下「商家中心」卡片即可，之后重跑本任务") \
            if on_auth_final else ("结果: 双按钮未出现（页面状态异常，见截图）",)
        report.write_report("store-switch", False, [f"店铺: {store_id}", *extra])
        raise SystemExit(3)
    lines = [
        f"店铺: {store_id}",
        f"账号: {acc or (expected or '新店（账号名已记录在截图）')}",
        f"双按钮: 按勾选同步{'✅' if b1 else '❌'} 忆托ERP同步{'✅' if b2 else '❌'}",
        f"耗时: {time.time()-t0:.0f}s",
        "未执行任何同步点击（只读验证）",
    ]
    report.write_report("store-switch", ok, lines)
    log(f"== 完成 ok={ok} 账号={acc} 耗时 {time.time()-t0:.0f}s ==")
    raise SystemExit(0 if ok else 3)


if __name__ == "__main__":
    main()
