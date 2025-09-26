# テーブル定義
Option指定なき場合、NOT NULL制約とする。

## Feed
RSSフィードの要素を保存するテーブル。
URL取得状況の管理も行う。

| name        | type       | description                                   |
| ----------- | ---------- | --------------------------------------------- |
| id          | text(PK)   | URLのhash。Bucket.idとjoinされる              |
| url         | text       | 記事のURL                                     |
| title       | text       | 記事のタイトル                                |
| status_code | int?       | HTTPステータスコード                          |
| pub_date    | timestampz | 記事の公開日時。ニュースという特性上UTCを使う |

### 永続化・接続設定
- デフォルトでは`sqlite:///data/datadoggo.db`に保存する。
- 環境変数`FEED_DATABASE_URL`を設定すると接続先を切り替えられる。
- テーブル初期化はアプリケーション起動時に`initialize_database()`で行う。

## Bucket
データの保存先を管理するテーブル。

| name           | type       | description                    |
| -------------- | ---------- | ------------------------------ |
| id             | text(PK)   | sha256 hash                    |
| created_at     | timestampz | 作成日時。デフォルトは現在時刻 |
| updated_at     | timestampz | 更新日時。デフォルトは現在時刻 |
| content_path   | text       | 記事が保存されているパス       |
| content_digest | text       | 記事の内容のハッシュ           |

**join元:**
- Feed.id = Bucket.id

# ドメインモデル

## Article
ArticleLinkにArticleContentをjoinしたもの。
ユーザーから見ればsourceは関心ごとではない。createとupdateも同じく。status_codeについては、ユーザーははじめから成功した記事を要求してるのだから、この項目は不要。contentも同じく失敗記事が要求されることはないためOptional指定を外している。

| name     | type       | description                             |
| -------- | ---------- | --------------------------------------- |
| id       | text(PK)   | URLのhash                               |
| url      | text       | 記事のURL                               |
| title    | text       | 記事のタイトル                          |
| pub_date | timestampz | 公開日時。ニュースという特性上UTCを使う |
| content  | text       | 記事の内容                              |

# 関数
## データ収集&保存
- feeds.yml -> list[str]
  - load_rss_urls(group: Optional[str]) -> list[str]
    - groupはfeeds.ymlのkeyを指定する。指定しない場合は全てのURLを返す。
- url -> Feed
  - fetch_feed(url: str) -> Feed
- Feed -> ArticleLink[list]
  - get_article_links(rss: Feed) -> ArticleLink[list]
    - Feedはxml形式のデータ(ex. parser.ParseURL("https://zenn.dev/spiegel/feed"))
  - store_article_links(article_links: ArticleLink[list]) -> None
- ArtileLink -> ArticleContent
  - fetch_article_content(url: str) -> ArticleContent
  - store_article_content(article_content: ArticleContent) -> None

## データ取得
- ArticleUrlStatus
  - search_article_url_status(query: ArticleUrlQuery) -> ArticleUrlStatus[list]
- Article
  - search_article(query: ArticleQuery) -> Article[list]

## ワークフロー
- feeds.ymlを元にArticleLinkを取得しDBに保存する
- ArticleLinkについて、未取得か失敗した内容のArticleContentを取得しDBに保存する
