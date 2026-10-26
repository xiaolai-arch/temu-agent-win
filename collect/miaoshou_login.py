"""妙手ERP 登录自动化 — 会话失效时调用（2026-10-17 建，凭据试跑链路配套）。

用法：python miaoshou_login.py [--chrome]  # 检测未登录则自动登录（含图形验证码 OCR 重试）
      python miaoshou_login.py --check    # 只检测登录态，不做任何输入
      python miaoshou_login.py --captcha 3210   # OCR 认不出时，人工看 ms-captcha.png 后直填重跑

凭据：项目根 local.config.json 的 miaoshou.phone/password（绝不打印）。
退出码：0=已登录/登录成功  1=环境/页面异常  2=需要人工（密码错等）  3=验证码多次失败

流程（每步 OCR 实时定位）：
  1. 导航 erp.91miaoshou.com → 已登录（有 ERP 导航特征）直接退出
  2. 未登录：账号框 ^a 重打 → 密码框 ^a 重打（OCR 定位「请输入密码」）
  3. 图形验证码：OCR「请输入验证码」定位输入框，验证码图片在输入框右侧，
     裁剪放大 4 倍 OCR 取数字；非 4 位则点击图片刷新重试（≤6 次）
  4. 点「立即登录」→ 「图形验证码不正确」则重试验证码；「密码错误」退出交人工
"""
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core")))

from PIL import Image

import winutil
import uia_shell
from input import human_click, type_keys
from shot import screenshot, ocr, _load_last_shot
from uia_shell import _lit

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, ".."))
ERP_URL = "https://erp.91miaoshou.com/"

LOGIN_MARKS = ["立即登录", "请输入验证码", "图形验证码", "忘记密码"]
LOGGED_MARKS = ["待办事项", "常用功能", "妙手ERP", "登录成功", "订购"]


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def creds():
    d = json.load(open(os.path.join(ROOT, "local.config.json"), encoding="utf-8"))
    m = d.get("miaoshou")
    if not m or not m.get("phone"):
        raise SystemExit("local.config.json 无 miaoshou 凭据")
    return str(m["phone"]), str(m["password"])


def shot(w, tag):
    return screenshot(w, f"ms-{tag}")


def ocr_lines(png):
    res = ocr(png)
    return res.get("lines", [])


def find_line(lines, *words):
    """返回第一条包含任一关键词的 OCR 行。"""
    for l in lines:
        t = (l.get("text") or "").replace(" ", "")
        if any(wd in t for wd in words):
            return l
    return None


def click_line(l, dx=0, dy=0):
    ls = _load_last_shot()
    x = ls["left"] + l["x"] + l["w"] // 2 + dx
    y = ls["top"] + l["y"] + l["h"] // 2 + dy
    human_click(x, y)


def type_into(lines, words, text, tag):
    """点中含关键词的输入框 → ^a 全选 → 重打。"""
    l = find_line(lines, *words)
    if not l:
        raise RuntimeError(f"未找到输入框: {words}")
    click_line(l, dx=-l["w"] // 4)  # 点左侧文字区内
    time.sleep(0.4)
    type_keys("^a")
    time.sleep(0.2)
    type_keys(_lit(text), pause=0.015)
    log(f"✓ 已填 {tag}")
    return l


def read_captcha(png, code_line):
    """从截图裁剪验证码图片（输入框右侧）→ 放大 → OCR 取 4 位数字。
    妙手验证码是黑底白字带干扰线：先原样 OCR，失败再反色 OCR。"""
    img = Image.open(png)
    x0 = code_line["x"] + code_line["w"] + 8
    y0 = max(0, code_line["y"] - 14)
    x1 = min(img.width, x0 + 160)
    y1 = min(img.height, code_line["y"] + code_line["h"] + 14)
    if x1 <= x0:
        return ""
    from PIL import ImageOps
    crop = img.crop((x0, y0, x1, y1)).resize(((x1 - x0) * 4, (y1 - y0) * 4), Image.LANCZOS)
    cp = os.path.join(BASE, "..", "screenshots", "ms-captcha.png")
    crop.save(cp)
    for variant in (crop, ImageOps.invert(crop.convert("L")).convert("RGB")):
        txt = "".join(l.get("text", "") for l in ocr(cp if variant is crop else _save_tmp(variant)).get("lines", []))
        digits = re.sub(r"\D", "", txt)
        log(f"验证码 OCR → {digits if digits else '(空)'}")
        if len(digits) == 4:
            return digits
    return ""


def _save_tmp(im):
    p = os.path.join(BASE, "..", "screenshots", "ms-captcha-inv.png")
    im.save(p)
    return p


def already_logged_in(lines):
    t = "".join(l.get("text", "") for l in lines).replace(" ", "")
    if any(m in t for m in LOGIN_MARKS):
        return False
    # ERP 壳特征：logo + 顶部导航（欢迎页/任意内页都含）
    if "妙手ERP" in t and any(m in t for m in ("首页", "订单", "采购", "托管")):
        return True
    return bool(find_line(lines, "登录成功", "待办事项", "常用功能"))


def wait_render(w, tries=8, gap=2.0):
    """ERP 渲染慢：轮询截图直到能判定登录态（或超时）。返回 (state, lines)。
    state: 'in' | 'out' | 'unknown'"""
    for i in range(tries):
        lines = ocr_lines(shot(w, f"detect{i}"))
        if already_logged_in(lines):
            return "in", lines
        if find_line(lines, *LOGIN_MARKS):
            return "out", lines
        time.sleep(gap)
    return "unknown", lines


def do_login(w, phone, password, max_rounds=3, max_captcha=6, captcha_override=None):
    for rnd in range(1, max_rounds + 1):
        log(f"— 登录第 {rnd} 轮 —")
        state, lines = wait_render(w, tries=4, gap=2.0)
        if state == "in":
            log("✓ 实际是已登录态（渲染慢导致误判），收工")
            return 0
        if state == "unknown":
            log("页面要素不全，等 2s 重扫")
            time.sleep(2)
            continue
        # 登录页要素（OCR 定位；账号框可能是记忆填充的 11 位手机号）
        acc = find_line(lines, "请输入账号", "请输入手机号") or next(
            (l for l in lines if re.fullmatch(r"\d{11}", (l.get("text") or "").replace(" ", ""))), None)
        btn = find_line(lines, "立即登录")
        if not (acc and btn):
            log("登录要素不全（无账号框/按钮），重扫")
            time.sleep(2)
            continue
        try:
            click_line(acc)
            time.sleep(0.4)
            type_keys("^a")
            type_keys(_lit(phone), pause=0.015)
            log("✓ 已填 账号")
            type_into(lines, ["请输入密码"], password, "密码")
        except RuntimeError as e:
            log(f"⚠ {e}")
            return 1
        # 验证码：--captcha 人工目视直填；否则 OCR，失败点图刷新重来
        ok_code = ""
        for ci in range(1, max_captcha + 1):
            png = shot(w, f"cap{rnd}-{ci}")
            lines = ocr_lines(png)
            code = find_line(lines, "请输入验证码")
            if not code:
                time.sleep(1)
                continue
            if captcha_override:
                ok_code = captcha_override
            else:
                ok_code = read_captcha(png, code)
            if ok_code:
                type_into(lines, ["请输入验证码"], ok_code, "验证码")
                break
            click_line(code, dx=code["w"] // 2 + 60)  # 点验证码图片刷新
            time.sleep(1.2)
        if not ok_code:
            log("✗ 验证码多轮失败。可人工看 screenshots/ms-captcha.png 后："
                "python miaoshou_login.py --captcha XXXX")
            return 3
        click_line(btn)
        log("已点 立即登录，等待…")
        time.sleep(3.5)
        lines = ocr_lines(shot(w, f"after{rnd}"))
        t = "".join(l.get("text", "") for l in lines).replace(" ", "")
        if "密码错误" in t or "账号或密码" in t:
            log("✗ 密码错误 —— 需人工核对凭据")
            return 2
        if any(m in t for m in ("登录成功", "待办事项", "常用功能")) or "立即登录" not in t:
            log("✓ 登录成功")
            return 0
        if "验证码" in t and "不正确" in t:
            log("验证码错，重试")
            continue
        log("状态不明，重试")
    return 3


def main():
    check_only = "--check" in sys.argv
    captcha_override = None
    if "--captcha" in sys.argv:
        i = sys.argv.index("--captcha")
        captcha_override = re.sub(r"\D", "", sys.argv[i + 1])[:4]
    chrome = "--chrome" in sys.argv
    w = winutil.chrome_window() if chrome else winutil.default_window()
    if not w:
        raise SystemExit("无可见 %s 窗口" % ("Chrome" if chrome else "Edge"))
    w.set_focus()
    time.sleep(0.5)
    # 优先复用妙手标签；没有才开新标签（绝不劫持 Temu 等其他标签）
    try:
        uia_shell.switch_tab(win=w, title_contains="妙手")
    except RuntimeError:
        type_keys("^t")
        time.sleep(0.8)
    uia_shell.navigate(w, ERP_URL)
    state, lines = wait_render(w)
    if state == "in":
        log("✓ 妙手ERP 已登录，无需操作")
        return 0
    if state == "unknown":
        log("✗ 页面加载异常，无法判定登录态")
        return 1
    if check_only:
        log("✗ 未登录（--check 模式不执行登录）")
        return 3
    phone, password = creds()
    return do_login(w, phone, password, captcha_override=captcha_override)


if __name__ == "__main__":
    sys.exit(main())
