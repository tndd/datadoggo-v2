import asyncio
import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Tuple

from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions


class OutputFormat(Enum):
    """出力形式の列挙型"""

    TEXT = "txt"
    HTML = "html"


# 定数定義
MIN_CONTENT_LENGTH = 100  # 十分なコンテンツがあると判断する最小文字数
MIN_TEXT_LENGTH = 50  # テキストとして有効と判断する最小文字数
BOT_BLOCKED_KEYWORDS = ["Access Denied", "Blocked", "403", "Forbidden", "Captcha"]


# カスタム例外クラス
class ContentFetchError(Exception):
    """コンテンツ取得時のエラー"""

    pass


class BrowserInitError(Exception):
    """ブラウザ初期化時のエラー"""

    pass


def get_browser_options() -> ChromiumOptions:
    """
    ブラウザオプションを取得する

    Returns:
        ChromiumOptions: 設定されたブラウザオプション
    """
    options = ChromiumOptions()

    # 環境変数からChromiumパスを取得、なければデフォルト値を使用
    default_chromium_path = "/Applications/Chromium.app/Contents/MacOS/Chromium"
    chromium_path = os.getenv("CHROMIUM_PATH", default_chromium_path)
    options.binary_location = chromium_path

    return options


async def fetch_page_content(url: str, page_timeout: int = 15) -> Tuple[str, str, str]:
    """
    指定されたURLからページコンテンツを取得する

    Args:
        url: アクセス対象のURL
        page_timeout: ページロードのタイムアウト時間（秒）

    Returns:
        Tuple[str, str, str]: (コンテンツテキスト, タイトル, 現在のURL)

    Raises:
        BrowserInitError: ブラウザ初期化に失敗した場合
        ContentFetchError: コンテンツ取得に失敗した場合
    """
    try:
        options = get_browser_options()

        async with Chrome(options=options) as browser:
            tab = await browser.start()

            # 指定URLにアクセス
            await tab.go_to(url)

            # ページが読み込まれるまで待機（効率的な単一待機）
            body_element = await tab.find(
                tag_name="body", timeout=page_timeout, raise_exc=False
            )

            if body_element is None:
                raise ContentFetchError("body要素が見つかりませんでした")

            print("ページが読み込まれました")

            # コンテンツとメタデータを取得
            content_text = await body_element.text

            # タイトルを取得
            try:
                title_element = await tab.find("title", timeout=2, raise_exc=False)
                title = await title_element.text if title_element else "Unknown"
            except Exception:
                title = "Unknown"

            # 現在のURLを取得
            try:
                current_url = await tab.get_url()
            except Exception:
                current_url = url

            print(f"コンテンツ長: {len(content_text)}文字")
            print(f"タイトル: {title}")
            print(f"最初の100文字: {content_text[:100]}")

            return content_text, title, current_url

    except Exception as e:
        if "Chrome" in str(e) or "browser" in str(e).lower():
            raise BrowserInitError(f"ブラウザ初期化エラー: {str(e)}") from e
        else:
            raise ContentFetchError(f"コンテンツ取得エラー: {str(e)}") from e


async def extract_article_text(tab, body_element) -> str:
    """
    記事コンテンツからテキストを抽出する

    Args:
        tab: ブラウザタブ
        body_element: body要素

    Returns:
        str: 抽出されたテキストコンテンツ
    """
    # JavaScriptコンテンツの読み込みを待機
    print("JavaScriptコンテンツの読み込みを待機中...")
    await asyncio.sleep(3)  # 追加待機

    # より具体的な要素を探す（記事コンテンツ）
    article_selectors = [
        "article",
        "[data-content-type='article']",
        ".content",
        ".article-body",
        ".post-content",
        "main",
        "p",  # 段落要素も試す
    ]

    content = ""
    try:
        for selector in article_selectors:
            elements = await tab.query(
                selector, timeout=2, find_all=True, raise_exc=False
            )
            if not elements:
                continue

            text_parts = []
            for element in elements:
                try:
                    element_text = await element.text
                except Exception:
                    # テキスト取得失敗時は次の要素を試す
                    continue

                if element_text and element_text.strip():
                    text_parts.append(element_text.strip())

            if text_parts:
                content = "\n\n".join(text_parts)
                if len(content) > MIN_CONTENT_LENGTH:
                    break
    except Exception as error:
        print(f"記事要素の取得でエラー発生: {error}")

    # 上記で取得できない場合はbody全体を取得
    if not content or len(content) < MIN_TEXT_LENGTH:
        try:
            body_text = await body_element.text
        except Exception as error:
            print(f"body要素からのテキスト取得に失敗: {error}")
            return content

        if body_text and len(body_text) > len(content):
            content = body_text

    return content


async def _start_browser_tab(browser) -> Any:
    """ブラウザタブを起動する"""

    try:
        return await browser.start()
    except Exception as error:
        raise BrowserInitError(f"ブラウザ起動に失敗しました: {error}") from error


async def _navigate_to_url(tab, url: str) -> None:
    """指定URLへ遷移する"""

    try:
        await tab.go_to(url)
    except Exception as error:
        raise ContentFetchError(f"URLへのアクセスに失敗しました: {error}") from error


async def _find_body_element(tab, page_timeout: int):
    """body要素を取得する"""

    body_element = await tab.find(
        tag_name="body",
        timeout=page_timeout,
        raise_exc=False,
    )
    if body_element is None:
        raise ContentFetchError("body要素が見つかりませんでした")
    return body_element


async def _retrieve_content(tab, body_element, output_format: OutputFormat) -> str:
    """出力形式に応じたコンテンツ取得を行う"""

    if output_format == OutputFormat.HTML:
        try:
            content = await tab.page_source
        except Exception as error:
            raise ContentFetchError(f"HTML取得に失敗しました: {error}") from error
        print(f"HTML長: {len(content)}文字")
        return content

    try:
        content = await extract_article_text(tab, body_element)
    except Exception as error:
        raise ContentFetchError(f"テキスト抽出に失敗しました: {error}") from error

    print(f"テキスト長: {len(content)}文字")
    return content


async def _fetch_title(tab) -> str:
    """ページタイトルを取得する"""

    try:
        title_element = await tab.find(tag_name="title", timeout=2, raise_exc=False)
        return await title_element.text if title_element else "Unknown"
    except Exception as error:
        print(f"タイトル取得エラー: {error}")
        return "Unknown"


async def _fetch_current_url(tab, fallback_url: str) -> str:
    """現在のURLを取得する"""

    try:
        return await tab.get_url()
    except Exception as error:
        print(f"URL取得エラー: {error}")
        return fallback_url


async def fetch_page_content_unified(
    url: str, output_format: OutputFormat = OutputFormat.HTML, page_timeout: int = 15
) -> Tuple[str, str, str]:
    """
    指定されたURLからページコンテンツを取得する（統合版）

    Args:
        url: アクセス対象のURL
        output_format: 出力形式（TEXT or HTML）
        page_timeout: ページロードのタイムアウト時間（秒）

    Returns:
        Tuple[str, str, str]: (コンテンツ, タイトル, 現在のURL)

    Raises:
        BrowserInitError: ブラウザ初期化に失敗した場合
        ContentFetchError: コンテンツ取得に失敗した場合
    """
    options = get_browser_options()

    try:
        async with Chrome(options=options) as browser:
            tab = await _start_browser_tab(browser)
            await _navigate_to_url(tab, url)

            body_element = await _find_body_element(tab, page_timeout)
            print("ページが読み込まれました")

            content = await _retrieve_content(tab, body_element, output_format)
            title = await _fetch_title(tab)
            current_url = await _fetch_current_url(tab, url)

            print(f"タイトル: {title}")
            print(f"最初の100文字: {content[:100]}")

            return content, title, current_url
    except ContentFetchError:
        raise
    except BrowserInitError:
        raise
    except Exception as error:
        if "Chrome" in str(error) or "browser" in str(error).lower():
            raise BrowserInitError(f"ブラウザ初期化エラー: {error}") from error
        raise ContentFetchError(f"コンテンツ取得エラー: {error}") from error


def analyze_content(
    content: str, title: str, original_url: str, current_url: str
) -> Tuple[str, bool, bool]:
    """
    取得したコンテンツを分析し、フォーマットされた結果を返す

    Args:
        content: 取得したコンテンツテキスト
        title: ページタイトル
        original_url: 元のURL
        current_url: 現在のURL

    Returns:
        Tuple[str, bool, bool]: (
            フォーマット済みコンテンツ,
            リダイレクト成功フラグ,
            Bot排除フラグ
        )
    """
    # リダイレクト成功を確認
    redirect_success = current_url != original_url

    # Bot排除を確認
    bot_blocked_keywords = BOT_BLOCKED_KEYWORDS
    is_bot_blocked = any(keyword in content for keyword in bot_blocked_keywords)

    # テキストコンテンツを整形
    formatted_content = f"タイトル: {title}\n"
    formatted_content += f"URL: {current_url}\n"
    formatted_content += f"リダイレクト成功: {redirect_success}\n"
    formatted_content += f"Bot排除: {is_bot_blocked}\n"
    formatted_content += f"コンテンツ:\n{content}"

    return formatted_content, redirect_success, is_bot_blocked


def generate_timestamped_filename(
    output_format: OutputFormat, output_dir: str = "mock"
) -> str:
    """
    タイムスタンプ付きファイル名を生成する

    Args:
        output_format: 出力形式
        output_dir: 出力ディレクトリ

    Returns:
        str: タイムスタンプ付きファイルパス
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"out_{timestamp}.{output_format.value}"
    return os.path.join(output_dir, filename)


def save_content_to_file(
    content: str,
    output_format: OutputFormat = OutputFormat.HTML,
    filepath: str = None,
    output_dir: str = "mock",
) -> str:
    """
    コンテンツをファイルに保存する

    Args:
        content: 保存するコンテンツ
        output_format: 出力形式
        filepath: 保存先ファイルパス（Noneの場合は自動生成）
        output_dir: 出力ディレクトリ

    Returns:
        str: 実際の保存先ファイルパス
    """
    try:
        # ファイルパスが指定されていない場合は自動生成
        if filepath is None:
            filepath = generate_timestamped_filename(output_format, output_dir)

        # ディレクトリが存在しない場合は作成
        Path(os.path.dirname(filepath)).mkdir(parents=True, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\nコンテンツを {filepath} に保存しました。")
        return filepath
    except Exception as e:
        print(f"ファイル保存エラー: {str(e)}")
        return ""


def handle_fetch_error(error: Exception) -> Tuple[str, bool, bool]:
    """
    エラーハンドリングを行い、エラー情報を整形して返す

    Args:
        error: 発生した例外

    Returns:
        Tuple[str, bool, bool]: (エラーメッセージ, False, True)
    """
    error_message = f"エラー: {str(error)}"
    print(f"処理中にエラーが発生しました: {error_message}")
    return error_message, False, True


async def fetch_news_content(
    url: str, output_format: OutputFormat = OutputFormat.HTML, page_timeout: int = 15
) -> Tuple[str, bool, bool]:
    """
    ニュースコンテンツを取得する（メイン関数）

    Args:
        url: ニュース記事のURL
        output_format: 出力形式（TEXT or HTML）
        page_timeout: ページロードのタイムアウト時間（秒）

    Returns:
        Tuple[str, bool, bool]: (コンテンツ, リダイレクト成功フラグ, Bot排除フラグ)
    """
    try:
        # 統合されたコンテンツ取得関数を使用
        content, title, current_url = await fetch_page_content_unified(
            url, output_format, page_timeout
        )

        # 簡単な分析（純粋なコンテンツを保持）
        redirect_success = current_url != url
        is_bot_blocked = any(keyword in content for keyword in BOT_BLOCKED_KEYWORDS)

        return content, redirect_success, is_bot_blocked

    except (BrowserInitError, ContentFetchError) as e:
        return handle_fetch_error(e)
    except Exception as e:
        return handle_fetch_error(e)


async def fetch_and_save_content(
    url: str,
    output_format: OutputFormat = OutputFormat.HTML,
    output_dir: str = "mock",
    page_timeout: int = 15,
) -> str:
    """
    URLからコンテンツを取得し、ファイルに保存する一貫処理関数

    Args:
        url: 取得対象のURL
        output_format: 出力形式（TEXT or HTML）
        output_dir: 出力ディレクトリ
        page_timeout: ページロードのタイムアウト時間（秒）

    Returns:
        str: 保存されたファイルのパス
    """
    print(f"コンテンツを取得中... ({output_format.value}形式)")

    # コンテンツ取得
    content, redirect_success, bot_blocked = await fetch_news_content(
        url, output_format, page_timeout
    )

    # 結果を表示
    print("=== 取得結果 ===")
    print(f"形式: {output_format.value}")
    print(f"文字数: {len(content)}文字")
    print(f"最初の100文字: {content[:100]}")
    print("\n=== 検証結果 ===")
    print(f"リダイレクト成功: {redirect_success}")
    print(f"Bot排除: {bot_blocked}")

    # ファイルに保存
    filepath = save_content_to_file(content, output_format, None, output_dir)

    return filepath


async def main():
    """メイン実行関数"""
    # Google NewsのRSS記事URL
    # google_news_url = "https://news.google.com/rss/articles/CBMiyAFBVV95cUxOWS1JeXBabU5BTkZaMWgyVFAzRlA0WDlpT0NTYjFEQnNkeWhpd3dtcGt6aU9pVFYzZGRQbVVBTENZcVhqb19RLWw0QkJtUFhoQnkzb3d2WjIyOXZHY0VRMWNZUUVTQ3JQRktpUUQ4NXAyYUkxdEFIcmFNUEZjWVZfWDVxVEN0ak9YRzEyYlZnTW5Zd05UMERMZmNVWDd4cWs0b1M3c0pUcWFaWC04b21CTjBPNkZNVHZ5UEZrNzNnNHh2dC1CNzRUbw?oc=5"
    google_news_url = "https://news.google.com/read/CBMidkFVX3lxTFBBQmZUaVRZalQwVkh4OUhpdHBfZlh3OVE4UVFCNldUVk81N1RLN2gyMkYyejREWUREU3BubGlibXA3SWVmWG1KcHNtSUtKVGcwc0VyTFlfY3kyekxXR3Y0UzRKS2VxWlNnZzE5dTd1RjRPOFRjU2c?hl=ja&gl=JP&ceid=JP%3Aja"

    # HTML形式でコンテンツを取得・保存
    html_filepath = await fetch_and_save_content(
        google_news_url, OutputFormat.HTML, "mock"
    )

    print(f"\nHTML形式で保存完了: {html_filepath}")

    # TEXT 形式でも取得・保存（比較のため）
    text_filepath = await fetch_and_save_content(
        google_news_url, OutputFormat.TEXT, "mock"
    )

    print(f"TEXT形式で保存完了: {text_filepath}")


if __name__ == "__main__":
    asyncio.run(main())
