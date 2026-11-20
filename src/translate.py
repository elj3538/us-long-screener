"""会社概要（英文）を日本語に翻訳し、ローカルキャッシュに保存するモジュール。"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"


def _call_google_translate(text: str) -> str | None:
    """APIキー不要の翻訳エンドポイントで英文を日本語訳する（長文は分割）。"""
    if not text or not text.strip():
        return None
    # 1リクエストあたりの文字数上限を避けるため約1400文字ごとに文単位で分割
    chunks: list[str] = []
    cur = ""
    for sentence in text.split(". "):
        part = sentence if sentence.endswith(".") else sentence + "."
        if len(cur) + len(part) > 1400 and cur:
            chunks.append(cur.strip())
            cur = part
        else:
            cur = (cur + " " + part).strip()
    if cur:
        chunks.append(cur.strip())

    translated_parts: list[str] = []
    for chunk in chunks:
        try:
            resp = requests.get(
                _TRANSLATE_URL,
                params={"client": "gtx", "sl": "en", "tl": "ja", "dt": "t", "q": chunk},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            seg_text = "".join(seg[0] for seg in data[0] if seg and seg[0])
            translated_parts.append(seg_text)
        except Exception as exc:
            logger.warning("翻訳API呼び出しに失敗: %s", exc)
            return None
        time.sleep(0.15)
    return "".join(translated_parts).strip()


def translate_summaries(items: list[dict], data_dir: Path, enable_network: bool = True) -> None:
    """各銘柄の detail.summary（英文）を日本語訳し detail.summary_ja に格納する。"""
    data_dir.mkdir(parents=True, exist_ok=True)
    cache_file = data_dir / "summaries_ja.json"

    cache: dict[str, str] = {}
    # 旧 cache/summaries_ja.json からの移行もサポート
    legacy_file = data_dir.parent / "cache" / "summaries_ja.json"
    for candidate in (legacy_file, cache_file):
        if candidate.exists():
            try:
                cache.update(json.loads(candidate.read_text(encoding="utf-8")))
            except Exception:
                pass

    updated = False
    translated_cnt = 0
    for item in items:
        sym = item["symbol"]
        det = item.setdefault("detail", {})
        en_text = (det.get("summary") or "").strip()
        if not en_text:
            det["summary_ja"] = ""
            continue
        if sym in cache and cache[sym]:
            det["summary_ja"] = cache[sym]
            continue
        if enable_network:
            ja_text = _call_google_translate(en_text)
            if ja_text:
                cache[sym] = ja_text
                det["summary_ja"] = ja_text
                updated = True
                translated_cnt += 1
                if translated_cnt % 25 == 0:
                    cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
                    logger.info("会社概要の日本語訳進捗: 新規 %d 件キャッシュ保存済み", translated_cnt)
                continue
        det["summary_ja"] = ""

    if updated:
        cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
