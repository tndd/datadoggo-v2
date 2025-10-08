# 009+ 大規模リファクタリング詳細仕様

## 概要

コードベース全体を再編成し、無駄を削減して責務を明確化する。

## 基本方針

1. **一行関数の削除**: 薄いラッパー関数は削除し、標準ライブラリを直接呼び出す
2. **命名の統一**: command.py → store.py など、一貫した命名規則を適用
3. **責務の明確化**: infraはインフラ、domainはビジネスロジックに集中
4. **トランザクション抽象化**: RDS操作の共通パターンを関数化

---

## Phase 1: infra層の整理

### 1.1 infra/compute.py の削除

**削除する関数**:
- `hash_text_sha256(value: str) -> str`
- `compress_text_to_zstd(...)`
- `decompress_zstd_to_text(...)`
- `compress_bytes_to_zstd(...)`
- `decompress_zstd_to_bytes(...)`

**移行方法**:
```python
# 変更前
from infra.compute import hash_text_sha256
request_id = hash_text_sha256(url)

# 変更後
import hashlib
request_id = hashlib.sha256(url.encode("utf-8")).hexdigest()
```

```python
# 変更前
from infra.compute import compress_text_to_zstd, decompress_zstd_to_text
compressed = compress_text_to_zstd(text, level=3)
restored = decompress_zstd_to_text(compressed)

# 変更後
import zstandard as zstd
compressor = zstd.ZstdCompressor(level=3)
compressed = compressor.compress(text.encode("utf-8"))
decompressor = zstd.ZstdDecompressor()
restored = decompressor.decompress(compressed).decode("utf-8")
```

**影響ファイル**:
- `src/infra/storage/bucket.py`
- `src/domain/news/task_queue/http_request/common.py` (後でinfra/web/queue/common.pyに移動)

---

### 1.2 infra/generate.py の削除

**削除する関数**:
- `generate_timestamp() -> str`
- `generate_timestamped_filename(...)`
- `generate_timestamped_key(...)`

**移行方法**:
```python
# 変更前
from infra.generate import generate_timestamp
timestamp = generate_timestamp()

# 変更後
from datetime import datetime
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
```

**影響ファイル**:
- `src/infra/storage/bucket.py` (1箇所のみ)

---

### 1.3 infra/app_log.py → infra/logger.py へリネーム

**変更内容**:
- ファイル名変更: `app_log.py` → `logger.py`
- 関数名変更: `get_logger()` → そのまま (名前は適切)

**影響ファイル**: 全域 (import文の変更)

---

### 1.4 infra/runtime.py → infra/config.py へリネーム

**変更内容**:
- ファイル名変更: `runtime.py` → `config.py`
- 関数名変更: `get_worker_count()` → `get_worker_num()`

**オプション**: 関数ではなく定数でも良い
```python
# 案1: 関数 (現状維持)
def get_worker_num(parallel: bool | int = False) -> int:
    ...

# 案2: 定数 (シンプル)
DEFAULT_WORKER_NUM = 4
```

**推奨**: 関数を維持 (parallel引数の動的処理が有用)

---

### 1.5 infra/storage/rds.py にトランザクションラッパーを追加

**追加する関数**:

```python
from typing import TypeVar
from sqlmodel import SQLModel

T = TypeVar('T', bound=SQLModel)

def save_record(record: T, *, engine: Engine | None = None) -> T:
    """SQLModelレコードを保存し、最新状態を返す

    - session.merge でupsert
    - flush + refresh で最新状態を取得
    - トランザクション管理を自動化

    Args:
        record: 保存するSQLModelレコード
        engine: 使用するエンジン (Noneの場合はデフォルト)

    Returns:
        保存後の最新状態のレコード
    """
    with session_scope(engine) as session:
        merged = session.merge(record)
        session.flush()
        session.refresh(merged)
        return merged


def save_records(records: list[T], *, engine: Engine | None = None) -> list[T]:
    """複数のSQLModelレコードを一括保存し、最新状態のリストを返す

    Args:
        records: 保存するSQLModelレコードのリスト
        engine: 使用するエンジン (Noneの場合はデフォルト)

    Returns:
        保存後の最新状態のレコードリスト
    """
    if not records:
        return []

    with session_scope(engine) as session:
        results: list[T] = []
        for record in records:
            merged = session.merge(record)
            session.flush()
            session.refresh(merged)
            results.append(merged)
        return results
```

**テスト追加**:
```python
class TestMod:
    def test_save_record_saves_and_returns_refreshed(self) -> None:
        """
        docs:
            目的: save_record が正しく保存し最新状態を返すことを確認する。
            検証観点:
                - レコードがDBに保存される
                - 返り値が最新状態 (flush + refresh 済み)
        """
        ...

    def test_save_records_saves_multiple_records(self) -> None:
        """
        docs:
            目的: save_records が複数レコードを一括保存できることを確認する。
            検証観点:
                - 全レコードが保存される
                - トランザクションが共有される
        """
        ...
```

---

### 1.6 infra/storage/bucket.py の関数名変更

**変更内容**:
- `save_object()` → そのまま (適切)
- `load_object()` → そのまま (適切)
- `load_objects()` → そのまま (適切)
- `search_object_keys()` → そのまま (適切)

**備考**: 現在の命名は既に適切なため変更不要

---

### 1.7 infra/storage/file.py の関数名確認

**現状の関数** (確認のみ、変更不要):
- `load_bytes(path)` → そのまま
- `save_bytes_to_file(data, path)` → そのまま
- その他のユーティリティ → そのまま

---

### 1.8 infra/web/https.py → infra/web/client.py へリネーム

**変更内容**:
- ファイル名変更: `https.py` → `client.py`
- クラス名変更: `HttpsClient` → `RequestClient`
- その他のクラス・定数はそのまま: `HttpResponse`, `HTTP_STATUS_OK` など

**影響ファイル**: 全域 (import文の変更)

---

### 1.9 infra/web/queue/ の新規作成 (http_requestからの移行)

**ディレクトリ構成**:
```
infra/web/queue/
  ├── model.py          # RequestTask, RequestTaskRecord
  ├── store.py          # store_request_task, store_request_tasks
  ├── search.py         # find_request_task_by_id, search_request_tasks
  ├── common.py         # create_request_task, 変換関数
  └── service.py        # execute_backlog_request_tasks
```

**変更内容**:

#### model.py
```python
"""RequestTaskドメインモデル群"""

from datetime import datetime
from pydantic import BaseModel, HttpUrl, field_validator
from sqlmodel import Field as SQLField, SQLModel

SUCCESS_STATUS_CODE = 200
_EXPECTED_GROUP_PARTS = 2


def validate_group_format(value: str | None) -> str | None:
    """groupフィールドの形式を検証する

    形式: "{source}:{category}" (例: "bbc:world")

    groupは任意の分類識別子。HTTP取得タスクをソース別・カテゴリ別に
    管理するための汎用項目。前後の空白や空の要素は不正として扱う。
    正規化は行わない。

    Args:
        value: 検証対象のgroup値

    Returns:
        検証済みのgroup値

    Raises:
        ValueError: groupが"{source}:{category}"形式でない場合
    """
    if value is None:
        return None

    error_msg = (
        f"groupは'{{source}}:{{category}}'形式である必要があります "
        f"(例: 'bbc:world'): {value}"
    )

    if value != value.strip():
        raise ValueError(error_msg)

    if ":" not in value:
        raise ValueError(error_msg)

    parts = value.split(":")
    if len(parts) != _EXPECTED_GROUP_PARTS:
        raise ValueError(error_msg)

    if not all(part and part == part.strip() for part in parts):
        raise ValueError(error_msg)

    return value


class RequestTask(BaseModel):
    """request_task_queueテーブルの要素を表すドメインモデル

    Attributes:
        id: URLのSHA256ハッシュ
        url: 取得対象のURL
        description: タスクの説明 (記事タイトルなど)
        group: 任意の分類識別子。形式は "{source}:{category}" (例: "bbc:world")。
               HTTP取得タスクをソース別・カテゴリ別に管理するための汎用項目。
               分類不能な場合はNoneも許容。
        status_code: HTTPステータスコード (未実行時はNone)
        created_at: タスク作成日時
        updated_at: タスク更新日時
    """

    id: str
    url: HttpUrl
    description: str | None
    group: str | None
    status_code: int | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("group")
    @classmethod
    def _validate_group(cls, value: str | None) -> str | None:
        """groupフィールドの形式を検証"""
        return validate_group_format(value)

    def is_success(self) -> bool:
        """成功通信を表す"""
        return self.status_code == SUCCESS_STATUS_CODE

    def is_backlog(self) -> bool:
        """通信未実行または通信失敗を表す"""
        return not self.is_success()


class RequestTaskRecord(SQLModel, table=True):
    """SQLModelによるrequest_task_queueテーブル定義"""

    __tablename__: str = "request_task_queue"

    id: str = SQLField(primary_key=True, index=True)
    url: str = SQLField(nullable=False)
    description: str | None = SQLField(default=None, nullable=True)
    group: str | None = SQLField(default=None, nullable=True)
    status_code: int | None = SQLField(default=None, nullable=True)
    created_at: datetime = SQLField(nullable=False)
    updated_at: datetime = SQLField(nullable=False)
```

#### common.py
```python
"""RequestTask向け共通サービスユーティリティ"""

from datetime import datetime
import hashlib
from pydantic import HttpUrl, TypeAdapter

from .model import RequestTask, RequestTaskRecord

_HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)


def ensure_http_url(value: str | HttpUrl) -> HttpUrl:
    """文字列やHttpUrlを受け取りHttpUrlとして正規化する"""
    return _HTTP_URL_ADAPTER.validate_python(value)


def ensure_saved_at(value: datetime | None = None) -> datetime:
    """保存日時をUTCのtimezone-aware datetimeに整形する"""
    from datetime import timezone

    target = value or datetime.now(timezone.utc)
    if target.tzinfo is None:
        return target.replace(tzinfo=timezone.utc)
    return target.astimezone(timezone.utc)


def create_request_task(
    *,
    url: str,
    description: str | None,
    group: str | None,
    status_code: int | None,
    created_at: datetime | None = None,
) -> RequestTask:
    """入力値からRequestTaskドメインモデルを生成する"""

    request_id = hashlib.sha256(url.encode("utf-8")).hexdigest()
    normalized_created_at = ensure_saved_at(created_at)
    normalized_updated_at = normalized_created_at

    return RequestTask(
        id=request_id,
        url=ensure_http_url(url),
        description=description,
        group=group,
        status_code=status_code,
        created_at=normalized_created_at,
        updated_at=normalized_updated_at,
    )


def request_task_to_record(task: RequestTask) -> RequestTaskRecord:
    """RequestTaskドメインモデルを永続化レコードへ変換する"""

    return RequestTaskRecord(
        id=task.id,
        url=str(task.url),
        description=task.description,
        group=task.group,
        status_code=task.status_code,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def record_to_request_task(record: RequestTaskRecord) -> RequestTask:
    """永続化レコードをRequestTaskドメインモデルに変換する"""

    return RequestTask(
        id=record.id,
        url=ensure_http_url(record.url),
        description=record.description,
        group=record.group,
        status_code=record.status_code,
        created_at=ensure_saved_at(record.created_at),
        updated_at=ensure_saved_at(record.updated_at),
    )
```

#### store.py
```python
"""RequestTaskをrequest_task_queueテーブルへ書き込む処理"""

from infra.storage.rds import save_record, save_records

from .common import (
    ensure_saved_at,
    record_to_request_task,
    request_task_to_record,
)
from .model import RequestTask


def store_request_task(task: RequestTask) -> RequestTask:
    """RequestTaskを保存し、保存後の状態を返す"""

    normalized = task.model_copy(update={"updated_at": ensure_saved_at()})
    record = request_task_to_record(normalized)
    saved_record = save_record(record)
    return record_to_request_task(saved_record)


def store_request_tasks(tasks: list[RequestTask]) -> list[RequestTask]:
    """複数のRequestTaskを一括保存し、保存後の状態を返す"""

    if not tasks:
        return []

    normalized_tasks = [
        task.model_copy(update={"updated_at": ensure_saved_at()})
        for task in tasks
    ]
    records = [request_task_to_record(task) for task in normalized_tasks]
    saved_records = save_records(records)
    return [record_to_request_task(record) for record in saved_records]
```

#### search.py
```python
"""RequestTaskをrequest_task_queueテーブルから読み出す処理"""

from datetime import datetime
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlmodel import select

from infra.storage.rds import session_scope

from .common import record_to_request_task
from .model import RequestTask, RequestTaskRecord


class SearchRequestTaskQuery(BaseModel):
    """RequestTask検索時の条件入力モデル"""

    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    description: str | None = None
    url: str | None = None
    group: str | None = None
    status_code: int | None = None
    created_at_from: datetime | None = None
    created_at_to: datetime | None = None


def find_request_task_by_id(task_id: str) -> RequestTask | None:
    """IDでRequestTaskを検索し、存在すれば返す"""

    with session_scope() as session:
        statement = select(RequestTaskRecord).where(
            RequestTaskRecord.id == task_id
        )
        record = session.exec(statement).first()
        if record is None:
            return None

        return record_to_request_task(record)


def search_request_tasks(query: SearchRequestTaskQuery) -> list[RequestTask]:
    """RequestTaskをページングして取得する"""

    with session_scope() as session:
        statement = select(RequestTaskRecord)

        if query.description:
            statement = statement.where(
                RequestTaskRecord.description.contains(query.description)  # type: ignore[attr-defined]
            )

        if query.url:
            statement = statement.where(RequestTaskRecord.url == query.url)

        if query.group:
            statement = statement.where(
                RequestTaskRecord.group.contains(query.group)  # type: ignore[attr-defined]
            )

        if query.status_code is not None:
            statement = statement.where(
                RequestTaskRecord.status_code == query.status_code
            )

        if query.created_at_from is not None:
            statement = statement.where(
                RequestTaskRecord.created_at >= query.created_at_from
            )

        if query.created_at_to is not None:
            statement = statement.where(
                RequestTaskRecord.created_at <= query.created_at_to
            )

        statement = (
            statement.order_by(desc(RequestTaskRecord.created_at))  # type: ignore[arg-type]
            .offset(query.offset)
            .limit(query.limit)
        )
        records = session.exec(statement).all()
        return [record_to_request_task(item) for item in records]
```

#### service.py
```python
"""RequestTaskキューのサービス層処理"""

from datetime import datetime
from pydantic import BaseModel, Field

from infra.logger import get_logger
from infra.web.client import RequestClient, HTTP_STATUS_OK

from .search import search_request_tasks, SearchRequestTaskQuery
from .store import store_request_task
from .model import RequestTask

_log = get_logger()


class ExecuteBacklogRequestTaskQuery(BaseModel):
    """バックログタスク実行時の条件入力モデル"""

    group: str | None = None
    limit: int = Field(default=100, ge=1, le=500)
    created_at_from: datetime | None = None
    created_at_to: datetime | None = None


def execute_backlog_request_tasks(
    query: ExecuteBacklogRequestTaskQuery,
    *,
    client: RequestClient | None = None,
) -> list[RequestTask]:
    """バックログ（未実行or失敗）のRequestTaskを実行し、結果を更新する

    Args:
        query: 実行対象を絞り込むクエリ
        client: HTTPクライアント (Noneの場合はデフォルト)

    Returns:
        実行したRequestTaskのリスト (status_code更新済み)
    """

    http_client = client or RequestClient()

    # バックログタスクを検索
    search_query = SearchRequestTaskQuery(
        group=query.group,
        limit=query.limit,
        created_at_from=query.created_at_from,
        created_at_to=query.created_at_to,
        status_code=None,  # 未実行のみ
    )

    backlog_tasks = search_request_tasks(search_query)

    if not backlog_tasks:
        _log.info("バックログタスクが見つかりませんでした", query=query.model_dump())
        return []

    _log.info(
        "バックログタスクの実行を開始します",
        count=len(backlog_tasks),
        query=query.model_dump(),
    )

    executed_tasks: list[RequestTask] = []

    for task in backlog_tasks:
        try:
            response = http_client.get(str(task.url))
            updated_task = task.model_copy(
                update={"status_code": response.status_code}
            )
            saved_task = store_request_task(updated_task)
            executed_tasks.append(saved_task)

            _log.info(
                "RequestTaskを実行しました",
                task_id=task.id,
                url=str(task.url),
                status_code=response.status_code,
            )
        except Exception as error:
            _log.exception(
                "RequestTask実行中に例外が発生しました",
                task_id=task.id,
                url=str(task.url),
                error=str(error),
            )
            continue

    _log.info(
        "バックログタスクの実行が完了しました",
        total=len(backlog_tasks),
        executed=len(executed_tasks),
    )

    return executed_tasks
```

---

## Phase 2: domain/news層の整理

### 2.1 domain/news/common.py の削除

**削除する関数**:
- `ensure_http_url()` → `infra/web/queue/common.py` へ移動済み
- `ensure_saved_at()` → `infra/web/queue/common.py` へ移動済み

**備考**: これらの関数はnews固有ではなく、web全般で使用されるためinfra層へ移動

---

### 2.2 domain/news/task_queue/http_request/ の削除

**移行先**: `infra/web/queue/` (Phase 1.9で完了)

**削除ファイル**:
- `command.py`
- `common.py`
- `model.py`
- `search.py`

---

### 2.3 domain/news/rss/ の整理

**ディレクトリ構成**:
```
domain/news/rss/
  ├── model.py          # RssLink (RssItemからリネーム)
  ├── search.py         # load_rss_links
  ├── fetch.py          # fetch_rss_element, parse_element_to_request_tasks
  └── service.py        # execute_rss_links
```

**変更内容**:

#### model.py
```python
"""RSSリンクドメインモデル"""

from pydantic import BaseModel


class RssLink(BaseModel):
    """RSSフィードのリンク情報

    Attributes:
        group: RSS配信元のグループ (例: "bbc", "cnn")
        name: フィード名 (例: "world", "business")
        url: RSSフィードのURL
    """

    group: str
    name: str
    url: str
```

#### search.py
```python
"""RSSリンクの検索・読み込み"""

from pathlib import Path
from pydantic import BaseModel
import yaml

from infra.storage.file import load_bytes

from .model import RssLink


class LoadRssLinkQuery(BaseModel):
    """RSSリンク読み込み時の条件入力モデル"""

    group: str | None = None
    path: str = "data/rss_links.yml"


def load_rss_links(query: LoadRssLinkQuery) -> list[RssLink]:
    """YAMLファイルからRSSリンクを読み込む

    Args:
        query: 検索条件 (groupで絞り込み可能)

    Returns:
        RssLinkのリスト
    """

    content = load_bytes(query.path)
    if not content:
        return []

    data = yaml.safe_load(content)
    if not isinstance(data, dict):
        return []

    links: list[RssLink] = []

    for group, feeds in data.items():
        if query.group and group != query.group:
            continue

        if not isinstance(feeds, dict):
            continue

        for name, url in feeds.items():
            links.append(RssLink(group=group, name=name, url=url))

    return links
```

#### fetch.py
```python
"""RSS取得とパース処理"""

from xml.etree.ElementTree import Element
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from infra.logger import get_logger
from infra.parse.rss import parse_rss
from infra.web.client import RequestClient, HTTP_STATUS_OK
from infra.web.queue.common import create_request_task
from infra.web.queue.model import RequestTask

from .model import RssLink

_log = get_logger()

DEFAULT_REQUEST_STATUS_CODE = None


def fetch_rss_element(
    link: RssLink,
    *,
    client: RequestClient | None = None,
) -> Element:
    """RSSリンクからXMLルート要素を取得する

    Args:
        link: RSSリンク情報
        client: HTTPクライアント (Noneの場合はデフォルト)

    Returns:
        RSSのXMLルート要素

    Raises:
        RuntimeError: 取得に失敗した場合
    """

    http_client = client or RequestClient()
    response = http_client.get(link.url)

    if response.status_code != HTTP_STATUS_OK:
        raise RuntimeError(
            f"RSS取得に失敗しました: status={response.status_code}"
        )

    return parse_rss(response.body)


def parse_element_to_request_tasks(
    element: Element,
    *,
    group: str | None,
    default_status_code: int | None = DEFAULT_REQUEST_STATUS_CODE,
) -> list[RequestTask]:
    """RSS Element をパースして RequestTask リストを生成する

    Args:
        element: RSSのXMLルート要素
        group: 分類グループ (例: "bbc:world")
        default_status_code: デフォルトのステータスコード

    Returns:
        RequestTaskのリスト
    """

    channel = _extract_channel(element)
    request_tasks: list[RequestTask] = []

    for item in channel.findall("item"):
        link = _extract_text(item, "link")
        title = _extract_text(item, "title")
        published_at_text = _extract_text(item, "pubDate")

        if not link or not title or not published_at_text:
            continue

        published_at = _parse_published_at(published_at_text)
        if published_at is None:
            continue

        try:
            request_tasks.append(
                create_request_task(
                    url=link,
                    description=title,
                    group=group,
                    status_code=default_status_code,
                    created_at=published_at,
                )
            )
        except (ValueError, Exception) as exc:
            _log.warning(
                "不正なRequestTaskアイテムをスキップしました",
                rss_group=group,
                request_url=link,
                error_type=type(exc).__name__,
                exception_message=str(exc),
                description=title,
            )
            continue

    return request_tasks


def _extract_channel(root: Element) -> Element:
    """RSSルートまたはchannel要素を返す"""

    local_name = root.tag.split("}", 1)[1] if "}" in root.tag else root.tag
    if local_name == "rss":
        channel = root.find("channel")
        if channel is None:
            raise ValueError("RSSにchannel要素が存在しません")
        return channel

    if local_name == "channel":
        return root

    raise ValueError("RSSルートにchannel要素が存在しません")


def _extract_text(parent: Element, tag: str) -> str | None:
    """指定タグのテキストを抽出し前後の空白を除去する"""

    child = parent.find(tag)
    if child is None:
        return None

    text = "".join(part for part in child.itertext() if part)
    stripped = text.strip()
    if not stripped:
        return None
    return stripped


def _parse_published_at(value: str) -> datetime | None:
    """RSS日付文字列をUTCのdatetimeに変換する"""

    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None

    if parsed is None:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)
```

#### service.py
```python
"""RSSリンク実行サービス"""

from pydantic import BaseModel

from infra.logger import get_logger
from infra.web.client import RequestClient
from infra.web.queue.model import RequestTask
from infra.web.queue.store import store_request_tasks

from .search import load_rss_links, LoadRssLinkQuery
from .fetch import fetch_rss_element, parse_element_to_request_tasks

_log = get_logger()


class ExecuteRssLinkQuery(BaseModel):
    """RSSリンク実行時の条件入力モデル"""

    group: str | None = None
    path: str = "data/rss_links.yml"


def execute_rss_links(
    query: ExecuteRssLinkQuery,
    *,
    client: RequestClient | None = None,
) -> list[RequestTask]:
    """RSSリンクを実行し、RequestTaskを生成・保存する

    Args:
        query: 実行対象を絞り込むクエリ
        client: HTTPクライアント (Noneの場合はデフォルト)

    Returns:
        生成・保存されたRequestTaskのリスト
    """

    http_client = client or RequestClient()

    # RSSリンクを読み込み
    load_query = LoadRssLinkQuery(group=query.group, path=query.path)
    rss_links = load_rss_links(load_query)

    if not rss_links:
        _log.info("RSSリンクが見つかりませんでした", query=query.model_dump())
        return []

    _log.info(
        "RSSリンクの実行を開始します",
        count=len(rss_links),
        query=query.model_dump(),
    )

    all_request_tasks: list[RequestTask] = []

    for link in rss_links:
        try:
            element = fetch_rss_element(link, client=http_client)
            group = f"{link.group}:{link.name}"
            request_tasks = parse_element_to_request_tasks(element, group=group)
            all_request_tasks.extend(request_tasks)

            _log.info(
                "RSSリンクからRequestTaskを生成しました",
                link_group=link.group,
                link_name=link.name,
                task_count=len(request_tasks),
            )
        except Exception as error:
            _log.exception(
                "RSSリンク実行中に例外が発生しました",
                link_group=link.group,
                link_name=link.name,
                url=link.url,
                error=str(error),
            )
            continue

    # 一括保存
    saved_tasks = store_request_tasks(all_request_tasks)

    _log.info(
        "RSSリンクの実行が完了しました",
        total_links=len(rss_links),
        total_tasks=len(saved_tasks),
    )

    return saved_tasks
```

---

### 2.4 domain/news/article/ の整理

**ディレクトリ構成**:
```
domain/news/article/
  ├── model.py          # Article
  ├── store.py          # store_article (command.pyからリネーム)
  ├── search.py         # search_articles
  ├── fetch.py          # fetch_article
  └── service.py        # execute_fetch_and_store_backlog_articles
```

**変更内容**:

#### command.py → store.py へリネーム
```python
"""Articleコンテンツの保存処理"""

from infra.storage.bucket import save_object

from .model import Article

BUCKET_NAME = "article"


def store_article(article: Article) -> str:
    """記事のHTMLコンテンツをバケットに保存する

    Args:
        article: 保存するArticle

    Returns:
        保存されたオブジェクトキー

    Raises:
        RuntimeError: 保存に失敗した場合
    """

    saved_key = save_object(
        payload=article.content,
        bucket_name=BUCKET_NAME,
        object_key=article.id,
    )
    if not saved_key:
        msg = f"記事HTMLの保存に失敗しました: article_id={article.id}"
        raise RuntimeError(msg)

    return saved_key
```

#### service.py (新規作成)
```python
"""Article取得・保存サービス"""

from pydantic import BaseModel, Field

from infra.logger import get_logger
from infra.web.client import RequestClient
from infra.web.queue.search import search_request_tasks, SearchRequestTaskQuery
from infra.web.queue.store import store_request_task
from infra.web.queue.model import RequestTask

from .fetch import fetch_article
from .store import store_article
from .model import Article

_log = get_logger()


class ExecuteFetchAndStoreBacklogArticleQuery(BaseModel):
    """バックログArticle取得・保存時の条件入力モデル"""

    group: str | None = None
    limit: int = Field(default=100, ge=1, le=500)


def execute_fetch_and_store_backlog_articles(
    query: ExecuteFetchAndStoreBacklogArticleQuery,
    *,
    client: RequestClient | None = None,
) -> list[Article]:
    """バックログRequestTaskからArticleを取得・保存する

    execute_backlog_request_tasks()のarticleドメイン特化版。
    RequestTaskの実行に加えて、Article取得・バケット保存まで行う。

    Args:
        query: 実行対象を絞り込むクエリ
        client: HTTPクライアント (Noneの場合はデフォルト)

    Returns:
        取得・保存されたArticleのリスト
    """

    http_client = client or RequestClient()

    # バックログタスクを検索
    search_query = SearchRequestTaskQuery(
        group=query.group,
        limit=query.limit,
        status_code=None,  # 未実行のみ
    )

    backlog_tasks = search_request_tasks(search_query)

    if not backlog_tasks:
        _log.info(
            "バックログArticleタスクが見つかりませんでした",
            query=query.model_dump(),
        )
        return []

    _log.info(
        "バックログArticleタスクの実行を開始します",
        count=len(backlog_tasks),
        query=query.model_dump(),
    )

    fetched_articles: list[Article] = []

    for task in backlog_tasks:
        # Article取得
        article = fetch_article(task, client=http_client)

        if article is None:
            # 取得失敗時もstatus_codeを更新
            updated_task = task.model_copy(update={"status_code": 404})
            store_request_task(updated_task)
            continue

        # Article保存
        try:
            store_article(article)
            fetched_articles.append(article)

            # RequestTaskのstatus_code更新
            updated_task = task.model_copy(update={"status_code": 200})
            store_request_task(updated_task)

            _log.info(
                "Articleを取得・保存しました",
                article_id=article.id,
                url=str(article.url),
            )
        except Exception as error:
            _log.exception(
                "Article保存中に例外が発生しました",
                article_id=article.id,
                url=str(article.url),
                error=str(error),
            )
            continue

    _log.info(
        "バックログArticleタスクの実行が完了しました",
        total=len(backlog_tasks),
        fetched=len(fetched_articles),
    )

    return fetched_articles
```

#### fetch.py の修正
```python
"""Article用のHTML取得処理"""

from infra.logger import get_logger
from infra.web.client import RequestClient, HTTP_STATUS_OK
from infra.web.queue.model import RequestTask

from .model import Article

_log = get_logger()


def fetch_article(
    request: RequestTask,
    *,
    client: RequestClient | None = None,
) -> Article | None:
    """RequestTaskを基に記事HTMLを取得しArticleを生成する

    特殊用途。原則的には execute_fetch_and_store_backlog_articles() で
    一括処理する。

    タイムスタンプの挙動:
        - created_at: RequestTaskのcreated_atを保持（記事の公開日時を表す）
        - updated_at: 現在時刻を設定（記事HTMLの取得日時を表す）

    Args:
        request: 取得対象のRequestTask
        client: HTTPクライアント (Noneの場合はデフォルト)

    Returns:
        取得されたArticle (失敗時はNone)
    """

    http_client = client or RequestClient()

    try:
        response = http_client.get(str(request.url))
    except Exception as error:
        _log.exception(
            "記事HTML取得中に例外が発生しました",
            request_task_id=request.id,
            url=str(request.url),
            error_type=type(error).__name__,
        )
        return None

    if response.status_code != HTTP_STATUS_OK:
        _log.warning(
            "記事HTMLの取得に失敗しました",
            request_task_id=request.id,
            url=str(request.url),
            status_code=response.status_code,
        )
        return None

    from datetime import datetime, timezone

    encoding = response.encoding or "utf-8"
    html = response.body.decode(encoding)
    now = datetime.now(timezone.utc)
    article = Article(
        id=request.id,
        url=request.url,
        content=html,
        group=request.group,
        created_at=request.created_at,
        updated_at=now,
        description=request.description,
    )
    _log.info(
        "記事HTMLの取得に成功しました",
        request_task_id=request.id,
        url=str(request.url),
        bytes=len(response.body),
    )
    return article
```

---

### 2.5 domain/news/google_rss/ の作成

**ディレクトリ構成**:
```
domain/news/google_rss/
  └── __init__.py       # 空ファイル
```

**目的**: 将来の拡張用プレースホルダー

---

## Phase 3: テーブル名の変更

### 3.1 データベースマイグレーション

**変更するテーブル名**:
- `http_request_queue` → `request_task_queue`

**マイグレーション手順**:
1. 既存データのバックアップ
2. 新テーブル作成 (`request_task_queue`)
3. データ移行 (`INSERT INTO request_task_queue SELECT * FROM http_request_queue`)
4. 旧テーブル削除 (`DROP TABLE http_request_queue`)

**備考**: 開発中のため、既存データ削除で問題なければテーブル再作成でOK

---

## Phase 4: テストの移行

### 4.1 テスト方針

- 各ファイルのテストはファイル内の`TestMod`クラスとして実装
- テスト関数名は検証内容を表す
- docsコメントで目的と検証観点を明記

### 4.2 移行が必要なテスト

- `domain/news/task_queue/http_request/` → `infra/web/queue/`
- `domain/news/rss/` (既存テストの修正)
- `domain/news/article/` (既存テストの修正)
- `infra/storage/rds.py` (新規テスト追加)

---

## Phase 5: import文の一括変更

### 5.1 変更が必要なimport

```python
# 変更前 → 変更後

from infra.compute import hash_text_sha256
→ import hashlib

from infra.generate import generate_timestamp
→ from datetime import datetime

from infra.app_log import get_logger
→ from infra.logger import get_logger

from infra.runtime import get_worker_count
→ from infra.config import get_worker_num

from infra.web.https import HttpsClient
→ from infra.web.client import RequestClient

from domain.news.task_queue.http_request.model import HttpRequestTask
→ from infra.web.queue.model import RequestTask

from domain.news.task_queue.http_request.command import store_http_request
→ from infra.web.queue.store import store_request_task

from domain.news.task_queue.http_request.search import search_http_requests
→ from infra.web.queue.search import search_request_tasks

from domain.news.rss.model import RssItem
→ from domain.news.rss.model import RssLink

from domain.news.article.command import save_article_content
→ from domain.news.article.store import store_article
```

---

## 実装順序

### Step 1: infra層の基盤整備
1. `infra/storage/rds.py` にトランザクションラッパー追加
2. `infra/app_log.py` → `infra/logger.py` リネーム
3. `infra/runtime.py` → `infra/config.py` リネーム
4. `infra/web/https.py` → `infra/web/client.py` リネーム (HttpsClient → RequestClient)

### Step 2: infra/web/queue/ の作成
1. `infra/web/queue/model.py` 作成 (HttpRequestTask → RequestTask)
2. `infra/web/queue/common.py` 作成 (ensure_http_url, ensure_saved_at移動)
3. `infra/web/queue/store.py` 作成
4. `infra/web/queue/search.py` 作成
5. `infra/web/queue/service.py` 作成

### Step 3: domain/news層の整理
1. `domain/news/rss/model.py` 修正 (RssItem → RssLink)
2. `domain/news/rss/fetch.py` 修正 (関数分割・リネーム)
3. `domain/news/rss/service.py` 作成
4. `domain/news/article/command.py` → `store.py` リネーム
5. `domain/news/article/service.py` 作成
6. `domain/news/article/fetch.py` 修正 (import変更)
7. `domain/news/google_rss/__init__.py` 作成

### Step 4: 旧コードの削除
1. `domain/news/task_queue/http_request/` 削除
2. `domain/news/common.py` 削除
3. `infra/compute.py` 削除
4. `infra/generate.py` 削除

### Step 5: テーブル名変更
1. データベースマイグレーション実行
2. テスト実行で動作確認

### Step 6: 全体テスト
1. 全テスト実行
2. 警告・エラーの修正
3. 最終確認

---

## チェックリスト

- [ ] infra/storage/rds.py にトランザクションラッパー追加
- [ ] infra/logger.py リネーム完了
- [ ] infra/config.py リネーム完了
- [ ] infra/web/client.py リネーム完了
- [ ] infra/web/queue/ 作成完了
- [ ] domain/news/rss/ 整理完了
- [ ] domain/news/article/ 整理完了
- [ ] domain/news/google_rss/ 作成完了
- [ ] 旧ファイル削除完了
- [ ] テーブル名変更完了
- [ ] 全テスト pass
- [ ] ruff check pass
- [ ] pyright pass

---

## 備考

- 一行関数（compute, generate）は削除し、標準ライブラリを直接使用
- トランザクション処理はrds.pyのラッパー関数で統一
- 命名規約は既存ルール（find/search/store/load）を維持
- テストは既存のTestModパターンを踏襲
