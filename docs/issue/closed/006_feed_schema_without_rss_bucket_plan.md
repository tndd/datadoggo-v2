# FeedテーブルからRssBucket依存を排除する計画 (v2)

## 1. 背景・目的
- `docs/design.md` で定義されている `RssBucket` テーブルは、RSS XML をバケットに退避したメタデータの保持が目的だったが、実際には RSS 取得結果をそのまま `feed` テーブルへ保存すれば要件を満たせる。
- `Feed` テーブルの `bucket_id` は `RssBucket` の主キーに依存しており、冗長な結合を生んでいる。`bucket_id` を廃止し、代わりに作成日時・更新日時を保持して記事取得時刻をトラッキングする。
- 将来的な CQRS 運用を見据え、RSS 取得フローをシンプル化し、余計なストレージ/テーブルを削除することで保守性を高める。

## 2. 対象スコープ
- `feed_item` テーブル定義 (`src/domain/news/feed/model.py`) と関連サービス/コマンド/検索処理。
- `src/domain/news/rss_link` 配下の RssBucket 関連コードおよびテストの削除・再編。
- `docs/design.md` などドキュメントの更新、および変更影響があるログ仕様の見直し。
- SQLite ファイルの初期化手順（既存データがない前提での再生成手順）。

## 3. 実装方針

### 3.1 スキーマ/モデル
- `FeedRecord` から `bucket_id` カラムを削除し、`created_at` `updated_at` (いずれも timezone-aware `datetime`) を追加する。
  - `FeedItem` ドメインモデルにも同名フィールドを追加し、`create_feed` が `ensure_saved_at` を利用して UTC で初期化する。
  - `feed_to_record` / `record_to_feed` は新フィールドを相互変換し、`updated_at` を latest 保存時刻で上書きする仕様にする。
- SQLModel のメタデータから `RssBucketRecord` を取り除くため、`src/domain/news/rss_link/model.py` を `RssItem` のみが残る構成へ改修する。
- 既存データは開発段階で存在しない前提のため、スキーマ変更後は `data/datadoggo.db` を削除して `initialize_database()` を再実行する運用を明記する（ALTER TABLE 系操作は行わない）。

### 3.2 サービス/コマンド層
- `create_feed` の引数から `bucket_id` を除外し、呼び出し側が URL・タイトル・HTTP ステータス・公開日時のみで FeedItem を生成できるようにする。
- `store_feed` は以下を担う:
  - Upsert 前に `initialize_database()` を呼んでテーブルを生成（開発環境では DB ファイル削除後に再生成される想定）。
  - 既存レコードに対する更新時は `created_at` を保持しつつ `updated_at` を現在時刻に差し替える。
- `convert_rss_items_to_feed_items` は `bucket_id` ではなく、呼び出し元が指定する `source_label` (例: `f"{group}:{name}"` や RSS URL) をログへ埋め込む形に改める。
  - ログ出力 (`logger.warning`) の `bucket_id` キーを `source_label` または `rss_source` へリネームし、付随テストを更新する。

### 3.3 RSSリンク周辺の再編
- `src/domain/news/rss_link/command.py` / `search.py` で提供しているバケット保存系 API を廃止する。
  - バケット I/O (`save_rss_element_to_bucket` など) に依存しているテストも削除。
- `src/domain/news/rss_link/service.py` は `load_rss_links` と `RssItem` 関連の最小限ユーティリティだけを残し、`create_rss_bucket_item` 等は削除。
- バケット保管そのものが不要になるため、`infra.storage.bucket` 自体は Article 機能で利用されているため残すものの、RSS 向けのユースケース説明をドキュメントから削除する。

### 3.4 ドキュメント/ナレッジ
- `docs/design.md`
  - `Feed` テーブル定義を最新化 (`bucket_id` 削除、`created_at`/`updated_at` 追加)。
  - `rss_link` セクションから `RssBucket` の章を削除し、必要であれば「RSS は直に Feed へ保存する」旨の注記を追記。
- `docs/concept.md` で RssBucket への言及があれば除去。
- 実装完了後、`AGENTS.md` に今回のスキーマ変更と SQLite ファイル再生成手順を追記する。

### 3.5 テスト/検証
- `Feed` 関連テストをリライトし、`bucket_id` に関するアサーションを削除、`created_at`/`updated_at` の検証を追加する。
  - 例: `store_feed` 連続呼び出しで `updated_at` が更新されること、`created_at` が変わらないこと。
- `convert_rss_items_to_feed_items` テストはログの `source_label` (仮称) を確認するよう更新。
- RssBucket 系テストを削除し、新たに必要であれば RSS 取得から Feed 保存へのエンドツーエンドテストを追加する。
- `uv run ruff check` / `uv run pyright` / `uv run pytest` を必須検証として CI 相当のローカル確認を行う。

## 4. データ初期化手順
- 開発段階で既存データが存在しない前提のため、スキーマ変更後は `data/datadoggo.db`（または環境変数で指すファイル）を削除してから `initialize_database()` を実行し、最新定義でテーブルを生成する。
- 既存ファイルを削除できないケースに備えて、ドキュメントに「DB 再生成が必要な場合はファイル削除→再実行」と明記する。

## 5. テスト計画
- 単体テスト: 変更した各モジュールの `Tests` クラスを更新し、新規カバレッジ (timestamp 検証) を追加。
- 結合テスト (必要に応じて新設): RSS 取得 (モック) → `convert_rss_items_to_feed_items` → `store_feed` までを一連で走らせ、DB に期待通りのスキーマで保存されることを確認。
- 静的解析/リンタ: `uv run ruff check`, `uv run pyright` をエラーなく通過すること。
- ユニットテスト実行: `uv run pytest` で全件パス。警告が出た際は必ず原因を調査し、原則解消する。

## 6. リスクと対応策
- SQLite ファイル削除を前提とするため、誤って不要な環境の DB を削除しないよう注意点を README/AGENTS に明記する。
- 過去ログや既存運用が `bucket_id` を前提としている場合、ダッシュボード等のクエリも修正が必要。
  - 対応: 実装前にログ項目の名称変更 (`bucket_id` → `rss_source` など) を関係者へ周知する。
- `FeedItem` の ID は URL ハッシュのまま変わらないため、同一 URL での再取得が想定通り `updated_at` のみ更新となるか、既存クライアントの期待を再確認する必要がある。
  - 対応: 実装後の検証で同一 URL の更新ケースを重点確認する。
