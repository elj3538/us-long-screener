"""yfinanceから米国株の株価・財務・決算データを取得しキャッシュするモジュール。"""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import certifi
import numpy as np
import pandas as pd

# 日本語パス配下の.venvだとcurl_cffi(libcurl)がCA証明書を読めないためASCII一時パスへコピー
def _ensure_ascii_ca_bundle() -> None:
    src = certifi.where()
    try:
        src.encode("ascii")
        return
    except UnicodeEncodeError:
        pass
    dst = Path(tempfile.gettempdir()) / "agy_cacert.pem"
    if not dst.exists() or dst.stat().st_size != Path(src).stat().st_size:
        shutil.copyfile(src, dst)
    os.environ["CURL_CA_BUNDLE"] = str(dst)
    os.environ["SSL_CERT_FILE"] = str(dst)

_ensure_ascii_ca_bundle()

import yfinance as yf

logger = logging.getLogger(__name__)


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _extract_series(df: pd.DataFrame | None, candidates: list[str], limit: int = 5) -> list[dict[str, Any]]:
    """財務諸表DataFrameから候補行名の時系列（新しい順）を抽出する。"""
    if df is None or df.empty:
        return []
    row_name = next((name for name in candidates if name in df.index), None)
    if row_name is None:
        return []

    series = df.loc[row_name]
    if isinstance(series, pd.DataFrame):
        series = series.iloc[0]

    # 列を日付降順に揃える
    cols = sorted(df.columns, key=lambda c: str(c), reverse=True)[:limit]
    result: list[dict[str, Any]] = []
    for col in cols:
        val = _safe_float(series.get(col))
        if val is not None:
            date_str = col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)[:10]
            result.append({"date": date_str, "value": val})
    return result


def _calc_returns_and_technicals(hist: pd.DataFrame | None) -> dict[str, Any]:
    """日次株価履歴から騰落率(D/W/M/3M/6M/9M/Y)・RSI(14)・MACD・年次平均株価を算出する。"""
    empty = {
        "latest_close": None,
        "latest_date": None,
        "returns": {"D": None, "W": None, "M": None, "3M": None, "6M": None, "9M": None, "Y": None},
        "rsi14": None,
        "macd": None,
        "macd_signal": None,
        "yearly_prices": {},
    }
    if hist is None or hist.empty or "Close" not in hist.columns:
        return empty

    close = hist["Close"].dropna()
    if close.empty:
        return empty

    latest_close = _safe_float(close.iloc[-1])
    latest_date = close.index[-1].strftime("%Y-%m-%d") if hasattr(close.index[-1], "strftime") else str(close.index[-1])[:10]

    offsets = {"D": 1, "W": 5, "M": 21, "3M": 63, "6M": 126, "9M": 189, "Y": 252}
    returns: dict[str, float | None] = {}
    n = len(close)
    for label, offset in offsets.items():
        if n > offset and latest_close is not None:
            prev = _safe_float(close.iloc[-1 - offset])
            if prev and prev > 0:
                returns[label] = round((latest_close / prev - 1.0) * 100.0, 2)
            else:
                returns[label] = None
        else:
            returns[label] = None

    # RSI(14)
    rsi14 = None
    if n >= 15:
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        last_gain = _safe_float(gain.iloc[-1])
        last_loss = _safe_float(loss.iloc[-1])
        if last_gain is not None and last_loss is not None:
            if last_loss == 0:
                rsi14 = 100.0
            else:
                rs = last_gain / last_loss
                rsi14 = round(100.0 - (100.0 / (1.0 + rs)), 2)

    # MACD(12, 26, 9)
    macd_val = None
    macd_sig = None
    if n >= 35:
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_val = _safe_float(macd_line.iloc[-1])
        macd_sig = _safe_float(signal_line.iloc[-1])
        if macd_val is not None:
            macd_val = round(macd_val, 3)
        if macd_sig is not None:
            macd_sig = round(macd_sig, 3)

    # 年別株価（過去レンジ算出用）
    yearly_prices: dict[str, dict[str, float]] = {}
    if hasattr(close.index, "year"):
        for yr, grp in close.groupby(close.index.year):
            yearly_prices[str(yr)] = {
                "min": round(float(grp.min()), 2),
                "max": round(float(grp.max()), 2),
                "avg": round(float(grp.mean()), 2),
            }

    return {
        "latest_close": round(latest_close, 2) if latest_close is not None else None,
        "latest_date": latest_date,
        "returns": returns,
        "rsi14": rsi14,
        "macd": macd_val,
        "macd_signal": macd_sig,
        "yearly_prices": yearly_prices,
    }


def fetch_stock_data(
    constituent: dict[str, Any],
    cache_dir: Path,
    use_cache: bool = True,
    max_cache_age_hours: float = 20.0,
    sleep_sec: float = 0.25,
) -> dict[str, Any] | None:
    """1銘柄分のデータをyfinanceから取得（またはキャッシュから読込）する。"""
    yf_symbol = constituent["yf_symbol"]
    stock_cache_dir = cache_dir / "stocks"
    stock_cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = stock_cache_dir / f"{yf_symbol}.json"

    if use_cache and cache_file.exists():
        age_hours = (time.time() - cache_file.stat().st_mtime) / 3600.0
        if age_hours <= max_cache_age_hours:
            try:
                return json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception:
                pass

    for attempt in range(2):
        try:
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info or {}
            hist = ticker.history(period="5y", interval="1d", auto_adjust=True)
            tech = _calc_returns_and_technicals(hist)

            inc = ticker.income_stmt
            q_inc = ticker.quarterly_income_stmt
            bs = ticker.balance_sheet
            cf = ticker.cashflow

            # 財務指標の抽出（新しい順）
            data: dict[str, Any] = {
                "symbol": constituent["symbol"],
                "yf_symbol": yf_symbol,
                "name": constituent["name"],
                "short_name": info.get("shortName") or constituent["name"],
                "sector_en": constituent["sector_en"],
                "sector_ja": constituent["sector_ja"],
                "sub_industry": constituent.get("sub_industry", ""),
                "industry_yf": info.get("industry", ""),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "price": {
                    "current": _safe_float(info.get("currentPrice"))
                    or _safe_float(info.get("regularMarketPrice"))
                    or tech["latest_close"],
                    "latest_date": tech["latest_date"],
                    "market_cap": _safe_float(info.get("marketCap")),
                    "enterprise_value": _safe_float(info.get("enterpriseValue")),
                    "returns": tech["returns"],
                    "rsi14": tech["rsi14"],
                    "macd": tech["macd"],
                    "macd_signal": tech["macd_signal"],
                    "yearly_prices": tech["yearly_prices"],
                },
                "valuation": {
                    "trailing_pe": _safe_float(info.get("trailingPE")),
                    "forward_pe": _safe_float(info.get("forwardPE")),
                    "price_to_book": _safe_float(info.get("priceToBook")),
                    "dividend_yield": _safe_float(info.get("dividendYield")),
                    "trailing_eps": _safe_float(info.get("trailingEps")),
                    "forward_eps": _safe_float(info.get("forwardEps")),
                    "book_value": _safe_float(info.get("bookValue")),
                    "roe_info": _safe_float(info.get("returnOnEquity")),
                    "roa_info": _safe_float(info.get("returnOnAssets")),
                    "shares_outstanding": _safe_float(info.get("sharesOutstanding")),
                },
                "analyst": {
                    "num_opinions": info.get("numberOfAnalystOpinions"),
                    "target_mean_price": _safe_float(info.get("targetMeanPrice")),
                    "target_high_price": _safe_float(info.get("targetHighPrice")),
                    "target_low_price": _safe_float(info.get("targetLowPrice")),
                    "recommendation_mean": _safe_float(info.get("recommendationMean")),
                },
                "financials": {
                    "revenue": _extract_series(inc, ["Total Revenue", "Operating Revenue"]),
                    "operating_income": _extract_series(inc, ["Operating Income", "EBIT"]),
                    "ebit": _extract_series(inc, ["EBIT", "Operating Income"]),
                    "net_income": _extract_series(inc, ["Net Income", "Net Income Common Stockholders"]),
                    "eps": _extract_series(inc, ["Diluted EPS", "Basic EPS"]),
                    "interest_expense": _extract_series(inc, ["Interest Expense", "Interest Expense Non Operating"]),
                    "shares": _extract_series(inc, ["Diluted Average Shares", "Basic Average Shares"]),
                },
                "quarterly": {
                    "revenue": _extract_series(q_inc, ["Total Revenue", "Operating Revenue"], limit=6),
                    "operating_income": _extract_series(q_inc, ["Operating Income", "EBIT"], limit=6),
                    "net_income": _extract_series(q_inc, ["Net Income", "Net Income Common Stockholders"], limit=6),
                },
                "balance_sheet": {
                    "total_debt": _extract_series(bs, ["Total Debt", "Long Term Debt And Capital Lease Obligation"]),
                    "cash": _extract_series(bs, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"]),
                    "equity": _extract_series(bs, ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"]),
                    "total_assets": _extract_series(bs, ["Total Assets"]),
                },
                "cashflow": {
                    "operating_cf": _extract_series(cf, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"]),
                    "capex": _extract_series(cf, ["Capital Expenditure"]),
                    "free_cf": _extract_series(cf, ["Free Cash Flow"]),
                    "depreciation": _extract_series(cf, ["Depreciation And Amortization", "Depreciation Amortization Depletion"]),
                    "dividends_paid": _extract_series(cf, ["Cash Dividends Paid", "Common Stock Dividend Paid"]),
                    "buybacks": _extract_series(cf, ["Repurchase Of Capital Stock"]),
                    "sbc": _extract_series(cf, ["Stock Based Compensation"]),
                },
                "summary": info.get("longBusinessSummary", ""),
            }

            cache_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            if sleep_sec > 0:
                time.sleep(sleep_sec)
            return data
        except Exception as exc:
            logger.warning("%s の取得に失敗 (attempt %d): %s", yf_symbol, attempt + 1, exc)
            time.sleep(1.0)

    # 取得失敗時は古いキャッシュでもあれば返す
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None
