# テーブル定義
- Option指定なき場合、NOT NULL制約とする。
- デフォルトでは`sqlite:///data/datadoggo.db`に保存する。
- テーブル初期化はアプリケーション起動時に`initialize_database()`で行う。

## task_queue

### http_request_queue
- HTTPリクエストの進捗管理テーブル。

| name        | type       | description                                        |
| ----------- | ---------- | -------------------------------------------------- |
| id          | text(PK)   | URLのhash                                          |
| url         | text       | 記事のURL                                          |
| status_code | int?       | HTTPステータスコード                               |
| created_at  | timestampz | レコードの生成日時(UTC), rssのpub_dateはここに入る |
| updated_at  | timestampz | レコードの最終更新日時(UTC)                        |
| description | text?      | 記事の説明。記事のタイトルや注釈など               |
| group       | text?      | グループ名                                         |

## rss_link

### RssItem
links.yml に定義された RSS フィードのエントリ。
- グループ名・リンク名・URL のみを保持するシンプルな構造。
- 取得した RSS XML はバケットへ保存せず、そのまま Feed テーブルへ変換して保存する。

| name  | type     | description |
| ----- | -------- | ----------- |
| url   | text(PK) | URL         |
| group | text     | グループ名  |
| name  | text     | リンク名    |

## article

Article機能は記事のHTMLコンテンツをバケットに保存し、Feedテーブルのメタデータと組み合わせて完全なArticleを提供する。

**設計方針:**
- ArticleBucketMetadataテーブルは廃止。メタデータは既存のFeedテーブルから取得。
- バケットには記事のHTMLコンテンツのみを保存。
- 記事の取得状況はFeedテーブルの `status_code` で管理（200=成功、その他=失敗）。

**処理フロー:**
1. `fetch_article_content`: FeedItemから記事HTMLを取得してArticleを生成
2. `save_article_content`: ArticleのHTMLコンテンツをバケットに保存
3. `find_article_by_id`: FeedテーブルとバケットからArticleを再構築

# バケット
## article
- 記事本体であるhtmlの圧縮物が保存される。keyはurlをハッシュ化したもの

# ドメインモデル

## article

### Article
ArticleLinkにArticleContentをjoinしたもの。
ユーザーから見ればsourceは関心ごとではない。createとupdateも同じく。status_codeについては、ユーザーははじめから成功した記事を要求してるのだから、この項目は不要。contentも同じく失敗記事が要求されることはないためOptional指定を外している。

| name        | type       | description                    |
| ----------- | ---------- | ------------------------------ |
| id          | text(PK)   | URLのhash                      |
| url         | text       | 記事のURL                      |
| content     | text       | 記事の内容                     |
| group       | text?      | グループ名                     |
| created_at  | timestampz | レコードの生成日時(UTC)        |
| updated_at  | timestampz | レコードの最終更新日時(UTC)    |
| description | text?      | 説明。記事のタイトルや注釈など |


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
