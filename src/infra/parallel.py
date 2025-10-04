"""並列実行制御ユーティリティ"""

import os


def get_worker_count(parallel: bool | int) -> int:
    """並列実行オプションからワーカー数を決定する"""

    if not parallel:
        return 1

    cpu_count = os.cpu_count() or 4

    if parallel is True:
        return cpu_count

    return min(parallel, cpu_count)


class TestMod:
    def test_get_worker_count_returns_1_when_disabled(self) -> None:
        """
        docs:
            目的: parallel=False時に逐次実行となることを確認する。
            検証観点:
                - parallel=Falseでワーカー数1を返す。
        """

        assert get_worker_count(False) == 1

    def test_get_worker_count_returns_cpu_count_when_enabled(self) -> None:
        """
        docs:
            目的: parallel=True時にCPU数を返すことを確認する。
            検証観点:
                - parallel=TrueでCPU数を返す。
        """

        worker_count = get_worker_count(True)
        assert worker_count == (os.cpu_count() or 4)

    def test_get_worker_count_respects_explicit_limit(self) -> None:
        """
        docs:
            目的: 明示的なワーカー数指定が上限適用されることを確認する。
            検証観点:
                - CPU数より少ない値は指定値そのままを返す。
                - CPU数より多い値はCPU数に制限される。
        """

        cpu_count = os.cpu_count() or 4

        # CPU数より少ない値
        assert get_worker_count(2) == min(2, cpu_count)

        # CPU数より多い値
        assert get_worker_count(999) == cpu_count
