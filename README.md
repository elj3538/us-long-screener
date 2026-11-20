# 10年保有米株スクリーナー（米国株 S&P 500）

S&P 500 構成銘柄の財務・株価・四半期決算データを毎日自動取得し、「ファンダ点（10年保有の質）」「買い時スコア（割安度）」「1軍〜3軍」を採点して静的Webサイトとして生成するスクリーナーです。

## 主な機能
- **ランキング＆詳細スクリーナー (`dist/index.html`)**：業種別ランキング、軍フィルタ、キーワード検索、4グループ詳細絞り込み、URL同期、ソート、CSV/TSV出力、7種＋カスタム配色・ダークモード、CSV一括バックアップ／復元
- **個別診断レポート (`dist/reports/<TICKER>.html`)**：ファンダ点・買い時のアコーディオン詳細、年次／四半期切替SVGグラフ、割安レンジSVG図、5年株価推移チャート、会社概要の日本語訳、参考・深掘り指標
- **ウォッチリスト (`dist/watchlist.html`)**：タブ管理、並び替え、メモ、テキスト出力／復元
- **ポートフォリオ (`dist/portfolio.html`)**：ロット記録、加重平均単価・含み損益、銘柄別／業種別SVG円グラフ
- **自動トレード連携用JSON (`dist/ranking.json`)**：全銘柄スコアに加え、`option_signals`（`bull_tier1`, `bear_watch_score`）を出力

## ローカル実行方法
```powershell
# 仮想環境作成＆依存パッケージインストール（初回のみ）
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# テスト実行（例：30銘柄）
.venv\Scripts\python.exe main.py --limit 30 --workers 3

# S&P 500 全銘柄の生成
.venv\Scripts\python.exe main.py --workers 3

# ローカルプレビュー
.venv\Scripts\python.exe -m http.server 8765 -d dist
# ブラウザで http://localhost:8765/ を開く
```

## Web公開＆毎日自動更新（GitHub Pages）手順
1. GitHub で新しいリポジトリを作成し、このフォルダの中身を push します（`data/summaries_ja.json` を含めて push すると翻訳が高速化されます）。
2. GitHub リポジトリの **Settings → Pages → Build and deployment → Source** を **`GitHub Actions`** に設定します。
3. **Actions** タブから **`Daily US Long Screener Build & Deploy`** を手動実行（Run workflow）すると数分で公開URLが発行され、以降は米国市場クローズ後（日本時間 火〜土 朝7:30）に毎日自動更新されます。
