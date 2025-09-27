# RSSリンクメタデータ永続化計画

## 背景
- `save_rss_element_to_bucket` はバケットへの保存しか行っておらず、group/name/url などの由来情報が失われる。
- 保存済みキーから元の RSS ソースや取得タイムスタンプを特定できず、再処理や参照が困難。
- `news/feed` ドメインのようにドメインモデルと永続化テーブルを分離し、CQRS に沿ったメタデータ管理を導入したい。

## 目的
- バケット保存時に RSS メタデータを SQLite (SQLModel) に同時保存し、後段処理で参照できるようにする。
- group/name/url/保存時刻/ステータスを持つドメインモデルを定義し、バケットキーと1対1で追跡可能にする。
- CQRS の原則に沿い、書き込み系(`command`)と読み出し系(`search`)の API を整理する。

## スコープ
- 対象: `src/domain/news/rss_link` 配下（`model.py`、`command.py`、`search.py`、必要に応じて `service.py`/`convert.py` の新設）。
- 再利用: `infra.storage.bucket`, `infra.storage.rds`, `infra.compute` の既存ユーティリティ。
- 非対象: RSS 取得ロジック (`fetch.py`) の並列制御、`links.yml` の構造変更、外部 API 通信仕様の刷新。

## 想定仕様
- テーブル名は `rss_bucket`。主キーはバケットの SHA256 キー (`id`) とする。
- フィールド案: `id`, `group`, `name`, `url`, `status`, `saved_at`, `content_length` (任意)。
- `id` は `save_rss_element_to_bucket` で得られるバケットキーと同一であり、追加の `object_key` や `content_hash` は保持しない。
- ステータスは StrEnum `RssBucketStatus` で管理し、`pending`(旧UNDO), `registered`, `overridden`, `error` を提供する。
- `saved_at` は UTC の timezone-aware datetime を保持し、`create_rss_bucket_item` で自動付与。
- `command` 層はバケット保存とメタデータ保存を一貫処理し、保存失敗時はロールバック/ステータス更新を行う。
- `search` 層は group/name/status/期間でフィルタし、最新順で取得する API を提供する。

## 実装ステップ
1. **モデル定義整備**
   - `model.py` に `RssBucketStatus(StrEnum)`、`RssBucketItem(BaseModel)`、`RssBucketRecord(SQLModel)` を定義。
   - URL バリデーション用に `HttpUrl` を利用し、`status`/`saved_at` のバリデーションを追加。
2. **ユーティリティ分離**
   - `rss_link/convert.py` を新設し、`bucket_to_record` / `record_to_bucket` を実装。
   - `rss_link/service.py` を新設し、`create_rss_bucket_item` やタイムスタンプ生成、重複時のステータス更新ポリシーを記述。
3. **コマンド層拡張**
   - `save_rss_element_to_bucket` を内部ヘルパー化し、公開 API `store_rss_bucket_payload(rss_item, element, status=...)` を追加。
   - バケット保存→メタデータ生成→`session_scope` で upsert → ステータス/タイムスタンプ更新の順で実装。
   - 既存テストを新 API に合わせて更新し、バケット保存単体の低レベル関数も必要に応じて残す。
4. **検索層実装**
   - `search.py` に `find_rss_bucket_by_id` と `search_rss_buckets(query)` を追加し、limit/offset/status/group/name などの条件をサポート。
   - 戻り値は `RssBucketItem` のリスト/単一。既存のバケット read API (`find_rss_content`) との連携を整理。
5. **テスト整備**
   - `model`/`service`/`convert`/`command`/`search` それぞれに最大5ケースでテストを追加。
   - バケット保存とメタデータ保存が同期して行われること、エラー時に status が `error` になることを検証。
   - docs 形式コメントで目的と検証観点を記載。
6. **ドキュメント更新**
   - `docs/design.md` のテーブル定義に `rss_bucket` を追記し、データフロー図を更新。
   - 新 API やステータス遷移の説明を加筆。
7. **検証**
   - `uv run ruff check` → `uv run pyright` → `uv run pytest` を実行し、警告も含めて解消。

## テスト戦略
- モデル: StrEnum の値検証、timezone-aware datetime の確認。
- コマンド: 正常系でバケットキーとレコードが一致し、自動生成フィールドが埋まることを確認。
- 失敗系: バケット保存が失敗した場合に DB 挿入を行わない or `error` に更新することを確認。
- 検索: group/name/status/期間 filter が期待通りに絞り込むこと、limit/offset が動作することを確認。
- リグレッション: 既存の `search_rss_keys`/`find_rss_content` が影響を受けないことを確認する。

## リスク・懸念
- バケット保存と DB upsert の一貫性担保。例外発生時のロールバック戦略を明確にする。
- SHA256 を主キーとするため、将来的にハッシュ方式を変えた場合の互換性に留意。
- ステータス遷移の定義が曖昧なままだと利用側の期待が一致しない可能性。ワークフロー定義を合わせて整理する必要。

## 完了条件
- `RssBucketItem`/`RssBucketRecord`/`RssBucketStatus` が実装され、`rss_bucket` テーブルが初期化される。
- バケット保存 API がメタデータ保存と一貫して動作し、検索 API から参照できる。
- 追加したテストが全て成功し、`ruff`/`pyright`/`pytest` がグリーンである。
- `docs/design.md` に新テーブルとデータフローが明記されている。

## 想定ファイル・シンボル構成
```
src/domain/news/rss_link
├── command.py          # store_rss_bucket_payload, save_rss_element_to_bucket
├── convert.py          # rss_bucket_to_record, record_to_rss_bucket
├── model.py            # RssBucketStatus, RssBucketItem, RssBucketRecord
├── search.py           # find_rss_bucket_by_id, search_rss_buckets, search_rss_keys
├── service.py          # create_rss_bucket_item, ensure_http_url 等
├── fetch.py
├── load.py
└── __init__.py
```
