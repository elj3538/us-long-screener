"""フェーズ3の補助ページ（options.html / watchlist.html / portfolio.html / guide.html / terms.html）を生成するモジュール。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))

_COMMON_CSS = """
:root {
  --bg: #fafafa; --card: #ffffff; --line: #e6e6e6; --muted: #666666; --fg: #1a1a1a;
  --accent: #2563eb; --th: #f3f4f6; --field: #f7f8fa; --info: #eff6ff;
  --t1: #166534; --t1bg: #dcfce7; --t2: #854d0e; --t2bg: #fef9c3; --t3: #6b7280; --t3bg: #f3f4f6;
  --wbg: #fff7ed; --wbd: #fed7aa; --wfg: #7c2d12; --pos: #15803d; --neg: #b91c1c;
}
body.dark {
  --bg: #0f172a; --card: #1e293b; --line: #334155; --muted: #94a3b8; --fg: #f1f5f9;
  --th: #1e293b; --field: #0f172a; --info: #1e3a8a;
  --t1: #86efac; --t1bg: #14532d; --t2: #fde047; --t2bg: #713f12; --t3: #cbd5e1; --t3bg: #334155;
  --wbg: #431407; --wbd: #9a3412; --wfg: #fdba74; --pos: #4ade80; --neg: #f87171;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 0 0 48px; background: var(--bg); color: var(--fg);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Hiragino Kaku Gothic ProN", Meiryo, sans-serif;
  font-size: 13px; line-height: 1.6;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
#theme-bar {
  background: var(--card); border-bottom: 1px solid var(--line);
  padding: 6px 16px; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: 12px;
}
.container { max-width: 1120px; margin: 0 auto; padding: 16px; }
.top-nav { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 14px; }
.btn {
  display: inline-flex; align-items: center; gap: 4px; padding: 5px 11px;
  border: 1px solid var(--line); border-radius: 6px; background: var(--card); color: var(--fg);
  cursor: pointer; font-size: 12px; font-weight: 500;
}
.btn:hover { border-color: var(--accent); }
.btn-primary { background: var(--accent); color: #fff; border-color: var(--accent); }
.btn-danger { color: var(--neg); border-color: color-mix(in srgb, var(--neg) 40%, var(--line)); }
.card {
  background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; margin-bottom: 14px;
}
h1 { margin: 0 0 8px; font-size: 21px; }
h2 { margin: 0 0 10px; font-size: 16px; border-bottom: 2px solid var(--accent); padding-bottom: 4px; }
input[type="text"], input[type="number"], input[type="date"], select, textarea {
  padding: 6px 8px; border: 1px solid var(--line); border-radius: 6px;
  background: var(--field); color: var(--fg); font-size: 13px;
}
.table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; }
table { width: 100%; border-collapse: collapse; font-size: 12px; white-space: nowrap; }
th, td { padding: 7px 8px; border-bottom: 1px solid var(--line); text-align: left; }
th { background: var(--th); font-weight: 700; }
th.num, td.num { text-align: right; }
.tier-badge { display: inline-block; padding: 2px 7px; border-radius: 99px; font-weight: 700; font-size: 11px; }
.t1 { background: var(--t1bg); color: var(--t1); }
.t2 { background: var(--t2bg); color: var(--t2); }
.t3 { background: var(--t3bg); color: var(--t3); }
.pos { color: var(--pos); font-weight: 700; } .neg { color: var(--neg); font-weight: 700; }
.tabs-bar { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; align-items: center; }
.tab-btn {
  padding: 6px 12px; border: 1px solid var(--line); border-radius: 6px;
  background: var(--field); color: var(--fg); cursor: pointer; font-size: 12px; font-weight: 600;
}
.tab-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.kpi-grid { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; }
.kpi-box { flex: 1 1 180px; background: var(--field); border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; }
.kpi-lbl { font-size: 11px; color: var(--muted); }
.kpi-val { font-size: 19px; font-weight: 800; margin-top: 2px; }
"""

_THEME_BAR_HTML = """
<div id="theme-bar">
  <span>配色:</span>
  <select id="theme-preset">
    <option value="genko">現行 (ブルー)</option>
    <option value="blueplus">ブルー＋</option>
    <option value="teal">ティール</option>
    <option value="slate">スレート</option>
    <option value="sand">サンド</option>
    <option value="violet">バイオレット</option>
    <option value="rose">ローズ</option>
    <option value="custom">カスタム</option>
  </select>
  <input type="color" id="theme-custom-color" value="#2563eb" title="カスタムアクセント色" style="width:28px;height:24px;padding:0;border:none;cursor:pointer;">
  <button type="button" class="btn" id="dark-toggle">🌙 ダークへ</button>
  <button type="button" class="btn" id="theme-reset">標準へ戻す</button>
</div>
"""

_THEME_JS = """
(() => {
  const PRESETS = {
    genko: "#2563eb", blueplus: "#0284c7", teal: "#0d9488",
    slate: "#475569", sand: "#b45309", violet: "#7c3aed", rose: "#e11d48"
  };
  const presetSel = document.getElementById("theme-preset");
  const colorInp = document.getElementById("theme-custom-color");
  const darkBtn = document.getElementById("dark-toggle");
  function applyTheme(preset, dark, customColor) {
    const c = (preset === "custom" && customColor) ? customColor : (PRESETS[preset] || PRESETS.genko);
    document.documentElement.style.setProperty("--accent", c);
    document.body.classList.toggle("dark", !!dark);
    darkBtn.textContent = dark ? "☀️ ライトへ" : "🌙 ダークへ";
    presetSel.value = preset;
    colorInp.value = c;
    localStorage.setItem("pp_theme_long", JSON.stringify({ preset, dark, customColor: c }));
  }
  try {
    const saved = JSON.parse(localStorage.getItem("pp_theme_long") || "{}");
    applyTheme(saved.preset || "genko", !!saved.dark, saved.customColor || "#2563eb");
  } catch { applyTheme("genko", false, "#2563eb"); }
  presetSel.addEventListener("change", () => applyTheme(presetSel.value, document.body.classList.contains("dark"), colorInp.value));
  colorInp.addEventListener("input", () => applyTheme("custom", document.body.classList.contains("dark"), colorInp.value));
  darkBtn.addEventListener("click", () => applyTheme(presetSel.value, !document.body.classList.contains("dark"), colorInp.value));
  document.getElementById("theme-reset").addEventListener("click", () => applyTheme("genko", false, "#2563eb"));
})();
"""


def _nav_html(active: str) -> str:
    links = [
        ("index.html", "← ランキング"),
        ("options.html", "🎯 オプション候補"),
        ("watchlist.html", "☆ ウォッチリスト"),
        ("portfolio.html", "💼 ポートフォリオ"),
        ("guide.html", "使い方・見方"),
        ("terms.html", "利用規約・免責事項"),
    ]
    btns = []
    for href, label in links:
        cls = "btn btn-primary" if href == active else "btn"
        btns.append(f'<a href="{href}" class="{cls}">{label}</a>')
    return f'<div class="top-nav"><div style="display:flex;gap:8px;flex-wrap:wrap;">{"".join(btns)}</div></div>'


def _build_watchlist_html() -> str:
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ウォッチリスト | 10年保有米株スクリーナー</title>
<style>{_COMMON_CSS}</style>
</head>
<body>
{_THEME_BAR_HTML}
<div class="container">
  {_nav_html("watchlist.html")}
  <h1>☆ ウォッチリスト</h1>
  <p style="color:var(--muted);margin-top:0;">ランキング画面で保存した銘柄や、ここで追加した銘柄をタブごとに管理できます（ブラウザの localStorage に保存）。</p>

  <div class="card">
    <div class="tabs-bar" id="tabs-bar"></div>
    <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">
      <input type="text" id="add-sym" placeholder="ティッカー追加（例: ADBE）" style="width:200px;">
      <button type="button" class="btn btn-primary" id="add-sym-btn">このタブに追加</button>
      <button type="button" class="btn" id="new-tab-btn">＋ 新規タブ</button>
      <button type="button" class="btn" id="rename-tab-btn">タブ名変更</button>
      <button type="button" class="btn btn-danger" id="del-tab-btn">タブ削除</button>
    </div>
  </div>

  <div class="card">
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>順</th><th>軍</th><th>コード</th><th>銘柄</th><th>業種</th>
            <th class="num">終値</th><th class="num">1Y騰落</th>
            <th class="num">ファンダ点</th><th class="num">買い時</th><th>メモ</th><th>操作</th>
          </tr>
        </thead>
        <tbody id="wl-tbody"></tbody>
      </table>
    </div>
  </div>

  <details class="card">
    <summary style="cursor:pointer;font-weight:700;">テキスト控え（PC間コピー・復元用）</summary>
    <div style="margin-top:10px;display:flex;flex-direction:column;gap:8px;">
      <textarea id="wl-io" rows="4" placeholder="ここにエクスポート文字列が出力されます。復元時は貼り付けて「復元」を押してください。"></textarea>
      <div style="display:flex;gap:8px;">
        <button type="button" class="btn" id="wl-export-txt">現在のデータを書き出す</button>
        <button type="button" class="btn btn-primary" id="wl-import-txt">テキストから復元</button>
      </div>
    </div>
  </details>
</div>

<script>
{_THEME_JS}
(async () => {{
  let stockMap = {{}};
  try {{
    const res = await fetch("ranking.json");
    const data = await res.json();
    (data.items || []).forEach(it => {{ stockMap[it.symbol.toUpperCase()] = it; }});
  }} catch (e) {{ console.warn("ranking.json 読込失敗", e); }}

  // 状態ロード（旧 wl_codes_long_us からの自動取り込み対応）
  let state = null;
  try {{ state = JSON.parse(localStorage.getItem("wl_tabs_long_us") || "null"); }} catch {{}}
  if (!state || !Array.isArray(state.tabs) || !state.tabs.length) {{
    state = {{ active: 0, tabs: [{{ name: "メイン", items: [] }}] }};
  }}
  // ランキング画面のチェック保存分をメインタブに自動同期
  try {{
    const legacy = JSON.parse(localStorage.getItem("wl_codes_long_us") || "[]");
    const existing = new Set(state.tabs.flatMap(t => t.items.map(x => x.sym)));
    legacy.forEach(sym => {{
      const s = String(sym).toUpperCase();
      if (s && !existing.has(s)) {{ state.tabs[0].items.push({{ sym: s, memo: "" }}); existing.add(s); }}
    }});
  }} catch {{}}

  function save() {{
    localStorage.setItem("wl_tabs_long_us", JSON.stringify(state));
    const allSyms = [...new Set(state.tabs.flatMap(t => t.items.map(x => x.sym)))];
    localStorage.setItem("wl_codes_long_us", JSON.stringify(allSyms));
  }}

  function render() {{
    const tabsBar = document.getElementById("tabs-bar");
    tabsBar.innerHTML = "";
    state.tabs.forEach((t, idx) => {{
      const b = document.createElement("button");
      b.type = "button";
      b.className = "tab-btn" + (idx === state.active ? " active" : "");
      b.textContent = `${{t.name}} (${{t.items.length}})`;
      b.addEventListener("click", () => {{ state.active = idx; save(); render(); }});
      tabsBar.appendChild(b);
    }});

    const cur = state.tabs[state.active] || state.tabs[0];
    const tbody = document.getElementById("wl-tbody");
    tbody.innerHTML = "";
    if (!cur.items.length) {{
      tbody.innerHTML = '<tr><td colspan="11" style="text-align:center;color:var(--muted);padding:18px;">登録銘柄がありません。上の入力欄またはランキング画面から追加してください。</td></tr>';
      return;
    }}
    cur.items.forEach((entry, idx) => {{
      const s = stockMap[entry.sym] || null;
      const tr = document.createElement("tr");
      const retY = s && s.returns ? s.returns.Y : null;
      const retCls = retY > 0 ? "pos" : (retY < 0 ? "neg" : "");
      tr.innerHTML = `
        <td>
          <button type="button" class="btn" data-mv="up" style="padding:1px 5px;">↑</button>
          <button type="button" class="btn" data-mv="dn" style="padding:1px 5px;">↓</button>
        </td>
        <td>${{s ? `<span class="tier-badge t${{s.tier}}">${{s.tier}}軍</span>` : "-"}}</td>
        <td><a href="reports/${{entry.sym}}.html"><strong>${{entry.sym}}</strong></a></td>
        <td>${{s ? `<a href="reports/${{entry.sym}}.html">${{s.name}}</a>` : "(ランキング外)"}}</td>
        <td>${{s ? s.sector_ja : "-"}}</td>
        <td class="num">${{s && s.close != null ? "$" + s.close.toFixed(2) : "-"}}</td>
        <td class="num ${{retCls}}">${{retY != null ? (retY > 0 ? "+" : "") + retY.toFixed(1) + "%" : "-"}}</td>
        <td class="num"><strong>${{s && s.quality_score != null ? s.quality_score.toFixed(1) : "-"}}</strong></td>
        <td class="num"><strong>${{s && s.buy_score != null ? s.buy_score.toFixed(1) : "-"}}</strong></td>
        <td><input type="text" class="memo-inp" value="${{(entry.memo || "").replace(/"/g, "&quot;")}}" placeholder="メモ..." style="width:160px;padding:3px 6px;"></td>
        <td><button type="button" class="btn btn-danger del-btn" style="padding:2px 7px;">削除</button></td>
      `;
      tr.querySelector('[data-mv="up"]').addEventListener("click", () => {{
        if (idx > 0) {{ [cur.items[idx - 1], cur.items[idx]] = [cur.items[idx], cur.items[idx - 1]]; save(); render(); }}
      }});
      tr.querySelector('[data-mv="dn"]').addEventListener("click", () => {{
        if (idx < cur.items.length - 1) {{ [cur.items[idx + 1], cur.items[idx]] = [cur.items[idx], cur.items[idx + 1]]; save(); render(); }}
      }});
      tr.querySelector(".memo-inp").addEventListener("input", (e) => {{ entry.memo = e.target.value; save(); }});
      tr.querySelector(".del-btn").addEventListener("click", () => {{ cur.items.splice(idx, 1); save(); render(); }});
      tbody.appendChild(tr);
    }});
  }}

  document.getElementById("add-sym-btn").addEventListener("click", () => {{
    const inp = document.getElementById("add-sym");
    const sym = inp.value.trim().toUpperCase();
    if (!sym) return;
    const cur = state.tabs[state.active];
    if (!cur.items.some(x => x.sym === sym)) cur.items.push({{ sym, memo: "" }});
    inp.value = "";
    save(); render();
  }});
  document.getElementById("new-tab-btn").addEventListener("click", () => {{
    const name = prompt("新しいタブ名を入力してください", "候補" + (state.tabs.length + 1));
    if (!name) return;
    state.tabs.push({{ name: name.trim(), items: [] }});
    state.active = state.tabs.length - 1;
    save(); render();
  }});
  document.getElementById("rename-tab-btn").addEventListener("click", () => {{
    const cur = state.tabs[state.active];
    const name = prompt("新しいタブ名を入力してください", cur.name);
    if (!name) return;
    cur.name = name.trim();
    save(); render();
  }});
  document.getElementById("del-tab-btn").addEventListener("click", () => {{
    if (state.tabs.length <= 1) {{ alert("最後のタブは削除できません。"); return; }}
    if (!confirm("このタブを削除しますか？")) return;
    state.tabs.splice(state.active, 1);
    state.active = Math.max(0, state.active - 1);
    save(); render();
  }});
  document.getElementById("wl-export-txt").addEventListener("click", () => {{
    document.getElementById("wl-io").value = JSON.stringify(state);
  }});
  document.getElementById("wl-import-txt").addEventListener("click", () => {{
    try {{
      const parsed = JSON.parse(document.getElementById("wl-io").value);
      if (!parsed.tabs || !Array.isArray(parsed.tabs)) throw new Error("形式エラー");
      state = parsed;
      save(); render();
      alert("復元しました！");
    }} catch (e) {{ alert("復元に失敗しました: " + e.message); }}
  }});

  save();
  render();
}})();
</script>
</body>
</html>"""


def _build_portfolio_html() -> str:
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ポートフォリオ | 10年保有米株スクリーナー</title>
<style>{_COMMON_CSS}</style>
</head>
<body>
{_THEME_BAR_HTML}
<div class="container">
  {_nav_html("portfolio.html")}
  <h1>💼 ポートフォリオ</h1>
  <p style="color:var(--muted);margin-top:0;">保有ロット（買付株数・取得単価）を記録し、現在評価額・含み損益・構成比円グラフを自動計算します。</p>

  <div class="kpi-grid">
    <div class="kpi-box"><div class="kpi-lbl">総評価額</div><div class="kpi-val" id="kpi-val">$0.00</div></div>
    <div class="kpi-box"><div class="kpi-lbl">総取得コスト</div><div class="kpi-val" id="kpi-cost">$0.00</div></div>
    <div class="kpi-box"><div class="kpi-lbl">含み損益（$）</div><div class="kpi-val" id="kpi-pl">$0.00</div></div>
    <div class="kpi-box"><div class="kpi-lbl">含み損益率</div><div class="kpi-val" id="kpi-plpct">0.0%</div></div>
  </div>

  <div class="card">
    <h2>ロットを追加</h2>
    <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">
      <input type="text" id="lot-sym" placeholder="ティッカー (例: ADBE)" style="width:140px;">
      <input type="number" id="lot-qty" placeholder="株数" step="0.01" style="width:95px;">
      <input type="number" id="lot-price" placeholder="取得単価($ 空欄=現在値)" step="0.01" style="width:170px;">
      <input type="date" id="lot-date">
      <input type="text" id="lot-memo" placeholder="メモ" style="width:160px;">
      <button type="button" class="btn btn-primary" id="lot-add-btn">追加</button>
    </div>
  </div>

  <div class="card" style="display:flex;flex-wrap:wrap;gap:16px;align-items:flex-start;">
    <div style="flex:1 1 280px;">
      <h2>構成比グラフ</h2>
      <div style="margin-bottom:8px;display:flex;gap:6px;">
        <button type="button" class="btn btn-primary" id="pie-by-sym">銘柄別</button>
        <button type="button" class="btn" id="pie-by-sec">業種別</button>
      </div>
      <div id="pie-wrap" style="display:flex;flex-wrap:wrap;gap:14px;align-items:center;"></div>
    </div>
    <div style="flex:2 1 420px;">
      <h2>保有銘柄サマリー（加重平均）</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th>軍</th><th>コード</th><th>業種</th><th class="num">株数</th><th class="num">平均単価</th><th class="num">現在値</th><th class="num">評価額</th><th class="num">損益</th><th class="num">比率</th></tr></thead>
          <tbody id="pf-sum-tbody"></tbody>
        </table>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>登録ロット一覧</h2>
    <div class="table-wrap">
      <table>
        <thead><tr><th>日付</th><th>コード</th><th class="num">株数</th><th class="num">取得単価</th><th>メモ</th><th>操作</th></tr></thead>
        <tbody id="pf-lots-tbody"></tbody>
      </table>
    </div>
  </div>
</div>

<script>
{_THEME_JS}
(async () => {{
  let stockMap = {{}};
  try {{
    const res = await fetch("ranking.json");
    const data = await res.json();
    (data.items || []).forEach(it => {{ stockMap[it.symbol.toUpperCase()] = it; }});
  }} catch (e) {{ console.warn("ranking.json 読込失敗", e); }}

  let lots = [];
  try {{ lots = JSON.parse(localStorage.getItem("pf_lots_long_us") || "[]"); }} catch {{}}
  let pieMode = "sym";

  function save() {{
    localStorage.setItem("pf_lots_long_us", JSON.stringify(lots));
    const syms = [...new Set(lots.map(l => l.sym))];
    localStorage.setItem("pf_sel_codes_long_us", JSON.stringify(syms));
  }}

  const COLORS = ["#2563eb","#16a34a","#d97706","#dc2626","#7c3aed","#0891b2","#db2777","#65a30d","#ea580c","#4f46e5"];
  function renderPie(entries, total) {{
    const wrap = document.getElementById("pie-wrap");
    if (!entries.length || total <= 0) {{
      wrap.innerHTML = '<div style="color:var(--muted);">ロットを追加すると円グラフが表示されます。</div>';
      return;
    }}
    let acc = 0;
    const paths = [];
    const legend = [];
    entries.forEach(([label, val], i) => {{
      const pct = val / total;
      const start = acc * 2 * Math.PI - Math.PI / 2;
      acc += pct;
      const end = acc * 2 * Math.PI - Math.PI / 2;
      const col = COLORS[i % COLORS.length];
      if (pct >= 0.9999) {{
        paths.push(`<circle cx="80" cy="80" r="70" fill="${{col}}" />`);
      }} else {{
        const x1 = 80 + 70 * Math.cos(start), y1 = 80 + 70 * Math.sin(start);
        const x2 = 80 + 70 * Math.cos(end), y2 = 80 + 70 * Math.sin(end);
        const large = pct > 0.5 ? 1 : 0;
        paths.push(`<path d="M80,80 L${{x1.toFixed(1)}},${{y1.toFixed(1)}} A70,70 0 ${{large}},1 ${{x2.toFixed(1)}},${{y2.toFixed(1)}} Z" fill="${{col}}" />`);
      }}
      legend.push(`<div style="display:flex;align-items:center;gap:6px;font-size:12px;"><span style="width:10px;height:10px;border-radius:2px;background:${{col}};display:inline-block;"></span><span>${{label}}: <strong>${{(pct*100).toFixed(1)}}%</strong></span></div>`);
    }});
    wrap.innerHTML = `<svg width="160" height="160" viewBox="0 0 160 160">${{paths.join("")}}<circle cx="80" cy="80" r="34" fill="var(--card)" /></svg><div style="display:flex;flex-direction:column;gap:4px;">${{legend.join("")}}</div>`;
  }}

  function render() {{
    const lotsBody = document.getElementById("pf-lots-tbody");
    lotsBody.innerHTML = "";
    if (!lots.length) {{
      lotsBody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:14px;">登録ロットがありません。</td></tr>';
    }}
    lots.forEach((l, idx) => {{
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${{l.date || "-"}}</td><td><a href="reports/${{l.sym}}.html"><strong>${{l.sym}}</strong></a></td><td class="num">${{l.qty}}</td><td class="num">$${{Number(l.price).toFixed(2)}}</td><td>${{l.memo || ""}}</td><td><button type="button" class="btn btn-danger" style="padding:2px 7px;">削除</button></td>`;
      tr.querySelector("button").addEventListener("click", () => {{ lots.splice(idx, 1); save(); render(); }});
      lotsBody.appendChild(tr);
    }});

    const agg = {{}};
    lots.forEach(l => {{
      if (!agg[l.sym]) agg[l.sym] = {{ qty: 0, cost: 0 }};
      agg[l.sym].qty += Number(l.qty);
      agg[l.sym].cost += Number(l.qty) * Number(l.price);
    }});

    let totalVal = 0, totalCost = 0;
    const rows = [];
    const secTotals = {{}};
    Object.entries(agg).forEach(([sym, info]) => {{
      if (info.qty <= 0) return;
      const s = stockMap[sym];
      const cur = (s && s.close != null) ? s.close : (info.cost / info.qty);
      const val = info.qty * cur;
      const pl = val - info.cost;
      const sec = s ? s.sector_ja : "その他";
      totalVal += val;
      totalCost += info.cost;
      secTotals[sec] = (secTotals[sec] || 0) + val;
      rows.push({{ sym, s, sec, qty: info.qty, avg: info.cost / info.qty, cur, val, pl }});
    }});
    rows.sort((a, b) => b.val - a.val);

    const totalPl = totalVal - totalCost;
    const plPct = totalCost > 0 ? (totalPl / totalCost * 100) : 0;
    document.getElementById("kpi-val").textContent = "$" + totalVal.toFixed(2);
    document.getElementById("kpi-cost").textContent = "$" + totalCost.toFixed(2);
    const plEl = document.getElementById("kpi-pl");
    plEl.textContent = (totalPl >= 0 ? "+" : "") + "$" + totalPl.toFixed(2);
    plEl.className = "kpi-val " + (totalPl >= 0 ? "pos" : "neg");
    const pctEl = document.getElementById("kpi-plpct");
    pctEl.textContent = (plPct >= 0 ? "+" : "") + plPct.toFixed(1) + "%";
    pctEl.className = "kpi-val " + (plPct >= 0 ? "pos" : "neg");

    const sumBody = document.getElementById("pf-sum-tbody");
    sumBody.innerHTML = "";
    rows.forEach(r => {{
      const tr = document.createElement("tr");
      const plCls = r.pl >= 0 ? "pos" : "neg";
      const ratio = totalVal > 0 ? (r.val / totalVal * 100) : 0;
      tr.innerHTML = `
        <td>${{r.s ? `<span class="tier-badge t${{r.s.tier}}">${{r.s.tier}}軍</span>` : "-"}}</td>
        <td><a href="reports/${{r.sym}}.html"><strong>${{r.sym}}</strong></a></td>
        <td>${{r.sec}}</td>
        <td class="num">${{r.qty}}</td>
        <td class="num">$${{r.avg.toFixed(2)}}</td>
        <td class="num">$${{r.cur.toFixed(2)}}</td>
        <td class="num"><strong>$${{r.val.toFixed(2)}}</strong></td>
        <td class="num ${{plCls}}">${{r.pl >= 0 ? "+" : ""}}$${{r.pl.toFixed(2)}}</td>
        <td class="num">${{ratio.toFixed(1)}}%</td>
      `;
      sumBody.appendChild(tr);
    }});

    const pieEntries = pieMode === "sym"
      ? rows.map(r => [r.sym, r.val])
      : Object.entries(secTotals).sort((a, b) => b[1] - a[1]);
    renderPie(pieEntries, totalVal);
  }}

  document.getElementById("lot-add-btn").addEventListener("click", () => {{
    const sym = document.getElementById("lot-sym").value.trim().toUpperCase();
    const qty = parseFloat(document.getElementById("lot-qty").value);
    let price = parseFloat(document.getElementById("lot-price").value);
    const date = document.getElementById("lot-date").value || new Date().toISOString().slice(0, 10);
    const memo = document.getElementById("lot-memo").value.trim();
    if (!sym || isNaN(qty) || qty <= 0) {{ alert("ティッカーと株数を入力してください。"); return; }}
    if (isNaN(price)) {{
      const s = stockMap[sym];
      if (s && s.close != null) price = s.close;
      else {{ alert("現在値が取得できない銘柄のため、取得単価を入力してください。"); return; }}
    }}
    lots.push({{ sym, qty, price, date, memo }});
    document.getElementById("lot-sym").value = "";
    document.getElementById("lot-qty").value = "";
    document.getElementById("lot-price").value = "";
    document.getElementById("lot-memo").value = "";
    save(); render();
  }});

  document.getElementById("pie-by-sym").addEventListener("click", () => {{
    pieMode = "sym";
    document.getElementById("pie-by-sym").className = "btn btn-primary";
    document.getElementById("pie-by-sec").className = "btn";
    render();
  }});
  document.getElementById("pie-by-sec").addEventListener("click", () => {{
    pieMode = "sec";
    document.getElementById("pie-by-sec").className = "btn btn-primary";
    document.getElementById("pie-by-sym").className = "btn";
    render();
  }});

  render();
}})();
</script>
</body>
</html>"""


def _build_guide_html() -> str:
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>使い方・見方 | 10年保有米株スクリーナー</title>
<style>{_COMMON_CSS}</style>
</head>
<body>
{_THEME_BAR_HTML}
<div class="container">
  {_nav_html("guide.html")}
  <h1>使い方・見方（スコア定義とルール）</h1>

  <div class="card">
    <h2>1. 2つの総合スコア（各 0〜110点）</h2>
    <ul>
      <li><strong>ファンダ点（10年保有できる事業の強さ）</strong>：配当利回りは採点に含めず、本業の成長力・財務健全性・キャッシュ創出力だけで評価します。
        <ul>
          <li><strong>一般企業</strong>：業績(重み0.28) ＋ 財務(0.27) ＋ キャッシュフロー(0.15) を正規化</li>
          <li><strong>銀行・保険・大手証券</strong>：ROE・増収率・EPS成長率・利益安定度の各25%</li>
          <li><strong>REIT</strong>：FFO成長率・増収率・FFO安定度・利払い余裕度の各25%</li>
        </ul>
      </li>
      <li><strong>買い時スコア（今の株価の割安度）</strong>：EV/EBIT（対業種中央値）、FCF利回り、PER割安度、PBR割安度（※情報技術・コミュニケーションはPBR除外）から算出します。</li>
    </ul>
  </div>

  <div class="card">
    <h2>2. 年次採点と「直近四半期の急減速ブレーキ」</h2>
    <p>基本の指標点は季節変動（繁忙期・閑散期）のノイズを避けるため<strong>年次（通期）データ</strong>で算出します。一方で足元の業績悪化を見逃さないよう、<strong>直近四半期の売上YoYが年率トレンドを5pt以上下回り、かつ営業利益または純利益がYoYマイナス</strong>の場合に「⚠急減速」フラグを立て、業績スコアへペナルティを適用します。</p>
  </div>

  <div class="card">
    <h2>3. 軍分け（1軍〜3軍）・業種級・カバレッジ</h2>
    <ul>
      <li><strong>1軍 / 2軍 / 3軍</strong>：各GICSセクター内でファンダ点順に、上位25%＝1軍、次45%＝2軍、下位30%＝3軍に分類します（カバレッジ「低」は2軍上限、絶対ファンダ点75点以上は3軍に落とさない下限補正あり）。</li>
      <li><strong>業種級（A / B / C）</strong>：セクター内のファンダ点中央値により判定します。</li>
      <li><strong>オプション取引向け参考シグナル</strong>：<code>ranking.json</code> および個別レポートには、強気戦略向けの「1軍＆急減速なし」フラグと、プット買い等の弱気検討向けの「弱気警戒スコア」も併記しています。</li>
    </ul>
  </div>

  <div class="card">
    <h2>4. データ保存とバックアップ</h2>
    <p>ウォッチリスト・ポートフォリオ・配色設定はすべてブラウザの <code>localStorage</code> に保存され、外部サーバーへ送信されません。別PCへ移行する場合は、トップページの「バックアップ（CSV）」から一括出力／復元をご利用ください。</p>
  </div>
</div>
<script>{_THEME_JS}</script>
</body>
</html>"""


def _build_terms_html() -> str:
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>利用規約・免責事項 | 10年保有米株スクリーナー</title>
<style>{_COMMON_CSS}</style>
</head>
<body>
{_THEME_BAR_HTML}
<div class="container">
  {_nav_html("terms.html")}
  <h1>利用規約・免責事項</h1>
  <div class="card">
    <h2>免責事項</h2>
    <ul>
      <li>本サイトおよび出力データ（<code>ranking.json</code> 等）は、個人の学習・研究および情報整理を目的として自動生成されたものであり、特定の有価証券の売買や投資戦略を推奨する投資助言ではありません。</li>
      <li>掲載している株価・財務・アナリスト予想等のデータは Yahoo Finance（<code>yfinance</code>）および Wikipedia 等の公開情報をもとに取得していますが、その正確性・完全性・最新性を保証するものではありません。</li>
      <li>本サイトの情報や自動生成されたスコアをもとにした投資判断・自動売買等によって生じたいかなる損失についても、一切の責任を負いかねます。最終的な判断はご自身の責任で行ってください。</li>
    </ul>
  </div>
</div>
<script>{_THEME_JS}</script>
</body>
</html>"""


def _build_options_html() -> str:
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>オプション取引候補スクリーナー | 10年保有米株スクリーナー</title>
<style>
{_COMMON_CSS}
.badge-warn {{
  display: inline-block; padding: 1px 6px; border-radius: 4px; font-size: 11px; font-weight: 700;
  background: var(--wbg); color: var(--wfg); border: 1px solid var(--wbd);
}}
.badge-bull {{
  display: inline-block; padding: 1px 6px; border-radius: 4px; font-size: 11px; font-weight: 700;
  background: var(--t1bg); color: var(--t1);
}}
.badge-bear {{
  display: inline-block; padding: 1px 6px; border-radius: 4px; font-size: 11px; font-weight: 700;
  background: color-mix(in srgb, var(--neg) 14%, var(--card)); color: var(--neg);
}}
.flt-row {{
  display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 12px;
  padding: 10px 12px; background: var(--field); border: 1px solid var(--line); border-radius: 8px;
}}
.flt-row label {{ display: inline-flex; align-items: center; gap: 5px; font-size: 12px; }}
.sub-desc {{ font-size: 12px; color: var(--muted); margin: 0 0 10px; }}
</style>
</head>
<body>
{_THEME_BAR_HTML}
<div class="container">
  {_nav_html("options.html")}
  <h1>🎯 オプション取引候補スクリーナー</h1>
  <p class="sub-desc" id="opt-meta">S&amp;P 500 構成銘柄から、強気戦略（CSP・カバードコール向け）と弱気警戒（プット買い等の逆スクリーニング向け）を自動抽出します。</p>

  <div class="kpi-grid">
    <div class="kpi-box"><div class="kpi-lbl">🟢 強気1軍候補（急減速なし）</div><div class="kpi-val pos" id="kpi-bull-all">-</div></div>
    <div class="kpi-box"><div class="kpi-lbl">💎 強気×割安（買い時70以上）</div><div class="kpi-val pos" id="kpi-bull-val">-</div></div>
    <div class="kpi-box"><div class="kpi-lbl">🔴 弱気警戒候補（警戒55以上）</div><div class="kpi-val neg" id="kpi-bear-all">-</div></div>
    <div class="kpi-box"><div class="kpi-lbl">⚠ 直近四半期 急減速銘柄</div><div class="kpi-val" id="kpi-decel">-</div></div>
  </div>

  <div class="card">
    <div class="tabs-bar">
      <button type="button" class="tab-btn active" id="tab-bull">🟢 強気候補（1軍・急減速なし）</button>
      <button type="button" class="tab-btn" id="tab-bear">🔴 弱気警戒・逆スクリーニング</button>
      <span style="flex:1"></span>
      <button type="button" class="btn" id="opt-copy-tickers">📋 ティッカー一覧コピー</button>
      <button type="button" class="btn" id="opt-csv-btn">⬇ CSV出力</button>
    </div>

    <div class="flt-row" id="flt-bull">
      <label>買い時スコア 下限: <input type="number" id="bull-min-buy" value="60" min="0" max="110" step="5" style="width:70px;"></label>
      <label>ファンダ点 下限: <input type="number" id="bull-min-q" value="0" min="0" max="110" step="5" style="width:70px;"></label>
      <label>並び替え:
        <select id="bull-sort">
          <option value="buy_desc">買い時スコア 高い順（CSP好機）</option>
          <option value="q_desc">ファンダ点 高い順</option>
          <option value="ret1y_asc">1Y騰落率 低い順（押し目）</option>
          <option value="ret1m_asc">1M騰落率 低い順（直近調整）</option>
        </select>
      </label>
      <label>業種: <select id="bull-sec"><option value="">すべて</option></select></label>
      <input type="text" id="bull-kw" placeholder="ティッカー・銘柄検索" style="width:160px;">
      <span style="color:var(--muted);font-size:12px;" id="bull-count">0件</span>
    </div>

    <div class="flt-row" id="flt-bear" style="display:none;">
      <label>弱気警戒スコア 下限: <input type="number" id="bear-min-score" value="50" min="0" max="100" step="5" style="width:70px;"></label>
      <label><input type="checkbox" id="bear-only-decel"> ⚠急減速のみ表示</label>
      <label>並び替え:
        <select id="bear-sort">
          <option value="bear_desc">弱気警戒スコア 高い順</option>
          <option value="q_asc">ファンダ点 低い順</option>
          <option value="buy_asc">買い時スコア 低い順（割高）</option>
          <option value="ret1m_desc">1M騰落率 高い順（過熱・反落警戒）</option>
        </select>
      </label>
      <label>業種: <select id="bear-sec"><option value="">すべて</option></select></label>
      <input type="text" id="bear-kw" placeholder="ティッカー・銘柄検索" style="width:160px;">
      <span style="color:var(--muted);font-size:12px;" id="bear-count">0件</span>
    </div>

    <div class="table-wrap">
      <table>
        <thead id="opt-thead"></thead>
        <tbody id="opt-tbody"><tr><td colspan="12" style="text-align:center;color:var(--muted);padding:24px;">データを読み込み中...</td></tr></tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <h2>抽出ロジックと活用メモ</h2>
    <ul style="margin:6px 0 0;padding-left:20px;">
      <li><strong>🟢 強気候補（CSP・カバードコール向け）</strong>：各セクター内上位25%の<strong>1軍</strong>かつ<strong>直近四半期の急減速フラグなし</strong>の銘柄を抽出しています。「買い時スコア」が高い銘柄ほど割安水準にあり、キャッシュセキュアド・プット（CSP）等で下値を拾う候補になります。</li>
      <li><strong>🔴 弱気警戒スコア（0〜100点・逆スクリーニング）</strong>：<code>(100 - ファンダ点) × 0.5 + (100 - 買い時スコア) × 0.3 + 急減速ペナルティ(+20)</code> で算出。事業地力が弱い・割高・足元の業績が急減速している銘柄ほど高スコアになります。</li>
      <li><strong>⚠️ 実トレード前の確認</strong>：個別レポート（ティッカーをクリック）で<strong>次回決算予定日</strong>や<strong>RSI / 株価推移</strong>を確認し、決算またぎのIVクラッシュや流動性（出来高・スプレッド）にご注意ください。</li>
    </ul>
  </div>
</div>
<script>{_THEME_JS}</script>
<script>
(async () => {{
  const res = await fetch("ranking.json");
  const data = await res.json();
  const items = data.items || [];
  const metaEl = document.getElementById("opt-meta");
  if (data.generated_at) {{
    metaEl.textContent = "最終更新: " + data.generated_at + " ／ 対象: " + items.length + " 銘柄（S&P 500）。強気戦略（CSP等）と弱気警戒（逆スクリーニング）を自動抽出します。";
  }}

  const bullAll = items.filter(x => x.option_signals && x.option_signals.bull_tier1);
  const bullVal = bullAll.filter(x => (x.buy_score ?? -1) >= 70);
  const bearAll = items.filter(x => ((x.option_signals && x.option_signals.bear_watch_score) ?? 0) >= 55);
  const decelAll = items.filter(x => x.rapid_decel);

  document.getElementById("kpi-bull-all").textContent = bullAll.length + " 銘柄";
  document.getElementById("kpi-bull-val").textContent = bullVal.length + " 銘柄";
  document.getElementById("kpi-bear-all").textContent = bearAll.length + " 銘柄";
  document.getElementById("kpi-decel").textContent = decelAll.length + " 銘柄";

  const sectors = [...new Set(items.map(x => x.sector_ja).filter(Boolean))].sort();
  ["bull-sec", "bear-sec"].forEach(id => {{
    const sel = document.getElementById(id);
    sectors.forEach(s => {{
      const o = document.createElement("option");
      o.value = s; o.textContent = s;
      sel.appendChild(o);
    }});
  }});

  let mode = "bull";
  let currentRows = [];

  const fmt = (v, d = 1) => (v == null || Number.isNaN(v)) ? "-" : Number(v).toFixed(d);
  const fmtPct = (v) => (v == null || Number.isNaN(v)) ? "-" : ((v > 0 ? "+" : "") + Number(v).toFixed(1) + "%");
  const retCls = (v) => (v == null) ? "" : (v > 0 ? "pos" : (v < 0 ? "neg" : ""));

  function getWlSet() {{
    try {{ return new Set(JSON.parse(localStorage.getItem("wl_codes_long_us") || "[]")); }} catch {{ return new Set(); }}
  }}
  function toggleWl(sym) {{
    const s = getWlSet();
    if (s.has(sym)) s.delete(sym); else s.add(sym);
    localStorage.setItem("wl_codes_long_us", JSON.stringify([...s]));
    render();
  }}

  function render() {{
    const thead = document.getElementById("opt-thead");
    const tbody = document.getElementById("opt-tbody");
    const wlSet = getWlSet();
    tbody.innerHTML = "";

    if (mode === "bull") {{
      const minBuy = parseFloat(document.getElementById("bull-min-buy").value) || 0;
      const minQ = parseFloat(document.getElementById("bull-min-q").value) || 0;
      const sec = document.getElementById("bull-sec").value;
      const kw = document.getElementById("bull-kw").value.trim().toLowerCase();
      const sort = document.getElementById("bull-sort").value;

      currentRows = bullAll.filter(x => {{
        if ((x.buy_score ?? -1) < minBuy) return false;
        if ((x.quality_score ?? -1) < minQ) return false;
        if (sec && x.sector_ja !== sec) return false;
        if (kw && !((x.symbol || "").toLowerCase().includes(kw) || (x.name || "").toLowerCase().includes(kw))) return false;
        return true;
      }});
      currentRows.sort((a, b) => {{
        if (sort === "q_desc") return (b.quality_score ?? -1) - (a.quality_score ?? -1);
        if (sort === "ret1y_asc") return ((a.returns && a.returns.Y) ?? 9999) - ((b.returns && b.returns.Y) ?? 9999);
        if (sort === "ret1m_asc") return ((a.returns && a.returns.M) ?? 9999) - ((b.returns && b.returns.M) ?? 9999);
        return (b.buy_score ?? -1) - (a.buy_score ?? -1);
      }});
      document.getElementById("bull-count").textContent = currentRows.length + "件";

      thead.innerHTML = '<tr><th class="num">#</th><th>軍</th><th>コード</th><th>銘柄</th><th>業種</th><th class="num">終値</th><th class="num">1M騰落</th><th class="num">1Y騰落</th><th class="num">ファンダ点</th><th class="num">買い時</th><th class="num">業績/財務/CF</th><th>☆WL</th></tr>';

      if (!currentRows.length) {{
        tbody.innerHTML = '<tr><td colspan="12" style="text-align:center;color:var(--muted);padding:24px;">条件に一致する銘柄がありません。下限スコアを下げてみてください。</td></tr>';
        return;
      }}
      currentRows.forEach((x, i) => {{
        const tr = document.createElement("tr");
        const r1m = x.returns ? x.returns.M : null;
        const r1y = x.returns ? x.returns.Y : null;
        const saved = wlSet.has(x.symbol);
        tr.innerHTML = `
          <td class="num">${{i + 1}}</td>
          <td><span class="tier-badge t${{x.tier}}">${{x.tier}}軍</span></td>
          <td><a href="reports/${{x.symbol}}.html"><strong>${{x.symbol}}</strong></a></td>
          <td>${{x.name || ""}} <span class="badge-bull">強気1軍</span></td>
          <td>${{x.sector_ja || "-"}}</td>
          <td class="num">${{x.close != null ? "$" + fmt(x.close, 2) : "-"}}</td>
          <td class="num ${{retCls(r1m)}}">${{fmtPct(r1m)}}</td>
          <td class="num ${{retCls(r1y)}}">${{fmtPct(r1y)}}</td>
          <td class="num"><strong>${{fmt(x.quality_score)}}</strong></td>
          <td class="num pos"><strong>${{fmt(x.buy_score)}}</strong></td>
          <td class="num" style="color:var(--muted)">${{fmt(x.perf_score, 0)}} / ${{fmt(x.fin_score, 0)}} / ${{fmt(x.cf_score, 0)}}</td>
          <td><button type="button" class="btn wl-btn" data-sym="${{x.symbol}}">${{saved ? "★登録済" : "☆追加"}}</button></td>
        `;
        tbody.appendChild(tr);
      }});
    }} else {{
      const minBear = parseFloat(document.getElementById("bear-min-score").value) || 0;
      const onlyDecel = document.getElementById("bear-only-decel").checked;
      const sec = document.getElementById("bear-sec").value;
      const kw = document.getElementById("bear-kw").value.trim().toLowerCase();
      const sort = document.getElementById("bear-sort").value;

      currentRows = items.filter(x => {{
        const bs = (x.option_signals && x.option_signals.bear_watch_score) ?? 0;
        if (bs < minBear) return false;
        if (onlyDecel && !x.rapid_decel) return false;
        if (sec && x.sector_ja !== sec) return false;
        if (kw && !((x.symbol || "").toLowerCase().includes(kw) || (x.name || "").toLowerCase().includes(kw))) return false;
        return true;
      }});
      currentRows.sort((a, b) => {{
        const ba = (a.option_signals && a.option_signals.bear_watch_score) ?? 0;
        const bb = (b.option_signals && b.option_signals.bear_watch_score) ?? 0;
        if (sort === "q_asc") return (a.quality_score ?? 999) - (b.quality_score ?? 999);
        if (sort === "buy_asc") return (a.buy_score ?? 999) - (b.buy_score ?? 999);
        if (sort === "ret1m_desc") return ((b.returns && b.returns.M) ?? -9999) - ((a.returns && a.returns.M) ?? -9999);
        return bb - ba;
      }});
      document.getElementById("bear-count").textContent = currentRows.length + "件";

      thead.innerHTML = '<tr><th class="num">#</th><th>軍</th><th>コード</th><th>銘柄</th><th>業種</th><th class="num">終値</th><th class="num">1M騰落</th><th class="num">1Y騰落</th><th class="num">弱気警戒点</th><th class="num">ファンダ点</th><th class="num">買い時</th><th>☆WL</th></tr>';

      if (!currentRows.length) {{
        tbody.innerHTML = '<tr><td colspan="12" style="text-align:center;color:var(--muted);padding:24px;">条件に一致する銘柄がありません。</td></tr>';
        return;
      }}
      currentRows.forEach((x, i) => {{
        const tr = document.createElement("tr");
        const bs = (x.option_signals && x.option_signals.bear_watch_score) ?? 0;
        const r1m = x.returns ? x.returns.M : null;
        const r1y = x.returns ? x.returns.Y : null;
        const saved = wlSet.has(x.symbol);
        const warn = x.rapid_decel ? ' <span class="badge-warn">⚠急減速</span>' : '';
        tr.innerHTML = `
          <td class="num">${{i + 1}}</td>
          <td><span class="tier-badge t${{x.tier}}">${{x.tier}}軍</span></td>
          <td><a href="reports/${{x.symbol}}.html"><strong>${{x.symbol}}</strong></a></td>
          <td>${{x.name || ""}}${{warn}}</td>
          <td>${{x.sector_ja || "-"}}</td>
          <td class="num">${{x.close != null ? "$" + fmt(x.close, 2) : "-"}}</td>
          <td class="num ${{retCls(r1m)}}">${{fmtPct(r1m)}}</td>
          <td class="num ${{retCls(r1y)}}">${{fmtPct(r1y)}}</td>
          <td class="num neg"><strong>${{fmt(bs)}}</strong></td>
          <td class="num">${{fmt(x.quality_score)}}</td>
          <td class="num">${{fmt(x.buy_score)}}</td>
          <td><button type="button" class="btn wl-btn" data-sym="${{x.symbol}}">${{saved ? "★登録済" : "☆追加"}}</button></td>
        `;
        tbody.appendChild(tr);
      }});
    }}

    tbody.querySelectorAll(".wl-btn").forEach(btn => {{
      btn.addEventListener("click", () => toggleWl(btn.dataset.sym));
    }});
  }}

  document.getElementById("tab-bull").addEventListener("click", () => {{
    mode = "bull";
    document.getElementById("tab-bull").classList.add("active");
    document.getElementById("tab-bear").classList.remove("active");
    document.getElementById("flt-bull").style.display = "flex";
    document.getElementById("flt-bear").style.display = "none";
    render();
  }});
  document.getElementById("tab-bear").addEventListener("click", () => {{
    mode = "bear";
    document.getElementById("tab-bear").classList.add("active");
    document.getElementById("tab-bull").classList.remove("active");
    document.getElementById("flt-bull").style.display = "none";
    document.getElementById("flt-bear").style.display = "flex";
    render();
  }});

  ["bull-min-buy","bull-min-q","bull-sort","bull-sec","bull-kw","bear-min-score","bear-only-decel","bear-sort","bear-sec","bear-kw"].forEach(id => {{
    const el = document.getElementById(id);
    el.addEventListener("input", render);
    el.addEventListener("change", render);
  }});

  document.getElementById("opt-copy-tickers").addEventListener("click", async () => {{
    const list = currentRows.map(x => x.symbol).join(", ");
    if (!list) {{ alert("コピーする銘柄がありません。"); return; }}
    await navigator.clipboard.writeText(list);
    alert(currentRows.length + "件のティッカーをクリップボードにコピーしました。");
  }});

  document.getElementById("opt-csv-btn").addEventListener("click", () => {{
    const headers = mode === "bull"
      ? ["順位","軍","コード","銘柄","業種","終値","1M騰落%","1Y騰落%","ファンダ点","買い時","業績","財務","CF"]
      : ["順位","軍","コード","銘柄","業種","終値","1M騰落%","1Y騰落%","弱気警戒点","ファンダ点","買い時","急減速"];
    const rows = [headers];
    currentRows.forEach((x, i) => {{
      const r1m = x.returns ? (x.returns.M ?? "") : "";
      const r1y = x.returns ? (x.returns.Y ?? "") : "";
      if (mode === "bull") {{
        rows.push([i+1, x.tier+"軍", x.symbol, x.name||"", x.sector_ja||"", x.close??"", r1m, r1y, x.quality_score??"", x.buy_score??"", x.perf_score??"", x.fin_score??"", x.cf_score??""]);
      }} else {{
        const bs = (x.option_signals && x.option_signals.bear_watch_score) ?? "";
        rows.push([i+1, x.tier+"軍", x.symbol, x.name||"", x.sector_ja||"", x.close??"", r1m, r1y, bs, x.quality_score??"", x.buy_score??"", x.rapid_decel ? "あり" : "なし"]);
      }}
    }});
    const csv = rows.map(r => r.map(v => '"' + String(v).replace(/"/g, '""') + '"').join(",")).join("\\r\\n");
    const blob = new Blob(["\\uFEFF" + csv], {{ type: "text/csv;charset=utf-8;" }});
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "us_options_" + mode + "_" + new Date().toISOString().slice(0, 10) + ".csv";
    a.click();
  }});

  render();
}})();
</script>
</body>
</html>"""


def generate_aux_pages(dist_dir: Path) -> None:
    """options.html, watchlist.html, portfolio.html, guide.html, terms.html を生成する。"""
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "options.html").write_text(_build_options_html(), encoding="utf-8")
    (dist_dir / "watchlist.html").write_text(_build_watchlist_html(), encoding="utf-8")
    (dist_dir / "portfolio.html").write_text(_build_portfolio_html(), encoding="utf-8")
    (dist_dir / "guide.html").write_text(_build_guide_html(), encoding="utf-8")
    (dist_dir / "terms.html").write_text(_build_terms_html(), encoding="utf-8")
