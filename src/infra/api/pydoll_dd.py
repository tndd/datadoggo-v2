import asyncio
import os
from typing import Tuple

from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions


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
            raise BrowserInitError(f"ブラウザ初期化エラー: {str(e)}")
        else:
            raise ContentFetchError(f"コンテンツ取得エラー: {str(e)}")


async def fetch_page_html(url: str, page_timeout: int = 15) -> Tuple[str, str, str]:
    """
    指定されたURLからページ全体のHTMLを取得する

    Args:
        url: アクセス対象のURL
        page_timeout: ページロードのタイムアウト時間（秒）

    Returns:
        Tuple[str, str, str]: (HTMLコンテンツ, タイトル, 現在のURL)

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

            # ページが読み込まれるまで待機
            body_element = await tab.find(
                tag_name="body", timeout=page_timeout, raise_exc=False
            )

            if body_element is None:
                raise ContentFetchError("body要素が見つかりませんでした")

            print("ページが読み込まれました")

            # HTML全体を取得
            html_content = await tab.page_source

            # タイトルを取得
            try:
                title_element = await tab.find(
                    tag_name="title", timeout=2, raise_exc=False
                )
                title = await title_element.text if title_element else "Unknown"
            except Exception:
                title = "Unknown"

            # 現在のURLを取得
            try:
                current_url = await tab.get_url()
            except Exception:
                current_url = url

            print(f"HTML長: {len(html_content)}文字")
            print(f"タイトル: {title}")
            print(f"最初の100文字: {html_content[:100]}")

            return html_content, title, current_url

    except Exception as e:
        if "Chrome" in str(e) or "browser" in str(e).lower():
            raise BrowserInitError(f"ブラウザ初期化エラー: {str(e)}")
        else:
            raise ContentFetchError(f"コンテンツ取得エラー: {str(e)}")


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
        Tuple[str, bool, bool]: (フォーマット済みコンテンツ, リダイレクト成功フラグ, Bot排除フラグ)
    """
    # リダイレクト成功を確認
    redirect_success = current_url != original_url

    # Bot排除を確認
    bot_blocked_keywords = ["Access Denied", "Blocked", "403", "Forbidden", "Captcha"]
    is_bot_blocked = any(keyword in content for keyword in bot_blocked_keywords)

    # テキストコンテンツを整形
    formatted_content = f"タイトル: {title}\n"
    formatted_content += f"URL: {current_url}\n"
    formatted_content += f"リダイレクト成功: {redirect_success}\n"
    formatted_content += f"Bot排除: {is_bot_blocked}\n"
    formatted_content += f"コンテンツ:\n{content}"

    return formatted_content, redirect_success, is_bot_blocked


def save_content_to_file(content: str, filepath: str = "out.html") -> None:
    """
    コンテンツをファイルに保存する

    Args:
        content: 保存するコンテンツ
        filepath: 保存先ファイルパス
    """
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\nコンテンツを {filepath} に保存しました。")
    except Exception as e:
        print(f"ファイル保存エラー: {str(e)}")


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
    url: str, page_timeout: int = 15
) -> Tuple[str, bool, bool]:
    """
    ニュースコンテンツを取得する（メイン関数）

    Args:
        url: ニュース記事のURL
        page_timeout: ページロードのタイムアウト時間（秒）

    Returns:
        Tuple[str, bool, bool]: (コンテンツテキスト, リダイレクト成功フラグ, Bot排除フラグ)
    """
    try:
        # ページHTML全体を取得
        content, title, current_url = await fetch_page_html(url, page_timeout)

        # HTML用の簡単な分析（純粋なHTMLを保持）
        redirect_success = current_url != url
        is_bot_blocked = any(
            keyword in content
            for keyword in ["Access Denied", "Blocked", "403", "Forbidden", "Captcha"]
        )

        return content, redirect_success, is_bot_blocked

    except (BrowserInitError, ContentFetchError) as e:
        return handle_fetch_error(e)
    except Exception as e:
        return handle_fetch_error(e)


async def main():
    """メイン実行関数"""
    # Google NewsのRSS記事URL
    google_news_url = "https://news.google.com/rss/articles/CBMiyAFBVV95cUxOWS1JeXBabU5BTkZaMWgyVFAzRlA0WDlpT0NTYjFEQnNkeWhpd3dtcGt6aU9pVFYzZGRQbVVBTENZcVhqb19RLWw0QkJtUFhoQnkzb3d2WjIyOXZHY0VRMWNZUUVTQ3JQRktpUUQ4NXAyYUkxdEFIcmFNUEZjWVZfWDVxVEN0ak9YRzEyYlZnTW5Zd05UMERMZmNVWDd4cWs0b1M3c0pUcWFaWC04b21CTjBPNkZNVHZ5UEZrNzNnNHh2dC1CNzRUbw?oc=5"

    print("ニュースコンテンツを取得中...")

    # コンテンツ取得
    content, redirect_success, bot_blocked = await fetch_news_content(google_news_url)

    # 結果を表示
    print("=== 取得結果 ===")
    print(content)
    print("\n=== 検証結果 ===")
    print(f"リダイレクト成功: {redirect_success}")
    print(f"Bot排除: {bot_blocked}")

    # ファイルに保存
    save_content_to_file(content)


if __name__ == "__main__":
    asyncio.run(main())
