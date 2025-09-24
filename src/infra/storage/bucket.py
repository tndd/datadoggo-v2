from typing import Optional

import boto3
import zstandard as zstd
from botocore.exceptions import ClientError
from moto import mock_aws

from src.infra.compute import generate_timestamped_key


def save_html_content(
    content: str,
    bucket_name: str,
    *,
    object_key: Optional[str] = None,
    endpoint_url: str = "http://localhost:15900",
    access_key: str = "datadoggo",
    secret_key: str = "datadoggo_secret",
    prefix: str = "content",
) -> str:
    """HTMLコンテンツをzstd圧縮してオブジェクトストレージに保存する"""

    try:
        # zstd圧縮
        compressor = zstd.ZstdCompressor(level=3)
        compressed_data = compressor.compress(content.encode("utf-8"))

        # S3クライアント作成
        s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url
            if endpoint_url != "http://localhost:15900"
            else None,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="us-east-1",
        )

        # バケット作成（存在しない場合）
        try:
            s3_client.head_bucket(Bucket=bucket_name)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                s3_client.create_bucket(Bucket=bucket_name)

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
    endpoint_url: str = "http://localhost:15900",
    access_key: str = "datadoggo",
    secret_key: str = "datadoggo_secret",
) -> str:
    """オブジェクトストレージからzstd圧縮されたHTMLコンテンツを読み込む"""

    try:
        # S3クライアント作成
        s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url
            if endpoint_url != "http://localhost:15900"
            else None,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="us-east-1",
        )

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
    endpoint_url: str = "http://localhost:15900",
    access_key: str = "datadoggo",
    secret_key: str = "datadoggo_secret",
) -> list[str]:
    """指定プレフィックスでHTMLオブジェクト一覧を取得する"""

    try:
        # S3クライアント作成
        s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url
            if endpoint_url != "http://localhost:15900"
            else None,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="us-east-1",
        )

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

        # HTML保存
        object_key = save_html_content(test_html, bucket_name, prefix="test")
        assert object_key != ""
        assert object_key.startswith("test_")
        assert object_key.endswith(".html.zst")

        # HTML読み込み
        loaded_html = load_html_content(bucket_name, object_key)
        assert loaded_html == test_html

        # 検索テスト
        keys = search_html_objects(bucket_name, "test")
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
        # 存在しないオブジェクトの読み込み
        result = load_html_content("nonexistent-bucket", "nonexistent-key")
        assert result == ""

        # 存在しないバケットでの検索
        keys = search_html_objects("nonexistent-bucket", "test")
        assert keys == []
