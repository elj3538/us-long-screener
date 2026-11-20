"""各銘柄の個別詳細レポートHTML（dist/reports/<TICKER>.html）を生成するモジュール。"""

from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

JST = timezone(timedelta(hours=9))


def _fmt(val: float | None, digits: int = 1, suffix: str = "", prefix: str = "") -> str:
    if val is None:
        return "-"
    return f"{prefix}{val:.{digits}f}{suffix}"


def _fmt_signed(val: float | None, digits: int = 1, suffix: str = "%") -> str:
    if val is None:
        return "-"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.{digits}f}{suffix}"


def _grade_badge(grade: str | None) -> str:
    if not grade:
        return '<span class="g-pill g-none">-</span>'
    cls = "g-good" if grade == "良好" else ("g-warn" if grade == "注意" else "g-weak")
    return f'<span class="g-pill {cls}">{html.escape(grade)}</span>'


def _score_bar(score: float | None) -> str:
    if score is None:
        return '<div class="bar-track"><div class="bar-fill" style="width:0%"></div></div>'
    pct = max(0.0, min(100.0, score / 110.0 * 100.0))
    cls = "bar-good" if score >= 70 else ("bar-warn" if score >= 50 else "bar-weak")
    return f'<div class="bar-track"><div class="bar-fill {cls}" style="width:{pct:.1f}%"></div></div>'


def _svg_line_chart(series: list[dict[str, Any]], unit: str = "", title: str = "") -> str:
    """年次推移のインラインSVG折れ線グラフを生成する。"""
    if len(series) < 2:
        return '<div class="svg-empty">推移データ不足</div>'

    w, h = 340, 120
    pad_l, pad_r, pad_t, pad_b = 46, 18, 22, 24
    pw, ph = w - pad_l - pad_r, h - pad_t - pad_b

    vals = [p["value"] for p in series]
    vmin, vmax = min(vals), max(vals)
    if vmin == vmax:
        vmin -= 1.0
        vmax += 1.0
    span = vmax - vmin
    vmin -= span * 0.1
    vmax += span * 0.1

    coords = []
    n = len(series)
    for i, pt in enumerate(series):
        x = pad_l + (pw * i / max(1, n - 1))
        y = pad_t + ph * (1.0 - (pt["value"] - vmin) / (vmax - vmin))
        coords.append((x, y, pt["date"], pt["value"]))

    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y, _, _ in coords)
    circles = []
    labels = []
    for x, y, dt, v in coords:
        circles.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="var(--accent)" />')
        labels.append(f'<text x="{x:.1f}" y="{y - 7:.1f}" text-anchor="middle" font-size="10" fill="var(--fg)">{v:.1f}{html.escape(unit)}</text>')
        labels.append(f'<text x="{x:.1f}" y="{h - 6}" text-anchor="middle" font-size="10" fill="var(--muted)">{html.escape(str(dt))}</text>')

    # ゼロライン（負値を含む場合）
    zero_line = ""
    if vmin < 0 < vmax:
        zy = pad_t + ph * (1.0 - (0.0 - vmin) / (vmax - vmin))
        zero_line = f'<line x1="{pad_l}" y1="{zy:.1f}" x2="{w - pad_r}" y2="{zy:.1f}" stroke="var(--muted)" stroke-dasharray="3,3" stroke-width="1" />'

    return f"""<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{html.escape(title)}" class="mini-svg">
  <rect x="0" y="0" width="{w}" height="{h}" rx="6" fill="var(--field)" />
  {zero_line}
  <polyline fill="none" stroke="var(--accent)" stroke-width="2.2" points="{poly}" />
  {"".join(circles)}
  {"".join(labels)}
</svg>"""


def _svg_range_bar(
    val: float | None,
    good_edge: float,
    warn_edge: float,
    max_scale: float,
    unit: str = "倍",
    lower_is_better: bool = True,
) -> str:
    """割安｜妥当｜割高 の3ゾーン帯SVGを生成する。"""
    if val is None:
        return '<div class="svg-empty">比較データなし</div>'

    w, h = 340, 62
    pad_l, pad_r = 16, 16
    bw = w - pad_l - pad_r
    y_bar, bar_h = 26, 14

    def pos(v: float) -> float:
        clamped = max(0.0, min(max_scale, v))
        return pad_l + bw * (clamped / max_scale)

    x1 = pos(good_edge)
    x2 = pos(warn_edge)
    xv = pos(val)

    if lower_is_better:
        zones = f"""
  <rect x="{pad_l}" y="{y_bar}" width="{max(1, x1 - pad_l):.1f}" height="{bar_h}" fill="var(--t1bg)" />
  <rect x="{x1:.1f}" y="{y_bar}" width="{max(1, x2 - x1):.1f}" height="{bar_h}" fill="var(--t2bg)" />
  <rect x="{x2:.1f}" y="{y_bar}" width="{max(1, pad_l + bw - x2):.1f}" height="{bar_h}" fill="var(--wbg)" />
  <text x="{(pad_l + x1)/2:.1f}" y="{y_bar + 11}" text-anchor="middle" font-size="9" fill="var(--t1)">割安</text>
  <text x="{(x1 + x2)/2:.1f}" y="{y_bar + 11}" text-anchor="middle" font-size="9" fill="var(--t2)">妥当</text>
  <text x="{(x2 + pad_l + bw)/2:.1f}" y="{y_bar + 11}" text-anchor="middle" font-size="9" fill="var(--wfg)">割高</text>"""
    else:
        zones = f"""
  <rect x="{pad_l}" y="{y_bar}" width="{max(1, x1 - pad_l):.1f}" height="{bar_h}" fill="var(--wbg)" />
  <rect x="{x1:.1f}" y="{y_bar}" width="{max(1, x2 - x1):.1f}" height="{bar_h}" fill="var(--t2bg)" />
  <rect x="{x2:.1f}" y="{y_bar}" width="{max(1, pad_l + bw - x2):.1f}" height="{bar_h}" fill="var(--t1bg)" />
  <text x="{(pad_l + x1)/2:.1f}" y="{y_bar + 11}" text-anchor="middle" font-size="9" fill="var(--wfg)">低い</text>
  <text x="{(x1 + x2)/2:.1f}" y="{y_bar + 11}" text-anchor="middle" font-size="9" fill="var(--t2)">標準</text>
  <text x="{(x2 + pad_l + bw)/2:.1f}" y="{y_bar + 11}" text-anchor="middle" font-size="9" fill="var(--t1)">高い(割安)</text>"""

    return f"""<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="割安レンジ図" class="mini-svg">
  <rect x="0" y="0" width="{w}" height="{h}" rx="6" fill="var(--field)" />
  {zones}
  <polygon points="{xv:.1f},{y_bar - 2} {xv - 5:.1f},{y_bar - 10} {xv + 5:.1f},{y_bar - 10}" fill="var(--accent)" />
  <text x="{xv:.1f}" y="13" text-anchor="middle" font-size="10" font-weight="700" fill="var(--accent)">現在 {val:.2f}{html.escape(unit)}</text>
  <text x="{x1:.1f}" y="{y_bar + bar_h + 13}" text-anchor="middle" font-size="9" fill="var(--muted)">{good_edge}</text>
  <text x="{x2:.1f}" y="{y_bar + bar_h + 13}" text-anchor="middle" font-size="9" fill="var(--muted)">{warn_edge}</text>
</svg>"""


def _svg_price_chart(yearly_prices: dict[str, dict[str, float]], current_price: float | None) -> str:
    """5年分の年次株価レンジ（安値〜高値帯＋年平均ライン）をインラインSVGで描画する。"""
    if not yearly_prices:
        return '<div class="svg-empty">株価推移データなし</div>'

    years = sorted(yearly_prices.keys())
    w, h = 680, 190
    pad_l, pad_r, pad_t, pad_b = 54, 24, 20, 28
    pw, ph = w - pad_l - pad_r, h - pad_t - pad_b

    all_vals = []
    for yr in years:
        all_vals.extend([yearly_prices[yr]["min"], yearly_prices[yr]["max"]])
    if current_price is not None:
        all_vals.append(current_price)
    vmin, vmax = min(all_vals), max(all_vals)
    if vmin == vmax:
        vmin *= 0.9
        vmax *= 1.1
    span = vmax - vmin
    vmin = max(0.0, vmin - span * 0.08)
    vmax += span * 0.08

    def y_of(v: float) -> float:
        return pad_t + ph * (1.0 - (v - vmin) / (vmax - vmin))

    n = len(years)
    avg_pts = []
    bars = []
    x_labels = []
    for i, yr in enumerate(years):
        x = pad_l + (pw * i / max(1, n - 1)) if n > 1 else pad_l + pw / 2
        yp = yearly_prices[yr]
        y_hi, y_lo, y_avg = y_of(yp["max"]), y_of(yp["min"]), y_of(yp["avg"])
        bars.append(f'<line x1="{x:.1f}" y1="{y_hi:.1f}" x2="{x:.1f}" y2="{y_lo:.1f}" stroke="color-mix(in srgb, var(--accent) 35%, transparent)" stroke-width="10" stroke-linecap="round" />')
        avg_pts.append(f"{x:.1f},{y_avg:.1f}")
        x_labels.append(f'<text x="{x:.1f}" y="{h - 8}" text-anchor="middle" font-size="11" fill="var(--muted)">{html.escape(yr)}</text>')

    grid = []
    for k in range(4):
        gv = vmin + (vmax - vmin) * k / 3.0
        gy = y_of(gv)
        grid.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{w - pad_r}" y2="{gy:.1f}" stroke="var(--line)" stroke-width="1" />')
        grid.append(f'<text x="{pad_l - 6}" y="{gy + 3:.1f}" text-anchor="end" font-size="10" fill="var(--muted)">${gv:.0f}</text>')

    cur_line = ""
    if current_price is not None:
        cy = y_of(current_price)
        cur_line = f'<line x1="{pad_l}" y1="{cy:.1f}" x2="{w - pad_r}" y2="{cy:.1f}" stroke="var(--pos)" stroke-dasharray="4,3" stroke-width="1.5" /><text x="{w - pad_r}" y="{cy - 4:.1f}" text-anchor="end" font-size="10" font-weight="700" fill="var(--pos)">現在 ${current_price:.2f}</text>'

    return f"""<svg viewBox="0 0 {w} {h}" style="width:100%;max-width:{w}px;height:auto;" role="img" aria-label="株価の推移" class="mini-svg">
  <rect x="0" y="0" width="{w}" height="{h}" rx="8" fill="var(--field)" />
  {"".join(grid)}
  {"".join(bars)}
  <polyline fill="none" stroke="var(--accent)" stroke-width="2.5" points="{" ".join(avg_pts)}" />
  {cur_line}
  {"".join(x_labels)}
</svg>"""


def _svg_toggle_chart(annual_svg: str, quarterly_svg: str, q_note: str = "") -> str:
    """年次／四半期の2つのSVGグラフをボタンで切り替えられるコンテナを生成する。"""
    note_html = f'<div class="q-note">{html.escape(q_note)}</div>' if q_note else ""
    return f"""<div class="chart-toggle-wrap">
  <div class="chart-tabs">
    <button type="button" class="ctab active" data-mode="annual">年次</button>
    <button type="button" class="ctab" data-mode="quarterly">四半期</button>
  </div>
  <div class="chart-pane pane-annual">{annual_svg}</div>
  <div class="chart-pane pane-quarterly" style="display:none;">{quarterly_svg}{note_html}</div>
</div>"""


def _metric_accordion(
    title: str,
    value_str: str,
    grade: str | None,
    score: float | None,
    point_text: str,
    rule_text: str,
    svg_html: str = "",
    score_note: str = "",
) -> str:
    sc_str = f"{score:.1f} / 110" if score is not None else "-"
    note_sfx = f"（{html.escape(score_note)}）" if score_note else ""
    return f"""<details class="metric-row">
  <summary>
    <span class="m-name">{html.escape(title)}</span>
    <span class="m-right">
      <span class="m-val">{html.escape(value_str)}</span>
      {_grade_badge(grade)}
      <span class="m-sc">{sc_str}</span>
    </span>
  </summary>
  <div class="m-body">
    <div class="m-info">
      <p><strong>見るポイント：</strong>{html.escape(point_text)}</p>
      <p><strong>判定ルール：</strong>{html.escape(rule_text)}</p>
      <p><strong>指標点：</strong>{sc_str}{note_sfx}</p>
    </div>
    {f'<div class="m-svg">{svg_html}</div>' if svg_html else ''}
  </div>
</details>"""


def _ref_accordion(title: str, value_str: str, desc: str) -> str:
    return f"""<details class="metric-row">
  <summary>
    <span class="m-name">{html.escape(title)}</span>
    <span class="m-right"><span class="m-val">{html.escape(value_str)}</span></span>
  </summary>
  <div class="m-body"><p style="margin:0;">{html.escape(desc)}</p></div>
</details>"""


def generate_report_for_stock(item: dict[str, Any], generated_at: str) -> str:
    sym = html.escape(item["symbol"])
    name = html.escape(item["name"])
    sec_ja = html.escape(item["sector_ja"])
    sub_ind = html.escape(item.get("sub_industry", ""))
    tier = item["tier"]
    model = item["model"]
    m = item["metrics"]
    g = item["grades"]
    ss = item.get("sub_scores", {})
    det = item.get("detail", {})
    series = det.get("series", {})
    q_series = det.get("q_series", {})
    ref = det.get("ref", {})
    analyst = det.get("analyst", {})
    q_yoy = det.get("q_yoy", {})
    sec_med = item.get("sector_medians", {})
    opt = item.get("option_signals", {})

    model_label = {"general": "一般企業モデル", "financial": "金融専用モデル（銀行・保険・証券）", "reit": "REIT専用モデル（FFOベース）"}.get(model, model)

    warn_banner = ""
    if item.get("rapid_decel"):
        warn_banner = '<div class="warn-banner">⚠ <strong>直近四半期の急減速フラグ</strong>：直近四半期の売上YoYが年率トレンドを5pt以上下回り、かつ利益が前年同期比マイナスのため、業績スコアにペナルティを適用しています。</div>'

    # ① 品質の指標
    decel_txt = "⚠ 急減速あり" if item.get("rapid_decel") else "急減速なし"
    q_rev_note = f'直近四半期 売上YoY: {_fmt_signed(q_yoy.get("rev"))}（{decel_txt}）'
    q_op_note = f'直近四半期 営業利益YoY: {_fmt_signed(q_yoy.get("op"))}（{decel_txt}）'

    rev_svg_html = _svg_toggle_chart(
        _svg_line_chart(series.get("revenue", []), "B$", "売上高推移（年次）"),
        _svg_line_chart(q_series.get("revenue", []), "B$", "売上高推移（四半期）"),
        q_note=q_rev_note,
    ) if len(q_series.get("revenue", [])) >= 2 else _svg_line_chart(series.get("revenue", []), "B$", "売上高推移")

    margin_svg_html = _svg_toggle_chart(
        _svg_line_chart(series.get("op_margin", []), "%", "営業利益率推移（年次）"),
        _svg_line_chart(q_series.get("op_margin", []), "%", "営業利益率推移（四半期）"),
        q_note=q_op_note,
    ) if len(q_series.get("op_margin", [])) >= 2 else _svg_line_chart(series.get("op_margin", []), "%", "営業利益率推移")

    perf_rows = "\n".join([
        _metric_accordion(
            "売上高（推移／年率）", _fmt_signed(m["rev_cagr"]), g.get("rev"), ss.get("rev"),
            "10年保有では本業の売上が長期的に右肩上がりであることが土台になります。四半期切替で足元の勢いも確認できます。",
            "良好: 年率+3%以上 ／ 注意: -6%〜+3% ／ 弱い: -6%未満",
            rev_svg_html,
            score_note="年次データで採点",
        ),
        _metric_accordion(
            "EPS（推移／年率）", _fmt_signed(m["eps_cagr"]), g.get("eps"), ss.get("eps"),
            "1株あたり利益の成長は、自社株買いも含めた株主価値の伸びを直接表します。",
            "良好: 年率+5%以上 ／ 注意: -5%〜+5% ／ 弱い: -5%未満",
            _svg_line_chart(series.get("eps", []), "$", "EPS推移"),
            score_note="年次データで採点",
        ),
        _metric_accordion(
            "営業利益率（直近・推移）", _fmt(m["op_margin"], 1, "%"), g.get("margin"), ss.get("margin"),
            "高い営業利益率は価格決定力や競争優位性（経済的な堀）の表れです。四半期切替で直近の利益率変化も確認できます。",
            "良好: 15%以上 ／ 注意: 5%〜15% ／ 弱い: 5%未満",
            margin_svg_html,
            score_note="年次データで採点",
        ),
        _metric_accordion(
            "利益の安定度", _fmt(m["profit_stability"], 1, "点"),
            "良好" if (m["profit_stability"] or 0) >= 75 else ("注意" if (m["profit_stability"] or 0) >= 50 else "弱い"),
            ss.get("stability"),
            "景気変動の中でも赤字を出さず安定して利益を積み上げられるかを評価します。",
            "過去3〜4年の黒字維持率と利益変動の小ささから算出（0〜110点）",
        ),
    ])

    fin_rows = "\n".join([
        _metric_accordion(
            "D/Eレシオ", _fmt(m["de_ratio"], 2, "倍"), g.get("de"), ss.get("de"),
            "自己資本に対する有利子負債の倍率。低いほど金利上昇や不況への耐性が高いです。",
            "良好: 1.0倍以下 ／ 注意: 1.0〜2.0倍 ／ 弱い: 2.0倍超",
        ),
        _metric_accordion(
            "ネットD/Eレシオ", _fmt(m["net_de_ratio"], 2, "倍"), g.get("nde"), ss.get("nde"),
            "有利子負債から手元現金を差し引いた実質負債倍率。マイナスは実質無借金を意味します。",
            "良好: 0.5倍以下 ／ 注意: 0.5〜1.5倍 ／ 弱い: 1.5倍超",
        ),
        _metric_accordion(
            "有利子負債 ÷ 営業CF", _fmt(m["debt_to_ocf"], 2, "年"), g.get("docf"), ss.get("docf"),
            "本業で稼ぐキャッシュ何年分で有利子負債を完済できるかの目安です。",
            "良好: 3.0年以下 ／ 注意: 3.0〜6.0年 ／ 弱い: 6.0年超",
        ),
        _metric_accordion(
            "インタレストカバレッジレシオ", _fmt(m["interest_cov"], 1, "倍"), g.get("icov"), ss.get("icov"),
            "営業利益（EBIT）が支払利息の何倍あるか。米国高金利環境での利払い余裕度を見ます。",
            "良好: 8.0倍以上 ／ 注意: 3.0〜8.0倍 ／ 弱い: 3.0倍未満",
        ),
    ])

    cf_rows = "\n".join([
        _metric_accordion(
            "営業CF（直近／推移）", "プラス" if m["ocf_positive"] else ("マイナス" if m["ocf_positive"] is False else "-"),
            "良好" if m["ocf_positive"] else ("弱い" if m["ocf_positive"] is False else None), ss.get("ocf"),
            "会計上の利益だけでなく、本業から実際に現金が入ってきているかを確認します。",
            "直近プラスかつ安定推移が望ましい",
            _svg_line_chart(series.get("ocf", []), "B$", "営業CF推移"),
        ),
        _metric_accordion(
            "フリーCF（営業CF−設備投資）", "プラス" if m["fcf_positive"] else ("マイナス" if m["fcf_positive"] is False else "-"),
            "良好" if m["fcf_positive"] else ("弱い" if m["fcf_positive"] is False else None), ss.get("fcf"),
            "事業維持に必要な設備投資を賄ったうえで手元に残る自由な現金です。",
            "直近プラスであることが長期保有の重要条件",
            _svg_line_chart(series.get("fcf", []), "B$", "フリーCF推移"),
        ),
        _metric_accordion(
            "FCF配当性向", _fmt(m["fcf_payout"], 1, "%"), g.get("fcf_pay"), ss.get("fcf_pay"),
            "配当の支払いがフリーCFの範囲内に無理なく収まっているかを確認します。",
            "良好: 50%以下（無配含む） ／ 注意: 50〜85% ／ 弱い: 85%超・FCF赤字",
        ),
    ])

    # ② 買い時の指標
    buy_rows = "\n".join([
        _metric_accordion(
            "EV/EBIT（対業種中央値）",
            f'{_fmt(m["ev_ebit"], 1, "倍")}（業種中央値 {_fmt(sec_med.get("ev_ebit"), 1, "倍")} ／ 対比 {_fmt(m.get("ev_ebit_rel"), 2, "倍")}）',
            g.get("ev_ebit"), ss.get("ev_ebit"),
            "企業価値（負債込み）が営業利益の何倍か。同業他社と比べて割安かを判定します。",
            "良好: 対業種0.85倍以下 ／ 注意: 0.85〜1.20倍 ／ 弱い: 1.20倍超",
            _svg_range_bar(m.get("ev_ebit_rel"), 0.85, 1.20, 2.0, "倍", lower_is_better=True),
        ),
        _metric_accordion(
            "FCF利回り", _fmt(m["fcf_yield"], 2, "%"), g.get("fcf_yield"), ss.get("fcf_yield"),
            "時価総額に対するフリーCFの割合。高いほど現金創出力に対して株価が割安です。",
            "良好: 4.0%以上 ／ 注意: 1.5〜4.0% ／ 弱い: 1.5%未満",
            _svg_range_bar(m.get("fcf_yield"), 1.5, 4.0, 8.0, "%", lower_is_better=False),
        ),
        _metric_accordion(
            "PER割安度（対業種平均・過去レンジ）",
            f'PER {_fmt(m["per"], 1, "倍")}（業種中央値 {_fmt(sec_med.get("per"), 1, "倍")} ／ 対比 {_fmt(m.get("per_rel"), 2, "倍")}）',
            g.get("per_rel"), ss.get("per"),
            "同業他社との比較および自社過去レンジ内での位置からPERの割安度を評価します。",
            "良好: 対業種0.95倍以下 ／ 注意: 0.95〜1.20倍 ／ 弱い: 1.20倍超",
            _svg_range_bar(m.get("per_rel"), 0.95, 1.20, 2.0, "倍", lower_is_better=True),
        ),
        _metric_accordion(
            "PBR割安度（対業種平均）",
            f'PBR {_fmt(m["pbr"], 2, "倍")}（業種中央値 {_fmt(sec_med.get("pbr"), 2, "倍")} ／ 対比 {_fmt(m.get("pbr_rel"), 2, "倍")}）',
            g.get("pbr_rel"), ss.get("pbr"),
            "純資産倍率の業種比較。※情報技術・コミュニケーションでは自社株買いの影響が大きいため買い時スコアから除外。",
            "良好: 対業種0.95倍以下 ／ 注意: 0.95〜1.20倍 ／ 弱い: 1.20倍超",
            _svg_range_bar(m.get("pbr_rel"), 0.95, 1.20, 2.2, "倍", lower_is_better=True),
        ),
    ])

    # アナリスト目標株価との差
    tgt_mean = analyst.get("target_mean_price")
    tgt_diff = None
    if tgt_mean and item.get("close") and item["close"] > 0:
        tgt_diff = (tgt_mean / item["close"] - 1.0) * 100.0

    # 期間別騰落率テーブル
    r = item.get("returns", {})
    ret_tds = "".join(f'<td><strong>{k}</strong><br><span class="{"pos" if (r.get(k) or 0) > 0 else ("neg" if (r.get(k) or 0) < 0 else "")}">{_fmt_signed(r.get(k))}</span></td>' for k in ["D", "W", "M", "3M", "6M", "9M", "Y"])

    # 参考指標
    rsi_v = item.get("rsi14")
    rsi_txt = f"{rsi_v:.1f}（{'買われすぎ' if rsi_v >= 70 else ('売られすぎ' if rsi_v <= 30 else '中立')}）" if rsi_v is not None else "-"
    macd_v, macd_s = item.get("macd"), item.get("macd_signal")
    macd_txt = f"{macd_v:.2f} / Signal {macd_s:.2f}（{'強気(上抜け)' if macd_v >= macd_s else '弱気(下抜け)'}）" if (macd_v is not None and macd_s is not None) else "-"

    ref_rows = "\n".join([
        _ref_accordion("市場が織り込むFCF成長率（簡易リバースDCF）", _fmt_signed(ref.get("implied_fcf_growth")), "割引率10%・永久成長率2.5%と仮定し、現在の時価総額を正当化するために必要な今後10年のFCF年率成長率を逆算した目安です。"),
        _ref_accordion("予想配当利回り（参考）", _fmt(m.get("div_yield"), 2, "%"), "採点には使用しない参考値です。"),
        _ref_accordion("自己資本比率", _fmt(ref.get("equity_ratio"), 1, "%"), "自己資本 ÷ 総資産。財務の厚みを示します。"),
        _ref_accordion("自社株買い（直近期・対時価総額比）", f'{_fmt(ref.get("buyback_b"), 2, "B$", "$")}（{_fmt(ref.get("buyback_yield"), 2, "%")}）', "直近年度に実施した自社株買いの規模と、時価総額に対する還元利回りです。"),
        _ref_accordion("総還元性向", _fmt(ref.get("total_return_ratio"), 1, "%"), "（配当支払＋自社株買い）÷ 純利益。株主還元の積極度合いを示します。"),
        _ref_accordion("益回り（1 ÷ PER）", _fmt(ref.get("earnings_yield"), 2, "%"), "株価に対する1株利益の利回り。国債利回り等との比較に用います。"),
        _ref_accordion("ROIC（投下資本利益率・近似）", _fmt(ref.get("roic"), 2, "%"), "税引後営業利益 ÷ 投下資本。資本効率の高さを示します（10%以上が優秀な目安）。"),
        _ref_accordion("RSI(14)", rsi_txt, "14日間の相対力指数。70以上は買われすぎ、30以下は売られすぎの目安です。"),
        _ref_accordion("MACD(12, 26, 9)", macd_txt, "移動平均収束拡散手法。MACDがシグナルを上回ると上昇トレンド示唆、下回ると下降示唆です。"),
    ])

    deep_rows = "\n".join([
        _ref_accordion("ROE / ROA / 財務レバレッジ", f'ROE {_fmt(m.get("roe"), 1, "%")} ／ ROA {_fmt(m.get("roa"), 1, "%")} ／ レバレッジ {_fmt(ref.get("fin_leverage"), 2, "倍")}', "ROE = ROA × 財務レバレッジに分解して、稼ぐ力由来か借入由来かを見極めます。"),
        _ref_accordion("営業CF ÷ 純利益（利益の質）", _fmt(ref.get("ocf_to_ni"), 2, "倍"), "1.0倍以上であれば、会計上の利益がしっかり現金の裏付けを伴っていると言えます。"),
        _ref_accordion("会計発生高（アクルーアル）", _fmt_signed(ref.get("accruals"), 2, "%"), "（純利益 − 営業CF）÷ 平均総資産。マイナス〜0%付近が健全で、大きくプラスの場合は利益の質に注意が必要です。"),
        _ref_accordion("設備投資 ÷ 減価償却費", _fmt(ref.get("capex_to_dep"), 2, "倍"), "1.0倍超は成長投資フェーズ、1.0倍未満は投資回収フェーズや資本軽量ビジネスの目安です。"),
        _ref_accordion("発行済株式数の変化（過去推移）", _fmt_signed(ref.get("shares_change_pct"), 2, "%"), "マイナスなら自社株買いによる株式数減少（1株価値の希薄化防止・向上）、プラスなら増資・希薄化を示します。"),
        _ref_accordion("株式報酬（SBC）の重さ", f'SBC/売上 {_fmt(ref.get("sbc_to_rev"), 2, "%")} ／ (FCF-SBC)/売上 {_fmt(ref.get("fcf_ex_sbc_margin"), 2, "%")}', "テック企業等で大きくなりがちな株式報酬を差し引いた実質フリーCFの厚みを確認します。"),
    ])

    summary_en = html.escape(det.get("summary") or "会社概要データなし")
    summary_ja = html.escape(det.get("summary_ja") or "")
    if summary_ja:
        summary_block = f"""    <details style="margin-top:10px;">
      <summary style="cursor:pointer;font-size:12px;color:var(--accent);">会社概要を開く（日本語）</summary>
      <p style="font-size:13px;color:var(--fg);margin:8px 0 6px;line-height:1.7;">{summary_ja}</p>
      <details style="margin-top:4px;">
        <summary style="cursor:pointer;font-size:11px;color:var(--muted);">原文（英語）を表示</summary>
        <p style="font-size:11px;color:var(--muted);margin:6px 0 0;">{summary_en}</p>
      </details>
    </details>"""
    else:
        summary_block = f"""    <details style="margin-top:10px;">
      <summary style="cursor:pointer;font-size:12px;color:var(--accent);">会社概要を開く</summary>
      <p style="font-size:12px;color:var(--muted);margin:8px 0 0;">{summary_en}</p>
    </details>"""

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name}（{sym}）診断レポート | 10年保有米株スクリーナー</title>
<style>
:root {{
  --bg: #fafafa; --card: #ffffff; --line: #e6e6e6; --muted: #666666; --fg: #1a1a1a;
  --accent: #2563eb; --th: #f3f4f6; --field: #f7f8fa; --info: #eff6ff;
  --t1: #166534; --t1bg: #dcfce7;
  --t2: #854d0e; --t2bg: #fef9c3;
  --t3: #6b7280; --t3bg: #f3f4f6;
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
  margin: 0; padding: 0 0 48px; background: var(--bg); color: var(--fg);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Hiragino Kaku Gothic ProN", Meiryo, sans-serif;
  font-size: 13px; line-height: 1.6;
}}
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
#theme-bar {{
  background: var(--card); border-bottom: 1px solid var(--line);
  padding: 6px 16px; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: 12px;
}}
.container {{ max-width: 960px; margin: 0 auto; padding: 16px; }}
.btn {{
  display: inline-flex; align-items: center; gap: 4px; padding: 5px 10px;
  border: 1px solid var(--line); border-radius: 6px; background: var(--card); color: var(--fg);
  cursor: pointer; font-size: 12px;
}}
.top-nav {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 12px; }}
.hero {{
  background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 16px; margin-bottom: 14px;
}}
.hero h1 {{ margin: 0 0 6px; font-size: 22px; }}
.hero-meta {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; color: var(--muted); font-size: 12px; }}
.tier-badge {{ display: inline-block; padding: 2px 9px; border-radius: 99px; font-weight: 700; font-size: 12px; }}
.t1 {{ background: var(--t1bg); color: var(--t1); }}
.t2 {{ background: var(--t2bg); color: var(--t2); }}
.t3 {{ background: var(--t3bg); color: var(--t3); }}
.warn-banner {{
  background: var(--wbg); border: 1px solid var(--wbd); color: var(--wfg);
  border-radius: 8px; padding: 10px 12px; margin-bottom: 14px; font-size: 12px;
}}
.score-cards {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }}
.score-card {{
  flex: 1 1 280px; background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px;
}}
.sc-head {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; }}
.sc-num {{ font-size: 28px; font-weight: 800; }}
.bar-track {{ width: 100%; height: 10px; background: var(--th); border-radius: 99px; overflow: hidden; }}
.bar-fill {{ height: 100%; border-radius: 99px; }}
.bar-good {{ background: var(--t1); }} .bar-warn {{ background: var(--t2); }} .bar-weak {{ background: var(--t3); }}
.section-card {{
  background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; margin-bottom: 16px;
}}
.section-card h2 {{ margin: 0 0 10px; font-size: 16px; border-bottom: 2px solid var(--accent); padding-bottom: 4px; }}
.group-head {{
  display: flex; justify-content: space-between; align-items: center;
  background: var(--th); padding: 6px 10px; border-radius: 6px; font-weight: 700; margin: 12px 0 6px;
}}
details.metric-row {{ border: 1px solid var(--line); border-radius: 6px; margin-bottom: 6px; background: var(--card); }}
details.metric-row > summary {{
  cursor: pointer; padding: 8px 10px; display: flex; justify-content: space-between; align-items: center; gap: 8px;
  list-style: none; font-weight: 600;
}}
details.metric-row > summary::-webkit-details-marker {{ display: none; }}
.m-right {{ display: flex; align-items: center; gap: 8px; font-weight: 400; flex-wrap: wrap; justify-content: flex-end; }}
.m-val {{ font-weight: 700; }}
.m-sc {{ color: var(--muted); font-size: 12px; min-width: 68px; text-align: right; }}
.g-pill {{ padding: 1px 7px; border-radius: 99px; font-size: 11px; font-weight: 700; }}
.g-good {{ background: var(--t1bg); color: var(--t1); }}
.g-warn {{ background: var(--t2bg); color: var(--t2); }}
.g-weak {{ background: var(--wbg); color: var(--wfg); }}
.g-none {{ background: var(--th); color: var(--muted); }}
.m-body {{
  border-top: 1px solid var(--line); padding: 10px 12px; background: var(--field);
  display: flex; flex-wrap: wrap; gap: 12px; justify-content: space-between; align-items: flex-start; font-size: 12px;
}}
.m-info {{ flex: 1 1 280px; }}
.m-info p {{ margin: 0 0 6px; }}
.m-svg {{ flex: 0 0 auto; }}
.chart-toggle-wrap {{ display: flex; flex-direction: column; gap: 4px; }}
.chart-tabs {{ display: flex; gap: 4px; justify-content: flex-end; }}
.ctab {{
  padding: 2px 9px; font-size: 11px; border: 1px solid var(--line); border-radius: 4px;
  background: var(--card); color: var(--muted); cursor: pointer; font-weight: 600;
}}
.ctab.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
.q-note {{ font-size: 11px; color: var(--muted); text-align: right; margin-top: 3px; }}
.mini-svg {{ display: block; border: 1px solid var(--line); border-radius: 6px; }}
.svg-empty {{ color: var(--muted); font-size: 12px; padding: 10px; }}
.ret-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; text-align: center; font-size: 12px; }}
.ret-table td {{ border: 1px solid var(--line); padding: 6px 4px; background: var(--field); }}
.pos {{ color: var(--pos); font-weight: 700; }} .neg {{ color: var(--neg); font-weight: 700; }}
.kv-grid {{ display: flex; flex-wrap: wrap; gap: 10px; }}
.kv-box {{ flex: 1 1 200px; background: var(--field); border: 1px solid var(--line); border-radius: 6px; padding: 8px 10px; }}
.kv-lbl {{ font-size: 11px; color: var(--muted); }}
.kv-val {{ font-size: 15px; font-weight: 700; margin-top: 2px; }}
footer.disclaimer {{ color: var(--muted); font-size: 11px; margin-top: 20px; border-top: 1px solid var(--line); padding-top: 12px; }}
</style>
</head>
<body>

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
  </select>
  <button type="button" class="btn" id="dark-toggle">🌙 ダークへ</button>
</div>

<div class="container">
  <div class="top-nav">
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
      <a href="../index.html" class="btn">← ランキングに戻る</a>
      <a href="../watchlist.html" class="btn">☆ ウォッチリスト</a>
      <a href="../portfolio.html" class="btn">💼 ポートフォリオ</a>
      <a href="../guide.html" class="btn">使い方・見方</a>
      <a href="../terms.html" class="btn">免責事項</a>
    </div>
    <span style="color:var(--muted);font-size:12px;">最終更新: {generated_at}</span>
  </div>

  <div class="hero">
    <h1>{name}（{sym}）</h1>
    <div class="hero-meta">
      <span class="tier-badge t{tier}">{tier}軍</span>
      <span>株価: <strong>{_fmt(item.get("close"), 2, "", "$")}</strong>（{html.escape(str(item.get("latest_date") or "-"))}）</span>
      <span>時価総額: <strong>{_fmt(item.get("market_cap_b"), 1, "B$", "$")}</strong></span>
      <span>業種: <strong>{sec_ja}</strong>（{sub_ind}）</span>
      <span>業種級: <strong>{html.escape(str(item.get("sector_grade", "-")))}</strong></span>
      <span>カバレッジ: <strong>{html.escape(str(item.get("coverage", "-")))}</strong></span>
      <span>採点モデル: <strong>{model_label}</strong></span>
    </div>
{summary_block}
  </div>

  {warn_banner}

  <div class="score-cards">
    <div class="score-card">
      <div class="sc-head">
        <strong>ファンダ点（10年保有の質）</strong>
        <span class="sc-num">{_fmt(item.get("quality_score"), 1)} <span style="font-size:13px;font-weight:400;color:var(--muted)">/ 110</span></span>
      </div>
      {_score_bar(item.get("quality_score"))}
      <div style="font-size:11px;color:var(--muted);margin-top:6px;">業績 {_fmt(item.get("perf_score"), 1)} ／ 財務 {_fmt(item.get("fin_score"), 1)} ／ CF {_fmt(item.get("cf_score"), 1)}</div>
    </div>
    <div class="score-card">
      <div class="sc-head">
        <strong>買い時スコア（今の割安度）</strong>
        <span class="sc-num">{_fmt(item.get("buy_score"), 1)} <span style="font-size:13px;font-weight:400;color:var(--muted)">/ 110</span></span>
      </div>
      {_score_bar(item.get("buy_score"))}
      <div style="font-size:11px;color:var(--muted);margin-top:6px;">業種中央値比較・FCF利回り・過去レンジから算出</div>
    </div>
  </div>

  <div class="section-card">
    <h2>① ファンダ点の指標（各行クリックで詳細・グラフ展開）</h2>
    <div class="group-head"><span>業績グループ</span><span>{_fmt(item.get("perf_score"), 1)} / 110</span></div>
    {perf_rows}
    <div class="group-head"><span>財務グループ</span><span>{_fmt(item.get("fin_score"), 1)} / 110</span></div>
    {fin_rows}
    <div class="group-head"><span>キャッシュフローグループ</span><span>{_fmt(item.get("cf_score"), 1)} / 110</span></div>
    {cf_rows}
  </div>

  <div class="section-card">
    <h2>② 買い時の指標（各行クリックでレンジ図・判定ルール展開）</h2>
    {buy_rows}
  </div>

  <div class="section-card">
    <h2>株価の推移（5年レンジ・年平均）と期間別騰落率</h2>
    {_svg_price_chart(det.get("yearly_prices", {}), item.get("close"))}
    <table class="ret-table"><tr>{ret_tds}</tr></table>
  </div>

  <div class="section-card">
    <h2>直近決算とアナリスト予想</h2>
    <div class="kv-grid">
      <div class="kv-box"><div class="kv-lbl">直近四半期 売上高 YoY</div><div class="kv-val">{_fmt_signed(q_yoy.get("rev"))}</div></div>
      <div class="kv-box"><div class="kv-lbl">直近四半期 営業利益 YoY</div><div class="kv-val">{_fmt_signed(q_yoy.get("op"))}</div></div>
      <div class="kv-box"><div class="kv-lbl">直近四半期 純利益 YoY</div><div class="kv-val">{_fmt_signed(q_yoy.get("ni"))}</div></div>
      <div class="kv-box"><div class="kv-lbl">予想EPS / 予想PER</div><div class="kv-val">{_fmt(det.get("forward_eps"), 2, "", "$")} ／ {_fmt(det.get("forward_pe"), 1, "倍")}</div></div>
      <div class="kv-box"><div class="kv-lbl">アナリスト目標株価（平均）</div><div class="kv-val">{_fmt(tgt_mean, 2, "", "$")}（{_fmt_signed(tgt_diff)}）</div></div>
      <div class="kv-box"><div class="kv-lbl">目標レンジ（安値〜高値）</div><div class="kv-val">{_fmt(analyst.get("target_low_price"), 0, "", "$")} 〜 {_fmt(analyst.get("target_high_price"), 0, "", "$")}</div></div>
      <div class="kv-box"><div class="kv-lbl">アナリスト・レーティング</div><div class="kv-val">{_fmt(analyst.get("recommendation_mean"), 2)}（1強気〜5弱気 / {analyst.get("num_opinions") or "-"}人）</div></div>
      <div class="kv-box"><div class="kv-lbl">オプション向け参考シグナル</div><div class="kv-val">強気1軍: {"〇" if opt.get("bull_tier1") else "−"} ／ 弱気警戒: {_fmt(opt.get("bear_watch_score"), 1)}</div></div>
    </div>
  </div>

  <div class="section-card">
    <h2>参考指標（採点しない）</h2>
    {ref_rows}
  </div>

  <div class="section-card">
    <h2>見方を深める指標（採点しない）</h2>
    {deep_rows}
  </div>

  <footer class="disclaimer">
    ※ 本ページは Yahoo Finance（yfinance）等の公開データをもとに自動生成された情報提供・学習用レポートであり、特定の銘柄の売買を推奨する投資助言ではありません。最終的な投資判断はご自身の責任で行ってください。
  </footer>
</div>

<script>
(() => {{
  const PRESETS = {{
    genko: "#2563eb", blueplus: "#0284c7", teal: "#0d9488",
    slate: "#475569", sand: "#b45309", violet: "#7c3aed", rose: "#e11d48"
  }};
  const presetSel = document.getElementById("theme-preset");
  const darkBtn = document.getElementById("dark-toggle");
  function applyTheme(preset, dark) {{
    document.documentElement.style.setProperty("--accent", PRESETS[preset] || PRESETS.genko);
    document.body.classList.toggle("dark", !!dark);
    darkBtn.textContent = dark ? "☀️ ライトへ" : "🌙 ダークへ";
    presetSel.value = preset;
    localStorage.setItem("pp_theme_long", JSON.stringify({{ preset, dark }}));
  }}
  try {{
    const saved = JSON.parse(localStorage.getItem("pp_theme_long") || "{{}}");
    applyTheme(saved.preset || "genko", !!saved.dark);
  }} catch {{ applyTheme("genko", false); }}
  presetSel.addEventListener("change", () => applyTheme(presetSel.value, document.body.classList.contains("dark")));
  darkBtn.addEventListener("click", () => applyTheme(presetSel.value, !document.body.classList.contains("dark")));

  // 年次／四半期グラフ切り替え
  document.querySelectorAll(".chart-toggle-wrap").forEach(wrap => {{
    const btns = wrap.querySelectorAll(".ctab");
    const pAnnual = wrap.querySelector(".pane-annual");
    const pQ = wrap.querySelector(".pane-quarterly");
    btns.forEach(btn => {{
      btn.addEventListener("click", () => {{
        const mode = btn.dataset.mode;
        btns.forEach(b => b.classList.toggle("active", b.dataset.mode === mode));
        if (pAnnual) pAnnual.style.display = mode === "annual" ? "" : "none";
        if (pQ) pQ.style.display = mode === "quarterly" ? "" : "none";
      }});
    }});
  }});
}})();
</script>
</body>
</html>"""


def generate_all_reports(scored_data: dict[str, Any], dist_dir: Path) -> int:
    """全銘柄分の個別レポートを dist/reports/<TICKER>.html に生成する。"""
    reports_dir = dist_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    now_jst = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")

    items: list[dict[str, Any]] = scored_data["items"]
    for item in items:
        file_sym = item["symbol"].replace("/", "_")
        report_html = generate_report_for_stock(item, generated_at=now_jst)
        (reports_dir / f"{file_sym}.html").write_text(report_html, encoding="utf-8")
    return len(items)
