# Article機能 実装計画 (v4 - 最終版)

`design.md`の定義と`infra.storage.bucket.py`の仕様に基づき、実装計画を以下の通り最終化する。

## 1. ディレクトリ・ファイル構成

```
src/domain/news/article/
├── __init__.py
├── model.py      # 各種Article関連モデル定義
├── fetch.py      # ArticleContentの生成
├── command.py    # バケット保存とメタデータ永続化
└── search.py     # メタデータとコンテンツの検索・結合
```

## 2. 各モジュールの詳細設計

### `model.py`

- **`ArticleFetchStatus(str, Enum)`**:
  - `SAVED`: コンテンツのバケット保存とメタデータ保存が完了した状態。
  - `FETCH_FAILED`: HTML取得に失敗した状態。

- **`ArticleContent(BaseModel)`**: `fetch`が生成する、生のHTMLを持つ中間モデル。
  - `id: str`
  - `url: HttpUrl`
  - `title: str`
  - `pub_date: datetime`
  - `html_content: str`

- **`ArticleBucketMetadata(BaseModel)`**: DBに保存されるメタデータのドメインモデル。
  - `id: str`
  - `url: HttpUrl`
  - `title: str`
  - `status: ArticleFetchStatus`
  - `pub_date: datetime`
  - `saved_at: datetime`

- **`ArticleBucketMetadataRecord(SQLModel, table=True)`**: 上記の永続化モデル。
  - `__tablename__ = "article_bucket_metadata"`
  - `id`, `url`, `title`, `status`, `pub_date`, `saved_at`の各フィールドを定義。

- **`Article(BaseModel)`**: `search`が返す、メタデータとコンテンツを結合した完全なビューモデル。
  - `id: str`
  - `url: HttpUrl`
  - `title: str`
  - `pub_date: datetime`
  - `html_content: str`

### `fetch.py`

- **`fetch_article_content(feed: HttpRequestTask) -> ArticleContent | None`**:
  - `infra.api.https`でHTMLを取得する。
  - 取得成功時、`feed`情報と生のHTMLで`ArticleContent`を生成して返す。
  - 取得失敗時はログを出力し`None`を返す。

- **テスト (`Tests`クラス内):**
  - ネットワークをモックし、成功時に`ArticleContent`が、失敗時に`None`が返ることを確認する。

### `command.py`

- **`save_article_content(session: Session, content: ArticleContent) -> ArticleBucketMetadata`**:
  - **入力**: `ArticleContent`
  - **責務**: バケット保存とメタデータ永続化
  - **処理フロー**:
    1. `infra.storage.bucket.save_object`を呼び出し、`content.html_content`を`article`バケットに保存。`object_key`は`content.id`。
    2. `ArticleBucketMetadata`を`status=SAVED`で生成する。
    3. `ArticleBucketMetadataRecord`に変換し、DBにUpsertする。
    4. 生成した`ArticleBucketMetadata`を返す。

- **テスト (`Tests`クラス内):**
  - `bucket.save_object`とDBセッションをモックし、`save_article_content`が各々を正しい引数で呼び出すことを確認する。

### `search.py`

- **`ArticleSearchQuery(BaseModel)`**: 検索クエリ用のモデル。
  - `statuses: list[ArticleFetchStatus] | None = None`

- **`search_article_metadata(session: Session, query: ArticleSearchQuery) -> list[ArticleBucketMetadata]`**:
  - DBから`ArticleBucketMetadataRecord`を検索し、`ArticleBucketMetadata`のリストに変換して返す。

- **`find_article_by_id(session: Session, id: str) -> Article | None`**:
  - **責務**: メタデータとバケットコンテンツを結合し、完全な`Article`を返す。
  - **処理フロー**:
    1. `id`をキーにDBから`ArticleBucketMetadataRecord`を検索。
    2. `infra.storage.bucket.load_object`を`as_text=True`で呼び出し、バケットからHTMLコンテンツを取得。
    3. メタデータとHTMLコンテンツを結合し、`Article`ビューモデルを生成して返す。
    4. いずれかが見つからない場合は`None`を返す。

- **テスト (`Tests`クラス内):**
  - `search_article_metadata`がDB検索を正しく行うことを確認。
  - `find_article_by_id`が、モックしたDBとバケットから`Article`を正しく再構築できることを確認。
