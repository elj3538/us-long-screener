"""取得した財務・株価データから品質スコア・買い時スコア・軍分け・業種級を算出するモジュール。"""

from __future__ import annotations

import math
from statistics import mean, median, pstdev
from typing import Any


def _piecewise(val: float | None, points: list[tuple[float, float]]) -> float | None:
    """区分線形補間で指標値を0〜110のスコアに変換する。pointsはx昇順。"""
    if val is None or math.isnan(val) or math.isinf(val):
        return None
    if val <= points[0][0]:
        return points[0][1]
    if val >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= val <= x1:
            if x1 == x0:
                return y1
            ratio = (val - x0) / (x1 - x0)
            return y0 + ratio * (y1 - y0)
    return None


def _avg(values: list[float | None]) -> float | None:
    valid = [v for v in values if v is not None]
    return sum(valid) / len(valid) if valid else None


def _calc_cagr(series: list[dict[str, Any]]) -> float | None:
    """新しい順の年次シリーズからCAGR(%)を算出する（2〜4年分）。"""
    if len(series) < 2:
        return None
    latest = series[0]["value"]
    oldest = series[-1]["value"]
    years = len(series) - 1
    if oldest is None or latest is None or oldest <= 0 or latest <= 0:
        # 負→正などの場合は単純変化率をクリップして近似
        if oldest and oldest != 0 and latest is not None:
            pct = (latest - oldest) / abs(oldest) * 100.0 / years
            return max(-50.0, min(50.0, pct))
        return None
    cagr = ((latest / oldest) ** (1.0 / years) - 1.0) * 100.0
    return round(max(-80.0, min(150.0, cagr)), 2)


def _grade3(val: float | None, good_cond: bool, warn_cond: bool) -> str | None:
    if val is None:
        return None
    if good_cond:
        return "良好"
    if warn_cond:
        return "注意"
    return "弱い"


def classify_model(stock: dict[str, Any]) -> str:
    """銘柄の業種から採点モデル（general / financial / reit）を判定する。"""
    sector_en = stock.get("sector_en", "")
    sub = stock.get("sub_industry", "")
    ind = stock.get("industry_yf", "")
    sym = stock.get("symbol", "")

    if sector_en == "Real Estate":
        if "REIT" in sub or "REIT" in ind:
            return "reit"
        return "general"

    if sector_en == "Financials":
        # 運用・取引所・決済網・格付等は一般企業モデル
        general_fin_tickers = {"V", "MA", "PYPL", "AXP", "MSCI", "SPGI", "MCO", "ICE", "CME", "NDAQ", "CBOE", "FDS", "FIS", "FI", "JKHY", "GPN"}
        if sym in general_fin_tickers:
            return "general"
        if any(k in sub or k in ind for k in ["Bank", "Insurance", "Capital Markets", "Brokerage"]) or sym in {"GS", "MS"}:
            return "financial"
    return "general"


def _compute_raw_metrics(stock: dict[str, Any]) -> dict[str, Any]:
    """1銘柄の財務指標・基礎スコア（業種比較前）を算出する。"""
    fin = stock.get("financials", {})
    q = stock.get("quarterly", {})
    bs = stock.get("balance_sheet", {})
    cf = stock.get("cashflow", {})
    val = stock.get("valuation", {})
    price_info = stock.get("price", {})

    model = classify_model(stock)
    mkt_cap = price_info.get("market_cap")
    ev = price_info.get("enterprise_value")
    cur_price = price_info.get("current")

    rev_s = fin.get("revenue", [])
    op_s = fin.get("operating_income", [])
    ebit_s = fin.get("ebit", []) or op_s
    ni_s = fin.get("net_income", [])
    eps_s = fin.get("eps", [])
    int_s = fin.get("interest_expense", [])

    debt_s = bs.get("total_debt", [])
    cash_s = bs.get("cash", [])
    eq_s = bs.get("equity", [])
    assets_s = bs.get("total_assets", [])

    ocf_s = cf.get("operating_cf", [])
    capex_s = cf.get("capex", [])
    fcf_s = cf.get("free_cf", [])
    dep_s = cf.get("depreciation", [])
    div_s = cf.get("dividends_paid", [])

    # 成長率
    rev_cagr = _calc_cagr(rev_s)
    eps_cagr = _calc_cagr(eps_s)
    if eps_cagr is None:
        eps_cagr = _calc_cagr(ni_s)

    # 営業利益率（直近 %）
    op_margin = None
    if rev_s and op_s and rev_s[0]["value"] and rev_s[0]["value"] > 0:
        op_margin = round(op_s[0]["value"] / rev_s[0]["value"] * 100.0, 2)

    # 利益の安定度（直近3〜4年の黒字比率＋変動抑制度）
    profit_stability = None
    if len(ni_s) >= 2:
        vals = [x["value"] for x in ni_s]
        pos_ratio = sum(1 for v in vals if v > 0) / len(vals)
        mean_abs = sum(abs(v) for v in vals) / len(vals)
        if mean_abs > 0:
            std = (sum((v - (sum(vals) / len(vals))) ** 2 for v in vals) / len(vals)) ** 0.5
            cv = std / mean_abs
            profit_stability = round(max(0.0, min(110.0, pos_ratio * 85.0 + max(0.0, 25.0 - cv * 25.0))), 1)
        else:
            profit_stability = 30.0

    # 急減速チェック（直近四半期YoYが年率トレンドより5pt以上下回り、かつ営業利益または純利益がYoYマイナス）
    rapid_decel = False
    q_rev = q.get("revenue", [])
    q_op = q.get("operating_income", [])
    q_ni = q.get("net_income", [])
    q_rev_yoy = None
    if len(q_rev) >= 5 and q_rev[4]["value"] and q_rev[4]["value"] > 0:
        q_rev_yoy = (q_rev[0]["value"] / q_rev[4]["value"] - 1.0) * 100.0
    q_op_yoy = None
    if len(q_op) >= 5 and q_op[4]["value"] and q_op[4]["value"] != 0:
        q_op_yoy = (q_op[0]["value"] / abs(q_op[4]["value"]) - (1.0 if q_op[4]["value"] > 0 else -1.0)) * 100.0
    q_ni_yoy = None
    if len(q_ni) >= 5 and q_ni[4]["value"] and q_ni[4]["value"] != 0:
        q_ni_yoy = (q_ni[0]["value"] / abs(q_ni[4]["value"]) - (1.0 if q_ni[4]["value"] > 0 else -1.0)) * 100.0

    if q_rev_yoy is not None and rev_cagr is not None:
        if (q_rev_yoy <= rev_cagr - 5.0) and ((q_op_yoy is not None and q_op_yoy < 0) or (q_ni_yoy is not None and q_ni_yoy < 0)):
            rapid_decel = True

    # 財務指標
    latest_debt = debt_s[0]["value"] if debt_s else None
    latest_cash = cash_s[0]["value"] if cash_s else None
    latest_eq = eq_s[0]["value"] if eq_s else None
    latest_assets = assets_s[0]["value"] if assets_s else None
    latest_ocf = ocf_s[0]["value"] if ocf_s else None
    latest_ebit = ebit_s[0]["value"] if ebit_s else None
    latest_int = abs(int_s[0]["value"]) if int_s else None

    de_ratio = None
    net_de_ratio = None
    if latest_debt is not None and latest_eq is not None and latest_eq > 0:
        de_ratio = round(latest_debt / latest_eq, 2)
        if latest_cash is not None:
            net_de_ratio = round((latest_debt - latest_cash) / latest_eq, 2)

    debt_to_ocf = None
    if latest_debt is not None and latest_ocf is not None and latest_ocf > 0:
        debt_to_ocf = round(latest_debt / latest_ocf, 2)

    interest_cov = None
    if latest_ebit is not None:
        if latest_int is None or latest_int <= 0:
            interest_cov = 99.9
        else:
            interest_cov = round(latest_ebit / latest_int, 2)

    # キャッシュフロー指標
    latest_fcf = None
    if fcf_s:
        latest_fcf = fcf_s[0]["value"]
    elif latest_ocf is not None and capex_s:
        latest_fcf = latest_ocf - abs(capex_s[0]["value"])

    fcf_yield = None
    if latest_fcf is not None and mkt_cap and mkt_cap > 0:
        fcf_yield = round(latest_fcf / mkt_cap * 100.0, 2)

    fcf_payout = None
    if latest_fcf is not None and div_s:
        div_abs = abs(div_s[0]["value"])
        if div_abs == 0:
            fcf_payout = 0.0
        elif latest_fcf > 0:
            fcf_payout = round(div_abs / latest_fcf * 100.0, 1)
        else:
            fcf_payout = 999.0

    # ROE / ROA (%)
    roe = round(val["roe_info"] * 100.0, 2) if val.get("roe_info") is not None else None
    if roe is None and ni_s and latest_eq and latest_eq > 0:
        roe = round(ni_s[0]["value"] / latest_eq * 100.0, 2)

    roa = round(val["roa_info"] * 100.0, 2) if val.get("roa_info") is not None else None
    if roa is None and ni_s and latest_assets and latest_assets > 0:
        roa = round(ni_s[0]["value"] / latest_assets * 100.0, 2)

    # EV/EBIT
    ev_ebit = None
    if ev and latest_ebit and latest_ebit > 0:
        ev_ebit = round(ev / latest_ebit, 2)

    per = val.get("trailing_pe") or val.get("forward_pe")
    if per is not None:
        per = round(per, 2)
    pbr = val.get("price_to_book")
    if pbr is not None:
        pbr = round(pbr, 2)

    div_yield = None
    if val.get("dividend_yield") is not None:
        dy = val["dividend_yield"]
        # yfinanceは環境により0.005または0.5(%)を返すことがあるため調整
        div_yield = round(dy * 100.0 if dy < 0.25 else dy, 2)

    # REIT用 FFO近似（純利益 + 減価償却費）
    ffo_cagr = None
    p_ffo = None
    ffo_stability = None
    ffo_int_cov = None
    if model == "reit" and ni_s:
        ffo_series = []
        dep_map = {d["date"][:4]: d["value"] for d in dep_s}
        for item in ni_s:
            yr = item["date"][:4]
            dep_val = dep_map.get(yr, 0.0)
            ffo_series.append({"date": item["date"], "value": item["value"] + dep_val})
        ffo_cagr = _calc_cagr(ffo_series)
        if ffo_series and mkt_cap and ffo_series[0]["value"] > 0:
            p_ffo = round(mkt_cap / ffo_series[0]["value"], 2)
        if len(ffo_series) >= 2:
            fvals = [x["value"] for x in ffo_series]
            pos_r = sum(1 for v in fvals if v > 0) / len(fvals)
            ffo_stability = round(pos_r * 95.0, 1)
        if ffo_series and latest_int and latest_int > 0:
            ffo_int_cov = round((ffo_series[0]["value"] + latest_int) / latest_int, 2)
        elif ffo_series:
            ffo_int_cov = 99.9

    # v2: 資本効率（ROIC）＆株式希薄化＆CF連続指標を先出し計算
    roic_pre = None
    if latest_ebit is not None and latest_eq is not None:
        ic_pre = (latest_debt or 0.0) + latest_eq - (latest_cash or 0.0)
        if ic_pre > 0:
            roic_pre = round(latest_ebit * 0.79 / ic_pre * 100.0, 2)
    shares_s_pre = fin.get("shares", [])
    shares_chg_pre = None
    if len(shares_s_pre) >= 2 and shares_s_pre[-1]["value"] and shares_s_pre[-1]["value"] > 0:
        shares_chg_pre = round((shares_s_pre[0]["value"] / shares_s_pre[-1]["value"] - 1.0) * 100.0, 2)
    rev_v_pre = rev_s[0]["value"] if rev_s else None
    ocf_margin = round(latest_ocf / rev_v_pre * 100.0, 2) if (latest_ocf is not None and rev_v_pre and rev_v_pre > 0) else None
    fcf_margin = round(latest_fcf / rev_v_pre * 100.0, 2) if (latest_fcf is not None and rev_v_pre and rev_v_pre > 0) else None
    ocf_to_ni_pre = round(latest_ocf / ni_s[0]["value"], 2) if (latest_ocf is not None and ni_s and ni_s[0]["value"] and ni_s[0]["value"] > 0) else None

    # v2: 各スコア要素の採点（0〜110）
    s_rev = _piecewise(rev_cagr, [(-10, 10), (-5, 28), (0, 50), (4, 70), (10, 92), (18, 110)])
    s_eps = _piecewise(eps_cagr, [(-15, 10), (-5, 28), (0, 50), (6, 74), (14, 94), (24, 110)])
    s_margin = _piecewise(op_margin, [(0, 15), (5, 42), (12, 66), (20, 86), (30, 102), (40, 110)])
    s_perf = _avg([s_rev, s_eps, s_margin, profit_stability])
    if s_perf is not None and rapid_decel:
        s_perf = round(s_perf * 0.72, 1)
    elif s_perf is not None:
        s_perf = round(s_perf, 1)

    # v2: 資本効率（ROIC 75% ＋ 株式希薄化/自社株買い 25%）
    s_roic = _piecewise(roic_pre, [(0, 15), (6, 42), (12, 70), (20, 94), (32, 110)])
    s_shchg = _piecewise(shares_chg_pre, [(-12, 108), (-4, 92), (0, 74), (4, 52), (12, 18)])
    if s_roic is not None and s_shchg is not None:
        s_cap_eff = round(s_roic * 0.75 + s_shchg * 0.25, 1)
    else:
        s_cap_eff = round(s_roic, 1) if s_roic is not None else (round(s_shchg, 1) if s_shchg is not None else None)

    s_de = _piecewise(de_ratio, [(0.0, 106), (0.5, 92), (1.0, 74), (1.5, 54), (2.2, 36), (3.5, 10)])
    s_nde = _piecewise(net_de_ratio, [(-0.5, 106), (0.0, 94), (0.5, 78), (1.0, 58), (1.8, 38), (3.0, 10)])
    s_docf = _piecewise(debt_to_ocf, [(0.0, 106), (1.5, 92), (3.0, 74), (4.5, 54), (6.5, 36), (10.0, 10)])
    s_icov = _piecewise(interest_cov, [(1.0, 10), (3.0, 42), (8.0, 76), (15.0, 94), (30.0, 108)])
    s_fin = _avg([s_de, s_nde, s_docf, s_icov])
    if s_fin is not None:
        s_fin = round(s_fin, 1)

    # v2: CF連続採点（2値採点廃止 → 営業CFマージン・FCFマージン・キャッシュ変換率・FCF配当性向）
    s_ocfm = _piecewise(ocf_margin, [(-2, 15), (5, 45), (12, 72), (22, 94), (35, 110)])
    s_fcfm = _piecewise(fcf_margin, [(-5, 15), (2, 45), (8, 72), (16, 94), (28, 110)])
    s_ocfni = _piecewise(ocf_to_ni_pre, [(0.3, 18), (0.8, 56), (1.1, 82), (1.5, 100), (2.0, 108)])
    s_fcf_pay = _piecewise(fcf_payout, [(0, 104), (30, 92), (55, 76), (80, 52), (100, 34), (130, 12)])
    s_cf = _avg([s_ocfm, s_fcfm, s_ocfni, s_fcf_pay])
    if s_cf is not None:
        s_cf = round(s_cf, 1)

    # v2: 品質スコア統合（一般企業はROIC/資本効率を組み込み、金融モデルは一般企業と分布を校正）
    quality_score: float | None = None
    if model == "general":
        parts = [(s_perf, 0.30), (s_cap_eff, 0.25), (s_fin, 0.25), (s_cf, 0.20)]
        valid_parts = [(sc, w) for sc, w in parts if sc is not None]
        if valid_parts:
            w_sum = sum(w for _, w in valid_parts)
            quality_score = round(sum(sc * w for sc, w in valid_parts) / w_sum, 1)
    elif model == "financial":
        # 金融株の高得点偏重を抑えるため、カーブを校正（上限103付近）
        s_roe_f = _piecewise(roe, [(0, 15), (6, 44), (10, 66), (15, 84), (22, 100)])
        s_rev_f = _piecewise(rev_cagr, [(-8, 15), (0, 48), (5, 70), (12, 88), (22, 102)])
        s_eps_f = _piecewise(eps_cagr, [(-10, 15), (0, 48), (7, 72), (15, 90), (25, 104)])
        s_stab_f = min(98.0, profit_stability * 0.92) if profit_stability is not None else None
        quality_score = _avg([s_roe_f, s_rev_f, s_eps_f, s_stab_f])
        if quality_score is not None and rapid_decel:
            quality_score *= 0.80
        if quality_score is not None:
            quality_score = round(quality_score, 1)
    elif model == "reit":
        s_ffo_g = _piecewise(ffo_cagr, [(-5, 20), (0, 52), (3, 72), (7, 92), (12, 106)])
        s_ffo_ic = _piecewise(ffo_int_cov, [(1.5, 20), (3.0, 52), (5.0, 78), (10.0, 102)])
        quality_score = _avg([s_ffo_g, s_rev, ffo_stability, s_ffo_ic])
        if quality_score is not None:
            quality_score = round(quality_score, 1)

    # Forward PER & PEG（v2 買い時スコア用）
    fwd_pe_v = val.get("forward_pe")
    if fwd_pe_v is not None and (fwd_pe_v <= 0 or fwd_pe_v > 200):
        fwd_pe_v = None
    eff_pe_v = fwd_pe_v or per
    peg_val = round(eff_pe_v / min(eps_cagr, 45.0), 2) if (eff_pe_v and eps_cagr is not None and eps_cagr >= 3.0) else None

    # 自社過去PERレンジ近似（5年年次価格レンジの中における現在株価の相対位置）
    per_range_pos = None
    yearly_prices = price_info.get("yearly_prices", {})
    if cur_price and len(yearly_prices) >= 2:
        all_min = min(v["min"] for v in yearly_prices.values())
        all_max = max(v["max"] for v in yearly_prices.values())
        if all_max > all_min:
            # レンジの下側にあるほど割安度が高い（元サイトの表現「良好60%以上」に合わせて割安位置%=100-(現在-min)/(max-min)*100）
            per_range_pos = round((1.0 - (cur_price - all_min) / (all_max - all_min)) * 100.0, 1)
            per_range_pos = max(0.0, min(100.0, per_range_pos))

    # カバレッジ（取得済み指標の充実度）
    check_fields = [rev_cagr, eps_cagr, op_margin, de_ratio, interest_cov, latest_ocf, latest_fcf, per, roe]
    filled = sum(1 for f in check_fields if f is not None)
    coverage = "高" if filled >= 8 else ("中" if filled >= 5 else "低")

    # 参考・深掘り指標の算出
    equity_ratio = round(latest_eq / latest_assets * 100.0, 1) if (latest_eq and latest_assets and latest_assets > 0) else None
    fin_leverage = round(latest_assets / latest_eq, 2) if (latest_assets and latest_eq and latest_eq > 0) else None
    earnings_yield = round(100.0 / per, 2) if (per and per > 0) else None

    # ROIC 近似 = EBIT * (1 - 0.21) / (総負債 + 自己資本 - 現金)
    roic = None
    if latest_ebit is not None and latest_eq is not None:
        invested_cap = (latest_debt or 0.0) + latest_eq - (latest_cash or 0.0)
        if invested_cap > 0:
            roic = round(latest_ebit * 0.79 / invested_cap * 100.0, 2)

    # 自社株買い・総還元性向
    buybacks_s = cf.get("buybacks", [])
    latest_buyback = abs(buybacks_s[0]["value"]) if buybacks_s else None
    buyback_yield = round(latest_buyback / mkt_cap * 100.0, 2) if (latest_buyback is not None and mkt_cap and mkt_cap > 0) else None
    latest_div_paid = abs(div_s[0]["value"]) if div_s else 0.0
    total_return_ratio = None
    if ni_s and ni_s[0]["value"] and ni_s[0]["value"] > 0 and (latest_buyback is not None or div_s):
        total_return_ratio = round((latest_div_paid + (latest_buyback or 0.0)) / ni_s[0]["value"] * 100.0, 1)

    # 営業CF / 純利益（利益の質）
    ocf_to_ni = round(latest_ocf / ni_s[0]["value"], 2) if (latest_ocf is not None and ni_s and ni_s[0]["value"] and ni_s[0]["value"] > 0) else None

    # 会計発生高 = (純利益 - 営業CF) / 平均総資産
    accruals = None
    if ni_s and latest_ocf is not None and assets_s:
        avg_assets = (assets_s[0]["value"] + assets_s[1]["value"]) / 2.0 if len(assets_s) >= 2 else assets_s[0]["value"]
        if avg_assets and avg_assets > 0:
            accruals = round((ni_s[0]["value"] - latest_ocf) / avg_assets * 100.0, 2)

    # 設備投資 / 減価償却費
    capex_to_dep = None
    if capex_s and dep_s and dep_s[0]["value"] and dep_s[0]["value"] > 0:
        capex_to_dep = round(abs(capex_s[0]["value"]) / dep_s[0]["value"], 2)

    # 発行済株式数の変化（過去3年 %）
    shares_s = fin.get("shares", [])
    shares_change_pct = None
    if len(shares_s) >= 2 and shares_s[-1]["value"] and shares_s[-1]["value"] > 0:
        shares_change_pct = round((shares_s[0]["value"] / shares_s[-1]["value"] - 1.0) * 100.0, 2)

    # SBC（株式報酬）の重さ
    sbc_s = cf.get("sbc", [])
    sbc_to_rev = None
    fcf_ex_sbc_margin = None
    if sbc_s and rev_s and rev_s[0]["value"] and rev_s[0]["value"] > 0:
        sbc_val = abs(sbc_s[0]["value"])
        sbc_to_rev = round(sbc_val / rev_s[0]["value"] * 100.0, 2)
        if latest_fcf is not None:
            fcf_ex_sbc_margin = round((latest_fcf - sbc_val) / rev_s[0]["value"] * 100.0, 2)

    # 簡易リバースDCF（割引率10%, ターミナル成長2.5%, 10年予測で現在時価総額を正当化するFCF年率成長率を二分探索）
    implied_fcf_growth = None
    if latest_fcf and latest_fcf > 0 and mkt_cap and mkt_cap > 0:
        r_disc, g_term = 0.10, 0.025
        lo, hi = -0.30, 0.80
        for _ in range(30):
            mid = (lo + hi) / 2.0
            pv = 0.0
            f_cur = latest_fcf
            for yr in range(1, 11):
                f_cur *= (1.0 + mid)
                pv += f_cur / ((1.0 + r_disc) ** yr)
            tv = f_cur * (1.0 + g_term) / (r_disc - g_term)
            pv += tv / ((1.0 + r_disc) ** 10)
            if pv < mkt_cap:
                lo = mid
            else:
                hi = mid
        implied_fcf_growth = round(((lo + hi) / 2.0) * 100.0, 1)

    # 年次営業利益率・FCF時系列（SVGグラフ用、古い順）
    op_margin_series = []
    op_map = {x["date"][:4]: x["value"] for x in op_s}
    for item in reversed(rev_s):
        yr = item["date"][:4]
        if yr in op_map and item["value"] and item["value"] > 0:
            op_margin_series.append({"date": yr, "value": round(op_map[yr] / item["value"] * 100.0, 1)})

    # 四半期売上高・営業利益・営業利益率時系列（古い順・直近6四半期）
    q_rev_series = [{"date": x["date"][2:7], "value": round(x["value"] / 1e9, 2)} for x in reversed(q_rev)]
    q_op_map = {x["date"][:7]: x["value"] for x in q_op}
    q_margin_series = []
    for item in reversed(q_rev):
        ym = item["date"][:7]
        if ym in q_op_map and item["value"] and item["value"] > 0:
            q_margin_series.append({"date": ym[2:], "value": round(q_op_map[ym] / item["value"] * 100.0, 1)})

    return {
        "symbol": stock["symbol"],
        "yf_symbol": stock["yf_symbol"],
        "name": stock.get("short_name") or stock["name"],
        "sector_en": stock["sector_en"],
        "sector_ja": stock["sector_ja"],
        "sub_industry": stock.get("sub_industry", ""),
        "model": model,
        "close": cur_price,
        "latest_date": price_info.get("latest_date"),
        "market_cap_b": round(mkt_cap / 1e9, 2) if mkt_cap else None,
        "returns": price_info.get("returns", {}),
        "rsi14": price_info.get("rsi14"),
        "macd": price_info.get("macd"),
        "macd_signal": price_info.get("macd_signal"),
        "quality_score": quality_score,
        "perf_score": s_perf,
        "fin_score": s_fin,
        "cf_score": s_cf,
        "rapid_decel": rapid_decel,
        "coverage": coverage,
        "sub_scores": {
            "rev": round(s_rev, 1) if s_rev is not None else None,
            "eps": round(s_eps, 1) if s_eps is not None else None,
            "margin": round(s_margin, 1) if s_margin is not None else None,
            "stability": profit_stability,
            "de": round(s_de, 1) if s_de is not None else None,
            "nde": round(s_nde, 1) if s_nde is not None else None,
            "docf": round(s_docf, 1) if s_docf is not None else None,
            "icov": round(s_icov, 1) if s_icov is not None else None,
            "ocf": round(s_ocfm, 1) if s_ocfm is not None else None,
            "fcf": round(s_fcfm, 1) if s_fcfm is not None else None,
            "fcf_pay": round(s_fcf_pay, 1) if s_fcf_pay is not None else None,
            "roic": round(s_roic, 1) if s_roic is not None else None,
            "cap_eff": s_cap_eff,
        },
        "detail": {
            "summary": stock.get("summary", ""),
            "analyst": stock.get("analyst", {}),
            "forward_pe": val.get("forward_pe"),
            "forward_eps": val.get("forward_eps"),
            "trailing_eps": val.get("trailing_eps"),
            "yearly_prices": price_info.get("yearly_prices", {}),
            "q_yoy": {
                "rev": round(q_rev_yoy, 1) if q_rev_yoy is not None else None,
                "op": round(q_op_yoy, 1) if q_op_yoy is not None else None,
                "ni": round(q_ni_yoy, 1) if q_ni_yoy is not None else None,
            },
            "series": {
                "revenue": [{"date": x["date"][:4], "value": round(x["value"] / 1e9, 2)} for x in reversed(rev_s)],
                "eps": [{"date": x["date"][:4], "value": round(x["value"], 2)} for x in reversed(eps_s)],
                "op_margin": op_margin_series,
                "ocf": [{"date": x["date"][:4], "value": round(x["value"] / 1e9, 2)} for x in reversed(ocf_s)],
                "fcf": [{"date": x["date"][:4], "value": round(x["value"] / 1e9, 2)} for x in reversed(fcf_s)],
            },
            "q_series": {
                "revenue": q_rev_series,
                "op_margin": q_margin_series,
            },
            "ref": {
                "implied_fcf_growth": implied_fcf_growth,
                "equity_ratio": equity_ratio,
                "fin_leverage": fin_leverage,
                "earnings_yield": earnings_yield,
                "roic": roic,
                "buyback_b": round(latest_buyback / 1e9, 2) if latest_buyback is not None else None,
                "buyback_yield": buyback_yield,
                "total_return_ratio": total_return_ratio,
                "ocf_to_ni": ocf_to_ni,
                "accruals": accruals,
                "capex_to_dep": capex_to_dep,
                "shares_change_pct": shares_change_pct,
                "sbc_to_rev": sbc_to_rev,
                "fcf_ex_sbc_margin": fcf_ex_sbc_margin,
            },
        },
        "metrics": {
            "rev_cagr": rev_cagr,
            "eps_cagr": eps_cagr,
            "op_margin": op_margin,
            "profit_stability": profit_stability,
            "de_ratio": de_ratio,
            "net_de_ratio": net_de_ratio,
            "debt_to_ocf": debt_to_ocf,
            "interest_cov": interest_cov,
            "ocf_positive": (latest_ocf > 0) if latest_ocf is not None else None,
            "fcf_positive": (latest_fcf > 0) if latest_fcf is not None else None,
            "fcf_payout": fcf_payout,
            "fcf_yield": fcf_yield,
            "ev_ebit": ev_ebit,
            "per": per,
            "forward_pe": round(fwd_pe_v, 2) if fwd_pe_v is not None else None,
            "peg": peg_val,
            "roic": roic_pre,
            "pbr": pbr,
            "p_ffo": p_ffo,
            "per_range_pos": per_range_pos,
            "roe": roe,
            "roa": roa,
            "div_yield": div_yield,
        },
        "grades": {
            "rev": _grade3(rev_cagr, (rev_cagr or -999) >= 3.0, -6.0 <= (rev_cagr or -999) < 3.0),
            "eps": _grade3(eps_cagr, (eps_cagr or -999) >= 5.0, -5.0 <= (eps_cagr or -999) < 5.0),
            "margin": _grade3(op_margin, (op_margin or -999) >= 15.0, 5.0 <= (op_margin or -999) < 15.0),
            "de": _grade3(de_ratio, (de_ratio or 999) <= 1.0, 1.0 < (de_ratio or 999) <= 2.0),
            "nde": _grade3(net_de_ratio, (net_de_ratio or 999) <= 0.5, 0.5 < (net_de_ratio or 999) <= 1.5),
            "docf": _grade3(debt_to_ocf, (debt_to_ocf or 999) <= 3.0, 3.0 < (debt_to_ocf or 999) <= 6.0),
            "icov": _grade3(interest_cov, (interest_cov or -1) >= 8.0, 3.0 <= (interest_cov or -1) < 8.0),
            "fcf_pay": _grade3(fcf_payout, (fcf_payout or 999) <= 50.0, 50.0 < (fcf_payout or 999) <= 85.0),
            "fcf_yield": _grade3(fcf_yield, (fcf_yield or -999) >= 4.0, 1.5 <= (fcf_yield or -999) < 4.0),
            "roe": _grade3(roe, (roe or -999) >= 8.0, 5.0 <= (roe or -999) < 8.0),
            "roa": _grade3(roa, (roa or -999) >= 5.0, 3.0 <= (roa or -999) < 5.0),
        },
    }


def score_all_stocks(raw_stocks: list[dict[str, Any]]) -> dict[str, Any]:
    """全銘柄を採点し、業種中央値・買い時スコア・軍分け・業種級を付与して返す。"""
    items = [_compute_raw_metrics(s) for s in raw_stocks if s]

    # セクター別集計（中央値算出）
    by_sector: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        by_sector.setdefault(item["sector_ja"], []).append(item)

    sector_stats: dict[str, dict[str, Any]] = {}
    for sec, sec_items in by_sector.items():
        q_vals = [x["quality_score"] for x in sec_items if x["quality_score"] is not None]
        ev_vals = [x["metrics"]["ev_ebit"] for x in sec_items if x["metrics"]["ev_ebit"] is not None and x["metrics"]["ev_ebit"] > 0]
        per_vals = [x["metrics"]["per"] for x in sec_items if x["metrics"]["per"] is not None and 0 < x["metrics"]["per"] < 150]
        pbr_vals = [x["metrics"]["pbr"] for x in sec_items if x["metrics"]["pbr"] is not None and 0 < x["metrics"]["pbr"] < 50]
        pffo_vals = [x["metrics"]["p_ffo"] for x in sec_items if x["metrics"]["p_ffo"] is not None and x["metrics"]["p_ffo"] > 0]

        q_med = round(median(q_vals), 1) if q_vals else 55.0
        sec_grade = "A" if q_med >= 66.0 else ("B" if q_med >= 54.0 else "C")

        sector_stats[sec] = {
            "count": len(sec_items),
            "quality_median": q_med,
            "sector_grade": sec_grade,
            "ev_ebit_median": round(median(ev_vals), 2) if ev_vals else None,
            "per_median": round(median(per_vals), 2) if per_vals else None,
            "pbr_median": round(median(pbr_vals), 2) if pbr_vals else None,
            "p_ffo_median": round(median(pffo_vals), 2) if pffo_vals else None,
        }

    # 買い時スコア算出 & 軍分け
    for sec, sec_items in by_sector.items():
        st = sector_stats[sec]
        for x in sec_items:
            m = x["metrics"]
            g = x["grades"]
            model = x["model"]

            # 対業種比
            ev_rel = round(m["ev_ebit"] / st["ev_ebit_median"], 2) if (m["ev_ebit"] and st["ev_ebit_median"]) else None
            per_rel = round(m["per"] / st["per_median"], 2) if (m["per"] and st["per_median"]) else None
            pbr_rel = round(m["pbr"] / st["pbr_median"], 2) if (m["pbr"] and st["pbr_median"]) else None

            m["ev_ebit_rel"] = ev_rel
            m["per_rel"] = per_rel
            m["pbr_rel"] = pbr_rel

            g["ev_ebit"] = _grade3(ev_rel, (ev_rel or 999) <= 0.85, 0.85 < (ev_rel or 999) <= 1.20)
            g["per_rel"] = _grade3(per_rel, (per_rel or 999) <= 0.95, 0.95 < (per_rel or 999) <= 1.20)
            g["pbr_rel"] = _grade3(pbr_rel, (pbr_rel or 999) <= 0.95, 0.95 < (pbr_rel or 999) <= 1.20)
            g["per_range"] = _grade3(m["per_range_pos"], (m["per_range_pos"] or -1) >= 60.0, 20.0 <= (m["per_range_pos"] or -1) < 60.0)

            s_ev = _piecewise(ev_rel, [(0.5, 110), (0.85, 88), (1.0, 68), (1.20, 48), (1.8, 15)])
            s_fcf_y = _piecewise(m["fcf_yield"], [(0.0, 20), (1.5, 45), (3.0, 68), (4.0, 82), (6.0, 100), (9.0, 110)])
            s_per_rel = _piecewise(per_rel, [(0.5, 110), (0.95, 82), (1.0, 68), (1.20, 45), (1.8, 15)])
            s_per_rng = _piecewise(m["per_range_pos"], [(0, 15), (20, 38), (50, 62), (60, 75), (85, 100), (100, 110)])
            s_per = _avg([s_per_rel, s_per_rng])
            s_pbr = _piecewise(pbr_rel, [(0.5, 110), (0.95, 82), (1.0, 68), (1.20, 45), (2.0, 15)])
            s_peg = _piecewise(m.get("peg"), [(0.7, 110), (1.2, 94), (1.8, 74), (2.6, 50), (4.0, 18)])

            # v2: 欠損時は60点固定埋めせず取得済み項目のみで平均＋PEGレシオ組み込み
            if model == "financial":
                b_raw = _avg([s_per, s_pbr, s_peg])
                buy_score = round(b_raw, 1) if b_raw is not None else 60.0
            elif model == "reit":
                pffo_rel = (m["p_ffo"] / st["p_ffo_median"]) if (m["p_ffo"] and st["p_ffo_median"]) else None
                buy_score = _piecewise(pffo_rel, [(0.6, 105), (0.9, 82), (1.0, 65), (1.2, 42), (1.6, 15)])
                buy_score = round(buy_score, 1) if buy_score is not None else 60.0
            else:
                exclude_pbr = x["sector_en"] in {"Information Technology", "Communication Services"}
                comps = [s_ev, s_fcf_y, s_per, s_peg] if exclude_pbr else [s_ev, s_fcf_y, s_per, s_pbr, s_peg]
                b_raw = _avg(comps)
                buy_score = round(b_raw, 1) if b_raw is not None else 60.0

            x["buy_score"] = buy_score
            x["sector_grade"] = st["sector_grade"]
            x["sector_medians"] = {
                "ev_ebit": st["ev_ebit_median"],
                "per": st["per_median"],
                "pbr": st["pbr_median"],
                "p_ffo": st["p_ffo_median"],
            }
            x["sub_scores"].update({
                "ev_ebit": round(s_ev, 1) if s_ev is not None else None,
                "fcf_yield": round(s_fcf_y, 1) if s_fcf_y is not None else None,
                "per": round(s_per, 1) if s_per is not None else None,
                "pbr": round(s_pbr, 1) if s_pbr is not None else None,
                "peg": round(s_peg, 1) if s_peg is not None else None,
            })

        # セクター内で品質スコア降順ソートして業種内偏差値＆軍分け
        sec_items.sort(key=lambda r: (r["quality_score"] if r["quality_score"] is not None else -1.0), reverse=True)
        q_valid = [r["quality_score"] for r in sec_items if r["quality_score"] is not None]
        q_mu = mean(q_valid) if q_valid else 50.0
        q_sd = pstdev(q_valid) if len(q_valid) >= 3 else 0.0
        n = len(sec_items)
        t1_cut = max(1, round(n * 0.25)) if n >= 4 else (1 if n >= 1 else 0)
        t2_cut = max(t1_cut, round(n * 0.70)) if n >= 3 else n

        for idx, x in enumerate(sec_items):
            q_sc = x["quality_score"]
            x["sector_dev"] = round(50.0 + 10.0 * (q_sc - q_mu) / q_sd, 1) if (q_sc is not None and q_sd > 0.01) else 50.0
            if q_sc is None:
                tier = 3
            elif idx < t1_cut:
                tier = 1
            elif idx < t2_cut:
                tier = 2
            else:
                tier = 3

            # カバレッジ「低」は2軍上限
            if x["coverage"] == "低" and tier == 1:
                tier = 2
            # 絶対品質スコアが高い（75点以上）場合は3軍に落とさない下限補正
            if q_sc is not None and q_sc >= 75.0 and tier == 3:
                tier = 2

            x["tier"] = tier
            x["sector_rank"] = idx + 1

            # オプション取引（強気・プット買い逆スクリーニング）向け補助指標
            x["option_signals"] = {
                "bull_tier1": (tier == 1 and not x["rapid_decel"]),
                "bear_watch_score": round(
                    max(0.0, min(100.0, (100.0 - (q_sc or 50.0)) * 0.5 + (100.0 - x["buy_score"]) * 0.3 + (20.0 if x["rapid_decel"] else 0.0))),
                    1,
                ),
            }

    return {
        "items": items,
        "sector_stats": sector_stats,
    }
