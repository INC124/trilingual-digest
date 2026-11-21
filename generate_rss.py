from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# ================= 設定區 =================
LATEST_JSON = Path("latest.json")
ARCHIVE_DIR = Path("archive")
OUTPUT_DIR = Path(".")
MAX_ITEMS = 10
SITE_BASE_URL = "https://inc124.github.io/trilingual-digest/"
TZ_TAIPEI = timezone(timedelta(hours=8))

FEED_META = {
    "en": {
        "filename": "feed-en.xml",
        "title": "Daily Trilingual Digest - English",
        "description": "Daily English reading digest with vocabulary and examples.",
        "language": "en-US",
        "vocab_heading": "Key Vocabulary",
    },
    "ja": {
        "filename": "feed-ja.xml",
        "title": "Daily Trilingual Digest - 日本語",
        "description": "毎日の日本語リーディング記事、語彙と例文。",
        "language": "ja-JP",
        "vocab_heading": "語彙と例文",
    },
    "vi": {
        "filename": "feed-vi.xml",
        "title": "Daily Trilingual Digest - Tiếng Việt",
        "description": "Bài đọc tiếng Việt hằng ngày kèm từ vựng và ví dụ.",
        "language": "vi-VN",
        "vocab_heading": "Từ vựng & Ví dụ",
    },
}
# ==========================================


def strip_ruby(text: str) -> str:
    """移除 <rt>...</rt> 與 <ruby>...</ruby> 標籤，保留漢字本體。"""
    if not text:
        return ""
    cleaned = re.sub(r"<rt\b[^>]*>.*?</rt>", "", text, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"</?ruby\b[^>]*>", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def to_rfc2822(date_str: str) -> str:
    """把 YYYY-MM-DD 轉成 RSS 標準的 RFC 2822 時間字串（UTC+8 06:37）。"""
    try:
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d").replace(
            hour=6, minute=37, second=0, tzinfo=TZ_TAIPEI
        )
    except ValueError:
        dt = datetime.now(TZ_TAIPEI)
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def cdata_safe(content: str) -> str:
    """避免內容中意外出現 ']]>' 導致 XML CDATA 提前結束。"""
    return content.replace("]]>", "]]]]><![CDATA[>")


def build_description_html(entry: dict[str, Any], meta: dict[str, str]) -> str:
    """組合文章摘要、段落與字彙清單 HTML。"""
    zh_title = html.escape(str(entry.get("zh_title", "")).strip())
    source_note = html.escape(str(entry.get("source_note", "")).strip())
    raw_content = strip_ruby(str(entry.get("content", "")))

    parts: list[str] = []

    if zh_title or source_note:
        source_part = f"（來源：{source_note}）" if source_note else ""
        parts.append(f"<p><strong>{zh_title}</strong>{source_part}</p>")

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", raw_content) if p.strip()]
    for p in paragraphs:
        safe_p = html.escape(p).replace("\n", "<br/>")
        parts.append(f"<p>{safe_p}</p>")

    vocab_list = entry.get("vocab") or []
    if isinstance(vocab_list, list) and vocab_list:
        parts.append(f"<h4>{html.escape(meta['vocab_heading'])}</h4>")
        parts.append("<ul>")
        for item in vocab_list:
            if not isinstance(item, dict):
                continue
            word = html.escape(strip_ruby(str(item.get("word", ""))).strip())
            pos = html.escape(str(item.get("pos", "")).strip())
            meaning = html.escape(str(item.get("meaning", "")).strip())
            example = html.escape(strip_ruby(str(item.get("example", ""))).strip())

            pos_str = f" ({pos})" if pos else ""
            line = f"<li><strong>{word}</strong>{pos_str} — {meaning}"
            if example:
                line += f"<br/><em>{example}</em>"
            line += "</li>"
            parts.append(line)
        parts.append("</ul>")

    return "".join(parts)


def _extract_records_from_json(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if isinstance(data.get("articles"), list):
            return [d for d in data["articles"] if isinstance(d, dict)]
        if "date" in data or "en" in data or "ja" in data or "vi" in data:
            return [data]
    elif isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]
    return []


def load_recent_records() -> list[dict[str, Any]]:
    """讀取 latest.json 與 archive/ 內的 JSON，依日期由新到舊去重並保留最新 MAX_ITEMS 篇。"""
    candidate_files: list[Path] = []
    if LATEST_JSON.exists():
        candidate_files.append(LATEST_JSON)
    if ARCHIVE_DIR.exists() and ARCHIVE_DIR.is_dir():
        archive_jsons = sorted(ARCHIVE_DIR.glob("*.json"), reverse=True)
        candidate_files.extend(archive_jsons)

    by_key: dict[str, dict[str, Any]] = {}
    for jf in candidate_files:
        for rec in _extract_records_from_json(jf):
            key = str(rec.get("date") or rec.get("article_id") or "").strip()
            if not key:
                continue
            if key not in by_key:
                by_key[key] = rec

    sorted_records = sorted(
        by_key.values(),
        key=lambda r: str(r.get("date") or r.get("article_id") or ""),
        reverse=True,
    )
    return sorted_records[:MAX_ITEMS]


def render_rss_xml(lang: str, records: list[dict[str, Any]], build_time_str: str) -> str:
    """產生指定語系的 RSS 2.0 XML 字串。"""
    meta = FEED_META[lang]
    base_url = SITE_BASE_URL.rstrip("/") + "/"
    items_xml: list[str] = []

    for rec in records:
        lang_data = rec.get(lang)
        if not isinstance(lang_data, dict):
            continue

        date_str = str(rec.get("date") or rec.get("article_id") or "").strip()
        title = html.escape(strip_ruby(str(lang_data.get("title", ""))).strip())
        if not title:
            continue

        article_url = html.escape(f"{base_url}?date={date_str}&lang={lang}")
        guid = html.escape(f"{date_str}-{lang}")
        pub_date = to_rfc2822(date_str)
        desc_html = cdata_safe(build_description_html(lang_data, meta))

        item_block = (
            "    <item>\n"
            f"      <title>{title}</title>\n"
            f"      <link>{article_url}</link>\n"
            f'      <guid isPermaLink="false">{guid}</guid>\n'
            f"      <pubDate>{pub_date}</pubDate>\n"
            f"      <description><![CDATA[{desc_html}]]></description>\n"
            "    </item>"
        )
        items_xml.append(item_block)

    joined_items = "\n".join(items_xml)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0">\n'
        "  <channel>\n"
        f"    <title>{html.escape(meta['title'])}</title>\n"
        f"    <link>{html.escape(base_url)}</link>\n"
        f"    <description>{html.escape(meta['description'])}</description>\n"
        f"    <language>{meta['language']}</language>\n"
        f"    <lastBuildDate>{build_time_str}</lastBuildDate>\n"
        f"{joined_items}\n"
        "  </channel>\n"
        "</rss>\n"
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records = load_recent_records()
    build_time_str = datetime.now(TZ_TAIPEI).strftime("%a, %d %b %Y %H:%M:%S %z")

    for lang, meta in FEED_META.items():
        xml_content = render_rss_xml(lang, records, build_time_str)
        out_file = OUTPUT_DIR / meta["filename"]
        out_file.write_text(xml_content, encoding="utf-8")
        print(f"已產出 {out_file}（共 {len(records)} 篇，上限 {MAX_ITEMS} 篇）")


if __name__ == "__main__":
    main()
