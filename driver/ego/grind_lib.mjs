// grind_lib.mjs — Temu 调价 ego-browser 引擎（grind_one.py 的 DOM 版）
// 铁律不变：①勾选行必须填值 ②成功唯一信号=弹窗关闭 ③最终以导出复核为准
// 架构：弹窗表格可能是长表（首屏只渲染一部分）——滚动多轮扫描，行用
// 稳定键 qty|cur|同名序号 标识（索引会随渲染漂移，键不会）；
// 填值=native setter+input事件；勾选=原始坐标点可见方块；提交失败自救=取消空勾选行

import { execSync } from "node:child_process";

// 窗口最小化 = 布局瘫痪 + React 渲染暂停（今晚所有诡异故障根源），每 SKC 前检查
export function ensureWindowVisible() {
  try {
    const out = execSync(
      "powershell -NoProfile -ExecutionPolicy Bypass -File C:/Users/34191/ego/store-c-20261024-1015/win.ps1",
      { encoding: "utf-8", timeout: 20000 });
    return out.includes("RESTORED");
  } catch { return false; }
}

export const COST = { "派对餐巾": 0.16, "餐巾": 0.16, "餐巾纸": 0.16, "儿童派对餐巾": 0.16, "身份腕带": 0.33, "压花机": 25 };  // 压花机=钢印，25元/个（2026-10-24 用户确认）
export const sug = (cat, q) => Math.ceil(((COST[cat] ?? 0.16) * q + 9) / 0.5 * 2) / 2;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// 行收集器（在页面里执行）：从「确认调价」向上找弹窗根 → 收集含数量+勾选框的 tr
// key = qty|cur|同名序号（DOM 顺序稳定，同名行按出现次序编号）
const COLLECT_FN = `(() => {
  const btn = [...document.querySelectorAll("button")].find((b) => (b.textContent || "").trim() === "确认调价");
  if (!btn) return { open: false };
  let m = btn;
  for (let i = 0; i < 18 && m; i++) {
    m = m.parentElement;
    if (m && (m.textContent || "").includes("SKC ID") && m.querySelectorAll("input[type=checkbox]").length >= 1) break;
  }
  if (!m) return { open: false };
  const skcM = (m.textContent || "").match(/SKC ID[:：]\\s*(\\d+)/);
  const occ = new Map();
  const rows = [];
  for (const tr of m.querySelectorAll("tr")) {
    const txt = (tr.textContent || "").replace(/\\s+/g, " ");
    const qtyM = txt.match(/(\\d+)\\s*(?:pcs|件|张|片)/i);
    const cb = tr.querySelector('input[type="checkbox"]');
    if (!qtyM || !cb) continue;
    const priceM = txt.match(/¥(\\d+(?:\\.\\d+)?)/);
    const cur = priceM ? parseFloat(priceM[1]) : null;
    const qty = parseInt(qtyM[1], 10);
    const k = qty + "|" + cur;
    const n = occ.get(k) || 0;
    occ.set(k, n + 1);
    const inputs = [...tr.querySelectorAll('input[type="text"]')];
    const inp = inputs.find((i) => !String(i.className).includes("disabled"));
    const r = tr.getBoundingClientRect();
    rows.push({
      key: k + "|" + n, qty, cur,
      voided: txt.includes("已作废"),
      checked: cb.checked,
      fillable: !!inp,
      val: inp ? inp.value : null,
      label: txt.includes("降价"),
      vis: r.width > 0 && r.height > 0 && r.y >= 0 && r.y + r.height <= innerHeight,
    });
  }
  return { open: true, skc: skcM ? skcM[1] : null, rows };
})()`;

// 弹窗内可滚动表格容器（用于翻页扫描）
const SCROLLBOX_FN = `(() => {
  const btn = [...document.querySelectorAll("button")].find((b) => (b.textContent || "").trim() === "确认调价");
  if (!btn) return null;
  let m = btn;
  for (let i = 0; i < 18 && m; i++) {
    m = m.parentElement;
    if (m && (m.textContent || "").includes("SKC ID") && m.querySelectorAll("input[type=checkbox]").length >= 1) break;
  }
  if (!m) return null;
  let best = null;
  for (const d of m.querySelectorAll("div")) {
    if (d.scrollHeight > d.clientHeight + 60 && d.clientHeight > 150) {
      if (!best || d.scrollHeight > best.scrollHeight) best = d;
    }
  }
  return best ? { sh: best.scrollHeight, ch: best.clientHeight, st: best.scrollTop } : null;
})()`;

export async function scanRows(page) {
  return page.evaluate(COLLECT_FN);
}

export async function rawClick(page, evalFn, arg, label) {
  const box = await page.evaluate(evalFn, arg);
  if (!box || !box.w || box.w <= 0 || !isFinite(box.x) || !isFinite(box.y)) return false;
  await page.mouse.click(box.x + box.w / 2, box.y + box.h / 2, { label });
  await sleep(600);
  return true;
}

// ---------- 弹窗清扫 ----------
// MDL 公告弹窗一律点 X；new-bell 消息气泡点 header 最右图标（Esc 无效）
// 调价弹窗本体（含 确认调价 按钮的 MDL）绝不动；弹窗打开时绝不 Esc
export async function closePopups(page) {
  for (let round = 0; round < 8; round++) {
    const st = await page.evaluate(() => {
      const out = { iknow: null, yidu: null, xl: [], bell: null, dialogOpen: false };
      out.dialogOpen = [...document.querySelectorAll("button")].some((b) => (b.textContent || "").trim() === "确认调价");
      const ik = [...document.querySelectorAll("button")].filter((b) => ["我知道了", "知道了"].includes((b.textContent || "").trim()));
      if (ik.length) {
        const r = ik[ik.length - 1].getBoundingClientRect();
        out.iknow = { x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width };
      }
      const yd = [...document.querySelectorAll("button,div,a,span")].filter((e) =>
        (e.textContent || "").replace(/\s+/g, "").includes("一键已读所有消息") && e.children.length <= 2);
      if (yd.length) {
        const r = yd[yd.length - 1].getBoundingClientRect();
        out.yidu = { x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width };
      }
      const modals = [...document.querySelectorAll('[class*="MDL_container"]')].filter((m) => {
        const r = m.getBoundingClientRect();
        if (!(r.width > 300 && r.height > 200)) return false;
        if ((m.textContent || "").includes("确认调价")) return false; // 调价弹窗本体
        return true;
      });
      for (const m of modals) {
        const icon = m.querySelector('[class*="CloseIcon"], [class*="closeIcon"]');
        if (!icon) continue;
        const r = icon.getBoundingClientRect();
        if (r.width > 0 && r.x >= 0 && r.y >= 0 && r.y < innerHeight) {
          out.xl.push({ x: r.x + r.width / 2, y: r.y + r.height / 2, txt: (m.textContent || "").replace(/\s+/g, "").slice(0, 24) });
        }
      }
      // 顶部消息铃铛（点击即切换面板开/关）——面板无头关闭钮时靠它
      const toggle = document.querySelector('[class*="new-bell_container"]');
      if (toggle) {
        const tr = toggle.getBoundingClientRect();
        if (tr.width > 0) out.bellToggle = { x: tr.x + tr.width / 2, y: tr.y + tr.height / 2, w: tr.width };
      }
      const list = document.querySelector('[class*="new-bell_list"]');
      if (list) {
        // 面板包围盒：关闭钮一定在面板 header 内（按页面最右图标会点到导航栏）
        const listR = list.getBoundingClientRect();
        const header = document.querySelector('[class*="new-bell_header"]');
        const hr = header ? header.getBoundingClientRect() : { x: listR.x, y: listR.y - 62, width: listR.width, height: 62 };
        out.bellPanel = { x: hr.x, y: hr.y, w: hr.width, h: listR.bottom - hr.y };
        const svgs = [...document.querySelectorAll("svg")].map((s) => {
          const r = s.getBoundingClientRect();
          return { x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width };
        }).filter((s) => s.w > 0 && s.x >= hr.x && s.x <= hr.x + hr.width && s.y >= hr.y && s.y <= hr.y + hr.height);
        if (svgs.length) out.bell = svgs.reduce((a, b) => (b.x > a.x ? b : a));
        // 兜底1：面板内「标记为已读」
        const mr = [...document.querySelectorAll("button")].filter((b) => (b.textContent || "").trim() === "标记为已读").map((b) => {
          const r = b.getBoundingClientRect();
          return { x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width };
        }).filter((b) => b.w > 0);
        if (mr.length) out.bellMark = mr[0];
        // 兜底2：点面板外空白
        out.bellOutside = { x: Math.max(20, hr.x - 120), y: Math.min(700, hr.y + hr.height + 60), w: 10 };
      }
      return out;
    });
    if (st.iknow) { await page.mouse.click(st.iknow.x, st.iknow.y, { label: "点掉我知道了" }); await sleep(800); continue; }
    if (st.xl.length) {
      for (const x of st.xl) await page.mouse.click(x.x, x.y, { label: "关闭弹窗X:" + x.txt });
      await sleep(1200);
      continue;
    }
    if (st.bell && !st.dialogOpen) {
      // 面板开着：**铃铛切换最可靠**（实测头部 X 点不掉）；其次标记已读、点空白
      if (st.bellToggle) await page.mouse.click(st.bellToggle.x, st.bellToggle.y, { label: "铃铛切换关闭面板" });
      else if (st.bell) await page.mouse.click(st.bell.x, st.bell.y, { label: "关闭消息面板" });
      else if (st.bellMark) await page.mouse.click(st.bellMark.x, st.bellMark.y, { label: "标记为已读" });
      else if (st.bellOutside) await page.mouse.click(st.bellOutside.x, st.bellOutside.y, { label: "点空白关闭消息面板" });
      await sleep(1000);
      continue;
    }
    if (st.yidu) { await page.mouse.click(st.yidu.x, st.yidu.y, { label: "一键已读所有消息" }); await sleep(1200); continue; }
    return true; // 干净了
  }
  return false;
}

// ---------- 查询 SKC ----------
// 页面是长命 SPA，弹窗崩溃后会坏掉查询上下文（症状：任何 SKC 都查 0）——
// 首次可疑归零时重建 Page 再试；两页都 0 才承认真没了
export async function recreatePage(task, old) {
  try { await old.close(); } catch {}
  try { const p2 = task.page("p2"); if (p2 && (await task.tabs()).some(t => t.label === "p2" && !t.title)) await p2.close(); } catch {}
  const p = await task.newPage();
  try { await p.cdp('Page.bringToFront'); } catch {}
  return p;
}

export async function querySkc(task, pageRef, skc) {
  let page = pageRef.page;
  // 每 SKC 一页：先重建，避免旧弹窗把页面 React 毒化
  page = await recreatePage(task, page);
  pageRef.page = page;
  const goto = async () => {
    await page.goto("https://agentseller.temu.com/newon/product-select", { timeout: 60_000 });
    await page.waitForLoadState("domcontentloaded");
    await sleep(6000);
    await closePopups(page);
  };
  await goto();
  let lastCnt = null;
  let recreated = false;
  let hitFails = 0;
  if (ensureWindowVisible()) console.log("WARN: ego window was minimized, restored");
  // 用户情报：待办筛选「商品信息待确认」被勾选时，查其他商品全是 0——必须先取消勾选
  const unfilt = await page.evaluate(() => {
    // 找选中态的「商品信息待确认」tab（选中特征：class 含 active/check，或带角标勾选样式）
    const els = [...document.querySelectorAll("div,span")];
    const tab = els.find((e) => {
      const t = (e.textContent || "").replace(/\s+/g, "");
      if (!t.startsWith("商品信息待确认")) return false;
      const cls = String(e.className);
      return (cls.includes("active") || cls.includes("check") || cls.includes("Check") || cls.includes("selected") || cls.includes("Selected"))
        && e.getBoundingClientRect().width > 0 && e.children.length <= 4;
    });
    if (!tab) return { selected: false };
    const r = tab.getBoundingClientRect();
    tab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    return { selected: true, clicked: true, x: r.x + r.width / 2, y: r.y + r.height / 2 };
  });
  if (unfilt.selected) {
    console.log(`取消「商品信息待确认」筛选（合成点击 ${unfilt.clicked}）`);
    if (unfilt.clicked) { await page.mouse.click(unfilt.x, unfilt.y, { label: "取消商品信息待确认筛选" }); }
    await sleep(1500);
  }
  for (let tr = 0; tr < 5; tr++) {
    let filled = { ok: false, why: "init" };
    for (let fr = 0; fr < 4; fr++) {
      filled = await page.evaluate((skc) => {
        const labels = [...document.querySelectorAll("div,span,label")];
        const lbl = labels.find((e) => (e.textContent || "").trim() === "商品ID查询" && e.children.length === 0);
        let inp = null;
        if (lbl) {
          let box = lbl;
          for (let i = 0; i < 6 && box && !inp; i++) {
            box = box.parentElement;
            inp = box && box.querySelector('input[placeholder*="查询"]');
          }
        }
        if (!inp) inp = [...document.querySelectorAll('input[placeholder*="查询"]')][0]; // 兜底：表单里第一个查询框就是商品ID
        if (!inp) return { ok: false, why: "no-input" };
        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
        setter.call(inp, skc);
        inp.dispatchEvent(new Event("input", { bubbles: true }));
        return { ok: inp.value === skc };
      }, skc);
      if (filled.ok) break;
      await sleep(2000);
    }
    if (!filled.ok) throw new Error("query fill failed: " + JSON.stringify(filled));
    await sleep(400);
    // 每次现算查询按钮坐标（关公告后布局会移动；先滚到可见）
    const qb = await page.evaluate(() => {
      const b = [...document.querySelectorAll("button")].find((x) => (x.textContent || "").trim() === "查询");
      if (!b) return null;
      window.scrollTo(0, 0); // 页面滚动位置可能坏掉（坐标跑到负值），先归零
      b.scrollIntoView({ block: "center" });
      const r = b.getBoundingClientRect();
      const x = r.x + r.width / 2, y = r.y + r.height / 2;
      if (!isFinite(x) || !isFinite(y) || y < 0 || y > innerHeight) return { bad: true };
      const t = document.elementFromPoint(x, y);
      return { x, y, w: r.width, hit: !!t && (b === t || b.contains(t) || t.contains(b)) };
    });
    if (qb && qb.bad) { await closePopups(page); await page.evaluate(() => { window.scrollTo(0, 0); }); continue; }
    if (!qb || !isFinite(qb.x) || qb.w <= 0) throw new Error("查询 button not found");
    if (!qb.hit) {
      hitFails++;
      await closePopups(page);
      if (hitFails >= 2 && !recreated) {
        // 按钮持续点不中：页面半死（渲染器被杀/布局坏），重建
        page = await recreatePage(task, page);
        pageRef.page = page;
        recreated = true;
        await goto();
      }
      continue;
    }
    await page.mouse.click(qb.x, qb.y, { label: "查询" });
    await sleep(7000);
    await closePopups(page);
    await sleep(1500); // 等「一键已读」类 toast 消失（其文本含「全部 0」会污染统计）
    let cnt = null;
    for (let rc = 0; rc < 3; rc++) {
      cnt = await page.evaluate(() => {
        const m = (document.body.innerText || "").match(/全部\s*(\d+)\s*未发布/);
        return m ? parseInt(m[1], 10) : null;
      });
      if (cnt !== null) break;
      await sleep(2500); // tab 统计条可能还没渲染完
    }
    if (cnt === 1) {
      // 先确认卡片真的是目标 SKC（查询被吞时旧卡片残留、计数仍是 1）
      const hasSkc = await page.evaluate((skc) => (document.body.innerText || "").includes(String(skc)), skc);
      if (!hasSkc) { lastCnt = cnt; continue; }
      // 卡片操作按钮（发起调价）懒渲染：先把结果卡滚进视口再计数
      for (let s = 0; s < 5; s++) {
        const n = await page.evaluate(() =>
          [...document.querySelectorAll("a,button,span,div")].filter((e) => (e.textContent || "").trim() === "发起调价" && e.children.length === 0).length);
        if (n > 0) return { n, page, recreated };
        await page.evaluate(() => { scrollBy(0, 700); });
        await sleep(1000);
      }
      // 兜底：按 SKC 文本定位卡片滚到中央再数一次
      await page.evaluate((skc) => {
        const el = [...document.querySelectorAll("div,span")].find((e) => {
          const t = e.textContent || "";
          return t.includes(String(skc)) && t.length < 400 && e.children.length <= 6;
        });
        if (el) el.scrollIntoView({ block: "center" });
      }, skc);
      await sleep(1200);
      const n2 = await page.evaluate(() =>
        [...document.querySelectorAll("a,button,span,div")].filter((e) => (e.textContent || "").trim() === "发起调价" && e.children.length === 0).length);
      return { n: n2, page, recreated };
    }
    if ((cnt === 0 || cnt === null) && !recreated) {
      // 可疑归零：页面状态坏 → 重建 Page 再试一轮
      page = await recreatePage(task, page);
      pageRef.page = page;
      recreated = true;
      await goto();
      lastCnt = null;
      continue;
    }
    if (cnt === 0) return { n: 0, page, recreated }; // 两页都 0：真没了（下架/删除）
    lastCnt = cnt;
    // cnt>1 或读不到 → 查询被吞，重试
  }
  throw new Error(`查询未生效 cnt=${lastCnt} recreated=${recreated}`);
}

// ---------- 行操作（按稳定键定位，每次现扫现定位，不吃索引漂移） ----------
async function rowBbox(page, key) {
  const box = await page.evaluate(`(() => {
    const res = ${COLLECT_FN};
    if (!res.open) return null;
    const row = res.rows.find((r) => r.key === ${JSON.stringify(key)});
    if (!row) return { gone: true, keys: res.rows.map((r) => r.key) };
    // 找到该行的方块坐标
    const btn = [...document.querySelectorAll("button")].find((b) => (b.textContent || "").trim() === "确认调价");
    let m = btn;
    for (let i = 0; i < 18 && m; i++) {
      m = m.parentElement;
      if (m && (m.textContent || "").includes("SKC ID") && m.querySelectorAll("input[type=checkbox]").length >= 1) break;
    }
    const occ = new Map();
    for (const tr of m.querySelectorAll("tr")) {
      const txt = (tr.textContent || "").replace(/\\s+/g, " ");
      const qtyM = txt.match(/(\\d+)\\s*(?:pcs|件|张|片)/i);
      const cb = tr.querySelector('input[type="checkbox"]');
      if (!qtyM || !cb) continue;
      const priceM = txt.match(/¥(\\d+(?:\\.\\d+)?)/);
      const cur = priceM ? parseFloat(priceM[1]) : null;
      const qty = parseInt(qtyM[1], 10);
      const k = qty + "|" + cur;
      const n = occ.get(k) || 0;
      occ.set(k, n + 1);
      if (k + "|" + n !== ${JSON.stringify(key)}) continue;
      // 不 scrollIntoView（虚拟列表重渲染会换节点）；只回报可见状态
      const wrap = cb.closest('[class*="CBX_checkbox"]') || cb.parentElement;
      const sq = wrap.querySelector('[class*="CBX_square_"]') || wrap;
      const r = sq.getBoundingClientRect();
      return { x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width, h: r.height, checked: cb.checked,
        vis: r.width > 0 && r.y >= 0 && r.y + r.height <= innerHeight };
    }
    return null;
  })()`);
  return box;
}

// 定位行：返回 input / checkbox 方块在文档中的 nth 索引（供 ego fill/click 用，
// ego 的 fill=真实键盘级输入，React 受控组件只认这个——native setter 会被重渲染抹掉）
async function rowLocator(page, key) {
  return page.evaluate(`(() => {
    const res = ${COLLECT_FN};
    if (!res.open) return null;
    const row = res.rows.find((r) => r.key === ${JSON.stringify(key)});
    if (!row) return { gone: true };
    const btn = [...document.querySelectorAll("button")].find((b) => (b.textContent || "").trim() === "确认调价");
    let m = btn;
    for (let i = 0; i < 18 && m; i++) {
      m = m.parentElement;
      if (m && (m.textContent || "").includes("SKC ID") && m.querySelectorAll("input[type=checkbox]").length >= 1) break;
    }
    if (!m) return null;
    const allInputs = [...document.querySelectorAll('input[type="text"]')];
    const allSquares = [...document.querySelectorAll('div[class^="CBX_square"]')];
    const occ = new Map();
    for (const tr of m.querySelectorAll("tr")) {
      const txt = (tr.textContent || "").replace(/\s+/g, " ");
      const qtyM = txt.match(/(\d+)\s*(?:pcs|件|张|片)/i);
      const cb = tr.querySelector('input[type="checkbox"]');
      if (!qtyM || !cb) continue;
      const priceM = txt.match(/\¥(\d+(?:\.\d+)?)/);
      const cur = priceM ? parseFloat(priceM[1]) : null;
      const qty = parseInt(qtyM[1], 10);
      const k = qty + "|" + cur;
      const n = occ.get(k) || 0;
      occ.set(k, n + 1);
      if (k + "|" + n !== ${JSON.stringify(key)}) continue;
      const inp = [...tr.querySelectorAll('input[type="text"]')].find((i) => !String(i.className).includes("disabled"));
      const wrap = cb.closest('[class*="CBX_checkbox"]') || cb.parentElement;
      const sq = wrap.querySelector('[class*="CBX_square_"]'); // 精确到 CBX_square_5-12x-0（^匹配会抓到 InputWrapper）
      const r = sq ? sq.getBoundingClientRect() : { width: 0 };
      return {
        inputNth: inp ? allInputs.indexOf(inp) : -1,
        squareNth: sq ? allSquares.indexOf(sq) : -1,
        checked: cb.checked,
        vis: r.width > 0 && r.y >= 0 && r.y + r.height <= innerHeight,
      };
    }
    return null;
  })()`);
}

export async function setRowCheck(page, key, want) {
  for (let attempt = 0; attempt < 3; attempt++) {
    // 打标记法：直接给该行可见方块打 data 属性再点（重复规格行也不会串）
    const marked = await page.evaluate(`(() => {
      const res = ${COLLECT_FN};
      if (!res.open) return { ok: false, why: "dialog-gone" };
      const row = res.rows.find((r) => r.key === ${JSON.stringify(key)});
      if (!row) return { ok: false, why: "row-gone" };
      if (row.checked === ${want ? "true" : "false"}) return { ok: true, already: true };
      const btn = [...document.querySelectorAll("button")].find((b) => (b.textContent || "").trim() === "确认调价");
      let m = btn;
      for (let i = 0; i < 18 && m; i++) {
        m = m.parentElement;
        if (m && (m.textContent || "").includes("SKC ID") && m.querySelectorAll("input[type=checkbox]").length >= 1) break;
      }
      if (!m) return { ok: false, why: "no-root" };
      const occ = new Map();
      for (const tr of m.querySelectorAll("tr")) {
        const txt = (tr.textContent || "").replace(/\\s+/g, " ");
        const qtyM = txt.match(/(\\d+)\\s*(?:pcs|件|张|片)/i);
        const cb = tr.querySelector('input[type="checkbox"]');
        if (!qtyM || !cb) continue;
        const priceM = txt.match(/¥(\\d+(?:\\.\\d+)?)/);
        const cur = priceM ? parseFloat(priceM[1]) : null;
        const qty = parseInt(qtyM[1], 10);
        const k = qty + "|" + cur;
        const n = occ.get(k) || 0;
        occ.set(k, n + 1);
        if (k + "|" + n !== ${JSON.stringify(key)}) continue;
        const wrap = cb.closest('[class*="CBX_checkbox"]') || cb.parentElement;
        const sq = wrap.querySelector('[class*="CBX_square_"]');
        if (!sq) return { ok: false, why: "no-square" };
        document.querySelectorAll("[data-grind-cb]").forEach((e) => e.removeAttribute("data-grind-cb"));
        sq.setAttribute("data-grind-cb", "1");
        sq.scrollIntoView({ block: "center" });
        return { ok: true };
      }
      return { ok: false, why: "not-found" };
    })()`);
    if (!marked.ok) {
      console.log(`  cb-diag ${key}: ${marked.why}`);
      if (marked.why === "dialog-gone") return false;
      await sleep(900); continue;
    }
    if (marked.already) return true;
    try {
      await page.click('css=[data-grind-cb="1"]', { timeout: 5000 });
    } catch (e) {
      console.log(`  cb-diag ${key}: click err ${String(e.message).slice(0, 80)}`);
      await sleep(800); continue;
    }
    await sleep(800);
    const st = await scanRows(page);
    if (!st.open) return false;
    const row = st.rows.find((r) => r.key === key);
    if (row && row.checked === want) return true;
    console.log(`  cb-diag ${key}: after click checked=${row ? row.checked : "?"} want=${want}`);
  }
  const st = await scanRows(page);
  const row = st.open && st.rows.find((r) => r.key === key);
  return !!row && row.checked === want;
}

// 填一行：snapshot ref 映射法（round-104 验证）——
// 弹窗尾部（确认调价按钮前）的 textbox refs 倒序 = 表格行输入框（含禁用行）；
// nth/css 选择器会在弹窗重渲染间漂移，ref 在同一次 snapshot 会话内是稳的
// 填一行：给目标输入框打 data 标记再 fill（无索引/ref 映射，弹窗重渲染也不漂）
export async function fillRow(page, key, value) {
  for (let attempt = 0; attempt < 3; attempt++) {
    const marked = await page.evaluate(`(() => {
      const res = ${COLLECT_FN};
      if (!res.open) return { ok: false, why: "dialog-gone" };
      const row = res.rows.find((r) => r.key === ${JSON.stringify(key)});
      if (!row) return { ok: false, why: "row-gone" };
      const btn = [...document.querySelectorAll("button")].find((b) => (b.textContent || "").trim() === "确认调价");
      let m = btn;
      for (let i = 0; i < 18 && m; i++) {
        m = m.parentElement;
        if (m && (m.textContent || "").includes("SKC ID") && m.querySelectorAll("input[type=checkbox]").length >= 1) break;
      }
      if (!m) return { ok: false, why: "no-root" };
      const occ = new Map();
      for (const tr of m.querySelectorAll("tr")) {
        const txt = (tr.textContent || "").replace(/\\s+/g, " ");
        const qtyM = txt.match(/(\\d+)\\s*(?:pcs|件|张|片)/i);
        const cb = tr.querySelector('input[type="checkbox"]');
        if (!qtyM || !cb) continue;
        const priceM = txt.match(/¥(\\d+(?:\.\\d+)?)/);
        const cur = priceM ? parseFloat(priceM[1]) : null;
        const qty = parseInt(qtyM[1], 10);
        const k = qty + "|" + cur;
        const n = occ.get(k) || 0;
        occ.set(k, n + 1);
        if (k + "|" + n !== ${JSON.stringify(key)}) continue;
        const inp = [...tr.querySelectorAll('input[type="text"]')].find((i) => !String(i.className).includes("disabled"));
        if (!inp || inp.disabled) return { ok: false, why: "input-disabled" };
        document.querySelectorAll("[data-grind-target]").forEach((e) => e.removeAttribute("data-grind-target"));
        inp.setAttribute("data-grind-target", "1");
        return { ok: true };
      }
      return { ok: false, why: "not-found" };
    })()`);
    if (!marked.ok) {
      console.log(`  fill-diag ${key}: mark failed why=${marked.why}`);
      if (marked.why === "dialog-gone") return false;
      await sleep(1000); continue;
    }
    try {
      await page.fill('css=input[data-grind-target="1"]', String(value));
    } catch (e) {
      console.log("  fill err: " + String(e.message).slice(0, 100));
      await sleep(1000);
      continue;
    }
    await sleep(900); // 等 React 提交
    const st = await scanRows(page);
    if (!st.open) return false;
    const row = st.rows.find((r) => r.key === key);
    if (row && row.val === String(value)) {
      await page.evaluate(() => document.querySelectorAll("[data-grind-target]").forEach((e) => e.removeAttribute("data-grind-target"))).catch(() => {});
      return true;
    }
    console.log(`  fill-diag ${key}: filled ${value} but row=${row ? JSON.stringify({ v: row.val, keys: st.rows.length }) : "gone"}`);
  }
  const st = await scanRows(page);
  const row = st.open && st.rows.find((r) => r.key === key);
  return !!row && row.val === String(value);
}

export async function cancelDialog(page) {
  for (let i = 0; i < 3; i++) {
    const ok = await rawClick(page, () => {
      const btns = [...document.querySelectorAll("button")].filter((b) => (b.textContent || "").trim() === "取消");
      if (!btns.length) return null;
      const r = btns[btns.length - 1].getBoundingClientRect();
      return { x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width };
    }, null, "取消弹窗");
    if (!ok) { await page.keyboard.press("Escape"); await sleep(1200); }
    await sleep(1200);
    const st = await scanRows(page);
    if (!st.open) return true;
  }
  return !(await scanRows(page)).open;
}

// ---------- 单 SKC 全流程 ----------
// 返回 {status: ok|no-tj|not-found|nothing-to-do|submit-failed|error, detail}
export async function grindOne(task, skc, cat, kw) {
  const log = [];
  // 实测：同一个 page 开过一次调价弹窗后，后续弹窗的 React 事件失效（写入被回滚）——
  // 每个 SKC 都用全新页面（约多花 7s，换稳定）
  const managed0 = await task.pages();
  const pageRef = { page: managed0.length ? managed0[managed0.length - 1] : await task.newPage() };
  const P = () => pageRef.page;
  try {
    const q = await querySkc(task, pageRef, skc);
        const nTj = q.n;
    log.push(`发起调价链接 ${nTj}${q.recreated ? "（重建页面后）" : ""}`);
    if (nTj === 0) return { status: "no-tj", log };

    let matched = false;
    for (let li = 0; li < Math.min(nTj, 4); li++) {
      try {
        // 重试循环：被弹窗挡住 → 清扫 → 重试（最多 3 轮）
        let pos = null;
        for (let tr = 0; tr < 3; tr++) {
          await P().evaluate((idx) => {
            const els = [...document.querySelectorAll("a,button,span,div")].filter((e) => (e.textContent || "").trim() === "发起调价" && e.children.length === 0);
            if (els[idx]) els[idx].scrollIntoView({ block: "center" });
          }, li);
          await sleep(900);
          pos = await P().evaluate((idx) => {
            const els = [...document.querySelectorAll("a,button,span,div")].filter((e) => (e.textContent || "").trim() === "发起调价" && e.children.length === 0);
            const el = els[idx];
            if (!el) return null;
            const r = el.getBoundingClientRect();
            const x = r.x + r.width / 2, y = r.y + r.height / 2;
            if (!isFinite(x) || !isFinite(y)) return null;
            const t = document.elementFromPoint(x, y);
            return { x, y, hit: !!t && (el === t || el.contains(t) || t.contains(el)),
              topText: t ? (t.textContent || "").replace(/\s+/g, "").slice(0, 24) : "NULL" };
          }, li);
          if (pos && pos.hit) break;
          log.push(`  链接${li}被挡(${pos ? pos.topText : "链接消失"})，清扫重试${tr + 1}`);
          await closePopups(P());
          await sleep(800);
        }
        if (!pos || !pos.hit) { continue; }
        await P().mouse.click(pos.x, pos.y, { label: "发起调价" });
        // 渲染门控：等 确认调价 出现；未出则同链接补点一次
        let st = { open: false };
        for (let i = 0; i < 5; i++) {
          await sleep(1500);
          st = await scanRows(P());
          if (st.open) break;
        }
        if (!st.open) {
          await P().mouse.click(pos.x, pos.y, { label: "发起调价补点" });
          for (let i = 0; i < 4; i++) {
            await sleep(1500);
            st = await scanRows(P());
            if (st.open) break;
          }
        }
        if (!st.open) { log.push(`链接${li} 未渲染，跳过`); await closePopups(P()); continue; }
        await closePopups(P()); // 「我知道了」等浮层（不会动调价弹窗本体）
        st = await scanRows(P());
        if (!st.open) continue;
        if (st.skc !== String(skc)) {
          log.push(`链接${li} 非目标(${st.skc})，取消`);
          await cancelDialog(P());
          continue;
        }
        matched = true;
        log.push(`✓ 弹窗匹配 SKC ${st.skc}，首屏 ${st.rows.length} 行`);
        // 弹窗刚打开时 React 未稳定（填充/勾选会被回滚），等 5s
        await sleep(5000);
        break;
      } catch (e) { log.push(`链接${li} 异常: ${e.message.slice(0, 60)}`); try { await cancelDialog(P()); } catch {} continue; }
    }
    if (!matched) return { status: "not-found", log };

    // ---- 滚动扫描 + 按键执行（弹窗表格可能是长表，首屏不全） ----
    const done = new Map();   // key -> {action, note}
    const filledKeys = new Set();
    let failedActions = 0;
    let fillFails = 0;
    let pass = 0;
    let cleanStreak = 0;
    while (pass++ < 40) {
      const sc = await scanRows(P());
      if (!sc.open) break;
      let acted = 0;
      for (const r of sc.rows) {
        if (done.has(r.key)) continue;
        if (!r.vis) continue; // 不在视口的行等滚动轮到它
        // 行计划（同 grind_one）：作废→取消勾选；可疑数量→取消勾选；
        // 达标→取消勾选；其余→填建议价
        let action = "skip";
        let target = null;
        if (!r.checked) action = "skip";
        else if (r.voided) action = "uncheck"; // 作废行勾着会挡提交，取消勾选
        else if (r.qty < 10) action = "uncheck";
        else {
          target = sug(cat, r.qty);
          if (r.cur !== null && r.cur <= target * 1.05) action = "uncheck";
          else action = "fill";
        }
        if (action === "skip") { done.set(r.key, { action, note: r.voided ? "作废" : "未勾选" }); acted++; continue; }
        if (action === "uncheck") {
          const ok = await setRowCheck(P(), r.key, false);
          if (!ok) failedActions++;
          done.set(r.key, { action, note: ok ? "已取消勾选" : "⚠取消失败" });
          log.push(`  ${r.qty}件 ¥${r.cur} 取消勾选(${r.voided ? "作废" : "达标"})${ok ? "" : " ⚠"}`);
          acted++;
          continue;
        }
        // fill
        const v = target;
        const ok = await fillRow(P(), r.key, v);
        if (!ok) {
          fillFails++;
          // 连续 3 行填不上 = 平台锁价（长期提效自动调价中，人工改价被重置），整单跳过
          if (fillFails >= 3) {
            log.push(`  连续${fillFails}行填不上→判定平台锁价，跳过该 SKC`);
            try { await cancelDialog(P()); } catch {}
            return { status: "locked", log };
          }
        }
        if (ok) {
          done.set(r.key, { action: "fill", note: "ok" });
          filledKeys.add(r.key);
          log.push(`  ${r.qty}件 ¥${r.cur}→${v} ✓`);
        } else {
          failedActions++;
          const ok2 = await setRowCheck(P(), r.key, false);
          if (!ok2) failedActions++;
          done.set(r.key, { action: "fill-fail", note: ok2 ? "填失败→已取消勾选" : "⚠填失败且取消失败" });
          log.push(`  ${r.qty}件 ¥${r.cur} 填${v}失败→取消勾选${ok2 ? "" : " ⚠"}`);
        }
        acted++;
      }
      // 翻页：滚动表格容器
      const box = await P().evaluate(SCROLLBOX_FN);
      let scrolled = false;
      if (box) {
        scrolled = await P().evaluate(() => {
          const btn = [...document.querySelectorAll("button")].find((b) => (b.textContent || "").trim() === "确认调价");
          let m = btn;
          for (let i = 0; i < 18 && m; i++) {
            m = m.parentElement;
            if (m && m.querySelectorAll("input[type=checkbox]").length >= 1) break;
          }
          let best = null;
          for (const d of m.querySelectorAll("div")) {
            if (d.scrollHeight > d.clientHeight + 60 && d.clientHeight > 150) {
              if (!best || d.scrollHeight > best.scrollHeight) best = d;
            }
          }
          if (!best) return false;
          const before = best.scrollTop;
          best.scrollTop = before + best.clientHeight * 0.8;
          return best.scrollTop > before + 10;
        });
        await sleep(900);
      }
      if (!acted) cleanStreak++;
      else cleanStreak = 0;
      if (!acted && !scrolled && cleanStreak >= 2) break; // 连续两轮无动作且到底
      if (!scrolled && acted) continue; // 无处可滚但本轮有动作，再扫一遍确认
    }
    log.push(`扫描完成：填 ${filledKeys.size} 行，处理 ${done.size} 行`);

    // ---- 提交前全表滚动清扫（边滚边补填/取消勾选，直到一整轮干净） ----
    const scrollTopOf = async () => P().evaluate(() => {
      const btn = [...document.querySelectorAll("button")].find((b) => (b.textContent || "").trim() === "确认调价");
      let m = btn;
      for (let i = 0; i < 18 && m; i++) {
        m = m.parentElement;
        if (m && m.querySelectorAll("input[type=checkbox]").length >= 1) break;
      }
      if (!m) return false;
      for (const d of m.querySelectorAll("div")) {
        if (d.scrollHeight > d.clientHeight + 60 && d.clientHeight > 150) d.scrollTop = 0;
      }
      return true;
    });
    const scrollStep = () => P().evaluate(() => {
      const btn = [...document.querySelectorAll("button")].find((b) => (b.textContent || "").trim() === "确认调价");
      let m = btn;
      for (let i = 0; i < 18 && m; i++) {
        m = m.parentElement;
        if (m && m.querySelectorAll("input[type=checkbox]").length >= 1) break;
      }
      if (!m) return false;
      let best = null;
      for (const d of m.querySelectorAll("div")) {
        if (d.scrollHeight > d.clientHeight + 60 && d.clientHeight > 150) {
          if (!best || d.scrollHeight > best.scrollHeight) best = d;
        }
      }
      if (!best) return false;
      const before = best.scrollTop;
      best.scrollTop = before + best.clientHeight * 0.8;
      return best.scrollTop > before + 10;
    });
    const sweep = async (tag) => {
      await scrollTopOf();
      await sleep(700);
      let fixes = 0;
      for (let sp = 0; sp < 40; sp++) {
        const sc = await scanRows(P());
        if (!sc.open) break;
        for (const r of sc.rows) {
          if (!r.checked) continue;
          const needsFill = r.fillable && (r.val ?? "") === "";
          const needsUncheck = !r.fillable; // 勾着但输入框不可用
          if (!needsFill && !needsUncheck) continue;
          if (needsFill && r.qty >= 10 && r.cur !== null) {
            const target = sug(cat, r.qty);
            if (target > r.cur) {
              // 建议价高于现价 = 涨价，平台禁止 → 取消勾选保持原价
              const okU = await setRowCheck(P(), r.key, false);
              if (okU) { log.push(`  [${tag}] ${r.qty}件 ¥${r.cur} 建议价${target}更高→取消勾选`); fixes++; }
              continue;
            }
            const ok = await fillRow(P(), r.key, target);
            if (ok) { log.push(`  [${tag}] ${r.qty}件 ¥${r.cur}→补填${target} ✓`); fixes++; continue; }
          }
          const okU = await setRowCheck(P(), r.key, false);
          if (okU) { log.push(`  [${tag}] ${r.qty}件 取消勾选`); fixes++; }
        }
        const moved = await scrollStep();
        await sleep(800);
        if (!moved) break;
      }
      return fixes;
    };
    const swFixes = await sweep("终扫");
    log.push(`终扫修复 ${swFixes} 行`);

    if (filledKeys.size === 0) {
      log.push(`0 行可调，取消（failedActions=${failedActions}）`);
      try { await cancelDialog(P()); } catch (e) { log.push("cancel err: " + String(e.message).slice(0, 50)); }
      // 有失败动作时不算完成（可能是交互失效而非真没得调）
      return failedActions === 0 ? { status: "nothing-to-do", log } : { status: "suspect", log };
    }

    const submitBtn = () => P().evaluate(() => {
      const b = [...document.querySelectorAll("button")].find((x) => (x.textContent || "").trim() === "确认调价");
      if (!b) return null;
      const r = b.getBoundingClientRect();
      return { x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width };
    });
    for (let attempt = 0; attempt < 4; attempt++) {
      const pos = await submitBtn();
      if (!pos) return { status: "ok", log: [...log, "弹窗已关闭=成功"] };
      if (!isFinite(pos.x)) break;
      await P().mouse.click(pos.x, pos.y, { label: "确认调价" });
      await sleep(5000);
      if (!(await scanRows(P())).open) return { status: "ok", log: [...log, `第${attempt + 1}次点击，弹窗关闭=成功`] };
      // 提交被拒：抓报错文本 + 截图，再全表清扫一遍后重试
      const errText = await P().evaluate(() => {
        const t = (document.body.innerText || "");
        return t.split(/\r?\n/).filter((l) => /失败|错误|请|不能|无法|低于|高于|限|重试|繁忙/.test(l) && l.length < 80).slice(0, 8);
      });
      log.push(`  提交未过报错文本: ${JSON.stringify(errText)}`);
      try {
        const sp = await P().screenshot({ path: `C:/Users/34191/ego/store-c-20261024-1015/submit-fail-${Date.now()}.png` });
        log.push(`  截图: ${String(sp).split("/").pop()}`);
      } catch {}
      const fixes = await sweep(`自救${attempt + 1}`);
      log.push(`  自扫修复 ${fixes} 行`);
      if (fixes === 0) await closePopups(P());
    }
    await cancelDialog(P());
    return { status: "submit-failed", log };
  } catch (e) {
    log.push("error: " + e.message);
    try { await cancelDialog(P()); } catch {}
    return { status: "error", log };
  }
}
