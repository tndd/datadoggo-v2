# Article機能 実装計画 (v2)

ユーザーからのフィードバックに基づき、実装計画を以下の通り修正する。

## 1. ディレクトリ・ファイル構成

`fetch.py`と`service.py`は不要とし、責務を`command.py`に集約する。

```
src/domain/news/article/
├── __init__.py
├── model.py      # Articleモデル、DBレコード定義、状態Enum
├── command.py    # HTML取得、圧縮、DB保存
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
  - `content: bytes`  # gzip圧縮されたHTMLコンテンツ
  - `status: ArticleStatus`
  - `pub_date: datetime`

- **`ArticleRecord(SQLModel, table=True)`**: 永続化モデル
  - `__tablename__ = "article"`
  - `id: str = Field(primary_key=True)`
  - `url: str`
  - `title: str`
  - `content: bytes = Field(sa_column=Column(LargeBinary))` # バイナリ型を指定
  - `status: str`
  - `pub_date: datetime`

- **テスト (`Tests`クラス内):**
  - `Article`モデルが正しく生成されるか。
  - `content`がbytes型を受け入れるか。

### `command.py`

- **`save_article(session: Session, feed: FeedItem) -> Article | None`**:
  - **入力**: `FeedItem`
  - **出力**: 生成・保存された`Article`、または失敗時に`None`
  - **処理フロー**:
    1. `feed.url`を元に`infra.api.https.fetch_content`でHTMLを取得。文字コードは`utf-8`でデコードする。
    2. 取得失敗時は、`status`を`FAILED`として空の`content`で`Article`を生成し、DBに保存後、`None`を返す。
    3. 取得成功時は、HTML文字列を`utf-8`でエンコードし、`gzip.compress()`で圧縮する。
    4. `feed`の情報と圧縮後の`bytes`から`Article`ドメインモデルを生成。`status`は`ArticleStatus.FETCHED`とする。
    5. 生成した`Article`を`ArticleRecord`に変換し、DBにUpsertする。
    6. 生成した`Article`を返す。

- **テスト (`Tests`クラス内):**
  - `infra.api.https`をモックし、`save_article`が`FeedItem`から`Article`を正しく生成し、DBに保存することを確認する。
  - HTML取得成功時に、`content`がgzip圧縮されていることを確認する。
  - HTML取得失敗時に、`status`が`FAILED`でDBに保存されることを確認する。

### `search.py`

- **`ArticleSearchQuery(BaseModel)`**:
  - `statuses: list[ArticleStatus] | None = None`
  - `has_content: bool | None = None` # contentが空でないかでフィルタ

- **`search_articles(session: Session, query: ArticleSearchQuery) -> list[Article]`**:
  - `ArticleSearchQuery`に基づき、DBから`ArticleRecord`を検索し、`Article`ドメインモデルのリストに変換して返す。
  - `content`は圧縮されたまま返す。

- **テスト (`Tests`クラス内):**
  - `search_articles`がインメモリDBに対して、各検索条件で正しくArticleをフィルタリングできるか。

## 3. ワークフロー

- `workflow/news.py`の変更は、今回のスコープに含めない。
