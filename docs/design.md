# テーブル定義
Option指定なき場合、NOT NULL制約とする。

## Feed
RSSフィードの要素を保存するテーブル。
URL取得状況の管理も行う。

| name        | type       | description                                   |
| ----------- | ---------- | --------------------------------------------- |
| id          | text(PK)   | URLのhash。Bucket.idとjoinされる              |
| bucket_id   | text       | 元となったRssBucketのID                        |
| url         | text       | 記事のURL                                     |
| title       | text       | 記事のタイトル                                |
| status_code | int?       | HTTPステータスコード                          |
| pub_date    | timestampz | 記事の公開日時。ニュースという特性上UTCを使う |

### 永続化・接続設定
- デフォルトでは`sqlite:///data/datadoggo.db`に保存する。
- 環境変数`FEED_DATABASE_URL`を設定すると接続先を切り替えられる。
- テーブル初期化はアプリケーション起動時に`initialize_database()`で行う。

## RSS Bucket
links.yml 由来の RSS フィードをバケットへ保存した際のメタデータを保持する。

| name           | type       | description                                      |
| -------------- | ---------- | ------------------------------------------------ |
| id             | text(PK)   | バケットキー (SHA256)。`save_rss_element_to_bucket` の戻り値 |
| group          | text       | links.yml のグループ名                           |
| name           | text       | links.yml のエントリ名                           |
| url            | text       | RSS フィードの取得先 URL                         |
| status         | text       | `RssBucketStatus`。`pending/registered/overridden/error` |
| saved_at       | timestampz | 保存日時(UTC)                                     |
| content_length | int?       | 保存した RSS XML のバイト長                       |

**補足:**
- デフォルトでは `sqlite:///data/datadoggo.db` に保存する。
- 環境変数 `FEED_DATABASE_URL` で接続先を切り替え可能。
- `store_rss_bucket_payload` がバケット保存とメタデータ upsert を同時に行う。

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
- RSS バケットメタデータ
  - store_rss_bucket_payload(rss_item: RssItem, element: Element) -> RssBucketItem

## データ取得
- ArticleUrlStatus
  - search_article_url_status(query: ArticleUrlQuery) -> ArticleUrlStatus[list]
- Article
  - search_article(query: ArticleQuery) -> Article[list]
- RSS Bucket
  - find_rss_bucket_by_id(bucket_id: str) -> RssBucketItem | None
  - search_rss_buckets(query: RssBucketQuery) -> list[RssBucketItem]

## ワークフロー
- feeds.ymlを元にArticleLinkを取得しDBに保存する
- ArticleLinkについて、未取得か失敗した内容のArticleContentを取得しDBに保存する
