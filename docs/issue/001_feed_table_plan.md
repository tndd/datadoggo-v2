# Feedテーブル実装計画

## 背景
- `design.md`のテーブル定義に基づき、RSSフィード情報の保存と取得を担う`Feed`テーブルを最初に実装する。
- ドメイン層で抽象化した保存インターフェイスを提供し、インフラ層(`rds`)でSQLModel/SQLAlchemyを用いた具象実装を行う構成とする。

## 目標
- SQLModelを中心としたORMスタックを導入し、`Feed`テーブル操作をモジュール化する。
- ドメイン層(`feed.py`)にてドメインモデル・プロトコル・ユースケース補助関数を定義する。
- `infra/rds`にてSQLModelベースの永続化レイヤーを整備し、RDB接続・マイグレーションの運用方針を明確化する。
- 将来的なBucket/Article実装に拡張可能な構成を確立する。

## ディレクトリ/モジュール構成案
- `src/domain/feed.py`
  - Pydantic(BaseModel)ベースのドメインエンティティ`Feed`。
  - 保存処理の抽象インターフェイス`FeedRepository`(Protocol)。
  - ドメインロジックやユーティリティ(例: `search_feed`のクエリDTO)の定義。
- `src/infra/db.py`
  - SQLModel/SQLAlchemyエンジンとセッション管理を集約するファクトリ関数。
  - 設定値の取得(`settings.py`想定)は暫定的に環境変数ベースで実装し、後続で設定モジュールを拡充予定。
- `src/infra/rds/feed_repository.py`
  - `FeedRepository`の具象実装`RDSFeedRepository`。
  - SQLModelで定義した`FeedRecord`(テーブルクラス)を利用してCRUDを提供。
  - セッションをコンテキストマネージャ経由で受け取り、トランザクション境界を呼び出し側が制御できるようにする。
- `src/infra/rds/models/feed.py`
  - SQLModel継承のテーブル定義`FeedRecord`を配置。将来的なテーブル増加に備えてモジュールを分割。

## 依存ライブラリ・ツール
- `sqlmodel` (ORM)
- `sqlalchemy` (すでに間接依存だがバージョンを明示管理)
- `alembic` (マイグレーション管理用。初期化はFeedテーブル実装と合わせて実施)
- `psycopg[binary]` (本番想定: PostgreSQL)。ローカル検証用にはSQLiteメモリDBを継続利用。

## 実装タスク詳細
1. **依存パッケージ追加**
   - `uv add sqlmodel alembic psycopg[binary]` 等で導入し、`pyproject.toml`と`uv.lock`を更新。
   - 既存依存とのバージョン互換を検証。
2. **SQLModel設定基盤**
   - `infra/db.py`に`create_engine`ラッパー、`sessionmaker`、初期化関数を実装。
   - Alembic設定ファイル(例:`alembic.ini`,`alembic/`)を生成し、SQLModel向けenvスクリプトを調整。
3. **ドメイン層整備 (`src/domain/feed.py`)**
   - `Feed`ドメインモデル(不変値のバリデーション&補助メソッド)。
   - 保存/検索を担う`FeedRepository` Protocol。メソッド構成は`store_feed`, `find_feed`, `search_feeds`など最小限から開始。
   - ドメインサービス的な関数が必要ならスタブを定義。
4. **永続層モデル (`src/infra/rds/models/feed.py`)**
   - `FeedRecord`(SQLModel, table=True)を定義し、`design.md`のカラム仕様に合わせる。
   - タイムスタンプ型には`sqlalchemy.dialects.postgresql.TIMESTAMP(timezone=True)`を使用し、SQLite互換のためのフォールバックも検討。
5. **リポジトリ実装 (`src/infra/rds/feed_repository.py`)**
   - `FeedRepository`を実装し、SQLModelセッションを受け取ってCRUDを提供。
   - 保存時のハッシュ生成(必要なら別ユーティリティ)と一意制約エラー処理を設計。
6. **マイグレーション初期設定**
   - Alembicディレクトリ作成、`FeedRecord`を対象に初期マイグレーションスクリプトを生成。
   - 自動生成設定`target_metadata`へSQLModelのmetadataを連携。
7. **テスト整備**
   - `tests/feed/`配下にユニットテストを配置し、インメモリSQLiteを使って`RDSFeedRepository`の保存/取得シナリオを検証。
   - テストコメントに目的と検証観点を記録する。
   - 既存テストランナーに統合し、`pytest` + `sqlite`でCI実行可能にする。
8. **ドキュメント整備**
   - `docs/design.md`に実装済み状態を追記(テーブルの確定カラム、マイグレーション方針など)。
   - 運用手順(マイグレーション適用、ローカル検証コマンド)を`README`もしくは`docs/`に補足。

## テスト戦略
- ユニット: インメモリSQLite + SQLModelでのCRUD検証。
- 統合: Alembicマイグレーションを適用した一連の起動テスト(後続イテレーションで`docker-compose`のPostgreSQLに対して実行)。
- 検証観点
  - ハッシュIDの一意性と既存レコード更新/Upsertの仕様。
  - `pub_date`のUTC変換とタイムゾーンオフセット保持。
  - `status_code`未設定時のバリデーション。

## 未決事項 / 次ステップで判断
- ドメイン層のハッシュ生成をどこで責務分担するか(ユーティリティ or リポジトリ)。
- `Feed`更新時の振る舞い(既存記事のステータス更新 vs 完全差し替え)。
- `Bucket`テーブルとの依存関係の扱い(外部キー制約導入タイミング)。
- 非同期実装の必要性(現状は同期型Sessionを前提)。
