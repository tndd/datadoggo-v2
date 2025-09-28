# loguruを用いたFeed変換エラーログ導入計画

## 背景
- RSS item変換処理`convert_rss_items_to_feed_items`は不正URLなどの例外を握りつぶしてスキップするが、現在はエラー内容が記録されない。
- 運用時に「どのbucket / URLで、どんな理由でスキップされたのか」を確認できず、原因調査が困難。
- SQLiteは永続化層として既に採用済みだが、即時に可観測性を向上させるには構造化ファイルログが低コスト。

## 目的
- スキップしたRSS itemの詳細（URL、bucket、例外種別、メッセージ）をローテーション付きファイルへ記録し、後続調査や再処理判断に役立てる。
- 実装コストを抑えつつ構造化ログを出力できる`loguru`をベースに、将来SQLiteや外部集約に拡張しやすい基盤を整える。

## ログ戦略
- **ライブラリ**: `loguru` を採用し、構造化辞書を JSON 形式で吐き出す。既存の`logging`未使用のため移行コストが低い。
- **記録先**: `logs/rss_errors.log`（新規ディレクトリ `logs/` をリポジトリ直下に作成）。
  - ローテーション: ファイルサイズ10MBで世代交代。
  - 保持: 最新10ファイル。
  - 圧縮: プロジェクト既定に合わせ `zstd`（`.zst`）で自動圧縮。
- **記録粒度**: Feed変換スキップ時は`logger.warning`、予期しない変換失敗は`logger.error`。
- **出力形式**: `serialize=True`でJSONログ。`bucket_id` / `feed_url` / `error_type` / `exception_message` / `published_at` / `source`（例:`convert_rss_items_to_feed_items`）をkeyとして含める。
- **拡張性**: 将来的にSQLiteへも永続化したい場合、同じ辞書データをキューへ送るhookを挟むだけで再利用できるよう、ログ構築を関数化する。

## 実装方針
1. **依存追加**
   - `uv add loguru` で依存関係を追加し、`just sync` 等で環境反映。
2. **初期化モジュールの新設**
   - `src/infra/logging.py` を新設し、`configure_logging()` を公開。
   - `logger = loguru.logger` を初期化し、上記設定（ファイルパス、ローテーション、保持、シリアライズ、バックトレース有効化、UTCタイムスタンプ）を適用。
   - `logging.getLogger`互換で必要に応じて標準ログへブリッジするHandlerも用意（今後標準ライブラリを併用する場面に備え、`InterceptHandler`を実装）。
3. **変換処理での利用**
   - `feed/service.py` 冒頭で `from infra.logging import logger` をインポート。
   - 例外捕捉ブロックで `logger.warning("invalid feed item", bucket_id=bucket_id, feed_url=link, error_type=type(exc).__name__, exception_message=str(exc))` を呼び出し。
   - 想定外例外（チャンネル欠損など）向けに、上位層からも同loggerを利用できるよう公開APIとする。
4. **テスト追加**
   - `tests`モジュールにログ出力を検証するテストを追加。`tmp_path`へログを出力するよう一時的にlogger sinkを差し替え、メッセージがJSONで記録されること、`error_type`が期待値になることを確認。
   - 既存の`convert_rss_items_to_feed_items`テストに副作用検証を追加するのではなく、新規で`Tests`配下に`Test_logging`モジュールを設ける。
5. **アプリ初期化点の整備**
   - CLIやワーカー起動想定箇所（`main.py`や今後のワークフローエントリ）で`configure_logging()`を最初に呼び出す。
   - pytestでは`conftest.py`を追加し、`configure_logging()`を一度だけ呼ぶfixtureを用意してテスト実行時のディスク書き込み先を`tmp_path`へ切り替える。

## 検証計画
- `uv run ruff check` / `uv run pyright` / `uv run pytest`
- ログファイルの生成をE2Eで確認するため、手動で`convert_rss_items_to_feed_items`を呼ぶスクリプトかテストを用意し、`logs/`配下にJSONログが生成されることを確認。

## 運用・保守
- ローテーション設定によりログ肥大化を防止。
- 1日1回のcron等で`logs/`配下を監視し、必要なら外部集約（CloudWatchなど）へ転送。
- 将来的にSQLiteへも保存する要件が出た場合は、`infra/logging`にHookを追加し、同データを`error_feed_items`テーブルへINSERTする機構を再利用。
