# Article機能 実装計画 (詳細版)

`design.md`および既存モジュールの設計に基づき、`Article`機能の実装を以下の通り詳細化する。

## 1. ディレクトリ・ファイル構成

ユーザーの指示に基づき、テストは各ファイルに同居させる。

```
src/domain/news/article/
├── __init__.py
├── model.py      # Articleモデル、DBレコード定義、状態Enum
├── fetch.py      # 記事HTMLの取得と本文抽出
├── command.py    # Articleの作成・更新(Upsert)
├── search.py     # Articleの検索
└── service.py    # FeedからのArticle生成ワークフロー
```

## 2. 各モジュールの詳細設計

### `model.py`

- **`ArticleStatus(str, Enum)`**:
  - `RAW`: コンテンツを未取得の状態。
  - `EXTRACTED`: HTMLから本文の抽出が完了した状態。
  - `SUMMARIZED`: (将来実装) LLMによる要約が完了した状態。

- **`Article(BaseModel)`**: ドメインモデル
  - `id: str`
  - `url: HttpUrl`
  - `title: str`
  - `content: str`
  - `status: ArticleStatus`
  - `pub_date: datetime`

- **`ArticleRecord(SQLModel, table=True)`**: 永続化モデル
  - `__tablename__ = "article"`
  - `id: str = Field(primary_key=True)`
  - `url: str`
  - `title: str`
  - `content: str`
  - `status: str`
  - `pub_date: datetime`

- **テスト (`Tests`クラス内):**
  - `Article`モデルが正しく生成されるか。
  - `ArticleStatus`のEnum値が期待通りか。

### `fetch.py`

- **`fetch_content(url: HttpUrl) -> str | None`**:
  - `infra.api.https`を利用して指定されたURLからHTMLコンテンツを取得する。
  - 失敗した場合は`None`を返し、ログを出力する。

- **`extract_main_content(html: str) -> str`**:
  - `infra.parse` (例: `BeautifulSoup`) を利用して、HTMLから記事の主要なテキストコンテンツを抽出する。

- **テスト (`Tests`クラス内):**
  - `fetch_content`がHTTPリクエストをモックして期待通りのHTMLを返すか。
  - `extract_main_content`がサンプルHTMLから正しく本文を抽出できるか。

### `command.py`

- **`upsert_article(session: Session, article: Article) -> ArticleRecord`**:
  - `Article`ドメインモデルを受け取り、`ArticleRecord`に変換してDBにUpsertする。
  - 処理は`infra.storage.rds`に委譲する。

- **テスト (`Tests`クラス内):**
  - `upsert_article`がインメモリDBに対して正しくUpsert処理を実行できるか。

### `search.py`

- **`ArticleSearchQuery(BaseModel)`**:
  - `statuses: list[ArticleStatus] | None = None`
  - `url_patterns: list[str] | None = None`
  - `start_date: datetime | None = None`
  - `end_date: datetime | None = None`

- **`search_articles(session: Session, query: ArticleSearchQuery) -> list[Article]`**:
  - `ArticleSearchQuery`に基づき、DBから`ArticleRecord`を検索し、`Article`ドメインモデルのリストに変換して返す。

- **テスト (`Tests`クラス内):**
  - `search_articles`がインメモリDBに対して、各検索条件で正しくArticleをフィルタリングできるか。

### `service.py`

- **`create_article_from_feed(feed: FeedItem) -> Article | None`**:
  - **入力**: `FeedItem`
  - **出力**: 生成・保存された`Article`、または失敗時に`None`
  - **処理フロー**:
    1. `feed.url`を元に`fetch.fetch_content`でHTMLを取得。取得失敗時はログを出力し`None`を返す。
    2. 取得したHTMLを`fetch.extract_main_content`で本文に変換。
    3. `feed`の情報と抽出した本文から`Article`ドメインモデルを生成。`status`は`ArticleStatus.EXTRACTED`とする。
    4. `command.upsert_article`を呼び出し、DBに永続化する。
    5. 生成した`Article`を返す。

- **テスト (`Tests`クラス内):**
  - `fetch`と`command`をモックし、`create_article_from_feed`が`FeedItem`から`Article`を正しく生成し、永続化処理を呼び出すことを確認する。
  - `fetch_content`が`None`を返した場合に、サービスが正しく`None`を返すことを確認する。

## 3. ワークフローの更新

- `src/workflow/news.py`にて、`Feed`をDBに保存した後、未処理の`Feed`を対象にこの`article.service.create_article_from_feed`を呼び出す処理を追加する。
