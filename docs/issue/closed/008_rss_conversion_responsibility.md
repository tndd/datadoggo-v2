# Issue #14: ElementからHttpRequestTaskへの変換責務の移動とrss_linkの改名

## 概要

現在、`ElementからHttpRequestTaskへの変換`は以下のように処理されている:
1. `rss_link`モジュールが`Element`を返す
2. 呼び出し側が`convert_rss_items_to_http_requests`を使って`HttpRequestTask`に変換

この変更では、変換責務を`rss_link`内に移動し、最初から`HttpRequestTask`を返すようにする。
また、より適切なドメイン名として`news/rss`へリネームする。

## 現状分析

### 現在のディレクトリ構造
```
src/domain/
├── news/
│   ├── article/
│   └── rss_link/           # 変更対象
│       ├── facade.py       # fetch_rss_elements_from_query
│       ├── fetch.py        # fetch_rss_element, fetch_rss_from_links
│       ├── model.py        # RssItem, RssItemQuery
│       ├── search.py       # load_rss_links
│       └── links.yml
└── task_queue/
    └── http_request/
        ├── command.py
        ├── model.py        # HttpRequestTask
        ├── search.py
        └── service.py      # convert_rss_items_to_http_requests
```

### 現在の処理フロー
```
RssItemQuery
  → load_rss_links() → list[RssItem]
  → fetch_rss_from_links() → list[Element]
  → convert_rss_items_to_http_requests() → list[HttpRequestTask]
```

### 主要な関数の責務
- `rss_link/search.py::load_rss_links`: links.ymlからRssItemリストを取得
- `rss_link/fetch.py::fetch_rss_element`: URLからRSS XMLを取得してElement化
- `rss_link/fetch.py::fetch_rss_from_links`: 複数RssItemを並列取得
- `rss_link/facade.py::fetch_rss_elements_from_query`: クエリから直接Element取得
- `http_request/service.py::convert_rss_items_to_http_requests`: Element → HttpRequestTask変換

## 変更方針

### 1. 責務の移動
`convert_rss_items_to_http_requests`の責務を`http_request/service.py`から`rss`モジュール内に移動し、
外部に公開するAPIを`list[Element]`から`list[HttpRequestTask]`に変更する。

**理由**:
- `convert_rss_items_to_http_requests`は**RSS固有の変換ロジック**
  - RSS XMLの`item`要素を解析（`link`, `title`, `pubDate`タグ）
  - RSS日付フォーマット（RFC 2822）のパース
  - `channel`構造の理解
- 汎用的な`http_request`モジュールにRSS固有の知識を持たせるべきではない
- RSS取得後に必ず必要な変換なので、RSSドメイン内にカプセル化するのが自然

### 2. ディレクトリ構造の変更
```
src/domain/news/rss_link/ → src/domain/news/rss/
```

**理由**:
- `HttpRequestTask`という具体的な名前が確立したため、
  モジュール名も`rss`とシンプルにする方が収まりが良い

### 3. 関数シグネチャの変更

#### Before (現在)
```python
# rss_link/facade.py
def fetch_rss_elements_from_query(
    query: RssItemQuery,
    *,
    client: HttpsClient | None = None,
    parallel: bool | int = False,
) -> list[Element]:
    ...

# http_request/service.py
def convert_rss_items_to_http_requests(
    root: Element,
    *,
    group: str | None,
    default_status_code: int | None = DEFAULT_HTTP_REQUEST_STATUS_CODE,
) -> list[HttpRequestTask]:
    ...
```

#### After (変更後)
```python
# rss/facade.py
def fetch_http_requests_from_query(
    query: RssItemQuery,
    *,
    client: HttpsClient | None = None,
    parallel: bool | int = False,
) -> list[HttpRequestTask]:
    """RssItemQuery に一致するリンクを取得し HttpRequestTask リストを返す"""
    ...

# rss/service.py (新規)
def convert_rss_element_to_http_requests(
    root: Element,
    *,
    group: str | None,
    default_status_code: int | None = None,
) -> list[HttpRequestTask]:
    """RSSのitem要素をHttpRequestTaskリストに変換する"""
    ...
```

## 実装手順

### Phase 1: 新しい構造の準備
1. `src/domain/news/rss/`ディレクトリを作成
2. `rss_link/`のファイル（`model.py`, `search.py`, `fetch.py`, `facade.py`, `links.yml`）を`rss/`にコピー
3. `rss/service.py`を新規作成し、`http_request/service.py`から以下を移植:
   - `convert_rss_items_to_http_requests` → `convert_rss_element_to_http_requests`に改名
   - RSS解析用ヘルパー関数（`_extract_channel`, `_extract_text`, `_join_itertext`, `_parse_published_at`, `_local_name`）
   - 必要な依存をimport（`Element`, `parse_rss`, `create_http_request`等）
   - テストも移植（`TestMod`クラス）

### Phase 2: facade.pyの更新
4. `rss/facade.py`を更新:
   - `fetch_rss_elements_from_query` → `fetch_http_requests_from_query`に改名
   - `fetch_rss_from_links`で取得した各`Element`に対して`convert_rss_element_to_http_requests`を呼ぶ
   - 返り値を`list[Element]` → `list[HttpRequestTask]`に変更
   - `RssItem`から`group`情報を取得して`convert_rss_element_to_http_requests`に渡す
5. テストを`HttpRequestTask`検証に書き換え:
   - `Element`のタイトル検証 → `HttpRequestTask`の`description`/`url`/`group`検証に変更

### Phase 3: 呼び出し側の更新
6. `rss_link`モジュールを使用している箇所を検索して更新:
   - `from domain.news.rss_link` → `from domain.news.rss`に置換
   - `fetch_rss_elements_from_query` → `fetch_http_requests_from_query`に置換
7. `convert_rss_items_to_http_requests`を使用している箇所を検索:
   - 新しいAPIは既に`HttpRequestTask`を返すため、変換呼び出しを削除
   - `Element`型の変数を`HttpRequestTask`型に変更

### Phase 4: クリーンアップ
8. `rss_link/`ディレクトリを削除
9. `http_request/service.py`から以下を削除:
   - `convert_rss_items_to_http_requests`関数
   - RSS解析用ヘルパー関数（`_extract_channel`, `_extract_text`, `_join_itertext`, `_parse_published_at`, `_local_name`）
   - 関連テスト（`TestMod`内の該当メソッド）
   - 不要なimport（`Element`, `parse_rss`等）
10. 全テストを実行して問題ないことを確認（`just test`）

### Phase 5: ドキュメント更新
11. `AGENTS.md`の該当箇所を更新
    - `rss_link` → `rss`
    - 新しい関数シグネチャを反映
12. `docs/design.md`の該当箇所を更新

## 影響範囲

### 変更が必要なファイル
- `src/domain/news/rss_link/` 配下の全ファイル (→ `rss/`へ移動+更新)
  - `facade.py`: 関数名変更、返り値型変更、内部ロジック変更
  - `model.py`, `search.py`, `fetch.py`, `links.yml`: コピーのみ
- `src/domain/task_queue/http_request/service.py` (RSS関連コード削除)
- `rss_link`をimportしている全ファイル（import文の更新）
- `AGENTS.md`: RSSリンク処理の指針セクション更新
- `docs/design.md`: 該当箇所更新

### 変更が不要なファイル
- `http_request/model.py` (HttpRequestTaskの定義は変更なし)
- `http_request/command.py` (HttpRequestTaskの保存処理は変更なし)
- `http_request/search.py` (HttpRequestTaskの検索処理は変更なし)
- `links.yml` (データ形式は変更なし、移動のみ)

## テスト方針

### 既存テストの移行
1. `rss_link/`配下のテストを`rss/`に移行
2. `fetch_rss_elements_from_query`のテストを`fetch_http_requests_from_query`用に書き換え
   - `Element`の検証 → `HttpRequestTask`の検証に変更
3. `http_request/service.py`の`convert_rss_items_to_http_requests`テストは`rss/service.py`に統合

### 統合テスト
4. クエリ→HttpRequestTask の一貫した変換フローを確認
5. `group`フィールドが正しく伝播されることを確認
6. 並列実行オプションが動作することを確認

## リスク

### 低リスク
- ディレクトリ名の変更は機械的な置換で対応可能
- 既存のテストカバレッジが高いため、デグレを検出しやすい

### 注意点
- `Element`を直接扱っているコードがあれば影響を受ける
  → 現状では`facade.py`の外には公開されていないため問題なし
- importパスの変更漏れに注意
  → 全体検索で確実に置換

## 完了条件

- [ ] `src/domain/news/rss/`ディレクトリが作成され、全ファイルが移動済み
- [ ] `fetch_http_requests_from_query`が`list[HttpRequestTask]`を返す
- [ ] `convert_rss_element_to_http_requests`が`rss/service.py`に実装済み
- [ ] `rss_link`への参照がコードベースから完全に削除
- [ ] `http_request/service.py`の`convert_rss_items_to_http_requests`が削除済み
- [ ] 全テストが成功 (`just test`でpass)
- [ ] `AGENTS.md`と`docs/design.md`が更新済み
