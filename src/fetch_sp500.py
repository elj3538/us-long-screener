"""WikipediaからS&P 500構成銘柄とGICS業種分類を取得するモジュール。"""

from __future__ import annotations

import json
import logging
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import requests

logger = logging.getLogger(__name__)

WIKIPEDIA_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

# 元サイト準拠のGICS 11セクター日本語マッピング（表示順も定義）
SECTOR_EN_TO_JA: dict[str, str] = {
    "Information Technology": "情報技術",
    "Health Care": "ヘルスケア",
    "Consumer Discretionary": "一般消費財",
    "Consumer Staples": "生活必需品",
    "Communication Services": "コミュニケーション",
    "Industrials": "資本財",
    "Energy": "エネルギー",
    "Utilities": "公益事業",
    "Materials": "素材",
    "Financials": "金融",
    "Real Estate": "不動産",
}

SECTOR_ORDER: list[str] = list(SECTOR_EN_TO_JA.values())

# オフラインやテスト用フォールバック（各セクター代表銘柄）
FALLBACK_CONSTITUENTS: list[dict[str, str]] = [
    {"symbol": "AAPL", "yf_symbol": "AAPL", "name": "Apple Inc.", "sector_en": "Information Technology", "sector_ja": "情報技術", "sub_industry": "Technology Hardware, Storage & Peripherals"},
    {"symbol": "MSFT", "yf_symbol": "MSFT", "name": "Microsoft", "sector_en": "Information Technology", "sector_ja": "情報技術", "sub_industry": "Systems Software"},
    {"symbol": "NVDA", "yf_symbol": "NVDA", "name": "Nvidia", "sector_en": "Information Technology", "sector_ja": "情報技術", "sub_industry": "Semiconductors"},
    {"symbol": "GOOGL", "yf_symbol": "GOOGL", "name": "Alphabet Inc. (Class A)", "sector_en": "Communication Services", "sector_ja": "コミュニケーション", "sub_industry": "Interactive Media & Services"},
    {"symbol": "META", "yf_symbol": "META", "name": "Meta Platforms", "sector_en": "Communication Services", "sector_ja": "コミュニケーション", "sub_industry": "Interactive Media & Services"},
    {"symbol": "AMZN", "yf_symbol": "AMZN", "name": "Amazon", "sector_en": "Consumer Discretionary", "sector_ja": "一般消費財", "sub_industry": "Broadline Retail"},
    {"symbol": "COST", "yf_symbol": "COST", "name": "Costco", "sector_en": "Consumer Staples", "sector_ja": "生活必需品", "sub_industry": "Consumer Staples Merchandise Retail"},
    {"symbol": "KO", "yf_symbol": "KO", "name": "Coca-Cola Company (The)", "sector_en": "Consumer Staples", "sector_ja": "生活必需品", "sub_industry": "Soft Drinks & Non-alcoholic Beverages"},
    {"symbol": "LLY", "yf_symbol": "LLY", "name": "Eli Lilly and Company", "sector_en": "Health Care", "sector_ja": "ヘルスケア", "sub_industry": "Pharmaceuticals"},
    {"symbol": "UNH", "yf_symbol": "UNH", "name": "UnitedHealth Group", "sector_en": "Health Care", "sector_ja": "ヘルスケア", "sub_industry": "Managed Health Care"},
    {"symbol": "JPM", "yf_symbol": "JPM", "name": "JPMorgan Chase", "sector_en": "Financials", "sector_ja": "金融", "sub_industry": "Diversified Banks"},
    {"symbol": "V", "yf_symbol": "V", "name": "Visa Inc.", "sector_en": "Financials", "sector_ja": "金融", "sub_industry": "Transaction & Payment Processing Services"},
    {"symbol": "BRK.B", "yf_symbol": "BRK-B", "name": "Berkshire Hathaway", "sector_en": "Financials", "sector_ja": "金融", "sub_industry": "Multi-Sector Holdings"},
    {"symbol": "CAT", "yf_symbol": "CAT", "name": "Caterpillar Inc.", "sector_en": "Industrials", "sector_ja": "資本財", "sub_industry": "Construction Machinery & Heavy Transportation Equipment"},
    {"symbol": "XOM", "yf_symbol": "XOM", "name": "ExxonMobil", "sector_en": "Energy", "sector_ja": "エネルギー", "sub_industry": "Integrated Oil & Gas"},
    {"symbol": "NEE", "yf_symbol": "NEE", "name": "NextEra Energy", "sector_en": "Utilities", "sector_ja": "公益事業", "sub_industry": "Electric Utilities"},
    {"symbol": "LIN", "yf_symbol": "LIN", "name": "Linde plc", "sector_en": "Materials", "sector_ja": "素材", "sub_industry": "Industrial Gases"},
    {"symbol": "DLR", "yf_symbol": "DLR", "name": "Digital Realty", "sector_en": "Real Estate", "sector_ja": "不動産", "sub_industry": "Data Center REITs"},
]


def to_yf_symbol(symbol: str) -> str:
    """Wikipedia表記（BRK.B等）をyfinance表記（BRK-B等）に変換する。"""
    return symbol.strip().replace(".", "-")


def fetch_sp500_constituents(
    cache_dir: Path | None = None,
    use_cache: bool = True,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """S&P 500構成銘柄リストを取得する。"""
    cache_file = cache_dir / "sp500_constituents.json" if cache_dir else None

    if use_cache and cache_file and cache_file.exists():
        logger.info("キャッシュからS&P500構成銘柄を読み込みます: %s", cache_file)
        items = json.loads(cache_file.read_text(encoding="utf-8"))
        return items[:limit] if limit else items

    items: list[dict[str, Any]] = []
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(WIKIPEDIA_SP500_URL, headers=headers, timeout=20)
        resp.raise_for_status()
        tables = pd.read_html(StringIO(resp.text))
        df = tables[0]

        for _, row in df.iterrows():
            symbol = str(row.get("Symbol", "")).strip()
            if not symbol:
                continue
            sector_en = str(row.get("GICS Sector", "")).strip()
            items.append(
                {
                    "symbol": symbol,
                    "yf_symbol": to_yf_symbol(symbol),
                    "name": str(row.get("Security", symbol)).strip(),
                    "sector_en": sector_en,
                    "sector_ja": SECTOR_EN_TO_JA.get(sector_en, sector_en),
                    "sub_industry": str(row.get("GICS Sub-Industry", "")).strip(),
                    "headquarters": str(row.get("Headquarters Location", "")).strip(),
                    "date_added": str(row.get("Date added", "")).strip(),
                }
            )
        logger.info("Wikipediaから %d 銘柄を取得しました。", len(items))

        if cache_file and items:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(
                json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    except Exception as exc:
        logger.warning("Wikipediaからの取得に失敗したためフォールバックを使用します: %s", exc)
        items = list(FALLBACK_CONSTITUENTS)

    return items[:limit] if limit else items
