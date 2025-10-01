# 概要
現在のFeedはrss feedの要素を格納するということに特化している。
だがそれを、HTTPリクエストの進捗管理テーブルとして変更したい。

# テーブル定義

## http_request_queue
テーブル名: `http_request_queue`
ドメインモデル名: `HttpRequestTask`
レコードモデル名: `HttpRequestTaskRecord`

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

### モデル・サービス層 (完了)
- [src/domain/task_queue/http_request/model.py](../../../src/domain/task_queue/http_request/model.py)
  - `HttpRequestTask` → `HttpRequestTask` にリネーム
  - `FeedRecord` → `HttpRequestTaskRecord` にリネーム
  - `__tablename__ = "feed_item"` → `"http_request_queue"` に変更
  - `title: str` → `description: str | None` に変更
  - `pub_date: datetime` → 削除 (created_atで代替)
  - `group: str` フィールドを追加
  - ディレクトリ移動: `src/domain/news/feed/` → `src/domain/task_queue/http_request/`

- [src/domain/task_queue/http_request/service.py](../../../src/domain/task_queue/http_request/service.py)
  - `create_feed()` → `create_http_request()` にリネーム
  - 引数: `title` → `description` に変更
  - 引数: `pub_date` → 削除 (`created_at`で代替)
  - 引数: `group` を追加
  - `feed_to_record()`, `record_to_feed()` → `http_request_to_record()`, `record_to_http_request()` にリネーム
  - `convert_rss_items_to_feed_items()` → `convert_rss_items_to_http_requests()` にリネーム
    - RSS取得時に`group`を`f"{rss_item.group}:{rss_item.name}"`形式で設定
    - `pub_date`を`created_at`として使用
    - `title`を`description`として使用

- [src/domain/task_queue/http_request/command.py](../../../src/domain/task_queue/http_request/command.py)
  - `store_feed()` → `store_http_request()` にリネーム
  - 引数: `HttpRequestTask` → `HttpRequestTask` に変更
  - 全テストを更新

- [src/domain/task_queue/http_request/search.py](../../../src/domain/task_queue/http_request/search.py)
  - `FeedQuery` → `HttpRequestQuery` にリネーム
  - クエリフィールド: `title` → `description` に変更
  - クエリフィールド: `pub_date_from`, `pub_date_to` → `created_at_from`, `created_at_to` に変更
  - クエリフィールド: `group` を追加
  - `find_feed_by_id()` → `find_http_request_by_id()` にリネーム
  - `search_feeds()` → `search_http_requests()` にリネーム
  - 全テストを更新

### Article関連 (完了)
- [src/domain/news/article/search.py](../../../src/domain/news/article/search.py)
  - `FeedRecord` → `HttpRequestTaskRecord` に変更
  - フィールド参照: `.title` → `.description` に変更
  - フィールド参照: `.pub_date` → `.created_at` に変更
  - `find_article_by_id()`, `search_articles_by_ids()` の動作確認
  - 全テストを更新

- [src/domain/news/article/fetch.py](../../../src/domain/news/article/fetch.py)
  - `HttpRequestTask` → `HttpRequestTask` に変更
  - フィールド参照: `.title` → `.description` に変更
  - フィールド参照: `.pub_date` → `.created_at` に変更

### ディレクトリ名変更 (完了)
- `src/domain/news/feed/` → `src/domain/task_queue/http_request/` に移動完了
  - HTTPリクエスト管理はニュース固有の機能ではないため、汎用的なtask_queueドメイン配下に配置
  - インポートパスの変更に伴い、Article層も更新済み

## テストの影響
- 全てのテストで以下を修正:
  - モデル名の変更
  - フィールド名の変更 (`title` → `description`, `pub_date` → `created_at`)
  - `group`フィールドの追加
  - 関数名の変更

## データベース移行
- 既存の`feed_item`テーブルを削除し、新しい`http_request_queue`テーブルを作成
- 開発段階のため、マイグレーションスクリプトは不要
- `data/datadoggo.db`を削除して`initialize_database()`で再生成

# 実装Phase

各Phaseごとに実装→テスト→検証のサイクルを回し、段階的に進めます。

## Phase 1: モデル層の変更 (task_queue/http_request/model.py) ✅
**実装内容**:
- `HttpRequestTask` → `HttpRequestTask` にリネーム
- `FeedRecord` → `HttpRequestTaskRecord` にリネーム
- `__tablename__` を `"http_request_queue"` に変更
- フィールド変更:
  - `title: str` → `description: str | None`
  - `pub_date: datetime` 削除
  - `group: str` 追加
- テスト修正 (同ファイル内の `TestMod`)
- ディレクトリ移動: `src/domain/news/feed/` → `src/domain/task_queue/http_request/`

**検証**: `pytest src/domain/task_queue/http_request/model.py -v` ✅

---

## Phase 2: サービス層の変更 (task_queue/http_request/service.py) ✅
**実装内容**:
- `create_feed()` → `create_http_request()` にリネーム
  - 引数: `title` → `description`
  - 引数: `pub_date` 削除、`created_at` で代替
  - 引数: `group` 追加
- `feed_to_record()` → `http_request_to_record()` にリネーム
- `record_to_feed()` → `record_to_http_request()` にリネーム
- `convert_rss_items_to_feed_items()` → `convert_rss_items_to_http_requests()` にリネーム
  - RSS変換ロジック修正:
    - `pub_date` を `created_at` として使用
    - `title` を `description` として使用
    - `group` パラメータ追加 (RSSソース識別用)
- テスト修正 (同ファイル内の `TestMod` 5テスト)

**検証**: `pytest src/domain/task_queue/http_request/service.py -v` ✅

---

## Phase 3: コマンド層の変更 (task_queue/http_request/command.py) ✅
**実装内容**:
- `store_feed()` → `store_http_request()` にリネーム
- 引数: `HttpRequestTask` → `HttpRequestTask`
- インポート修正
- テスト修正 (同ファイル内の `TestMod` 1テスト)

**検証**: `pytest src/domain/task_queue/http_request/command.py -v` ✅

---

## Phase 4: 検索層の変更 (task_queue/http_request/search.py) ✅
**実装内容**:
- `FeedQuery` → `HttpRequestQuery` にリネーム
  - フィールド: `title` → `description`
  - フィールド: `pub_date_from`, `pub_date_to` → `created_at_from`, `created_at_to`
  - フィールド: `group` 追加
- `find_feed_by_id()` → `find_http_request_by_id()` にリネーム
- `search_feeds()` → `search_http_requests()` にリネーム
- テスト修正 (同ファイル内の `TestMod` 3テスト)

**検証**: `pytest src/domain/task_queue/http_request/search.py -v` ✅

---

## Phase 5: Article検索層の修正 (article/search.py) ✅
**実装内容**:
- インポート: `FeedRecord` → `HttpRequestTaskRecord`
- インポートパス: `src.domain.news.feed` → `src.domain.task_queue.http_request`
- フィールド参照:
  - `.title` → `.description` (38, 88行目)
  - `.pub_date` → `.created_at` (39, 89行目)
- テスト修正 (同ファイル内の `TestMod` 5テスト)

**検証**: `pytest src/domain/news/article/search.py -v` ✅

---

## Phase 6: Article取得層の修正 (article/fetch.py) ✅
**実装内容**:
- インポート: `HttpRequestTask` → `HttpRequestTask`
- インポートパス: `src.domain.news.feed` → `src.domain.task_queue.http_request`
- フィールド参照:
  - `.title` → `.description` (45行目)
  - `.pub_date` → `.created_at` (46行目)
- テスト修正 (同ファイル内の `TestMod` 2テスト)

**検証**: `pytest src/domain/news/article/fetch.py -v` ✅

---

## Phase 7: 統合テスト ✅
**実装内容**:
- 全テスト実行
- ruff check
- pyright検証

**検証**:
```bash
pytest src/domain/news/ -v
ruff check src/
pyright src/
```
**結果**: 全テストパス、Lint/型チェックも問題なし ✅

---

## Phase 8: ドキュメント更新 ✅
**実装内容**:
- AGENTS.md に変更内容を反映
- 変更されたAPI、モデル名、テーブル名、ディレクトリ構造を記録
- issue doc 007 の実装状況を更新

---

## 各Phase実行時の注意点
1. **Phase完了ごとに必ずテスト実行**
2. **エラーが出たら次のPhaseに進まない**
3. **conftest.pyの`initialize_test_db`により、各テストで自動的に新スキーマが適用される**
4. **本番DB (`data/datadoggo.db`) は手動削除が必要** (開発段階のため)
