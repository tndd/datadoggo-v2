# Feedテーブル実装計画

## 背景
- `design.md`で定義された`Feed`テーブルを最初に具現化し、RSSフィード取得結果の保存・更新基盤を整える。
- ドメイン層では公開関数を通じて操作を提供し、内部でRDS(SQLite)への保存処理を隠蔽する。
- インフラ層(`rds.py`)は汎用的なセッション/エンジン生成関数だけを持ち、接続先は環境変数で切り替える。

## 目標
- SQLModelを中核に据え、SQLite向けの`Feed`テーブル操作をシンプルに実装する。
- ドメイン層(`src/domain/feed.py`)でドメインモデル・入力DTO・ユースケース関数をまとめ、RDS関連処理はモジュール内の非公開関数として保持する。
- インフラ層(`src/infra/rds.py`)で環境変数ベースの接続先切り替えロジックとセッション管理を提供し、テスト時はSQLiteメモリDBへ容易に切り替えられるようにする。

## モジュール構成案
- `src/domain/feed.py`
  - Pydantic(BaseModel)によるドメインエンティティ`Feed`。
  - ハッシュ生成や入力正規化の補助関数(例:`create_feed_id`, `build_feed_from_raw`).
  - 公開ユースケース関数: `store_feed`, `find_feed_by_id`, `search_feeds`。
  - モジュール内部でのみ利用するRDS操作関数: `_save_feed`, `_load_feed_by_id`, `_load_feeds`。
- `src/infra/rds.py`
  - デフォルトの`DATABASE_URL`(例:`sqlite:///data/feed.db`)と、環境変数`FEED_DATABASE_URL`による上書き機構。
  - `get_database_url`, `create_sqlite_engine`, `get_session_factory`, `initialize_database`などの汎用関数。
  - SQLModel metadataを使った`create_all`処理を提供し、SQLiteでのテーブル初期化を担当。

## 依存ライブラリ・ツール
- `sqlmodel`
- (任意) `alembic` はSQLite運用が安定化してから導入検討。現段階では`SQLModel.metadata.create_all`運用とする。

## 実装タスク詳細
1. **依存パッケージ追加**
   - `uv add sqlmodel`を実行し、`pyproject.toml`/`uv.lock`を更新。
   - 既存依存との互換性を確認。
2. **インフラ基盤 (`src/infra/rds.py`)**
   - `FEED_DATABASE_URL`環境変数を読み、未設定時は`sqlite:///data/feed.db`を返す`get_database_url`を実装。
   - SQLModel用エンジン/セッションファクトリを返す`create_sqlite_engine`/`get_session_factory`を用意。
   - `initialize_database`で`SQLModel.metadata.create_all`を実行し、テーブルを生成。
3. **ドメイン層 (`src/domain/feed.py`)**
   - `Feed`モデル、入力DTO(`FeedQuery`等)を定義。
   - 公開関数(`store_feed`, `find_feed_by_id`, `search_feeds`)でビジネスロジックを提供し、内部で`_save_feed`などのRDS操作関数を呼び出す。
   - `_save_feed`等は`infra.rds`のセッションファクトリを利用し、SQLite接続を取得する。
4. **初期データベース生成**
   - 実行エントリポイントまたはCLI(例:`main.py`)に`initialize_database`呼び出しを組み込み、初回起動でテーブルが作成されるようにする。
5. **テスト整備**
   - `tests/feed/test_store_feed.py`などに、`FEED_DATABASE_URL=sqlite:///:memory:`を設定した状態でCRUD動作を検証するテストを追加。
   - テスト冒頭に目的・検証観点をコメントで明記。
   - 主要シナリオ(新規保存、同一URLの更新、検索クエリ)を各最大5ケース以内で実装。
6. **ドキュメント更新**
   - `docs/design.md`に環境変数での接続切り替え方針を追記。
   - `README`または`docs/`配下に、SQLiteファイルの配置場所と初期化コマンド(`python -m datadoggo_v2.init_db`等)を記載。

## モジュール構造ツリー
```
src/domain/feed.py
  ├─ モデル: Feed
  ├─ 型: FeedQuery, FeedSearchResult
  ├─ ユーティリティ関数: create_feed_id, build_feed_from_raw
  ├─ 公開関数: store_feed, find_feed_by_id, search_feeds
  └─ 内部関数: _save_feed, _load_feed_by_id, _load_feeds
src/infra/rds.py
  ├─ 定数: DEFAULT_DATABASE_URL
  ├─ 関数: get_database_url, create_sqlite_engine, get_session_factory
  └─ 関数: initialize_database
```

## テスト戦略
- ユニット/インメモリ: `sqlite:///:memory:` を環境変数で指定してCRUD動作を確認。
- 統合/ローカル: `data/feed.db`(ローカルファイル)で実行し、テーブル生成と永続化の流れを検証。
- 検証観点
  - `id`ハッシュ生成と一意制約の保持。
  - `pub_date`のUTC保持、`status_code`必須制約。
  - SQLModel⇄ドメイン変換の整合性。

## 未決事項 / 次ステップ
- ハッシュ生成をどこまでドメイン関数に寄せるか(現状はドメイン内で実装する想定)。
  - 将来的に切り替えが必要ならユーティリティ化。
- SQLite特有の制約(同時書き込みロック等)が問題になった際の対応方針。
- Alembic等のマイグレーションツール導入タイミング。
- 非同期対応が必要になった場合の方針(現状は同期セッション前提)。
