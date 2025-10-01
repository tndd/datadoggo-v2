# Datadoggo
webからニュース等のを集め、保存・分析を行う。

# アーキテクチャ
```
src
├── core      # ドメインロジック（記事、リンク、RSS処理）
├── infra     # インフラストラクチャ層（DB、API、ファイル操作）
└── workflow  # ビジネスワークフロー
```

## 注意
- テストは `tests/` ディレクトリに分離し、`test_*.py` 形式で実装すること。
- `pip`ではなく`uv`を使用すること。


# データベース設定

- **本番実行時**: 固定パス `sqlite:///data/datadoggo.db`
- **pytest実行時**: 自動的にインメモリDB `sqlite:///:memory:`

環境変数の設定は不要です。
