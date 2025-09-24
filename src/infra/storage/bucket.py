from dataclasses import dataclass
from typing import Literal, Optional

import boto3
import zstandard as zstd
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import ClientError
from moto import mock_aws

from src.infra.compute import generate_timestamped_key

DEFAULT_ENDPOINT_URL = "http://localhost:15900"
DEFAULT_REGION_NAME = "garage"
DEFAULT_ADDRESSING_STYLE: Literal["path", "virtual"] = "path"
DEFAULT_SIGNATURE_VERSION = "s3v4"


@dataclass(frozen=True)
class StorageClientConfig:
    """Garageを含むS3互換ストレージ接続設定"""

    endpoint_url: Optional[str] = DEFAULT_ENDPOINT_URL
    access_key: str = "datadoggo"
    secret_key: str = "datadoggo_secret"
    region_name: str = DEFAULT_REGION_NAME
    addressing_style: Literal["path", "virtual"] = DEFAULT_ADDRESSING_STYLE


def _build_s3_client(config: StorageClientConfig) -> BaseClient:
    """garage対応設定でS3クライアントを生成する"""

    client_config = Config(
        signature_version=DEFAULT_SIGNATURE_VERSION,
        s3={"addressing_style": config.addressing_style},
    )

    return boto3.client(
        "s3",
        endpoint_url=config.endpoint_url,
        aws_access_key_id=config.access_key,
        aws_secret_access_key=config.secret_key,
        region_name=config.region_name,
        config=client_config,
    )


def save_html_content(
    content: str,
    bucket_name: str,
    *,
    object_key: Optional[str] = None,
    prefix: str = "content",
    client_config: Optional[StorageClientConfig] = None,
) -> str:
    """HTMLコンテンツをzstd圧縮してオブジェクトストレージに保存する"""

    try:
        # zstd圧縮
        compressor = zstd.ZstdCompressor(level=3)
        compressed_data = compressor.compress(content.encode("utf-8"))

        # 接続設定決定
        config = client_config or StorageClientConfig()

        # S3クライアント作成 (garage向けにパススタイルを強制)
        s3_client = _build_s3_client(config)

        # バケット作成（存在しない場合）
        try:
            s3_client.head_bucket(Bucket=bucket_name)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                create_params = {"Bucket": bucket_name}
                if config.region_name not in ("", "us-east-1"):
                    create_params["CreateBucketConfiguration"] = {
                        "LocationConstraint": config.region_name
                    }
                s3_client.create_bucket(**create_params)

        # オブジェクトキー決定
        resolved_key = object_key or generate_timestamped_key(
            prefix, extension="html.zst"
        )

        # オブジェクト保存
        s3_client.put_object(
            Bucket=bucket_name,
            Key=resolved_key,
            Body=compressed_data,
            ContentType="application/zstd",
            Metadata={"original_format": "html", "compression": "zstd"},
        )

        print(f"\nHTMLコンテンツを {bucket_name}/{resolved_key} に保存しました。")
        return resolved_key

    except Exception as error:
        print(f"HTML保存エラー: {error}")
        return ""


def load_html_content(
    bucket_name: str,
    object_key: str,
    *,
    client_config: Optional[StorageClientConfig] = None,
) -> str:
    """オブジェクトストレージからzstd圧縮されたHTMLコンテンツを読み込む"""

    try:
        # S3クライアント作成
        config = client_config or StorageClientConfig()
        s3_client = _build_s3_client(config)

        # オブジェクト取得
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        compressed_data = response["Body"].read()

        # zstd展開
        decompressor = zstd.ZstdDecompressor()
        decompressed_data = decompressor.decompress(compressed_data)
        content = decompressed_data.decode("utf-8")

        return content

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "NoSuchKey":
            print(f"HTMLオブジェクトが見つかりません: {bucket_name}/{object_key}")
        elif error_code == "NoSuchBucket":
            print(f"バケットが見つかりません: {bucket_name}")
        else:
            print(f"S3エラー: {e}")
        return ""
    except Exception as error:
        print(f"HTML読み込みエラー: {error}")
        return ""


def search_html_objects(
    bucket_name: str,
    prefix: str = "",
    *,
    client_config: Optional[StorageClientConfig] = None,
) -> list[str]:
    """指定プレフィックスでHTMLオブジェクト一覧を取得する"""

    try:
        # S3クライアント作成
        config = client_config or StorageClientConfig()
        s3_client = _build_s3_client(config)

        # オブジェクト一覧取得
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

        if "Contents" not in response:
            return []

        return [obj["Key"] for obj in response["Contents"]]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "NoSuchBucket":
            print(f"バケットが見つかりません: {bucket_name}")
        else:
            print(f"S3エラー: {e}")
        return []
    except Exception as error:
        print(f"HTMLオブジェクト検索エラー: {error}")
        return []


class Tests:
    @mock_aws
    def test_generate_timestamped_key(self) -> None:
        """
        docs:
            目的: タイムスタンプ付きキー生成の正常性を確認する。
            検証観点:
                - プレフィックスが正しく反映される。
                - html.zst拡張子が付与される。
        """
        key = generate_timestamped_key("test", extension="html.zst")
        assert key.startswith("test_")
        assert key.endswith(".html.zst")
        # タイムスタンプ部分の長さチェック (YYYYMMDD_HHMMSS = 15文字)
        timestamp_part = "_".join(key.split("_")[1:]).split(".")[0]
        TIMESTAMP_LENGTH = 15
        assert len(timestamp_part) == TIMESTAMP_LENGTH

    @mock_aws
    def test_zstd_compression_decompression(self) -> None:
        """
        docs:
            目的: zstd圧縮・展開ロジックの正常性を確認する。
            検証観点:
                - HTML文字列の圧縮・展開が正常に動作する。
                - 日本語を含むHTMLでも正常処理される。
        """
        test_html = (
            "<html><body><h1>テストHTML</h1><p>日本語コンテンツ</p></body></html>"
        )

        # 圧縮
        compressor = zstd.ZstdCompressor(level=3)
        compressed = compressor.compress(test_html.encode("utf-8"))

        # 展開
        decompressor = zstd.ZstdDecompressor()
        decompressed = decompressor.decompress(compressed).decode("utf-8")

        assert decompressed == test_html

    @mock_aws
    def test_html_storage_flow(self) -> None:
        """
        docs:
            目的: HTML保存→読み込み一連フローの統合テスト。
            検証観点:
                - HTMLコンテンツの保存と読み込みが正常に動作する。
                - 圧縮・展開を通じてデータの整合性が保たれる。
                - バケット自動作成が正常に動作する。
        """
        bucket_name = "test-html-bucket"
        test_html = """
        <html>
            <head><title>テストページ</title></head>
            <body>
                <h1>スクレイピングテスト</h1>
                <p>日本語のHTMLコンテンツです。</p>
                <ul>
                    <li>項目1</li>
                    <li>項目2</li>
                </ul>
            </body>
        </html>
        """

        test_config = StorageClientConfig(
            endpoint_url=None,
            region_name="us-east-1",
        )

        # HTML保存
        object_key = save_html_content(
            test_html,
            bucket_name,
            prefix="test",
            client_config=test_config,
        )
        assert object_key != ""
        assert object_key.startswith("test_")
        assert object_key.endswith(".html.zst")

        # HTML読み込み
        loaded_html = load_html_content(
            bucket_name,
            object_key,
            client_config=test_config,
        )
        assert loaded_html == test_html

        # 検索テスト
        keys = search_html_objects(
            bucket_name,
            "test",
            client_config=test_config,
        )
        assert object_key in keys
        assert len(keys) >= 1

    @mock_aws
    def test_error_handling(self) -> None:
        """
        docs:
            目的: エラーハンドリングの正常性を確認する。
            検証観点:
                - 存在しないバケット・オブジェクトに対して適切にエラー処理される。
                - エラー時に空文字列・空リストが返される。
        """
        test_config = StorageClientConfig(
            endpoint_url=None,
            region_name="us-east-1",
        )

        # 存在しないオブジェクトの読み込み
        result = load_html_content(
            "nonexistent-bucket",
            "nonexistent-key",
            client_config=test_config,
        )
        assert result == ""

        # 存在しないバケットでの検索
        keys = search_html_objects(
            "nonexistent-bucket",
            "test",
            client_config=test_config,
        )
        assert keys == []
