"""採点済みデータから ranking.json と静的HTML（index.html）を生成するモジュール。"""

from __future__ import annotations

import html
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .fetch_sp500 import SECTOR_ORDER

JST = timezone(timedelta(hours=9))


def _fmt_num(val: float | None, digits: int = 1, suffix: str = "") -> str:
    if val is None:
        return "-"
    return f"{val:.{digits}f}{suffix}"


def _fmt_pct(val: float | None, digits: int = 1) -> str:
    if val is None:
        return "-"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.{digits}f}%"


def _score_cls(val: float | None) -> str:
    if val is None:
        return ""
    if val >= 70:
        return "sc-good"
    if val >= 50:
        return "sc-warn"
    return "sc-weak"


def _ret_cls(val: float | None) -> str:
    if val is None:
        return ""
    if val > 0:
        return "pos"
    if val < 0:
        return "neg"
    return ""


def _build_row_html(item: dict[str, Any], include_sector_col: bool = False) -> str:
    m = item["metrics"]
    g = item["grades"]
    r = item.get("returns", {})
    tier = item["tier"]
    tier_cls = f"t{tier}"
    sym = html.escape(item["symbol"])
    name = html.escape(item["name"])
    sec_ja = html.escape(item["sector_ja"])

    badges = []
    if item.get("rapid_decel"):
        badges.append('<span class="badge-warn" title="直近四半期で急減速フラグあり">⚠急減速</span>')
    if item["model"] == "financial":
        badges.append('<span class="badge-model" title="金融専用スコアで採点">金融</span>')
    elif item["model"] == "reit":
        badges.append('<span class="badge-model" title="REIT専用(FFO)スコアで採点">REIT</span>')
    badge_html = " ".join(badges)

    # data-* 属性（詳細スクリーナー用）
    attrs = {
        "data-sym": sym,
        "data-name": name,
        "data-sec": sec_ja,
        "data-tier": str(tier),
        "data-model": item["model"],
        "data-secgrade": item.get("sector_grade", "B"),
        "data-cov": item.get("coverage", "中"),
        "data-decel": "1" if item.get("rapid_decel") else "0",
        "data-q": "" if item["quality_score"] is None else str(item["quality_score"]),
        "data-b": "" if item["buy_score"] is None else str(item["buy_score"]),
        "data-close": "" if item["close"] is None else str(item["close"]),
        "data-mcap": "" if item["market_cap_b"] is None else str(item["market_cap_b"]),
        "data-rev": "" if m["rev_cagr"] is None else str(m["rev_cagr"]),
        "data-eps": "" if m["eps_cagr"] is None else str(m["eps_cagr"]),
        "data-margin": "" if m["op_margin"] is None else str(m["op_margin"]),
        "data-fcfy": "" if m["fcf_yield"] is None else str(m["fcf_yield"]),
        "data-roe": "" if m["roe"] is None else str(m["roe"]),
        "data-roa": "" if m["roa"] is None else str(m["roa"]),
        "data-ocfpos": "1" if m["ocf_positive"] else "0",
        "data-fcfpos": "1" if m["fcf_positive"] else "0",
        "data-g-rev": g.get("rev") or "",
        "data-g-eps": g.get("eps") or "",
        "data-g-margin": g.get("margin") or "",
        "data-g-de": g.get("de") or "",
        "data-g-nde": g.get("nde") or "",
        "data-g-docf": g.get("docf") or "",
        "data-g-icov": g.get("icov") or "",
        "data-g-fcfpay": g.get("fcf_pay") or "",
        "data-g-fcfy": g.get("fcf_yield") or "",
        "data-g-evebit": g.get("ev_ebit") or "",
        "data-g-perrng": g.get("per_range") or "",
        "data-g-perrel": g.get("per_rel") or "",
        "data-g-pbrrel": g.get("pbr_rel") or "",
        "data-g-roe": g.get("roe") or "",
        "data-g-roa": g.get("roa") or "",
    }
    attr_str = " ".join(f'{k}="{html.escape(v)}"' for k, v in attrs.items())

    sec_td = f'<td class="col-sec">{sec_ja}</td>' if include_sector_col else ""

    ret_cells = ""
    for k in ["D", "W", "M", "3M", "6M", "9M", "Y"]:
        rv = r.get(k)
        cls = _ret_cls(rv)
        extra_cls = "ret-y" if k == "Y" else "ret-extra hidden-col"
        ret_cells += f'<td class="num {extra_cls} {cls}" data-sort="{"" if rv is None else rv}">{_fmt_pct(rv)}</td>'

    return f"""<tr class="stock-row" {attr_str}>
  <td class="chk-col"><input type="checkbox" class="wl-chk" value="{sym}" aria-label="ウォッチリスト選択"></td>
  <td class="chk-col"><input type="checkbox" class="pf-chk" value="{sym}" aria-label="ポートフォリオ選択"></td>
  <td><span class="tier-badge {tier_cls}">{tier}軍</span></td>
  <td class="code-col"><a href="reports/{sym}.html"><strong>{sym}</strong></a></td>
  <td class="name-col"><a href="reports/{sym}.html" class="stock-name">{name}</a> {badge_html}</td>
  {sec_td}
  <td class="num" data-sort="{"" if item["close"] is None else item["close"]}">{_fmt_num(item["close"], 2, "$") if item["close"] is not None else "-"}</td>
  {ret_cells}
  <td class="num score-cell {_score_cls(item["quality_score"])}" data-sort="{"" if item["quality_score"] is None else item["quality_score"]}">{_fmt_num(item["quality_score"], 1)}</td>
  <td class="num" data-sort="{"" if item["perf_score"] is None else item["perf_score"]}">{_fmt_num(item["perf_score"], 1)}</td>
  <td class="num" data-sort="{"" if item["fin_score"] is None else item["fin_score"]}">{_fmt_num(item["fin_score"], 1)}</td>
  <td class="num" data-sort="{"" if item["cf_score"] is None else item["cf_score"]}">{_fmt_num(item["cf_score"], 1)}</td>
  <td class="num score-cell {_score_cls(item["buy_score"])}" data-sort="{"" if item["buy_score"] is None else item["buy_score"]}">{_fmt_num(item["buy_score"], 1)}</td>
  <td class="num" data-sort="{"" if m["div_yield"] is None else m["div_yield"]}">{_fmt_num(m["div_yield"], 2, "%")}</td>
  <td class="num" data-sort="{"" if m["roe"] is None else m["roe"]}">{_fmt_num(m["roe"], 1, "%")}</td>
  <td class="num" data-sort="{"" if m["roa"] is None else m["roa"]}">{_fmt_num(m["roa"], 1, "%")}</td>
  <td class="cov-col">{html.escape(item["coverage"])}</td>
</tr>"""


def _build_table_html(rows_html: str, include_sector_col: bool = False) -> str:
    sec_th = '<th class="sortable" data-key="sec"><span class="th-lbl" data-term="業種">業種</span><span class="sort-btn">▼</span></th>' if include_sector_col else ""
    return f"""<div class="table-wrap">
<table class="rank-table">
<thead>
<tr>
  <th class="chk-col" title="ウォッチリストに追加">☆</th>
  <th class="chk-col" title="ポートフォリオに追加">💼</th>
  <th class="sortable" data-key="tier"><span class="th-lbl" data-term="軍">軍</span><span class="sort-btn">▼</span></th>
  <th class="sortable" data-key="sym"><span class="th-lbl" data-term="コード">コード</span><span class="sort-btn">▼</span></th>
  <th class="sortable" data-key="name"><span class="th-lbl" data-term="銘柄">銘柄</span><span class="sort-btn">▼</span></th>
  {sec_th}
  <th class="sortable num" data-key="close"><span class="th-lbl" data-term="終値">終値</span><span class="sort-btn">▼</span></th>
  <th class="sortable num ret-extra hidden-col" data-key="ret_d"><span class="th-lbl" data-term="D">D</span><span class="sort-btn">▼</span></th>
  <th class="sortable num ret-extra hidden-col" data-key="ret_w"><span class="th-lbl" data-term="W">W</span><span class="sort-btn">▼</span></th>
  <th class="sortable num ret-extra hidden-col" data-key="ret_m"><span class="th-lbl" data-term="M">M</span><span class="sort-btn">▼</span></th>
  <th class="sortable num ret-extra hidden-col" data-key="ret_3m"><span class="th-lbl" data-term="3M">3M</span><span class="sort-btn">▼</span></th>
  <th class="sortable num ret-extra hidden-col" data-key="ret_6m"><span class="th-lbl" data-term="6M">6M</span><span class="sort-btn">▼</span></th>
  <th class="sortable num ret-extra hidden-col" data-key="ret_9m"><span class="th-lbl" data-term="9M">9M</span><span class="sort-btn">▼</span></th>
  <th class="sortable num ret-y" data-key="ret_y"><button type="button" class="ret-toggle-btn" title="クリックで期間展開">騰落率(1Y) ⇄</button><span class="sort-btn">▼</span></th>
  <th class="sortable num" data-key="q"><span class="th-lbl" data-term="ファンダ点">ファンダ点</span><span class="sort-btn">▼</span></th>
  <th class="sortable num" data-key="perf"><span class="th-lbl" data-term="業績">業績</span><span class="sort-btn">▼</span></th>
  <th class="sortable num" data-key="fin"><span class="th-lbl" data-term="財務">財務</span><span class="sort-btn">▼</span></th>
  <th class="sortable num" data-key="cf"><span class="th-lbl" data-term="CF">CF</span><span class="sort-btn">▼</span></th>
  <th class="sortable num" data-key="b"><span class="th-lbl" data-term="買い時">買い時</span><span class="sort-btn">▼</span></th>
  <th class="sortable num" data-key="dy"><span class="th-lbl" data-term="利回り">利回り</span><span class="sort-btn">▼</span></th>
  <th class="sortable num" data-key="roe"><span class="th-lbl" data-term="ROE">ROE</span><span class="sort-btn">▼</span></th>
  <th class="sortable num" data-key="roa"><span class="th-lbl" data-term="ROA">ROA</span><span class="sort-btn">▼</span></th>
  <th class="sortable" data-key="cov"><span class="th-lbl" data-term="カバレッジ">カバー</span><span class="sort-btn">▼</span></th>
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
</div>"""


def generate_outputs(scored_data: dict[str, Any], dist_dir: Path) -> None:
    """dist/ranking.json と dist/index.html を生成する。"""
    dist_dir.mkdir(parents=True, exist_ok=True)
    now_jst = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")

    items: list[dict[str, Any]] = scored_data["items"]
    sector_stats: dict[str, dict[str, Any]] = scored_data["sector_stats"]

    # ranking.json 出力
    ranking_payload = {
        "generated_at": now_jst,
        "total_count": len(items),
        "sector_stats": sector_stats,
        "items": items,
    }
    (dist_dir / "ranking.json").write_text(
        json.dumps(ranking_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    total_n = len(items)
    t1_n = sum(1 for x in items if x["tier"] == 1)
    t2_n = sum(1 for x in items if x["tier"] == 2)
    t3_n = sum(1 for x in items if x["tier"] == 3)

    # 全体品質スコア上位50
    top50 = sorted(
        [x for x in items if x["quality_score"] is not None],
        key=lambda r: r["quality_score"],
        reverse=True,
    )[:50]
    top50_rows = "\n".join(_build_row_html(x, include_sector_col=True) for x in top50)
    top50_table = _build_table_html(top50_rows, include_sector_col=True)

    # 業種別テーブル
    by_sec: dict[str, list[dict[str, Any]]] = {}
    for x in items:
        by_sec.setdefault(x["sector_ja"], []).append(x)

    ordered_sectors = [s for s in SECTOR_ORDER if s in by_sec] + [
        s for s in by_sec if s not in SECTOR_ORDER
    ]

    sector_sections_html = []
    for sec in ordered_sectors:
        sec_items = sorted(
            by_sec[sec],
            key=lambda r: (r["quality_score"] if r["quality_score"] is not None else -1.0),
            reverse=True,
        )
        st = sector_stats.get(sec, {})
        grade = st.get("sector_grade", "B")
        q_med = st.get("quality_median", "-")
        rows_html = "\n".join(_build_row_html(x, include_sector_col=False) for x in sec_items)
        tbl_html = _build_table_html(rows_html, include_sector_col=False)
        sector_sections_html.append(
            f"""<section class="sector-sec" data-sector="{html.escape(sec)}">
  <h2 class="sec-title">
    <span>{html.escape(sec)}</span>
    <span class="sec-meta">
      <span class="grade-pill grade-{grade}">業種級 {grade}</span>
      <span>ファンダ点中央値: <strong>{q_med}</strong></span>
      <span>銘柄数: <strong class="sec-vis-cnt">{len(sec_items)}</strong> / {len(sec_items)}</span>
    </span>
  </h2>
  {tbl_html}
</section>"""
        )

    sector_options_html = "\n".join(
        f'<label class="chk-pill"><input type="checkbox" class="flt-sec" value="{html.escape(sec)}"> {html.escape(sec)}</label>'
        for sec in ordered_sectors
    )

    page_html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>10年保有できる優良企業ランキング（米国株）</title>
<style>
:root {{
  --bg: #fafafa; --card: #ffffff; --line: #e6e6e6; --muted: #666666; --fg: #1a1a1a;
  --accent: #2563eb; --th: #f3f4f6; --field: #f7f8fa; --info: #eff6ff;
  --t1: #166534; --t1bg: #dcfce7;
  --t2: #854d0e; --t2bg: #fef9c3;
  --t3: #6b7280; --t3bg: #f3f4f6;
  --gA: #166534; --gB: #854d0e; --gC: #b91c1c;
  --wbg: #fff7ed; --wbd: #fed7aa; --wfg: #7c2d12;
  --pos: #15803d; --neg: #b91c1c;
}}
body.dark {{
  --bg: #0f172a; --card: #1e293b; --line: #334155; --muted: #94a3b8; --fg: #f1f5f9;
  --th: #1e293b; --field: #0f172a; --info: #1e3a8a;
  --t1: #86efac; --t1bg: #14532d;
  --t2: #fde047; --t2bg: #713f12;
  --t3: #cbd5e1; --t3bg: #334155;
  --wbg: #431407; --wbd: #9a3412; --wfg: #fdba74;
  --pos: #4ade80; --neg: #f87171;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; padding: 0 0 72px; background: var(--bg); color: var(--fg);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Hiragino Kaku Gothic ProN", Meiryo, sans-serif;
  font-size: 13px; line-height: 1.5;
}}
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
#theme-bar {{
  background: var(--card); border-bottom: 1px solid var(--line);
  padding: 6px 16px; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: 12px;
}}
.container {{ max-width: 1360px; margin: 0 auto; padding: 16px; }}
header.top-head {{
  display: flex; flex-wrap: wrap; justify-content: space-between; align-items: flex-start; gap: 12px;
  margin-bottom: 14px;
}}
h1 {{ margin: 0 0 6px; font-size: 22px; font-weight: 700; }}
.nav-links {{ display: flex; flex-wrap: wrap; gap: 12px; font-size: 12px; align-items: center; }}
.head-right {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
.btn {{
  display: inline-flex; align-items: center; gap: 5px; padding: 6px 12px;
  border: 1px solid var(--line); border-radius: 6px; background: var(--card); color: var(--fg);
  cursor: pointer; font-size: 12px; font-weight: 500;
}}
.btn:hover {{ border-color: var(--accent); }}
.btn-primary {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
.meta-line {{ color: var(--muted); font-size: 12px; margin-bottom: 12px; }}
.tier-cards {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }}
.tier-card {{
  background: var(--card); border: 1px solid var(--line); border-radius: 8px;
  padding: 8px 14px; cursor: pointer; display: flex; align-items: baseline; gap: 6px;
  transition: border-color .15s, box-shadow .15s;
}}
.tier-card.active {{ border-color: var(--accent); box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 25%, transparent); }}
.tier-card .cnt {{ font-size: 18px; font-weight: 700; }}
.toolbar {{
  background: var(--card); border: 1px solid var(--line); border-radius: 8px;
  padding: 10px 12px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 12px;
}}
.toolbar input[type="text"] {{
  flex: 1; min-width: 220px; padding: 7px 10px; border: 1px solid var(--line);
  border-radius: 6px; background: var(--field); color: var(--fg); font-size: 13px;
}}
details.box {{
  background: var(--card); border: 1px solid var(--line); border-radius: 8px;
  padding: 10px 14px; margin-bottom: 12px;
}}
details.box > summary {{ cursor: pointer; font-weight: 700; font-size: 14px; user-select: none; }}
.flt-groups {{ display: flex; flex-direction: column; gap: 10px; margin-top: 10px; }}
.flt-group {{
  border: 1px solid var(--line); border-radius: 6px; padding: 8px 12px; background: var(--field);
}}
.flt-group > summary {{ font-weight: 700; cursor: pointer; }}
.flt-grid {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 8px; }}
.flt-item {{
  background: var(--card); border: 1px solid var(--line); border-radius: 6px;
  padding: 8px 10px; min-width: 210px; flex: 1 1 220px;
}}
.flt-item-title {{ font-weight: 700; font-size: 12px; margin-bottom: 4px; }}
.flt-row {{ display: flex; flex-wrap: wrap; gap: 6px; align-items: center; font-size: 12px; }}
.flt-item input[type="number"] {{
  width: 72px; padding: 3px 6px; border: 1px solid var(--line); border-radius: 4px;
  background: var(--field); color: var(--fg);
}}
.chk-pill {{ display: inline-flex; align-items: center; gap: 3px; cursor: pointer; font-size: 12px; }}
.sec-title {{
  display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center;
  gap: 8px; font-size: 16px; margin: 18px 0 8px; padding-bottom: 4px; border-bottom: 2px solid var(--accent);
}}
.sec-meta {{ display: flex; gap: 12px; font-size: 12px; font-weight: 400; color: var(--muted); align-items: center; }}
.grade-pill {{ padding: 2px 8px; border-radius: 99px; font-weight: 700; font-size: 11px; color: #fff; }}
.grade-A {{ background: var(--gA); }} .grade-B {{ background: var(--gB); }} .grade-C {{ background: var(--gC); }}
.table-wrap {{ overflow-x: auto; background: var(--card); border: 1px solid var(--line); border-radius: 8px; }}
table.rank-table {{ width: 100%; border-collapse: collapse; font-size: 12px; white-space: nowrap; }}
table.rank-table th, table.rank-table td {{ padding: 6px 8px; border-bottom: 1px solid var(--line); text-align: left; }}
table.rank-table th {{ background: var(--th); font-weight: 700; position: sticky; top: 0; z-index: 2; }}
table.rank-table th.num, table.rank-table td.num {{ text-align: right; }}
table.rank-table tr:hover {{ background: color-mix(in srgb, var(--accent) 6%, transparent); }}
.th-lbl {{ cursor: pointer; border-bottom: 1px dotted var(--muted); }}
.sort-btn {{ cursor: pointer; margin-left: 3px; font-size: 10px; color: var(--muted); }}
.ret-toggle-btn {{
  background: none; border: 1px solid var(--line); border-radius: 4px; padding: 1px 5px;
  font-size: 11px; cursor: pointer; color: var(--fg);
}}
.hidden-col {{ display: none; }}
.tier-badge {{ display: inline-block; padding: 2px 7px; border-radius: 99px; font-weight: 700; font-size: 11px; }}
.tier-badge.t1 {{ background: var(--t1bg); color: var(--t1); }}
.tier-badge.t2 {{ background: var(--t2bg); color: var(--t2); }}
.tier-badge.t3 {{ background: var(--t3bg); color: var(--t3); }}
.badge-warn {{ background: var(--wbg); color: var(--wfg); border: 1px solid var(--wbd); padding: 1px 5px; border-radius: 4px; font-size: 10px; font-weight: 700; }}
.badge-model {{ background: var(--info); color: var(--accent); padding: 1px 5px; border-radius: 4px; font-size: 10px; font-weight: 700; }}
.score-cell {{ font-weight: 700; }}
.sc-good {{ color: var(--t1); }} .sc-warn {{ color: var(--t2); }} .sc-weak {{ color: var(--t3); }}
.pos {{ color: var(--pos); }} .neg {{ color: var(--neg); }}
.chk-col {{ text-align: center !important; width: 28px; }}
.name-col {{ max-width: 240px; overflow: hidden; text-overflow: ellipsis; }}
#terminfo {{
  display: none; position: fixed; top: 14px; right: 14px; max-width: 380px; z-index: 50;
  background: var(--card); border: 2px solid var(--accent); border-radius: 8px;
  padding: 12px 14px; box-shadow: 0 8px 24px rgba(0,0,0,.18);
}}
#terminfo-head {{ display: flex; justify-content: space-between; align-items: center; font-weight: 700; margin-bottom: 6px; }}
#wlbar {{
  position: fixed; bottom: 0; left: 0; right: 0; z-index: 40;
  background: var(--card); border-top: 1px solid var(--line); padding: 8px 16px;
  display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 10px;
  box-shadow: 0 -4px 12px rgba(0,0,0,.06);
}}
.hidden-row {{ display: none !important; }}
</style>
</head>
<body>
<div id="hub-portal-bar" style="background:#0f172a;color:#e2e8f0;padding:7px 14px;display:flex;flex-wrap:wrap;align-items:center;gap:6px;font-size:12px;border-bottom:1px solid #1e293b;"><a href="https://elj3538.github.io/" style="color:#cbd5e1;background:transparent;padding:4px 10px;border-radius:6px;text-decoration:none;font-weight:600;white-space:nowrap;">🏠 ポータル</a><a href="https://elj3538.github.io/us-long-screener/" style="color:#ffffff;background:#2563eb;padding:4px 10px;border-radius:6px;text-decoration:none;font-weight:600;white-space:nowrap;">🇺🇸 米国10年保有</a><a href="https://elj3538.github.io/us-dividend-screener/" style="color:#cbd5e1;background:transparent;padding:4px 10px;border-radius:6px;text-decoration:none;font-weight:600;white-space:nowrap;">🇺🇸 米国配当株</a><a href="https://elj3538.github.io/jp-long-screener/" style="color:#cbd5e1;background:transparent;padding:4px 10px;border-radius:6px;text-decoration:none;font-weight:600;white-space:nowrap;">🇯🇵 日本10年保有</a><a href="https://elj3538.github.io/jp-dividend-screener/" style="color:#cbd5e1;background:transparent;padding:4px 10px;border-radius:6px;text-decoration:none;font-weight:600;white-space:nowrap;">🇯🇵 日本配当株</a></div>

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

<div class="container">
  <header class="top-head">
    <div>
      <h1>10年保有できる優良企業ランキング（米国株）</h1>
      <div class="nav-links">
        <a href="terms.html">利用規約・免責事項</a>
        <a href="guide.html">使い方・見方</a>
      </div>
    </div>
    <div class="head-right">
      <a href="options.html" class="btn">🎯 オプション候補</a>
      <a href="watchlist.html" class="btn" id="wl-count-pill">☆ ウォッチリスト (<span id="wl-saved-cnt">0</span>)</a>
      <a href="portfolio.html" class="btn" id="pf-count-pill">💼 ポートフォリオ (<span id="pf-saved-cnt">0</span>)</a>
    </div>
  </header>

  <div class="meta-line">
    最終更新: <strong>{now_jst}</strong> ／ 対象銘柄数: <strong>{total_n}</strong> 銘柄（S&amp;P 500 構成銘柄 / データ元: yfinance）
  </div>

  <div class="tier-cards">
    <div class="tier-card active" data-tier-btn="all"><span class="cnt">{total_n}</span><span>銘柄（全て）</span></div>
    <div class="tier-card" data-tier-btn="1"><span class="cnt sc-good">{t1_n}</span><span>1軍</span></div>
    <div class="tier-card" data-tier-btn="2"><span class="cnt sc-warn">{t2_n}</span><span>2軍</span></div>
    <div class="tier-card" data-tier-btn="3"><span class="cnt sc-weak">{t3_n}</span><span>3軍</span></div>
  </div>

  <div class="toolbar">
    <input type="text" id="q-input" placeholder="コード・銘柄名・業種で検索（例: AAPL, 情報技術）">
    <button type="button" class="btn" id="q-clear">クリア</button>
    <span>表示: <strong id="hit-cnt">{total_n}</strong> 件</span>
    <button type="button" class="btn" id="csv-btn">表示中の銘柄をCSV出力</button>
    <button type="button" class="btn" id="tsv-btn">クリップボードにコピー</button>
  </div>

  <details class="box" id="screener-box">
    <summary>詳しい条件で絞り込む</summary>
    <div class="flt-groups">
      <details class="flt-group" open>
        <summary>① 銘柄選定（ファンダ点）</summary>
        <div class="flt-grid">
          <div class="flt-item">
            <div class="flt-item-title">ファンダ点</div>
            <div class="flt-row"><input type="number" id="flt-q-min" placeholder="70"> 点以上</div>
          </div>
          <div class="flt-item">
            <div class="flt-item-title">売上高（年率 %）</div>
            <div class="flt-row">
              <input type="number" id="flt-rev-min" placeholder="3"> %以上
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="rev" value="良好">良好</label>
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="rev" value="注意">注意</label>
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="rev" value="弱い">弱い</label>
            </div>
          </div>
          <div class="flt-item">
            <div class="flt-item-title">EPS（年率 %）</div>
            <div class="flt-row">
              <input type="number" id="flt-eps-min" placeholder="5"> %以上
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="eps" value="良好">良好</label>
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="eps" value="注意">注意</label>
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="eps" value="弱い">弱い</label>
            </div>
          </div>
          <div class="flt-item">
            <div class="flt-item-title">営業利益率（直近 %）</div>
            <div class="flt-row">
              <input type="number" id="flt-margin-min" placeholder="15"> %以上
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="margin" value="良好">良好</label>
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="margin" value="注意">注意</label>
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="margin" value="弱い">弱い</label>
            </div>
          </div>
          <div class="flt-item">
            <div class="flt-item-title">財務健全性（3段階）</div>
            <div class="flt-row">
              D/E:
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="de" value="良好">良</label>
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="de" value="注意">注</label>
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="de" value="弱い">弱</label>
              ／ 利払余裕:
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="icov" value="良好">良</label>
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="icov" value="注意">注</label>
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="icov" value="弱い">弱</label>
            </div>
          </div>
          <div class="flt-item">
            <div class="flt-item-title">キャッシュフロー</div>
            <div class="flt-row">
              <label class="chk-pill"><input type="checkbox" id="flt-ocf-pos"> 営業CFプラスのみ</label>
              <label class="chk-pill"><input type="checkbox" id="flt-fcf-pos"> フリーCFプラスのみ</label>
            </div>
          </div>
        </div>
      </details>

      <details class="flt-group">
        <summary>② 買い時スコア</summary>
        <div class="flt-grid">
          <div class="flt-item">
            <div class="flt-item-title">買い時スコア</div>
            <div class="flt-row"><input type="number" id="flt-b-min" placeholder="65"> 点以上</div>
          </div>
          <div class="flt-item">
            <div class="flt-item-title">FCF利回り（%）</div>
            <div class="flt-row">
              <input type="number" id="flt-fcfy-min" step="0.1" placeholder="3.0"> %以上
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="fcfy" value="良好">良好</label>
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="fcfy" value="注意">注意</label>
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="fcfy" value="弱い">弱い</label>
            </div>
          </div>
          <div class="flt-item">
            <div class="flt-item-title">EV/EBIT（対業種中央値）</div>
            <div class="flt-row">
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="evebit" value="良好">良好</label>
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="evebit" value="注意">注意</label>
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="evebit" value="弱い">弱い</label>
            </div>
          </div>
          <div class="flt-item">
            <div class="flt-item-title">PER（対業種平均）</div>
            <div class="flt-row">
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="perrel" value="良好">良好</label>
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="perrel" value="注意">注意</label>
              <label class="chk-pill"><input type="checkbox" class="flt-g" data-k="perrel" value="弱い">弱い</label>
            </div>
          </div>
        </div>
      </details>

      <details class="flt-group">
        <summary>③ ROE・ROA（参考）・業種区分</summary>
        <div class="flt-grid">
          <div class="flt-item">
            <div class="flt-item-title">ROE（%）</div>
            <div class="flt-row"><input type="number" id="flt-roe-min" placeholder="10"> %以上</div>
          </div>
          <div class="flt-item">
            <div class="flt-item-title">ROA（%）</div>
            <div class="flt-row"><input type="number" id="flt-roa-min" placeholder="5"> %以上</div>
          </div>
          <div class="flt-item">
            <div class="flt-item-title">業種区分</div>
            <div class="flt-row">
              <select id="flt-model">
                <option value="all">すべて</option>
                <option value="general">一般企業のみ</option>
                <option value="special">銀行・保険・証券・REITのみ</option>
              </select>
            </div>
          </div>
        </div>
      </details>

      <details class="flt-group">
        <summary>④ 銘柄属性</summary>
        <div class="flt-grid">
          <div class="flt-item">
            <div class="flt-item-title">時価総額・終値</div>
            <div class="flt-row">
              時価総額 <input type="number" id="flt-mcap-min" placeholder="100"> B$以上 ／
              終値 <input type="number" id="flt-close-max" placeholder="500"> $以下
            </div>
          </div>
          <div class="flt-item">
            <div class="flt-item-title">業種級・カバレッジ・急減速</div>
            <div class="flt-row">
              業種級:
              <label class="chk-pill"><input type="checkbox" class="flt-secgrade" value="A">A</label>
              <label class="chk-pill"><input type="checkbox" class="flt-secgrade" value="B">B</label>
              <label class="chk-pill"><input type="checkbox" class="flt-secgrade" value="C">C</label>
              ／ 急減速:
              <select id="flt-decel">
                <option value="all">すべて</option>
                <option value="0">フラグ無しのみ</option>
                <option value="1">急減速ありのみ</option>
              </select>
            </div>
          </div>
          <div class="flt-item" style="flex: 1 1 100%;">
            <div class="flt-item-title">業種グループ</div>
            <div class="flt-row">{sector_options_html}</div>
          </div>
        </div>
      </details>
    </div>
    <div style="margin-top:10px; display:flex; gap:10px; align-items:center;">
      <button type="button" class="btn" id="flt-clear-btn">条件をクリア</button>
      <span style="color:var(--muted)">ヒット: <strong id="flt-hit-cnt">{total_n}</strong> 件</span>
    </div>
  </details>

  <details class="box" id="backup-box">
    <summary>バックアップ（CSV 一括保存／復元）</summary>
    <div style="margin-top:10px;display:flex;flex-wrap:wrap;gap:10px;align-items:center;">
      <button type="button" class="btn btn-primary" id="bk-export-btn">全データをCSVに保存</button>
      <label class="btn" style="cursor:pointer;">
        CSVから復元 <input type="file" id="bk-import-file" accept=".csv,text/csv" style="display:none;">
      </label>
      <span style="color:var(--muted);font-size:12px;">※ 絞り込みURL・テーマ設定・ウォッチリスト・ポートフォリオを1つのCSVにまとめて保存／復元できます（PC間移行に便利）。</span>
    </div>
  </details>

  <details class="box">
    <summary>全体 ファンダ点 上位50（業種横断）</summary>
    <div style="margin-top:10px;" id="top50-wrap">
      {top50_table}
    </div>
  </details>

  <div id="sector-list">
    {"".join(sector_sections_html)}
  </div>
</div>

<div id="terminfo">
  <div id="terminfo-head">
    <span id="terminfo-title">用語解説</span>
    <button type="button" class="btn" id="terminfo-close" style="padding:2px 8px;">✕</button>
  </div>
  <div id="terminfo-body" style="font-size:12px;"></div>
</div>

<div id="wlbar">
  <div style="font-size:12px;">
    選択中: ☆ウォッチリスト <strong id="sel-wl-cnt">0</strong>件 ／ 💼ポートフォリオ <strong id="sel-pf-cnt">0</strong>件
  </div>
  <div style="display:flex; gap:8px;">
    <button type="button" class="btn btn-primary" id="wl-save-btn">選択をローカル保存</button>
    <button type="button" class="btn" id="wl-clear-sel">選択解除</button>
  </div>
</div>

<script>
(() => {{
  const PRESETS = {{
    genko: "#2563eb", blueplus: "#0284c7", teal: "#0d9488",
    slate: "#475569", sand: "#b45309", violet: "#7c3aed", rose: "#e11d48"
  }};
  const presetSel = document.getElementById("theme-preset");
  const colorInp = document.getElementById("theme-custom-color");
  const darkBtn = document.getElementById("dark-toggle");
  function applyTheme(preset, dark, customColor) {{
    const c = (preset === "custom" && customColor) ? customColor : (PRESETS[preset] || PRESETS.genko);
    document.documentElement.style.setProperty("--accent", c);
    document.body.classList.toggle("dark", !!dark);
    darkBtn.textContent = dark ? "☀️ ライトへ" : "🌙 ダークへ";
    presetSel.value = preset;
    colorInp.value = c;
    localStorage.setItem("pp_theme_long", JSON.stringify({{ preset, dark, customColor: c }}));
  }}
  try {{
    const saved = JSON.parse(localStorage.getItem("pp_theme_long") || "{{}}");
    applyTheme(saved.preset || "genko", !!saved.dark, saved.customColor || "#2563eb");
  }} catch {{ applyTheme("genko", false, "#2563eb"); }}
  presetSel.addEventListener("change", () => {{
    applyTheme(presetSel.value, document.body.classList.contains("dark"), colorInp.value);
  }});
  colorInp.addEventListener("input", () => {{
    applyTheme("custom", document.body.classList.contains("dark"), colorInp.value);
  }});
  darkBtn.addEventListener("click", () => {{
    applyTheme(presetSel.value, !document.body.classList.contains("dark"), colorInp.value);
  }});
  document.getElementById("theme-reset").addEventListener("click", () => applyTheme("genko", false, "#2563eb"));

  // 用語解説
  const TERMS = {{
    "軍": "セクター内でファンダ点上位25%が1軍、次45%が2軍、下位30%が3軍（カバレッジ低や絶対ファンダ点による補正あり）。",
    "ファンダ点": "業績(0.28)・財務(0.27)・キャッシュフロー(0.15)の総合点（0〜110点）。配当は採点に含めません。",
    "業績": "売上成長率・EPS成長率・営業利益率・利益安定度の総合評価。直近四半期の急減速時はペナルティ。",
    "財務": "D/Eレシオ・ネットD/E・有利子負債÷営業CF・インタレストカバレッジから算出した財務健全性。",
    "CF": "営業CF・フリーCFのプラス維持とFCF配当性向の余裕度から算出した現金創出力。",
    "買い時": "EV/EBIT対業種・FCF利回り・PER割安度・PBR割安度から算出した割安度（0〜110点）。",
    "利回り": "参考表示の配当利回り（採点には未使用）。",
    "ROE": "自己資本利益率（参考表示・採点には未使用）。",
    "ROA": "総資産利益率（参考表示・採点には未使用）。",
    "カバレッジ": "財務指標の取得充実度（高・中・低）。「低」の場合は最大2軍までとなります。"
  }};
  const termBox = document.getElementById("terminfo");
  document.querySelectorAll(".th-lbl").forEach(el => {{
    el.addEventListener("click", (e) => {{
      e.stopPropagation();
      const t = el.dataset.term;
      if (!TERMS[t]) return;
      document.getElementById("terminfo-title").textContent = t;
      document.getElementById("terminfo-body").textContent = TERMS[t];
      termBox.style.display = "block";
    }});
  }});
  document.getElementById("terminfo-close").addEventListener("click", () => termBox.style.display = "none");

  // 騰落率展開トグル
  let retExpanded = false;
  document.querySelectorAll(".ret-toggle-btn").forEach(btn => {{
    btn.addEventListener("click", (e) => {{
      e.stopPropagation();
      retExpanded = !retExpanded;
      document.querySelectorAll(".ret-extra").forEach(c => c.classList.toggle("hidden-col", !retExpanded));
      document.querySelectorAll(".ret-toggle-btn").forEach(b => {{
        b.textContent = retExpanded ? "Y ⇄" : "騰落率(1Y) ⇄";
      }});
    }});
  }});

  // ソート機能
  document.querySelectorAll("th.sortable").forEach(th => {{
    const btn = th.querySelector(".sort-btn");
    if (!btn) return;
    btn.addEventListener("click", () => {{
      const table = th.closest("table");
      const tbody = table.querySelector("tbody");
      const colIdx = Array.from(th.parentElement.children).indexOf(th);
      const asc = th.dataset.dir === "desc";
      th.dataset.dir = asc ? "asc" : "desc";
      const rows = Array.from(tbody.querySelectorAll("tr"));
      rows.sort((a, b) => {{
        const ca = a.children[colIdx];
        const cb = b.children[colIdx];
        const sa = ca.dataset.sort !== undefined ? ca.dataset.sort : ca.textContent.trim();
        const sb = cb.dataset.sort !== undefined ? cb.dataset.sort : cb.textContent.trim();
        const na = parseFloat(sa), nb = parseFloat(sb);
        if (!isNaN(na) && !isNaN(nb)) return asc ? na - nb : nb - na;
        if (sa === "" && sb !== "") return 1;
        if (sb === "" && sa !== "") return -1;
        return asc ? sa.localeCompare(sb, "ja") : sb.localeCompare(sa, "ja");
      }});
      rows.forEach(r => tbody.appendChild(r));
    }});
  }});

  // フィルタ状態
  let activeTier = "all";
  const qInput = document.getElementById("q-input");
  const tierBtns = document.querySelectorAll(".tier-card");
  tierBtns.forEach(btn => {{
    btn.addEventListener("click", () => {{
      const val = btn.dataset.tierBtn;
      activeTier = (activeTier === val && val !== "all") ? "all" : val;
      tierBtns.forEach(b => b.classList.toggle("active", b.dataset.tierBtn === activeTier));
      applyFilters();
    }});
  }});

  function numVal(id) {{
    const v = document.getElementById(id).value;
    return v === "" ? null : parseFloat(v);
  }}
  function checkedVals(selector) {{
    return Array.from(document.querySelectorAll(selector + ":checked")).map(x => x.value);
  }}

  let urlTimer = null;
  function applyFilters() {{
    const q = qInput.value.trim().toLowerCase();
    const qMin = numVal("flt-q-min"), revMin = numVal("flt-rev-min"), epsMin = numVal("flt-eps-min"),
          marginMin = numVal("flt-margin-min"), bMin = numVal("flt-b-min"), fcfyMin = numVal("flt-fcfy-min"),
          roeMin = numVal("flt-roe-min"), roaMin = numVal("flt-roa-min"),
          mcapMin = numVal("flt-mcap-min"), closeMax = numVal("flt-close-max");
    const ocfPos = document.getElementById("flt-ocf-pos").checked;
    const fcfPos = document.getElementById("flt-fcf-pos").checked;
    const modelSel = document.getElementById("flt-model").value;
    const decelSel = document.getElementById("flt-decel").value;
    const secGrades = checkedVals(".flt-secgrade");
    const secs = checkedVals(".flt-sec");

    const gradeFilters = {{}};
    document.querySelectorAll(".flt-g:checked").forEach(el => {{
      (gradeFilters[el.dataset.k] = gradeFilters[el.dataset.k] || []).push(el.value);
    }});

    const seenSyms = new Set();
    document.querySelectorAll("tr.stock-row").forEach(row => {{
      const d = row.dataset;
      let ok = true;
      if (activeTier !== "all" && d.tier !== activeTier) ok = false;
      if (ok && q) {{
        const hay = (d.sym + " " + d.name + " " + d.sec).toLowerCase();
        if (!hay.includes(q)) ok = false;
      }}
      if (ok && qMin !== null && (d.q === "" || parseFloat(d.q) < qMin)) ok = false;
      if (ok && revMin !== null && (d.rev === "" || parseFloat(d.rev) < revMin)) ok = false;
      if (ok && epsMin !== null && (d.eps === "" || parseFloat(d.eps) < epsMin)) ok = false;
      if (ok && marginMin !== null && (d.margin === "" || parseFloat(d.margin) < marginMin)) ok = false;
      if (ok && bMin !== null && (d.b === "" || parseFloat(d.b) < bMin)) ok = false;
      if (ok && fcfyMin !== null && (d.fcfy === "" || parseFloat(d.fcfy) < fcfyMin)) ok = false;
      if (ok && roeMin !== null && (d.roe === "" || parseFloat(d.roe) < roeMin)) ok = false;
      if (ok && roaMin !== null && (d.roa === "" || parseFloat(d.roa) < roaMin)) ok = false;
      if (ok && mcapMin !== null && (d.mcap === "" || parseFloat(d.mcap) < mcapMin)) ok = false;
      if (ok && closeMax !== null && (d.close === "" || parseFloat(d.close) > closeMax)) ok = false;
      if (ok && ocfPos && d.ocfpos !== "1") ok = false;
      if (ok && fcfPos && d.fcfpos !== "1") ok = false;
      if (ok && modelSel === "general" && d.model !== "general") ok = false;
      if (ok && modelSel === "special" && d.model === "general") ok = false;
      if (ok && decelSel !== "all" && d.decel !== decelSel) ok = false;
      if (ok && secGrades.length && !secGrades.includes(d.secgrade)) ok = false;
      if (ok && secs.length && !secs.includes(d.sec)) ok = false;

      if (ok) {{
        for (const [k, vals] of Object.entries(gradeFilters)) {{
          const rowG = d["g" + k.charAt(0).toUpperCase() + k.slice(1)] || row.getAttribute("data-g-" + k) || "";
          if (!vals.includes(rowG)) {{ ok = false; break; }}
        }}
      }}
      row.classList.toggle("hidden-row", !ok);
      if (ok && row.closest("#sector-list")) seenSyms.add(d.sym);
    }});

    document.querySelectorAll(".sector-sec").forEach(sec => {{
      const vis = sec.querySelectorAll("tr.stock-row:not(.hidden-row)").length;
      sec.style.display = vis === 0 ? "none" : "";
      const cntEl = sec.querySelector(".sec-vis-cnt");
      if (cntEl) cntEl.textContent = vis;
    }});
    document.getElementById("hit-cnt").textContent = seenSyms.size;
    document.getElementById("flt-hit-cnt").textContent = seenSyms.size;

    clearTimeout(urlTimer);
    urlTimer = setTimeout(() => {{
      const p = new URLSearchParams();
      if (q) p.set("q", q);
      if (activeTier !== "all") p.set("tier", activeTier);
      const qs = p.toString();
      history.replaceState(null, "", qs ? "?" + qs : location.pathname);
    }}, 300);
  }}

  qInput.addEventListener("input", applyFilters);
  document.getElementById("q-clear").addEventListener("click", () => {{ qInput.value = ""; applyFilters(); }});
  document.querySelectorAll("#screener-box input, #screener-box select").forEach(el => {{
    el.addEventListener("input", applyFilters);
    el.addEventListener("change", applyFilters);
  }});
  document.getElementById("flt-clear-btn").addEventListener("click", () => {{
    document.querySelectorAll("#screener-box input[type='number']").forEach(i => i.value = "");
    document.querySelectorAll("#screener-box input[type='checkbox']").forEach(c => c.checked = false);
    document.querySelectorAll("#screener-box select").forEach(s => s.value = "all");
    activeTier = "all";
    tierBtns.forEach(b => b.classList.toggle("active", b.dataset.tierBtn === "all"));
    applyFilters();
  }});

  // URLパラメータ復元
  const initP = new URLSearchParams(location.search);
  if (initP.get("q")) qInput.value = initP.get("q");
  if (initP.get("tier")) {{
    activeTier = initP.get("tier");
    tierBtns.forEach(b => b.classList.toggle("active", b.dataset.tierBtn === activeTier));
  }}
  applyFilters();

  // CSV / TSV 出力
  function getVisibleRowsData() {{
    const headers = ["軍", "コード", "銘柄", "業種", "終値", "ファンダ点", "業績", "財務", "CF", "買い時", "利回り", "ROE", "ROA", "カバレッジ"];
    const rows = [headers];
    document.querySelectorAll("#sector-list tr.stock-row:not(.hidden-row)").forEach(tr => {{
      const d = tr.dataset;
      rows.push([
        d.tier + "軍", d.sym, d.name, d.sec, d.close, d.q,
        tr.children[13].textContent.trim(), tr.children[14].textContent.trim(), tr.children[15].textContent.trim(),
        d.b, tr.children[17].textContent.trim(), d.roe, d.roa, d.cov
      ]);
    }});
    return rows;
  }}
  document.getElementById("csv-btn").addEventListener("click", () => {{
    const rows = getVisibleRowsData();
    const csv = rows.map(r => r.map(v => '"' + String(v ?? "").replace(/"/g, '""') + '"').join(",")).join("\\r\\n");
    const blob = new Blob(["\\uFEFF" + csv], {{ type: "text/csv;charset=utf-8;" }});
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "us_long_ranking.csv";
    a.click();
  }});
  document.getElementById("tsv-btn").addEventListener("click", async () => {{
    const rows = getVisibleRowsData();
    const tsv = rows.map(r => r.join("\\t")).join("\\n");
    await navigator.clipboard.writeText(tsv);
    alert((rows.length - 1) + "件をクリップボードにコピーしました。");
  }});

  // チェックボックス同期＆localStorage保存
  function refreshSelection() {{
    const wl = new Set(), pf = new Set();
    document.querySelectorAll(".wl-chk:checked").forEach(c => wl.add(c.value));
    document.querySelectorAll(".pf-chk:checked").forEach(c => pf.add(c.value));
    document.getElementById("sel-wl-cnt").textContent = wl.size;
    document.getElementById("sel-pf-cnt").textContent = pf.size;
  }}
  document.addEventListener("change", (e) => {{
    if (e.target.classList.contains("wl-chk") || e.target.classList.contains("pf-chk")) {{
      const cls = e.target.classList.contains("wl-chk") ? "wl-chk" : "pf-chk";
      document.querySelectorAll("." + cls + '[value="' + e.target.value + '"]').forEach(x => x.checked = e.target.checked);
      refreshSelection();
    }}
  }});
  function updateSavedPills() {{
    const wl = JSON.parse(localStorage.getItem("wl_codes_long_us") || "[]");
    const pf = JSON.parse(localStorage.getItem("pf_sel_codes_long_us") || "[]");
    document.getElementById("wl-saved-cnt").textContent = wl.length;
    document.getElementById("pf-saved-cnt").textContent = pf.length;
  }}
  updateSavedPills();
  document.getElementById("wl-save-btn").addEventListener("click", () => {{
    const curWl = new Set(JSON.parse(localStorage.getItem("wl_codes_long_us") || "[]"));
    const curPf = new Set(JSON.parse(localStorage.getItem("pf_sel_codes_long_us") || "[]"));
    document.querySelectorAll(".wl-chk:checked").forEach(c => curWl.add(c.value));
    document.querySelectorAll(".pf-chk:checked").forEach(c => curPf.add(c.value));
    localStorage.setItem("wl_codes_long_us", JSON.stringify([...curWl]));
    localStorage.setItem("pf_sel_codes_long_us", JSON.stringify([...curPf]));
    updateSavedPills();
    alert("ローカルストレージに保存しました。");
  }});
  document.getElementById("wl-clear-sel").addEventListener("click", () => {{
    document.querySelectorAll(".wl-chk, .pf-chk").forEach(c => c.checked = false);
    refreshSelection();
  }});

  // CSV 一括バックアップ／復元
  const BK_KEYS = ["pp_theme_long", "wl_codes_long_us", "wl_tabs_long_us", "pf_sel_codes_long_us", "pf_lots_long_us"];
  document.getElementById("bk-export-btn").addEventListener("click", () => {{
    const rows = [["key", "value"], ["filter_query", location.search]];
    BK_KEYS.forEach(k => {{
      const v = localStorage.getItem(k);
      if (v !== null) rows.push([k, v]);
    }});
    const csv = rows.map(r => r.map(v => '"' + String(v).replace(/"/g, '""') + '"').join(",")).join("\\r\\n");
    const blob = new Blob(["\\uFEFF" + csv], {{ type: "text/csv;charset=utf-8;" }});
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "us_long_backup_" + new Date().toISOString().slice(0, 10) + ".csv";
    a.click();
  }});
  document.getElementById("bk-import-file").addEventListener("change", async (e) => {{
    const file = e.target.files[0];
    if (!file) return;
    const text = (await file.text()).replace(/^\\uFEFF/, "");
    const lines = text.split(/\\r?\\n/).filter(Boolean);
    let restored = 0;
    for (let i = 1; i < lines.length; i++) {{
      const m = lines[i].match(/^"((?:[^"]|"")*)","((?:[^"]|"")*)"$/);
      if (!m) continue;
      const k = m[1].replace(/""/g, '"'), v = m[2].replace(/""/g, '"');
      if (BK_KEYS.includes(k)) {{ localStorage.setItem(k, v); restored++; }}
    }}
    updateSavedPills();
    alert(restored + "件の設定を復元しました。ページを再読み込みします。");
    location.reload();
  }});
}})();
</script>
</body>
</html>"""

    (dist_dir / "index.html").write_text(page_html, encoding="utf-8")
