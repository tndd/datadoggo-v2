# Feedテーブル実装計画

## 背景
- `design.md`で定義された`Feed`テーブルを最初に具現化し、RSSフィード取得結果の保存・更新基盤を整える。
- ドメイン層では関数中心のAPIで抽象化を行い、インフラ層(`rds`)でSQLModel/SQLAlchemyを用いた実データベース処理を担当する構成とする。

## 目標
- SQLModelを中核に据えたORMスタックを導入し、`Feed`テーブル操作をシンプルに扱えるようにする。
- ドメイン層(`src/domain/feed.py`)でドメインモデル・入力DTO・リポジトリ操作を関数形式で提供する。
- インフラ層(`src/infra/rds.py`, `src/infra/rds/feed.py`)でRDS向けのセッション管理・永続化処理をまとめる。
- 後続のBucket/Article実装にも拡張しやすい土台を築く。

## モジュール構造ツリー
```
src/domain/feed.py
  ├─ モデル: Feed
  ├─ 型: FeedQuery, FeedSearchResult
  ├─ ユーティリティ関数: create_feed_id, build_feed
  ├─ ユースケース関数: store_feed, find_feed_by_id, search_feeds
src/infra/rds.py
  ├─ 関数: create_rds_engine, get_session_factory, get_migration_config
  └─ 関数: run_sync_migrations
src/infra/rds/feed.py
  ├─ テーブル: FeedRecord(SQLModel)
  ├─ 変換関数: to_domain_feed, to_record
  ├─ DB操作関数: save_feed, load_feed_by_id, load_feeds
  └─ 補助関数: apply_feed_filters
```

## モジュール構成案
- `src/domain/feed.py`
  - Pydantic(BaseModel)によるドメインエンティティ`Feed`(最小限のクラス利用)。
  - リポジトリ用Protocolではなく`Protocol`依存を避け、`TypedDict`や型エイリアスで契約を表現しつつ、関数シグネチャで抽象化を行う。
  - `create_feed_id(url: str) -> str`等の補助関数、`store_feed`や`find_feed`などのユースケース関数を定義。
- `src/infra/rds.py`
  - SQLModel/SQLAlchemyエンジンの初期化とセッション管理をまとめる。
  - 既定RDS(PostgreSQL)向けの接続設定、テスト時のSQLite切り替えロジックを関数で公開する。
- `src/infra/rds/feed.py`
  - SQLModelのテーブル定義`FeedRecord`(table=True)を配置。
  - `FeedRecord`⇄ドメイン`Feed`の変換関数、およびセッションを受け取って永続化・検索を行う関数群(`save_feed`, `find_feed`, `search_feeds`)を実装。
  - クラスベースのリポジトリ実装ではなく、関数と依存注入用のCallableで構成する。

## 依存ライブラリ・ツール
- `sqlmodel`
- `sqlalchemy`
- `alembic`
- `psycopg[binary]` (本番PostgreSQL接続用)
- ローカルテストではSQLiteメモリDBを継続利用

## 実装タスク詳細
1. **依存パッケージ追加**
   - `uv add sqlmodel alembic psycopg[binary]`を実行し、`pyproject.toml`/`uv.lock`を更新。
   - 既存依存との互換性を確認し、必要ならバージョン固定を調整。
2. **RDS基盤整備 (`src/infra/rds.py`)**
   - `create_rds_engine`, `get_session_factory`, `run_migrations`等の関数を用意。
   - 環境変数読み取りを暫定的に実装し、後続で設定モジュールを差し替えられるようにする。
3. **ドメイン層整備 (`src/domain/feed.py`)**
   - `Feed`モデル(最小限のクラス利用)と、リクエストDTO/レスポンスDTOとしての`FeedQuery`などを定義。
   - `store_feed`, `find_feed_by_id`, `search_feeds`などの関数でリポジトリ呼び出しを抽象化。
   - `create_feed_id`などのユーティリティを同ファイルに集約。
4. **RDS永続化処理 (`src/infra/rds/feed.py`)**
   - SQLModelテーブル`FeedRecord`を定義し、`design.md`のカラム仕様を反映。
   - セッションを受け取る関数(`save_feed`, `load_feed_by_id`, `load_feeds`)を実装し、ドメインモデルとの相互変換を行う。
5. **マイグレーション初期設定**
   - Alembicプロジェクトを初期化、`src/infra/alembic/`(想定)に設定を配置。
   - `target_metadata`としてSQLModelのmetadataを参照し、`FeedRecord`だけを含む初期マイグレーションを生成。
6. **テスト整備**
   - `tests/feed/test_feed_repository.py`などに、`sqlite:///:memory:`を使ったCRUD検証テストを実装。
   - テスト冒頭にコメントで目的・検証観点を明記。
   - 主要シナリオ(新規保存・上書き・検索結果整形)を中心に、各関数最大5ケース以内でまとめる。
7. **ドキュメント更新**
   - `docs/design.md`に実装確定内容を追記。
   - `README`または`docs/`配下にマイグレーション手順や環境変数一覧を追加。

## テスト戦略
- ユニット: インメモリSQLite + SQLModelでCRUD動作を確認。
- 統合: Alembicマイグレーション適用後の起動確認(後続で`docker-compose`のPostgreSQLにも適用予定)。
- 検証観点
  - `id`ハッシュ生成と一意制約の保持。
  - `pub_date`のUTC保持、`status_code`の必須制約。
  - SQLModel⇄ドメイン変換の整合性。

## 未決事項 / 次ステップ
- ハッシュ生成をどの層で責務分担するか(現状はドメイン関数案)。
- `Feed`の更新ポリシー(差分更新 vs 全体更新)をどのタイミングで確定するか。
- 将来的なNoSQL実装向けインターフェイスをどう整備するか。
- 非同期対応が必要になった場合の方針(現状は同期セッション前提)。
