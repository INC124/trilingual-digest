import os
import json
import asyncio
from datetime import datetime, timezone, timedelta
import google.generativeai as genai
import edge_tts

# 設定台灣時區 (UTC+8)
tz = timezone(timedelta(hours=8))
now = datetime.now(tz)
date_str = now.strftime("%Y-%m-%d")
date_display = now.strftime("%Y.%m.%d")
weekdays = ["一", "二", "三", "四", "五", "六", "日"]
weekday_str = weekdays[now.weekday()]

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.5-flash")

prompt = f"""
請為 {date_display} ({weekday_str}) 生成《Daily Trilingual Digest • 每日三語精選新聞》。
主題請選擇三個不同國家、溫馨有文化氣息或生活感的新聞短文（每篇約 3～4 句話）：
1. 英文 (en)
2. 日文 (ja)：注意！title_html 與 article_html 中的所有日文漢字都必須加上正上方振假名 <ruby>漢字<rt>かな</rt></ruby> 標籤；但 title_plain 與 article_plain 必須是「純日文（不含任何振假名或 HTML 標籤）」，供語音朗讀使用。
3. 越南文 (vi)

請嚴格以純 JSON 格式回覆（不要加 markdown 標記），結構如下：
{{
  "en": {{
    "tag": "ISSUE NO. 01 • 英文分類 • 中文主題",
    "title": "英文標題",
    "subtitle": "中文副標題",
    "article": "英文內文",
    "vocab": ["<strong>單字1</strong> (詞性)：中文解釋", "<strong>單字2</strong> (詞性)：中文解釋", "<strong>單字3</strong> (詞性)：中文解釋", "<strong>單字4</strong> (詞性)：中文解釋", "<strong>單字5</strong> (詞性)：中文解釋", "<strong>單字6</strong> (詞性)：中文解釋"],
    "translation": "<strong>中文標題</strong><br>中文全譯內文"
  }},
  "ja": {{
    "tag": "ISSUE NO. 02 • JAPAN CULTURE • 中文主題",
    "title_html": "含ruby標籤的日文標題",
    "title_plain": "純日文標題（無ruby）",
    "subtitle": "中文副標題",
    "article_html": "含ruby標籤的日文內文",
    "article_plain": "純日文內文（無ruby）",
    "vocab": ["<strong>詞彙1</strong>：中文解釋", "<strong>詞彙2</strong>：中文解釋", "<strong>詞彙3</strong>：中文解釋", "<strong>詞彙4</strong>：中文解釋", "<strong>詞彙5</strong>：中文解釋", "<strong>詞彙6</strong>：中文解釋"],
    "translation": "<strong>中文標題</strong><br>中文全譯內文"
  }},
  "vi": {{
    "tag": "ISSUE NO. 03 • VIETNAM LIFESTYLE • 中文主題",
    "title": "越南文標題",
    "subtitle": "中文副標題",
    "article": "越南文內文",
    "vocab": ["<strong>詞彙1</strong>：中文解釋", "<strong>詞彙2</strong>：中文解釋", "<strong>詞彙3</strong>：中文解釋", "<strong>詞彙4</strong>：中文解釋", "<strong>詞彙5</strong>：中文解釋", "<strong>詞彙6</strong>：中文解釋"],
    "translation": "<strong>中文標題</strong><br>中文全譯內文"
  }}
}}
"""

response = model.generate_content(prompt)
raw_text = response.text.strip()
if raw_text.startswith("```"):
    raw_text = raw_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

data = json.loads(raw_text)

# 自動生成三語真人發音 MP3
os.makedirs("audio", exist_ok=True)
async def make_audio():
    voices = {
        "en": ("en-US-JennyNeural", data["en"]["article"]),
        "ja": ("ja-JP-NanamiNeural", data["ja"]["article_plain"]),
        "vi": ("vi-VN-HoaiMyNeural", data["vi"]["article"])
    }
    for lang, (voice, text) in voices.items():
        communicate = edge_tts.Communicate(text, voice, rate="-8%")
        await communicate.save(f"audio/{date_str}-{lang}.mp3")

asyncio.run(make_audio())

# 生成當日 HTML 頁面（內建原生 MP3 播放器）
vocab_en = "\n".join([f"<li>{v}</li>" for v in data["en"]["vocab"]])
vocab_ja = "\n".join([f"<li>{v}</li>" for v in data["ja"]["vocab"]])
vocab_vi = "\n".join([f"<li>{v}</li>" for v in data["vi"]["vocab"]])

daily_html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Daily Trilingual Digest - {date_display}</title>
  <style>
    :root {{ --bg: #f4f5f7; --card: #ffffff; --text: #1f2937; --muted: #6b7280; --en: #2563eb; --ja: #dc2626; --vi: #059669; --border: #e5e7eb; }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans TC", sans-serif; background: var(--bg); color: var(--text); line-height: 1.7; padding: 16px; }}
    .container {{ max-width: 680px; margin: 0 auto; }}
    header {{ text-align: center; padding: 20px 0 12px; }}
    .nav-top {{ text-align: left; margin-bottom: 12px; }}
    .back-btn {{ text-decoration: none; color: var(--muted); font-size: 0.9rem; font-weight: 500; }}
    h1 {{ font-size: 1.5rem; margin-bottom: 4px; }}
    .date-badge {{ font-size: 0.9rem; color: var(--muted); }}
    input[type="radio"].lang-radio {{ display: none; }}
    .filter-bar {{ display: flex; justify-content: center; gap: 8px; margin: 14px 0 24px; flex-wrap: wrap; position: sticky; top: 10px; z-index: 10; background: rgba(244,245,247,0.92); backdrop-filter: blur(6px); padding: 8px; border-radius: 12px; }}
    .filter-btn {{ border: 1px solid var(--border); background: #fff; color: var(--text); padding: 8px 14px; border-radius: 20px; font-size: 0.9rem; font-weight: 600; cursor: pointer; user-select: none; }}
    #opt-all:checked ~ .filter-bar label[for="opt-all"], #opt-en:checked ~ .filter-bar label[for="opt-en"], #opt-ja:checked ~ .filter-bar label[for="opt-ja"], #opt-vi:checked ~ .filter-bar label[for="opt-vi"] {{ background: #1f2937; color: #fff; border-color: #1f2937; }}
    #opt-en:checked ~ .cards-wrapper .card:not([data-lang="en"]), #opt-ja:checked ~ .cards-wrapper .card:not([data-lang="ja"]), #opt-vi:checked ~ .cards-wrapper .card:not([data-lang="vi"]) {{ display: none; }}
    .card {{ background: var(--card); border-radius: 16px; padding: 24px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); border-top: 4px solid #ccc; }}
    .card[data-lang="en"] {{ border-top-color: var(--en); }}
    .card[data-lang="ja"] {{ border-top-color: var(--ja); }}
    .card[data-lang="vi"] {{ border-top-color: var(--vi); }}
    .tag {{ font-size: 0.75rem; font-weight: 700; color: var(--muted); margin-bottom: 8px; display: block; }}
    h2 {{ font-size: 1.25rem; line-height: 1.4; margin-bottom: 8px; }}
    .subtitle {{ font-size: 0.95rem; color: var(--muted); margin-bottom: 16px; padding-bottom: 14px; border-bottom: 1px solid var(--border); }}
    audio {{ width: 100%; height: 40px; margin: 8px 0 14px; border-radius: 20px; }}
    .section-label {{ font-size: 0.75rem; font-weight: 700; color: var(--muted); display: block; margin-top: 16px; }}
    .article-text {{ font-size: 1.05rem; margin-top: 6px; }}
    ruby rt {{ font-size: 0.6em; color: #555; }}
    .vocab-list {{ list-style: none; background: #f9fafb; padding: 14px 16px; border-radius: 10px; font-size: 0.95rem; margin-top: 8px; }}
    .vocab-list li {{ margin-bottom: 6px; }}
    .vocab-list li:last-child {{ margin-bottom: 0; }}
    .translation {{ font-size: 0.95rem; color: #374151; margin-top: 8px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="nav-top"><a href="index.html" class="back-btn">← 返回日期目錄</a></div>
    <header>
      <h1>Daily Trilingual Digest</h1>
      <div class="date-badge">{date_display} ({weekday_str}) • 每日三語精選新聞</div>
    </header>
    <input type="radio" name="lang" id="opt-all" class="lang-radio" checked>
    <input type="radio" name="lang" id="opt-en" class="lang-radio">
    <input type="radio" name="lang" id="opt-ja" class="lang-radio">
    <input type="radio" name="lang" id="opt-vi" class="lang-radio">
    <div class="filter-bar">
      <label for="opt-all" class="filter-btn">全部閱讀</label>
      <label for="opt-en" class="filter-btn">🇺🇸 英文</label>
      <label for="opt-ja" class="filter-btn">🇯🇵 日文</label>
      <label for="opt-vi" class="filter-btn">🇻🇳 越南文</label>
    </div>
    <div class="cards-wrapper">
      <article class="card" data-lang="en">
        <span class="tag">{data["en"]["tag"]}</span>
        <h2>{data["en"]["title"]}</h2>
        <p class="subtitle">{data["en"]["subtitle"]}</p>
        <span class="section-label">🔊 真人發音朗讀 • 英文</span>
        <audio controls preload="none" src="audio/{date_str}-en.mp3"></audio>
        <span class="section-label">ARTICLE • 英文報導</span>
        <p class="article-text">{data["en"]["article"]}</p>
        <span class="section-label">VOCABULARY & PHRASES 核心詞彙</span>
        <ul class="vocab-list">{vocab_en}</ul>
        <span class="section-label">TRANSLATION 中文全譯</span>
        <p class="translation">{data["en"]["translation"]}</p>
      </article>
      <article class="card" data-lang="ja">
        <span class="tag">{data["ja"]["tag"]}</span>
        <h2>{data["ja"]["title_html"]}</h2>
        <p class="subtitle">{data["ja"]["subtitle"]}</p>
        <span class="section-label">🔊 真人發音朗讀 • 日文</span>
        <audio controls preload="none" src="audio/{date_str}-ja.mp3"></audio>
        <span class="section-label">ARTICLE • 日文報導</span>
        <p class="article-text">{data["ja"]["article_html"]}</p>
        <span class="section-label">VOCABULARY & PHRASES 核心詞彙</span>
        <ul class="vocab-list">{vocab_ja}</ul>
        <span class="section-label">TRANSLATION 中文全譯</span>
        <p class="translation">{data["ja"]["translation"]}</p>
      </article>
      <article class="card" data-lang="vi">
        <span class="tag">{data["vi"]["tag"]}</span>
        <h2>{data["vi"]["title"]}</h2>
        <p class="subtitle">{data["vi"]["subtitle"]}</p>
        <span class="section-label">🔊 真人發音朗讀 • 越南文</span>
        <audio controls preload="none" src="audio/{date_str}-vi.mp3"></audio>
        <span class="section-label">ARTICLE • 越南文報導</span>
        <p class="article-text">{data["vi"]["article"]}</p>
        <span class="section-label">VOCABULARY & PHRASES 核心詞彙</span>
        <ul class="vocab-list">{vocab_vi}</ul>
        <span class="section-label">TRANSLATION 中文全譯</span>
        <p class="translation">{data["vi"]["translation"]}</p>
      </article>
    </div>
  </div>
</body>
</html>"""

with open(f"{date_str}.html", "w", encoding="utf-8") as f:
    f.write(daily_html)

# 更新 index.html 插入今日卡片
new_card = f"""      <!-- {date_display} -->
      <a href="{date_str}.html" class="digest-item">
        <div class="item-header">
          <span class="item-date">{date_display} ({weekday_str})</span>
          <span class="item-arrow">閱讀全文 →</span>
        </div>
        <ul class="topic-list">
          <li><span class="lang-badge bg-en">EN</span><div class="title-group"><span class="orig-title">{data["en"]["title"]}</span><span class="zh-title">{data["en"]["subtitle"]}</span></div></li>
