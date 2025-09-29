# テーブル定義
- Option指定なき場合、NOT NULL制約とする。
- デフォルトでは`sqlite:///data/datadoggo.db`に保存する。
- 環境変数`FEED_DATABASE_URL`を設定すると接続先を切り替えられる。
- テーブル初期化はアプリケーション起動時に`initialize_database()`で行う。

## feed

### Feed
- RSSフィードの要素を保存するテーブル。
- URL取得状況の管理も行う。

| name        | type       | description                                   |
| ----------- | ---------- | --------------------------------------------- |
| id          | text(PK)   | URLのhash                                     |
| url         | text       | 記事のURL                                     |
| title       | text       | 記事のタイトル                                |
| status_code | int?       | HTTPステータスコード                          |
| pub_date    | timestampz | 記事の公開日時。ニュースという特性上UTCを使う |
| created_at  | timestampz | レコードの生成日時(UTC)                       |
| updated_at  | timestampz | レコードの最終更新日時(UTC)                   |

## rss_link

### RssItem
links.yml に定義された RSS フィードのエントリ。
- グループ名・リンク名・URL のみを保持するシンプルな構造。
- 取得した RSS XML はバケットへ保存せず、そのまま Feed テーブルへ変換して保存する。

## article

### ArticleBucketMetadata
Articleの記事内容のバケットのメタデータ

| name       | type       | description                                              |
| ---------- | ---------- | -------------------------------------------------------- |
| id         | text(PK)   | バケットキー (SHA256)。`save_article_to_bucket` の戻り値 |
| url        | text       | RSS フィードの取得先 URL                                 |
| status     | text       | `RssBucketStatus`。`pending/registered/overridden/error` |
| saved_at   | timestampz | 保存日時(UTC)                                            |
| updated_at | timestampz | 更新日時(UTC)                                            |


**補足:**
- デフォルトでは `sqlite:///data/datadoggo.db` に保存する。
- 環境変数 `FEED_DATABASE_URL` で接続先を切り替え可能。
- RSS 取得時に XML をバケットへ保存するステップは廃止し、パース結果を直に Feed テーブルへ永続化する。

# ドメインモデル

## article

### Article
ArticleLinkにArticleContentをjoinしたもの。
ユーザーから見ればsourceは関心ごとではない。createとupdateも同じく。status_codeについては、ユーザーははじめから成功した記事を要求してるのだから、この項目は不要。contentも同じく失敗記事が要求されることはないためOptional指定を外している。

| name     | type       | description                                      |
| -------- | ---------- | ------------------------------------------------ |
| id       | text(PK)   | URLのhash                                        |
| url      | text       | 記事のURL                                        |
| title    | text       | 記事のタイトル                                   |
| pub_date | timestampz | 公開日時。ニュースという特性上UTCを使う          |
| content  | text       | 記事の内容                                       |
| statsu   | text       | articleの記事内容の加工状況(llmなどを用いる予定) |

### ArticleContent
Articleの記事内容のバケット。
fetchしてきたものをクラスとして表現することを目的としてる。

| name | type     | description                                              |
| ---- | -------- | -------------------------------------------------------- |
| id   | text(PK) | バケットキー (SHA256)。`save_article_to_bucket` の戻り値 |
| url  | text     | RSS フィードの取得先 URL                                 |
| data | str      | htmlコンテンツ                                           |

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
