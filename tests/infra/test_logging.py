"""構造化ログシステムのテスト"""

import sys
from types import ModuleType
from typing import Any, cast


def _create_logger_extra(module_name: str) -> dict[str, object]:
    """
    docs:
        目的:
            任意のモジュール名で get_logger を呼び出し、付与される
            extra 情報を取得する共通ヘルパーを提供する。
        検証観点:
            - module_name で指定したパスが component に反映される。
            - 実行後に sys.modules の状態を汚さない。
    """

    module = ModuleType(module_name)
    package_name = module_name.rpartition(".")[0]
    module.__dict__["__package__"] = package_name
    module.__dict__["__file__"] = __file__
    sys.modules[module_name] = module

    try:
        exec(
            "from infra.logging import get_logger\nPROBE_LOGGER = get_logger()",
            module.__dict__,
        )
        logger_with_extra = cast(Any, module.__dict__["PROBE_LOGGER"])
        return cast(dict[str, object], logger_with_extra._options[-1])
    finally:
        sys.modules.pop(module_name, None)


def test_resolve_component_from_domain_module() -> None:
    """
    docs:
        目的:
            多段モジュールから get_logger を呼び出した際に
            正しいコンポーネントが付与されることを確認する。
        検証観点:
            - component がモジュール名そのものになる。
            - label が先頭2階層へ縮約される。
    """

    extra = _create_logger_extra("probe_domain.task_queue.http_request.service")

    assert extra["component"] == "probe_domain.task_queue.http_request.service"
    assert extra["label"] == "probe_domain.task_queue"


def test_resolve_component_from_src_namespaced_module() -> None:
    """
    docs:
        目的:
            src 名前空間で get_logger を呼び出しても
            元モジュールのコンポーネントが利用されることを確認する。
        検証観点:
            - component がモジュール名そのものになる。
            - label が期待通り先頭2階層に縮約される。
    """

    extra = _create_logger_extra("src.probe_infra.storage.bucket")

    assert extra["component"] == "src.probe_infra.storage.bucket"
    assert extra["label"] == "probe_infra.storage"
