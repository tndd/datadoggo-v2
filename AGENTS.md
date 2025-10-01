# Repository Guidelines

## プロジェクト構成とモジュール
リポジトリの中核コードは `src/` 配下にまとまり、ドメインロジックは `src/domain/`、外部I/Oは `src/infra/`、業務フローは `src/workflow/` に配置されています。テストは専用ディレクトリではなく各モジュール内に `class TestMod:` を設けて共存させ、検証対象ごとにサブクラスやメソッド名で意図を明示します。永続化に必要なデータは `data/`、追加ドキュメントは `docs/` を参照してください。

## ビルド・テスト・開発コマンド
主要タスクは `uv` 経由で実行し、複数ステップのワークフローは `justfile` のターゲットを利用してください。

```bash
just sync               # 依存定義を同期し editable インストール
just test               # lint / 型チェック / pytest をまとめて実行
uv run ruff check       # 単体でスタイル確認したい場合
uv run pyright          # 単体で型チェックしたい場合
uv run pytest           # ユニット／統合テスト（online マーカー除外）
uv run python main.py   # CLI エントリーポイント実行
```

## コーディングスタイルと命名規約
Python は4スペースインデント、型ヒント必須、テキストコメントは日本語で簡潔に残します。命名は「計算系は `get_*`」「DB 複数取得は `search_*`」「単一取得は `find_*`」「API 呼び出しは `fetch_*`」「ファイル読込は `load_*`」を遵守します。不要な関数抽出は避け、短い処理は呼び出し元に留めて可読性を保ってください。

## CQRS 運用規則
- `fetch` レイヤは外部システムとの通信専用とし、ネットワーク呼び出しや解析までを担うがローカル状態を変更しない。
- `command` レイヤは永続化・バケット書き込みなど状態変化を伴う操作を担当し、必要であれば `fetch` の結果を受け取って処理する。
- `search` レイヤは既存データの参照専用であり、DB やバケットなどからの読み出しのみを行い、書き込みは禁止とする。
- 各レイヤのモジュール・関数は命名と責務を一致させ、境界を越える処理が必要な場合は上位層で orchestration する。
- CQRS の区分に沿うテストを用意し、個々のレイヤが担当外の副作用を持たないことを確認する。

## テスト方針
テストは `Tests` モジュール配下で目的と検証観点を docstring に記述し、ケース数は対象ごと最大5件に絞ります。自動化チェックは `ruff`→`pyright`→`pytest` の順で実行し、警告も必ず解消します。外部通信を伴う場合は `@pytest.mark.online` を付け、既定のコマンドでは除外される前提です。
- pytest は `Test*` で始まるクラスのみを収集するため、`class TestMod:` 配下のネストしたクラスも必ず `Test*` 形式で命名する。命名漏れはテスト未実行の原因になるため、リネーム時は関連コメントやdocstringも含めて一貫させること。

## コミットとプルリクエスト
コミットメッセージは日本語で、動詞始まりの短い要約（例: `HTTPレスポンスモデルをPydantic化`）を推奨します。プルリクエストでは概要、検証ログ、関連 Issue を記載し、UI 変更や CLI 出力差分がある場合はスクリーンショットや抜粋を添付します。マージ可能な状態まで lint・テストを通した上でレビューを依頼してください。

## 環境設定とセキュリティ
データベースは実行環境により自動的に切り替わります：
- **本番実行時**: 固定パス `sqlite:///data/datadoggo.db`
- **pytest実行時**: 自動的にインメモリDB `sqlite:///:memory:`

環境変数の設定は不要です。資格情報やトークンは `.env` などの秘匿ファイルに保存し、リポジトリにはコミットしないでください。外部サービスとの通信が必要なテストはオンライン専用マーカーで隔離し、誤って本番エンドポイントへ負荷を掛けないよう注意します。

## データベース更新時の注意
- **テーブル名変更**: `feed_item` → `http_request_queue` に変更。
- **モデル名変更**: `FeedItem` → `HttpRequestTask`, `FeedRecord` → `HttpRequestTaskRecord` に変更。
- **ディレクトリ構造変更**: `src/domain/news/feed/` → `src/domain/task_queue/http_request/` に移動。
  - HTTPリクエスト管理はニュース固有ではないため、汎用的なtask_queue配下に配置。
- **フィールド変更**:
  - `title` → `description` (nullable)
  - `pub_date` 削除 → `created_at` で代替（RSSのpubDateはcreated_atとして保存）
  - `group` フィールド追加（`{source}:{category}` 形式推奨、例: `bbc:world`）
- **関数名変更**:
  - `create_feed` → `create_http_request`
  - `store_feed` → `store_http_request`
  - `find_feed_by_id` → `find_http_request_by_id`
  - `search_feeds` → `search_http_requests`
  - `FeedQuery` → `HttpRequestQuery`
- スキーマ変更を反映する際は、開発環境で `data/datadoggo.db` を削除した上で `initialize_database()` を再実行し、新しいカラム定義でテーブルを作り直す。

## エージェント作業時のヒント
スクリプト実行前に既存プロセスの有無を確認し、依存追加は必ず `uv add` を用いて `pyproject.toml` と `uv.lock` を同期させます。命名リネームを行う場合は、関連コメント・テスト名まで一貫して更新してください。問題調査が必要な場合は英語クエリでウェブ検索し、信頼できるドキュメントを参照した上で実装へ反映します。
依存追加は必ず `uv add` を用い、必要に応じて `just sync` で環境を再構築します。命名リネームを行う場合は、関連コメント・テスト名まで一貫して更新してください。問題調査が必要な場合は英語クエリでウェブ検索し、信頼できるドキュメントを参照した上で実装へ反映します。

## RSSリンク処理の指針
- `src/domain/news/rss_link/search.py` の `load_rss_links` は `RssItemQuery` を受け取り、group/name/path でフィルタしつつ `RssItem` のリストを返す。既定のパスはクエリの `path` デフォルト (`./links.yml`) に従う。
- `src/domain/news/rss_link/fetch.py` の `fetch_rss_from_links` はフィルタ済みの `RssItem` リストを引数に取り、並列オプションを維持したまま `Element` のリストを返す。リンクの絞り込みは呼び出し元で行うこと。
- `src/domain/news/rss_link/service.py` の `fetch_rss_elements_from_query` は `RssItemQuery` からリンクを読み込み、並列オプション付きで RSS ルート要素を一括取得する。通信不要なクエリの場合は空リストを返す。

## Article機能の実装ガイド
- ドメイン構成は `fetch.py`（HTML取得で `Article` を生成）、`command.py`（バケット保存）、`search.py`（`Article` 再構築）のシンプルな三層構成。
- `save_article_content` は `Article` を受け取り、HTMLをバケットに保存。DBへのメタデータ保存は廃止。
- バケットキーは HttpRequestTask のハッシュIDそのものを使用し、保存先は `data/bucket/article/<shard>/` 配下。テストでは `pyfakefs` の `fs` フィクスチャで仮想化する。
- `find_article_by_id` は `HttpRequestTaskRecord` からメタデータを取得し、バケットからHTMLを取得して `Article` を再構築する。`status_code` が200以外の場合は `None` を返す。
- `fetch_article_content` は `HttpRequestTask` を引数に取り、記事HTMLを取得して `Article` を生成する。`description` が `None` の場合は空文字列を使用する。

## docsの更新
issueの更新についてだが、closed下の文書についての更新は不要です。
