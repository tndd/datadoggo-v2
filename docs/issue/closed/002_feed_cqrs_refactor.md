# Feed CQRS分割計画（再構成アップデート）

## 背景
- 旧`feed.py`の責務を分割したのち、永続化レイヤの構成をさらに整理する必要が生じた。
- CQRS原則に沿いつつ、永続化レコード定義や変換ロジックの所在を明確化し、サービス境界を再調整する。
- HTTPステータスコードは任意値(整数)を許容する必要があるため、列挙型による制約(例:`FeedStatus`)は導入しない。

## 目的
- 書き込み系のユースケースは`command.py`、読み出し系は`search.py`で提供する。
- 永続化レコード定義は`model.py`へ移し、変換ロジックは`convert.py`、初期化処理やエンティティ生成は`service.py`と役割ごとに分割する。
- 公開API (`create_feed`/`store_feed`/`find_feed_by_id`/`search_feeds`/`FeedQuery`) のシグネチャと振る舞いを維持する。

## スコープ
- 対象: `feed/`配下の`command.py`/`search.py`/`model.py`/`convert.py`/`service.py`。
- 非対象: `infra.storage.rds`の接続ロジック、`infra.compute.hash_text_sha256`の実装、HTTPステータスコードの検証強化。

## 実装ステップ
1. **公開APIと依存関係の棚卸し**
   - `create_feed`/`store_feed`/`find_feed_by_id`/`search_feeds`/`FeedQuery`が依存する各モジュールを洗い出し、担当を整理する。
   - 単一箇所でしか使われないラップ関数は廃止候補として確認する。
2. **モデル再編**
   - SQLModelのテーブル定義を`FeedRecord`として`model.py`に移動し、公開クラスとして扱う。
   - 既存コードから参照される箇所を更新する。
3. **変換ユーティリティ分離**
   - URL検証とレコード変換を`convert.py`に移し、`command`/`search`が直接利用できるようにする。
4. **サービス層整理**
   - `service.py`にURL検証ヘルパーとドメイン生成処理を集約し、共通バリデーションとエンティティ生成を担わせる。
5. **command.py / search.py の依存更新**
   - 新しい`model`/`convert`/`service`構成に合わせて import を整理し、冗長なラップを削除する。
6. **テスト・ドキュメント更新**
   - モジュール内テストを最新構造に合わせて更新し、docs形式コメントを維持。
   - `docs/issue/001_feed_table_plan.md`を含む関連資料を最新構成に追随させる。
7. **検証**
   - `ruff check`、`pyright`、`pytest`を再実行し、警告を含めて解消する。

## リスク・懸念
- `FeedRecord`を公開クラス化することで import 循環が発生しないよう依存方向を整理する。
- `FeedQuery`のバリデーションが移動後も同一になるよう、型・制約を維持する。
- 変換関数移動に伴って既存呼び出しが破綻しないよう参照を点検する。

## 完了条件
- `FeedRecord`が`model.py`で公開クラスとして定義されている。
- `convert.py`に変換系関数が集約され、`service.py`が初期化ヘルパーを提供している。
- `command.py`/`search.py`が新構造に合わせて動作し、公開APIのシグネチャが維持されている。
- 冗長なラップ関数が排除されている。
- `FeedStatus`等の列挙型が導入されていない。
- `ruff check`/`pyright`/`pytest`が成功している。

## 想定ファイル・シンボル構成

```
src/domain/news
├── feed
│   ├── command.py
│   │   └── store_feed(feed: HttpRequestTask) -> HttpRequestTask
│   ├── convert.py
│   │   ├── ensure_http_url(value: str | HttpUrl) -> HttpUrl
│   │   ├── feed_to_record(feed: HttpRequestTask) -> FeedRecord
│   │   └── record_to_feed(record: FeedRecord) -> HttpRequestTask
│   ├── model.py
│   │   ├── HttpRequestTask(BaseModel)
│   │   └── FeedRecord(SQLModel)
│   ├── search.py
│   │   ├── class FeedQuery(BaseModel)
│   │   ├── find_feed_by_id(feed_id: str) -> HttpRequestTask | None
│   │   └── search_feeds(query: FeedQuery) -> list[HttpRequestTask]
│   └── service.py
│       ├── ensure_http_url(value: str | HttpUrl) -> HttpUrl
│       └── create_feed(url: str, title: str, status_code: int, pub_date: datetime) -> HttpRequestTask
└── rss.py 他
```
