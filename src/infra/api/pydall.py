import asyncio

from pydoll.browser.chromium import Chrome
from pydoll.browser.options import ChromiumOptions


async def fetch_news_content(url: str) -> tuple[str, bool, bool]:
    """
    Google Newsのリンクからコンテンツを取得する

    Args:
        url: Google NewsのRSS記事URL

    Returns:
        tuple: (コンテンツテキスト, リダイレクト成功フラグ, Bot排除フラグ)
    """
    try:
        # Chromiumブラウザのパスを指定
        options = ChromiumOptions()
        options.binary_location = "/Applications/Chromium.app/Contents/MacOS/Chromium"

        async with Chrome(options=options) as browser:
            # タブを起動
            tab = await browser.start()

            # 指定URLにアクセス
            await tab.go_to(url)

            # ページが完全に読み込まれるまで待機（body要素が出現するまで）
            try:
                await tab.find("body", timeout=30, raise_exc=False)
                print("ページが読み込まれました")
            except:
                pass  # タイムアウトしても続行

            # ページのテキストコンテンツを取得
            try:
                body_element = await tab.find(
                    tag_name="body", timeout=10, raise_exc=False
                )
                if body_element:
                    content_text = await body_element.text
                    print("body要素が見つかりました")
                    print(f"コンテンツ長: {len(content_text)}文字")
                    print(f"最初の100文字: {content_text[:100]}")

                    # コンテンツが空の場合、さらに待機
                    if len(content_text) == 0:
                        print("コンテンツが空です。さらに待機します...")
                        await asyncio.sleep(3)  # 追加で10秒待機
                        content_text = await body_element.text
                        print(f"追加待機後のコンテンツ長: {len(content_text)}文字")
                else:
                    content_text = "body要素が見つかりませんでした"
                    print("body要素が見つかりませんでした")
                title = "Unknown"
                current_url = url
            except Exception as e:
                content_text = f"コンテンツ取得エラー: {str(e)}"
                title = "Unknown"
                current_url = url
                print(f"例外発生: {str(e)}")

            # リダイレクト成功を確認
            redirect_success = current_url != url

            # Bot排除を確認
            is_bot_blocked = (
                "Access Denied" in content_text
                or "Blocked" in content_text
                or "403" in content_text
                or "Forbidden" in content_text
            )

            # テキストコンテンツを整形
            text_content = f"タイトル: {title}\n"
            text_content += f"URL: {current_url}\n"
            text_content += f"リダイレクト成功: {redirect_success}\n"
            text_content += f"Bot排除: {is_bot_blocked}\n"
            text_content += f"コンテンツ:\n{content_text}"  # 文字数制限を解除

            return text_content, redirect_success, is_bot_blocked

    except Exception as e:
        return f"エラー: {str(e)}", False, True


async def main():
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

    # ファイルを保存
    with open("out.txt", "w", encoding="utf-8") as f:
        f.write(content)

    print("\nコンテンツを out.txt に保存しました。")


if __name__ == "__main__":
    asyncio.run(main())
