# domain

## news

### rss

- model
    - RssLink # 改名されてる
- search
    - LoadRssLinkQuery
    - load_rss_links(q: LoadRssLinkQuery) → List[RssLink]
- fetch
    - fetch_elements(rss_link: RssLink) → Element
    - parse_element_to_request_tasks(e: Element) → List[RequestTask]
- service
    - ExecuteRssLinkQuery
    - execute_rss_links()

### gogole_rss

WIP

### article

- model
    - Article
- store
    - store_article()
- search
    - SearchArticleQuery
    - search_articles(q: SearchArticleQuery)
- fetch
    - fetch_article(r: RequestTask, cli: RequestClient) # 特殊用途。原則的には `execute_backlog_request_tasks()`で一括処理する。
- service
    - execute_fetch_and_store_backlog_articles() # `execute_backlog_request_tasks()`のarticleのみにいて部分的な実行を行う

# infra

- config
    - get_worker_num() #ここは関数ではなく定数でいいかもしれん
- logger

## web

- client
    - RequestClient
- queue
    - model
        - RequestTask
    - store
        - store_request_task()
    - search
        - SearchRequestTaskQuery
        - search_request_task(q: SearchRequestTaskQuery)
    - service
        - ExecuteBacklogRequestTaskQuery # groupやタイムスタンプなど、RequestTaskQueryよりもさらに制限された内容のクエリ
        - execute_backlog_request_tasks(q: ExecuteBacklogRequestTaskQuery)

## storage

### bucket

- store_bucket(payload: str, bucket_name: str, key: str)
- find_bucket(bucket_name: str, key: str)

### file

- load_file(path)

### rds

WIP: 最小限のみ残す

備考:

- computeにおけるhashや圧縮はわざわざ関数化せずその場で呼べばいい。
- generateもfileが直接持てばいい