import html
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
GROUP_ID = os.environ.get("LINE_GROUP_ID", "").strip()
GROUP_IDS_RAW = os.environ.get("LINE_GROUP_IDS", "").strip()
USER_ID = os.environ.get("LINE_USER_ID", "").strip()
VERSION_SUFFIX = os.environ.get("VERSION_SUFFIX", "").strip()

PAGES_BASE_URL = "https://inc124.github.io/trilingual-digest"


def get_target_ids(is_test: bool) -> list:
    # 試閱/測試模式（例如 VERSION_SUFFIX="v1"）：只通知巡檢機器人/管理員 (USER_ID)，絕不發給群組
    if is_test:
        return [USER_ID] if USER_ID else []

    targets = []
    if GROUP_IDS_RAW:
        for gid in GROUP_IDS_RAW.split(","):
            clean_gid = gid.strip()
            if clean_gid and clean_gid not in targets:
                targets.append(clean_gid)
    if GROUP_ID and GROUP_ID not in targets:
        targets.append(GROUP_ID)
    if not targets and USER_ID:
        targets.append(USER_ID)
    return targets


def parse_titles_from_html(raw_html: str) -> dict:
    titles = {"en": "", "ja": "", "vi": ""}

    # 支援原本 <article data-lang="en">...<h2>...</h2>
    cards = re.findall(
        r'<article\b[^>]*\bdata-lang="(en|ja|vi)"[^>]*>(.*?)</article>',
        raw_html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    for lang, card_html in cards:
        h2_match = re.search(r"<h2\b[^>]*>(.*?)</h2>", card_html, flags=re.DOTALL | re.IGNORECASE)
        if h2_match:
            clean_title = re.sub(r"<[^>]+>", "", h2_match.group(1))
            clean_title = html.unescape(clean_title)
            clean_title = re.sub(r"\s+", " ", clean_title).strip()
            titles[lang] = clean_title

    # 備援支援 <section class="lang-card" id="sec-en">...<h2>...</h2>
    if not any(titles.values()):
        sec_cards = re.findall(
            r'<section\b[^>]*\bid="sec-(en|ja|vi)"[^>]*>(.*?)</section>',
            raw_html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        for lang, card_html in sec_cards:
            h2_match = re.search(r"<h2\b[^>]*>(.*?)</h2>", card_html, flags=re.DOTALL | re.IGNORECASE)
            if h2_match:
                clean_title = re.sub(r"<[^>]+>", "", h2_match.group(1))
                clean_title = html.unescape(clean_title)
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
        page_html = resp.read().decode("utf-8", errors="replace")
    return parse_titles_from_html(page_html)


def fetch_local_titles(article_id: str) -> dict:
    candidate_paths = [
        f"{article_id}.html",
        os.path.join("archive", f"{article_id}.html"),
        os.path.join("docs", "archive", f"{article_id}.html"),
    ]
    for path in candidate_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return parse_titles_from_html(f.read())

    # 若有對應 JSON 也可直接讀標題
    json_paths = [
        os.path.join("archive", f"{article_id}.json"),
        os.path.join("docs", "archive", f"{article_id}.json"),
        os.path.join("docs", "latest.json"),
    ]
    for jpath in json_paths:
        if os.path.exists(jpath):
            with open(jpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {
                "en": data.get("en", {}).get("title", ""),
                "ja": data.get("ja", {}).get("title", ""),
                "vi": data.get("vi", {}).get("title", ""),
            }

    return {"en": "", "ja": "", "vi": ""}


def get_synced_titles(article_url: str, article_id: str, is_test: bool) -> dict:
    local_titles = fetch_local_titles(article_id)
    expected_en = local_titles.get("en", "")

    # 測試版優先用本機剛產出的標題，避免遠端 GitHub Pages 還沒部署好就等太久
    if is_test and any(local_titles.values()):
        print(f"[INFO] 測試版 ({article_id}) 直接使用本機最新產出標題發送巡檢通知")
        return local_titles

    max_attempts = 6
    latest_remote = {"en": "", "ja": "", "vi": ""}

    for attempt in range(1, max_attempts + 1):
        try:
            remote_titles = fetch_remote_titles(article_url)
            if any(remote_titles.values()):
                latest_remote = remote_titles

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

    if any(local_titles.values()):
        print("[INFO] 遠端頁面仍在部署中，改用本機最新產出文章的標題發送推播")
        return local_titles

    return latest_remote


def main():
    if not CHANNEL_ACCESS_TOKEN:
        raise RuntimeError("缺少環境變數 LINE_CHANNEL_ACCESS_TOKEN")

    is_test = bool(VERSION_SUFFIX)
    target_ids = get_target_ids(is_test)
    if not target_ids:
        if is_test:
            raise RuntimeError("測試模式需要設定環境變數 LINE_USER_ID 才能通知巡檢機器人")
        raise RuntimeError("缺少環境變數 LINE_GROUP_IDS、LINE_GROUP_ID 或 LINE_USER_ID")

    now = datetime.now(timezone(timedelta(hours=8)))
    d_str = now.strftime("%Y-%m-%d")
    article_id = f"{d_str}{VERSION_SUFFIX}"

    if is_test:
        article_url = f"{PAGES_BASE_URL}/archive/{article_id}.html"
    else:
        article_url = f"{PAGES_BASE_URL}/{d_str}.html"

    titles = get_synced_titles(article_url, article_id, is_test)
    en_title = titles["en"] or "無"
    ja_title = titles["ja"] or "無"
    vi_title = titles["vi"] or "無"

    if is_test:
        message_text = (
            f"🧪 [巡檢試閱版] Daily Trilingual Digest ({article_id})\n"
            f"（已略過讀者群組，僅通知巡檢機器人）\n\n"
            f"🇬🇧 EN：{en_title}\n"
            f"🇯🇵 JA：{ja_title}\n"
            f"🇻🇳 VI：{vi_title}\n\n"
            f"👉 試閱網址：\n{article_url}"
        )
    else:
        message_text = (
            f"🌅 早安！今天的 Daily Trilingual Digest ({d_str}) 文章已準備好囉：\n\n"
            f"🇬🇧 EN：{en_title}\n"
            f"🇯🇵 JA：{ja_title}\n"
            f"🇻🇳 VI：{vi_title}\n\n"
            f"👉 立即閱讀全文：\n{article_url}"
        )

    success_count = 0
    errors = []

    for idx_num, target_id in enumerate(target_ids, start=1):
        payload = {
            "to": target_id,
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
                print(f"[SUCCESS] ({idx_num}/{len(target_ids)}) 已發送至 {target_id}（HTTP {status_code}）：{body}")
                success_count += 1
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            msg = f"推播至 {target_id} 失敗（HTTP {e.code}）：{err_body}"
            print(f"[ERROR] {msg}")
            errors.append(msg)

    if success_count == 0 and errors:
        raise RuntimeError("所有目標皆推播失敗：" + " | ".join(errors))


if __name__ == "__main__":
    main()
