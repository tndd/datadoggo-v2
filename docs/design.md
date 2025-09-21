# テーブル定義
Option指定なき場合、NOT NULL制約とする。

## ArticleLink
記事のリンク

| name     | type       | description                                   |
| -------- | ---------- | --------------------------------------------- |
| url      | text       | URLを主キーとする                             |
| title    | text       | 記事のタイトル                                |
| source   | text       | どこから取得されたリンクかを表す              |
| pub_data | timestampz | 記事の公開日時。ニュースという特性上UTCを使う |

## ArticleContent
記事の内容を保存するテーブル。linkとjoinして使う。

| name        | type       | description                                |
| ----------- | ---------- | ------------------------------------------ |
| url         | str(FK)    | linkのurlを外部キーとする                  |
| created_at  | timestampz | 作成日時。デフォルトは現在時刻             |
| updated_at  | timestampz | 更新日時。デフォルトは現在時刻             |
| status_code | int        | HTTPステータスコード                       |
| content     | text       | 記事の内容。取得に失敗しても空文字は入れる |

# ドメインモデル
## ArticleUrlStatus
URLごとの取得状況を確認するためのモデル。

| name        | type          | description                                                            |
| ----------- | ------------- | ---------------------------------------------------------------------- |
| url         | text          | URLを主キーとする                                                      |
| status      | text          | 取得状況。成功か失敗かを表す                                           |
| pub_data    | timestampz    | 記事の公開日時                                                         |
| status_code | int(Optional) | HTTPステータスコード。未実行のものがjoinされる可能性があるためOptional |


## Article
ArticleLinkにArticleContentをjoinしたもの。
ユーザーから見ればsourceは関心ごとではない。createとupdateも同じく。status_codeについては、ユーザーははじめから成功した記事を要求してるのだから、この項目は不要。contentも同じく失敗記事が要求されることはないためOptional指定を外している。

| name     | type       | description                             |
| -------- | ---------- | --------------------------------------- |
| url      | text       | URLを主キーとする                       |
| title    | text       | 記事のタイトル                          |
| pub_data | timestampz | 公開日時。ニュースという特性上UTCを使う |
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