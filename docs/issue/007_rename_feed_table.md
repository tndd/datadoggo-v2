# 概要
現在のFeedはrss feedの要素を格納するということに特化している。
だがそれを、HTTPリクエストの進捗管理テーブルとして変更したい。

# テーブル定義

## http_request
テーブル名: `http_request`
ドメインモデル名: `HttpRequest`
レコードモデル名: `HttpRequestRecord`

| name        | type     | nullable | description                                                       |
| ----------- | -------- | -------- | ----------------------------------------------------------------- |
| id          | str      | False    | urlのhash (PRIMARY KEY)                                           |
| url         | str      | False    | 記事URL                                                           |
| status_code | int      | True     | HTTP通信結果コード。Noneは未実行を意味する                        |
| group       | str      | False    | 取得元識別子。階層を持たせる場合は`{source}:{category}`形式で指定 |
| created_at  | datetime | False    | 初回登録日時。RSSの場合はpub_dateをここに入れる                   |
| updated_at  | datetime | False    | 最終更新日時                                                      |
| description | str      | True     | 記事タイトル等の説明。RSSにおけるtitleをここに入れる              |

## groupフィールドの設計方針
- **形式**: `{source}:{category}`を推奨するが、単純な文字列も許容
- **例**:
  - 直接RSS: `bbc:world`, `cbs:politics`
  - アグリゲータ経由: `google_news:tech`, `yahoo_japan:topics_business`
  - その他: `manual`, `api:some_service`
- **理由**: Google News、Yahoo、MSN等のアグリゲータ経由では全て同一ドメインになるため、groupによる識別が必須
- **平坦な分類**: 階層構造は持たず、文字列として柔軟に扱う
- **クエリ例**: `WHERE group LIKE 'bbc:%'` で特定ソース由来を抽出可能

# 変更の波及範囲

## 影響を受けるファイル

### モデル・サービス層 (要修正)
- [src/domain/news/feed/model.py](../../../src/domain/news/feed/model.py)
  - `FeedItem` → `HttpRequest` にリネーム
  - `FeedRecord` → `HttpRequestRecord` にリネーム
  - `__tablename__ = "feed_item"` → `"http_request"` に変更
  - `title: str` → `description: str | None` に変更
  - `pub_date: datetime` → 削除 (created_atで代替)
  - `group: str` フィールドを追加

- [src/domain/news/feed/service.py](../../../src/domain/news/feed/service.py)
  - `create_feed()` → `create_http_request()` にリネーム
  - 引数: `title` → `description` に変更
  - 引数: `pub_date` → 削除 (`created_at`で代替)
  - 引数: `group` を追加
  - `feed_to_record()`, `record_to_feed()` → `http_request_to_record()`, `record_to_http_request()` にリネーム
  - `convert_rss_items_to_feed_items()` → `convert_rss_items_to_http_requests()` にリネーム
    - RSS取得時に`group`を`f"{rss_item.group}:{rss_item.name}"`形式で設定
    - `pub_date`を`created_at`として使用
    - `title`を`description`として使用

- [src/domain/news/feed/command.py](../../../src/domain/news/feed/command.py)
  - `store_feed()` → `store_http_request()` にリネーム
  - 引数: `FeedItem` → `HttpRequest` に変更
  - 全テストを更新

- [src/domain/news/feed/search.py](../../../src/domain/news/feed/search.py)
  - `FeedQuery` → `HttpRequestQuery` にリネーム
  - クエリフィールド: `title` → `description` に変更
  - クエリフィールド: `pub_date_from`, `pub_date_to` → `created_at_from`, `created_at_to` に変更
  - クエリフィールド: `group` を追加
  - `find_feed_by_id()` → `find_http_request_by_id()` にリネーム
  - `search_feeds()` → `search_http_requests()` にリネーム
  - 全テストを更新

### Article関連 (互換性維持が必要)
- [src/domain/news/article/search.py](../../../src/domain/news/article/search.py)
  - `FeedRecord` → `HttpRequestRecord` に変更
  - フィールド参照: `.title` → `.description` に変更
  - フィールド参照: `.pub_date` → `.created_at` に変更
  - `find_article_by_id()`, `search_articles_by_ids()` の動作確認
  - 全テストを更新

- [src/domain/news/article/fetch.py](../../../src/domain/news/article/fetch.py)
  - `FeedItem` → `HttpRequest` に変更
  - フィールド参照: `.title` → `.description` に変更
  - フィールド参照: `.pub_date` → `.created_at` に変更

### ディレクトリ名変更
- `src/domain/news/feed/` → `src/domain/news/http_request/` に変更を検討
  - ただし、変更範囲が大きいため、当面は内部の名前変更のみで対応
  - 将来的なリファクタリングで対応

## テストの影響
- 全てのテストで以下を修正:
  - モデル名の変更
  - フィールド名の変更 (`title` → `description`, `pub_date` → `created_at`)
  - `group`フィールドの追加
  - 関数名の変更

## データベース移行
- 既存の`feed_item`テーブルを削除し、新しい`http_request`テーブルを作成
- 開発段階のため、マイグレーションスクリプトは不要
- `data/datadoggo.db`を削除して`initialize_database()`で再生成