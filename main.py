"""10年保有米株スクリーナー パイプライン実行スクリプト。"""

from __future__ import annotations

import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from src.fetch_data import fetch_stock_data
from src.fetch_sp500 import fetch_sp500_constituents
from src.generate_pages import generate_aux_pages
from src.generate_reports import generate_all_reports
from src.generate_site import generate_outputs
from src.scoring import score_all_stocks
from src.translate import translate_summaries

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="10年保有米株スクリーナー 静的サイト生成")
    parser.add_argument("--limit", type=int, default=None, help="テスト用に取得銘柄数を制限する（例: --limit 50）")
    parser.add_argument("--no-cache", action="store_true", help="キャッシュを使わず最新データを再取得する")
    parser.add_argument("--workers", type=int, default=3, help="データ取得の並列数（デフォルト: 3）")
    parser.add_argument("--sleep", type=float, default=0.2, help="銘柄取得ごとの待機秒数")
    parser.add_argument("--skip-translate", action="store_true", help="未翻訳の会社概要のネット翻訳をスキップする")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    cache_dir = root / "cache"
    data_dir = root / "data"
    dist_dir = root / "dist"

    use_cache = not args.no_cache
    constituents = fetch_sp500_constituents(cache_dir=cache_dir, use_cache=use_cache, limit=args.limit)
    total = len(constituents)
    logger.info("対象銘柄数: %d（並列数: %d）", total, args.workers)

    raw_stocks: list[dict] = []
    if args.workers <= 1:
        for idx, item in enumerate(constituents, start=1):
            logger.info("[%d/%d] %s (%s) を処理中...", idx, total, item["symbol"], item["sector_ja"])
            data = fetch_stock_data(item, cache_dir=cache_dir, use_cache=use_cache, sleep_sec=args.sleep)
            if data:
                raw_stocks.append(data)
    else:
        done = 0
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(fetch_stock_data, item, cache_dir, use_cache, 20.0, args.sleep): item
                for item in constituents
            }
            for fut in as_completed(futures):
                done += 1
                item = futures[fut]
                try:
                    data = fut.result()
                    if data:
                        raw_stocks.append(data)
                except Exception as exc:
                    logger.warning("%s の処理中に例外: %s", item["symbol"], exc)
                if done % 25 == 0 or done == total:
                    logger.info("進捗: %d / %d 銘柄処理完了（成功: %d）", done, total, len(raw_stocks))

    logger.info("データ取得完了: %d 銘柄。採点を開始します...", len(raw_stocks))
    scored = score_all_stocks(raw_stocks)

    logger.info("会社概要の日本語訳キャッシュを確認・補完しています...")
    translate_summaries(scored["items"], data_dir=data_dir, enable_network=not args.skip_translate)

    generate_outputs(scored, dist_dir=dist_dir)
    rep_cnt = generate_all_reports(scored, dist_dir=dist_dir)
    generate_aux_pages(dist_dir=dist_dir)
    logger.info("生成完了！出力先: %s（個別レポート %d 件＋補助ページ4件）", dist_dir, rep_cnt)


if __name__ == "__main__":
    main()
