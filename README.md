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
- `tests`ディレクトリは使わず、そのファイル内に`test_*`という形でテストを実装してる。


# 環境変数の設定
このプロジェクトは**環境変数でのテスト・本番切り替え**の仕組みがある。
`.env`ファイルには以下の設定が必要。

```bash
DATABASE_URL=postgresql://datadoggo:datadoggo@localhost:16432/datadoggo_test
DATABASE_URL_PROD=postgresql://datadoggo:datadoggo@localhost:15432/datadoggo
```
