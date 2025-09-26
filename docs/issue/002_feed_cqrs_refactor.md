# Feed CQRS分割計画（feed.py・service.py廃止版）

## 背景
- 現行の`src/domain/news/feed.py`は書き込み・読み出し・永続化・テストを1ファイルで扱っており、責務境界が不明瞭になっている。
- CQRS原則による責務分離と、不要なラップ関数の整理を同時に進めることで、保守性と拡張性を高める。
- HTTPステータスコードは任意値(整数)を許容する必要があるため、列挙型による制約(例:`FeedStatus`)は導入しない。

## 目的
- 書き込み系のユースケースを`command.py`、読み出し系を`search.py`へ分離する。
- 永続化レイヤの共通処理は`persistence.py`にまとめ、サービス層(`service.py`)やファサード(`feed.py`)を排除する。
- 公開API (`create_feed`/`store_feed`/`find_feed_by_id`/`search_feeds`/`FeedQuery`) のシグネチャと振る舞いを維持しつつ、モジュール構成を刷新する。

## スコープ
- 対象: `src/domain/news/feed.py`と、`feed/`配下の`command.py`/`search.py`/`model.py`、新設する`persistence.py`。
- 非対象: `infra.storage.rds`の接続ロジック、`infra.compute.hash_text_sha256`の実装、HTTPステータスコードの検証強化。

## 実装ステップ
1. **公開APIと依存関係の棚卸し**
   - `create_feed`/`store_feed`/`find_feed_by_id`/`search_feeds`/`FeedQuery`が依存する内部関数(`_FeedRecord`、URL検証、DB初期化など)と外部モジュール(`hash_text_sha256`、`session_scope`)を洗い出す。
   - 単一箇所からしか呼ばれていない薄いラップ関数は削除候補としてマーキングする。
2. **persistenceモジュール新設**
   - `_FeedRecord`定義、DB初期化ヘルパー(`ensure_feed_table_initialized`)、レコード⇔ドメイン変換関数(`feed_to_record`/`record_to_feed`)を`persistence.py`へ移管。
   - 複数モジュールで利用する処理のみ配置し、冗長な関数は追加しない。
3. **command.pyの再構成**
   - `create_feed`と`store_feed`を`command.py`へ集約し、`persistence`モジュール経由で永続化を行う。
   - `_ensure_http_url`等のユーティリティは`command.py`内で完結させるか、共用が必要であれば`persistence`に移す。
4. **search.pyの再構成**
   - `FeedQuery`、`find_feed_by_id`、`search_feeds`を移動し、SQLステートメント構築と結果のドメイン変換を担当させる。
   - `persistence.record_to_feed`と`persistence.ensure_feed_table_initialized`を利用しつつ、単独利用の関数は直接記述して冗長なラップを作らない。
5. **feed.pyの削除**
   - 旧ファサード`feed.py`は削除し、呼び出し側が`feed.command`/`feed.search`/`feed.model`を直接参照する構成へ変更する。
   - 参照箇所をリネームし、不要になったインポートを整理する。
6. **テストの再配置と更新**
   - 既存テストクラスを`tests/domain/news/feed/command`や`tests/domain/news/feed/search`など機能別モジュールに再配置し、docs形式のコメントを維持。
   - 新構成で冗長なヘルパーを使わずにテストが書けるように調整する。
7. **ドキュメント更新**
   - `docs/issue/001_feed_table_plan.md`等、旧`feed.py`/`service.py`を言及している資料を更新する。
   - 新構成とテスト方針を必要に応じて追記する。
8. **検証**
   - `ruff check`、`pyright`、`pytest`を実行し、警告も含めて解消する。
   - テスト配置変更で`pytest`がテストを検出できることを確認する。

## リスク・懸念
- `_FeedRecord`移動時にimport循環が発生しないよう、依存方向を`persistence`→(`command`/`search`)の一方向に保つ。
- `FeedQuery`のバリデーションが移動後も同一になるよう、フィールド定義と制約を慎重に移植する。
- ラップ関数削除で既存呼び出しが失われないよう、削除前に参照箇所を徹底的に確認する。

## 完了条件
- `feed.py`および`service.py`が削除されている。
- `command.py`/`search.py`/`persistence.py`で責務が明確に分割され、公開APIのシグネチャが維持されている。
- 冗長なラップ関数が排除され、共有が必要な処理のみ`persistence.py`に残っている。
- `FeedStatus`等の列挙型が導入されていない。
- `ruff check`/`pyright`/`pytest`が成功している。

## 想定ファイル・シンボル構成

```
src/domain/news
├── feed
│   ├── command.py
│   │   ├── create_feed(url: str, title: str, status_code: int, pub_date: datetime) -> FeedItem
│   │   └── store_feed(feed: FeedItem) -> FeedItem
│   ├── model.py
│   │   └── FeedItem(BaseModel)
│   ├── persistence.py
│   │   ├── class _FeedRecord(SQLModel)
│   │   ├── ensure_feed_table_initialized() -> None
│   │   ├── feed_to_record(feed: FeedItem) -> _FeedRecord
│   │   └── record_to_feed(record: _FeedRecord) -> FeedItem
│   └── search.py
│       ├── class FeedQuery(BaseModel)
│       ├── find_feed_by_id(feed_id: str) -> FeedItem | None
│       └── search_feeds(query: FeedQuery) -> list[FeedItem]
└── rss.py 他
```
