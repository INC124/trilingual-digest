import json
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone

CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
GROUP_ID = os.environ.get("LINE_GROUP_ID", "").strip()
USER_ID = os.environ.get("LINE_USER_ID", "").strip()

# 優先推播到群組；若未設定 LINE_GROUP_ID，則退回推播給個人 LINE_USER_ID
TARGET_ID = GROUP_ID or USER_ID

PAGES_BASE_URL = "https://inc124.github.io/trilingual-digest"


def fetch_today_titles(page_url: str) -> dict:
    titles = {"en": "", "ja": "", "vi": ""}
    try:
        req = urllib.request.Request(
            page_url,
            headers={"User-Agent": "Mozilla/5.0 (TrilingualDigestNotifier/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        cards = re.findall(
            r'<article\b[^>]*\bdata-lang="(en|ja|vi)"[^>]*>(.*?)</article>',
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        for lang, card_html in cards:
            h2_match = re.search(r"<h2\b[^>]*>(.*?)</h2>", card_html, flags=re.DOTALL | re.IGNORECASE)
            if h2_match:
                clean_title = re.sub(r"<[^>]+>", "", h2_match.group(1))
                clean_title = re.sub(r"\s+", " ", clean_title).strip()
                titles[lang] = clean_title
    except Exception as e:
        print(f"[WARN] 無法讀取當日文章頁面標題 ({page_url}): {e}")
    return titles


def main():
    if not CHANNEL_ACCESS_TOKEN:
        raise RuntimeError("缺少環境變數 LINE_CHANNEL_ACCESS_TOKEN")
    if not TARGET_ID:
        raise RuntimeError("缺少環境變數 LINE_GROUP_ID 或 LINE_USER_ID")

    now = datetime.now(timezone(timedelta(hours=8)))
    d_str = now.strftime("%Y-%m-%d")
    article_url = f"{PAGES_BASE_URL}/{d_str}.html"

    titles = fetch_today_titles(article_url)
    en_title = titles["en"] or "無"
    ja_title = titles["ja"] or "無"
    vi_title = titles["vi"] or "無"

    message_text = (
        f"🌅 早安！今天的 Daily Trilingual Digest ({d_str}) 文章已準備好囉：\n\n"
        f"🇬🇧 EN：{en_title}\n"
        f"🇯🇵 JA：{ja_title}\n"
        f"🇻🇳 VI：{vi_title}\n\n"
        f"👉 立即閱讀全文：\n{article_url}"
    )

    payload = {
        "to": TARGET_ID,
        "messages": [
            {
                "type": "text",
                "text": message_text,
            }
        ],
    }

    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            status_code = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
            target_type = "群組" if GROUP_ID else "個人"
            print(f"[SUCCESS] 已透過 LINE Push API 發送通知至{target_type}（HTTP {status_code}）：{body}")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LINE API 推播失敗（HTTP {e.code}）：{err_body}") from e


if __name__ == "__main__":
    main()
