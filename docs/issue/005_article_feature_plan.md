# Article機能 実装計画 (v3)

度重なる議論に基づき、実装計画を以下の通り最終化する。

## 1. ディレクトリ・ファイル構成

ネットワーク処理を`fetch.py`に分離し、責務を明確化する。

```
src/domain/news/article/
├── __init__.py
├── model.py      # Articleモデル、DBレコード定義、状態Enum
├── fetch.py      # 記事HTMLの取得とネットワークエラー処理
├── command.py    # Articleの保存と、取得・保存のオーケストレーション
└── search.py     # Articleの検索
```

## 2. 各モジュールの詳細設計

### `model.py`

- **`ArticleStatus(str, Enum)`**:
  - `PENDING`: 処理待ち。
  - `FETCHED`: HTMLコンテンツの取得と保存が完了した状態。
  - `FAILED`: HTML取得に失敗した状態。

- **`Article(BaseModel)`**: ドメインモデル
  - `id: str`
  - `url: HttpUrl`
  - `title: str`
  - `content: str`  # 生のHTMLコンテンツ
  - `status: ArticleStatus`
  - `pub_date: datetime`

- **`ArticleRecord(SQLModel, table=True)`**: 永続化モデル
  - `__tablename__ = "article"`
  - `id: str = Field(primary_key=True)`
  - `url: str`
  - `title: str`
  - `content: bytes = Field(sa_column=Column(LargeBinary))` # gzip圧縮されたHTML
  - `status: str`
  - `pub_date: datetime`

### `fetch.py`

- **`fetch_html(url: HttpUrl) -> str | None`**:
  - `infra.api.https`を利用してHTMLコンテンツを取得する。
  - タイムアウト、HTTPエラー、リダイレクト等のネットワークエラーをハンドリングし、ログを出力する。
  - 成功した場合はHTML文字列(`str`)を、失敗した場合は`None`を返す。

- **テスト (`Tests`クラス内):**
  - ネットワークをモックし、成功ケース・失敗ケース（タイムアウト等）で期待通りの戻り値とログが出力されることを確認する。

### `command.py`

- **`save_article(session: Session, article: Article) -> ArticleRecord`**:
  - **入力**: `Article`ドメインモデル
  - **責務**: 純粋な永続化処理
  - **処理フロー**:
    1. `article.content` (str) を `utf-8` でエンコードし、`gzip.compress()` で圧縮する。
    2. `article`ドメインモデルと圧縮後の`bytes`から`ArticleRecord`を生成する。
    3. DBにUpsertし、生成した`ArticleRecord`を返す。

- **`fetch_and_save_article(session: Session, feed: FeedItem) -> Article | None`**:
  - **入力**: `FeedItem`
  - **責務**: HTML取得からDB保存までの一連の処理の統括
  - **処理フロー**:
    1. `fetch.fetch_html(feed.url)` を呼び出し、HTMLを取得する。
    2. 取得成功時は、`status=FETCHED`、`content=取得したHTML`として`Article`ドメインモデルを生成する。
    3. 取得失敗時は、`status=FAILED`、`content=""`として`Article`ドメインモデルを生成する。
    4. 生成した`Article`モデルを引数に `save_article` を呼び出し、DBに保存する。
    5. HTML取得に成功した場合のみ、生成した`Article`を返し、失敗した場合は`None`を返す。

- **テスト (`Tests`クラス内):**
  - `save_article`が`Article`を`ArticleRecord`へ正しく変換（圧縮含む）し、DBに保存することを確認する。
  - `fetch_and_save_article`が、`fetch.py`の成功/失敗に応じて`save_article`を正しい引数で呼び出すことを確認する。

### `search.py`

- **`ArticleSearchQuery(BaseModel)`**:
  - `statuses: list[ArticleStatus] | None = None`

- **`search_articles(session: Session, query: ArticleSearchQuery) -> list[Article]`**:
  - `ArticleSearchQuery`に基づきDBから`ArticleRecord`を検索する。
  - 各`ArticleRecord`について、`content` (bytes) を `gzip.decompress()` で解凍し、`utf-8`でデコードして `str` にする。
  - `Article`ドメインモデルのリストに変換して返す。

- **テスト (`Tests`クラス内):**
  - `search_articles`が、保存時に圧縮した`content`を正しく解凍・デコードして`Article`モデルを生成できるか確認する。

## 3. ワークフロー

- `workflow/news.py`の変更は、今回のスコープに含めない。
