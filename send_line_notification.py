import json
import os
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone

CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
GROUP_ID = os.environ.get("LINE_GROUP_ID", "").strip()
USER_ID = os.environ.get("LINE_USER_ID", "").strip()

# 優先推播到群組；若未設定 LINE_GROUP_ID，則退回推播給個人 LINE_USER_ID
TARGET_ID = GROUP_ID or USER_ID

PAGES_BASE_URL = "https://inc124.github.io/trilingual-digest"


def parse_titles_from_html(html: str) -> dict:
    titles = {"en": "", "ja": "", "vi": ""}
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
    return titles


def fetch_remote_titles(page_url: str) -> dict:
    sep = "&" if "?" in page_url else "?"
    bust_url = f"{page_url}{sep}_cb={int(time.time())}"
    req = urllib.request.Request(
        bust_url,
        headers={
            "User-Agent": "Mozilla/5.0 (TrilingualDigestNotifier/1.0)",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    return parse_titles_from_html(html)


def fetch_local_titles(d_str: str) -> dict:
    local_path = f"{d_str}.html"
    if not os.path.exists(local_path):
        return {"en": "", "ja": "", "vi": ""}
    with open(local_path, "r", encoding="utf-8") as f:
        return parse_titles_from_html(f.read())


def get_synced_titles(article_url: str, d_str: str) -> dict:
    local_titles = fetch_local_titles(d_str)
    expected_en = local_titles.get("en", "")

    # 給 GitHub Pages 一些時間完成最新部署，最多重試 6 次（每次等 15 秒）
    max_attempts = 6
    latest_remote = {"en": "", "ja": "", "vi": ""}

    for attempt in range(1, max_attempts + 1):
        try:
            remote_titles = fetch_remote_titles(article_url)
            if any(remote_titles.values()):
                latest_remote = remote_titles

            # 若有本機剛生成的英文標題，比對遠端是否已經同步成同一篇
            if expected_en:
                if remote_titles.get("en") == expected_en:
                    print(f"[INFO] 第 {attempt} 次檢查：GitHub Pages 已同步為最新文章標題")
                    return remote_titles
                print(
                    f"[INFO] 第 {attempt}/{max_attempts} 次檢查：遠端尚未同步最新標題 "
                    f"(遠端: {remote_titles.get('en') or '無'} / 最新: {expected_en})，15 秒後再確認..."
                )
            else:
                if any(remote_titles.values()):
                    return remote_titles
        except Exception as e:
            print(f"[WARN] 第 {attempt}/{max_attempts} 次讀取遠端頁面失敗 ({article_url}): {e}")

        if attempt < max_attempts:
            time.sleep(15)

    # 若 GitHub Pages 仍未完成快取更新，退回使用本機剛生成的標題，確保摘要與剛產出的文章一致
    if any(local_titles.values()):
        print("[INFO] 遠端頁面仍在部署中，改用本機最新產出文章的標題發送推播")
        return local_titles

    return latest_remote


def main():
    if not CHANNEL_ACCESS_TOKEN:
        raise RuntimeError("缺少環境變數 LINE_CHANNEL_ACCESS_TOKEN")
    if not TARGET_ID:
        raise RuntimeError("缺少環境變數 LINE_GROUP_ID 或 LINE_USER_ID")

    now = datetime.now(timezone(timedelta(hours=8)))
    d_str = now.strftime("%Y-%m-%d")
    article_url = f"{PAGES_BASE_URL}/{d_str}.html"

    titles = get_synced_titles(article_url, d_str)
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
