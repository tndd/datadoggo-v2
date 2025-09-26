# Feedテーブル実装計画

## 背景
- `design.md`で定義された`Feed`テーブルを最初に具現化し、RSSフィード取得結果の保存・更新基盤を整える。
- ドメイン層では公開関数を通じて操作を提供し、内部でRDS(SQLite)への保存処理を隠蔽する。
- インフラ層(`rds.py`)は接続設定とセッション生成に徹し、接続先は環境変数で切り替える。

## 目標
- SQLModelを中核に据え、SQLite向けの`Feed`テーブル操作をシンプルに実装する。
- ドメイン層では書き込み(`command.py`)と読み出し(`search.py`)を明確に分離し、永続化レコードは`model.py`、変換処理は`convert.py`、初期化ヘルパーやエンティティ生成は`service.py`に配置する。
- ハッシュ生成などの汎用計算ロジックは`infra/compute.py`に集約し、ドメインはそれを利用してID生成を行う。

## モジュール構成案
- `src/domain/news/feed/command.py`
  - `store_feed`で永続化する。
- `src/domain/news/feed/search.py`
  - `FeedQuery`入力モデルと、`find_feed_by_id`/`search_feeds`による読み出し処理を提供する。
- `src/domain/news/feed/model.py`
  - `FeedItem`と`FeedRecord`を定義する。
- `src/domain/news/feed/convert.py`
  - URL検証とレコード⇔ドメイン変換ロジックを提供する。
- `src/domain/news/feed/service.py`
  - URL検証ヘルパー(`ensure_http_url`)とドメイン生成(`create_feed`)を提供する。
- `src/infra/storage/rds.py`
  - 定数: `DEFAULT_DATABASE_URL`(`sqlite:///data/datadoggo.db`想定)。
  - 関数: `get_database_url`, `create_sqlite_engine`, `get_session_factory`, `initialize_database`。
  - SQLiteファイル利用時は親ディレクトリを自動生成する。
  - `SQLModel.metadata.create_all`を使って初期化を行う。
- `src/infra/compute.py`
  - 既存の計算系ユーティリティに、URLハッシュ生成関数(例: `hash_text_sha256`)を追加/利用することで`Feed`のID生成に流用。

## 依存ライブラリ・ツール
- `sqlmodel`
- (マイグレーションは後続のjustfile統合時に検討するため現段階では不要)

## 実装タスク詳細
1. **依存パッケージ追加**
   - `uv add sqlmodel`を実行し、`pyproject.toml`/`uv.lock`を更新。
   - 互換性を確認。
2. **インフラ基盤 (`src/infra/storage/rds.py`)**
   - `FEED_DATABASE_URL`環境変数を読み、未設定時は`DEFAULT_DATABASE_URL`を返す`get_database_url`を実装。
   - SQLModel用エンジン/セッションファクトリを返す`create_sqlite_engine`/`get_session_factory`を用意。
   - `initialize_database`で`SQLModel.metadata.create_all`を実行し、テーブルを生成。
3. **ハッシュユーティリティ整備 (`src/infra/compute.py`)**
   - URL文字列をハッシュ化する関数(例:`hash_text_sha256`)を定義し、既存利用箇所との整合性を確認。
4. **ドメイン層 (`src/domain/news/feed/`)**
   - `model.py`で`FeedItem`/`FeedRecord`を定義。
   - `convert.py`でURL検証と変換ヘルパーを提供する。
   - `command.py`で`create_feed`/`store_feed`を提供し、`convert.py`・`service.py`を利用する。
   - `search.py`で`FeedQuery`・`find_feed_by_id`・`search_feeds`を提供する。
5. **初期データベース生成**
   - エントリポイント(例:`main.py`)に`initialize_database`呼び出しを追加し、初回起動でテーブルが作成されるようにする。
6. **テスト整備**
   - `tests/feed/`配下に、`FEED_DATABASE_URL=sqlite:///:memory:`を設定した状態でCRUD動作を検証するテストを追加。
   - テスト冒頭に目的・検証観点をコメントで明記。
   - 主要シナリオ(新規保存、同一URLの更新、検索クエリ)を各最大5ケース以内で実装。
7. **ドキュメント更新**
   - `docs/design.md`に環境変数での接続切り替え方針を追記。
   - `README`または`docs/`配下に、SQLiteファイルの配置場所と初期化手順を記載。

## モジュール構造ツリー
```
src/domain/news/feed
  ├─ command.py (store_feed)
  ├─ convert.py (ensure_http_url, feed_to_record, record_to_feed)
  ├─ model.py (FeedItem, FeedRecord)
  ├─ search.py (FeedQuery, find_feed_by_id, search_feeds)
  └─ service.py (ensure_http_url, create_feed)
src/infra/storage/rds.py
  ├─ 定数: DEFAULT_DATABASE_URL
  ├─ 関数: get_database_url, create_sqlite_engine, get_session_factory
  └─ 関数: initialize_database
src/infra/compute.py
  └─ 関数: hash_text_sha256 (Feed ID生成に利用)
```

## テスト戦略
- ユニット/インメモリ: `sqlite:///:memory:` を環境変数で指定してCRUD動作を確認。
- 統合/ローカル: `data/datadoggo.db`(ローカルファイル)で実行し、テーブル生成と永続化の流れを検証。
- 検証観点
  - `hash_text_sha256`によるID生成と一意制約の保持。
  - `pub_date`のUTC保持、`status_code`必須制約。
  - SQLModel⇄ドメイン変換の整合性。

## 未決事項 / 次ステップ
- 直近はマイグレーション/非同期を扱わないため未決事項なし。要件変化時に再検討する。
