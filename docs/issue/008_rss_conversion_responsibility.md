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
`convert_rss_items_to_http_requests`の責務を`rss_link`モジュール内に移動し、
外部に公開するAPIを`list[Element]`から`list[HttpRequestTask]`に変更する。

**理由**:
- `HttpRequestTask`は`task_queue`配下で汎用的なドメインモデルとなった
- RSS固有の処理が最初から汎用モデルを返す方が自然
- 変換ロジックをRSSドメイン内にカプセル化できる

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
2. `rss_link/`のファイルを`rss/`にコピー
3. `convert_rss_items_to_http_requests`を`rss/service.py`に移植
   - 関数名を`convert_rss_element_to_http_requests`に変更
   - 必要な依存をimport

### Phase 2: facade.pyの更新
4. `fetch_rss_elements_from_query`を`fetch_http_requests_from_query`に変更
   - 内部で`convert_rss_element_to_http_requests`を呼ぶ
   - 返り値を`list[HttpRequestTask]`に変更
5. テストを更新して動作確認

### Phase 3: 呼び出し側の更新
6. `rss`モジュールを使用している箇所を検索
   - `from domain.news.rss_link` → `from domain.news.rss`
   - `fetch_rss_elements_from_query` → `fetch_http_requests_from_query`
7. `convert_rss_items_to_http_requests`の呼び出しを削除
   - 新しいAPIは既に変換済みなので不要

### Phase 4: クリーンアップ
8. `rss_link/`ディレクトリを削除
9. `http_request/service.py`から`convert_rss_items_to_http_requests`を削除
   - 関連テストも削除
10. 全テストを実行して問題ないことを確認

### Phase 5: ドキュメント更新
11. `AGENTS.md`の該当箇所を更新
    - `rss_link` → `rss`
    - 新しい関数シグネチャを反映
12. `docs/design.md`の該当箇所を更新

## 影響範囲

### 変更が必要なファイル
- `src/domain/news/rss_link/` 配下の全ファイル (移動+更新)
- `src/domain/task_queue/http_request/service.py` (関数削除)
- 上記モジュールをimportしている全ファイル
- `AGENTS.md`, `docs/design.md`

### 変更が不要なファイル
- `http_request/model.py` (HttpRequestTaskの定義は変更なし)
- `http_request/command.py`, `search.py` (参照のみ)
- `links.yml` (データ形式は変更なし)

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
