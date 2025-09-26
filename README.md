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
- `tests`ディレクトリは使わず、そのファイル内に`test_*`という形でテストを実装すること。
- `pip`ではなく`uv`を使用すること。


# 環境変数の設定
`Feed`テーブルの接続先は環境変数`FEED_DATABASE_URL`で切り替えられる。
未設定時は`sqlite:///data/datadoggo.db`が利用される。

```bash
# 例: テスト時に一時ファイルへ切り替える
FEED_DATABASE_URL=sqlite:///tmp/test-datadoggo.db
```
