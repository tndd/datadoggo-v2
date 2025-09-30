# 概要
現在のFeedはrss feedの要素を格納するということに特化している。
だがそれを、クロールされるurlの進捗管理テーブルとして変更したい。

# テーブル定義

## url_waitlist(仮)

| name        | type     | description                                                              |
| ----------- | -------- | ------------------------------------------------------------------------ |
| id          | str      | urlのhash                                                                |
| url         | str      | urlそのもの                                                              |
| status_code | int?     | http通信のコード。存在しない場合は未実行を意味する                       |
| group       | str      | urlが属するグループ名。これがないとurlが何に由来してるのかの判別が難しく |
| created_at  | timetime | 作成日時。rssの場合はpub_dataをここに入れる予定                          |
| updated_at  | datetime | 更新日時                                                                 |
| description | str      | このurlについての何らかの説明。rssにおけるtitleはここに入れる予定        |

**検討点**
- groupの必要性
  - urlである程度絞り込みができる以上、必須ではないかもしれない