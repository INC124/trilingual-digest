import os
import re
import json
import random
import asyncio
import datetime
import pytz
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import edge_tts

# ==========================================
# 1. 基本環境與 API 設定
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("找不到 GEMINI_API_KEY 環境變數，請確認 GitHub Secrets 設定！")

genai.configure(api_key=GEMINI_API_KEY)

TZ = pytz.timezone("Asia/Taipei")
NOW = datetime.datetime.now(TZ)
TODAY_STR = NOW.strftime("%Y-%m-%d")
MONTH_DAY_ZH = f"{NOW.month}月{NOW.day}日"
MONTH_DAY_EN = NOW.strftime("%B %d")

OUTPUT_DIR = "docs"
AUDIO_DIR = os.path.join(OUTPUT_DIR, "audio")
ARCHIVE_DIR = os.path.join(OUTPUT_DIR, "archive")
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
}

# ==========================================
# 2. 三語多來源 RSS 設定池
# ==========================================
RSS_SOURCES = {
    "en": [
        {"name": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
        {"name": "AP News", "url": "https://feedx.net/rss/ap.xml"},
        {"name": "The Japan Times", "url": "https://www.japantimes.co.jp/feed/"},
        {"name": "The Japan News", "url": "https://japannews.yomiuri.co.jp/feed/"},
        {"name": "SoraNews24", "url": "https://soranews24.com/feed/"},
        {"name": "Unseen Japan", "url": "https://unseen-japan.com/feed/"},
        {"name": "Tokyo Weekender", "url": "https://www.tokyoweekender.com/japan-life/news-and-opinion/feed/"},
        {"name": "Spoon & Tamago", "url": "https://spoon-tamago.com/feed/"},
        {"name": "Vietnam News Society", "url": "https://vietnamnews.vn/rss/society.rss"},
        {"name": "FluentU Japanese", "url": "https://www.fluentu.com/blog/japanese/feed/"},
    ],
    "ja": [
        {"name": "NHK News", "url": "https://www3.nhk.or.jp/rss/news/cat0.xml"},
        {"name": "苫小牧民報", "url": "https://www.tomamin.co.jp/feed"},
        {"name": "KBS World 日文今日新聞", "url": "http://world.kbs.co.kr/rss/rss_news.htm?lang=j&today=Y"},
        {"name": "KBS World 日文文化", "url": "http://world.kbs.co.kr/rss/rss_news.htm?lang=j&id=Cu"},
    ],
    "vi": [
        {"name": "Tuổi Trẻ", "url": "https://tuoitre.vn/rss/tin-moi-nhat.rss"},
        {"name": "Người Việt", "url": "https://www.nguoi-viet.com/feed/"},
        {"name": "Thanh Niên", "url": "https://thanhnien.vn/rss/home.rss"},
        {"name": "Gia đình & Xã hội", "url": "https://giadinh.suckhoedoisong.vn/rss/home.rss"},
    ],
}

# 每日內容切角（結合當天真實新聞、歷史同月同日、生活文化與節慶小故事）
ANGLE_POOL = [
    {
        "name": "當日真實新聞與生活影響",
        "instruction": (
            f"從下方素材中挑選一則具體真實事件，寫出明確的人事時地物與它對一般人日常生活的影響，"
            f"避免空泛的總結或口號。"
        ),
    },
    {
        "name": "歷史上同月同日（{md_zh} / {md_en}）的真實事件或文化里程碑",
        "instruction": (
            f"優先結合「歷史上 {MONTH_DAY_ZH}（{MONTH_DAY_EN}）曾發生的真實事件、發明、文化作品或生活變遷」"
            f"（若素材中無直接關聯，可獨立選取歷史上 {MONTH_DAY_ZH} 確有記載的真實故事），"
            f"写出當時的具體場景與細節，並點出它與現代生活的連結。"
        ),
    },
    {
        "name": "貼近日常的生活文化與飲食小故事",
        "instruction": (
            f"從素材或在地文化脈絡中，聚焦一個具體的生活細節、街頭飲食、地方習慣或工藝設計，"
            f"描述人們實際怎麼做、在哪裡發生、有什麼獨特之處，讓讀者有身歷其境的畫面感。"
        ),
    },
    {
        "name": "節慶習俗、季節更迭與地方風情",
        "instruction": (
            f"結合 {MONTH_DAY_ZH} 前後的季節氛圍、傳統節慶習俗或素材中的地方活動，"
            f"具體描寫當地人如何準備、吃什麼、做什麼活動，避免只用形容詞讚美。"
        ),
    },
]

# ==========================================
# 3. RSS 素材抓取與抽樣
# ==========================================
def clean_html_text(raw_html: str, max_len: int = 280) -> str:
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
    if len(text) > max_len:
        text = text[:max_len].rstrip() + "..."
    return text


def fetch_single_rss(source_name: str, url: str, per_source_limit: int = 4) -> list:
    items = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"

        soup = BeautifulSoup(resp.text, "xml")
        entries = soup.find_all("item")
        if not entries:
            entries = soup.find_all("entry")

        for entry in entries[:per_source_limit]:
            title_tag = entry.find("title")
            desc_tag = entry.find("description") or entry.find("summary") or entry.find("content")
            title = clean_html_text(title_tag.get_text() if title_tag else "", max_len=140)
            desc = clean_html_text(desc_tag.get_text() if desc_tag else "", max_len=280)
            if title:
                items.append({
                    "source": source_name,
                    "title": title,
                    "summary": desc,
                })
    except Exception as e:
        print(f"⚠️ RSS 抓取略過 [{source_name}]: {e}")
    return items


def gather_rss_seeds() -> dict:
    seeds = {"en": [], "ja": [], "vi": []}
    for lang, source_list in RSS_SOURCES.items():
        pool = []
        for src in source_list:
            fetched = fetch_single_rss(src["name"], src["url"], per_source_limit=4)
            pool.extend(fetched)
        random.shuffle(pool)
        # 每次最多挑 8 則候選給模型挑選其中「最具體的一則」深入撰寫
        seeds[lang] = pool[:8]
        print(f"✅ [{lang.upper()}] 共取得 {len(pool)} 則素材，抽樣 {len(seeds[lang])} 則供寫作參考")
    return seeds


# ==========================================
# 4. 語言清洗與格式防呆
# ==========================================
def clean_vi_text(text: str) -> str:
    if not text:
        return ""
    # 移除意外夾雜的 CJK（中文/日文假名/漢字）與韓文字元
    text = re.sub(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]+", "", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def sanitize_vi_data(vi_obj: dict) -> dict:
    if not isinstance(vi_obj, dict):
        return vi_obj
    for key in ["title", "content", "audio_text"]:
        if key in vi_obj and isinstance(vi_obj[key], str):
            vi_obj[key] = clean_vi_text(vi_obj[key])
    if "vocab" in vi_obj and isinstance(vi_obj["vocab"], list):
        cleaned_vocab = []
        for item in vi_obj["vocab"]:
            if not isinstance(item, dict):
                continue
            item["word"] = clean_vi_text(item.get("word", ""))
            item["example"] = clean_vi_text(item.get("example", ""))
            cleaned_vocab.append(item)
        vi_obj["vocab"] = cleaned_vocab
    return vi_obj


def strip_ruby_tags(html_text: str) -> str:
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, "html.parser")
    for rt in soup.find_all(["rt", "rp"]):
        rt.decompose()
    return re.sub(r"\s+", " ", soup.get_text()).strip()


# ==========================================
# 5. Gemini 文章生成
# ==========================================
def generate_trilingual_digest(seeds: dict) -> dict:
    day_index = NOW.toordinal()
    angle = ANGLE_POOL[day_index % len(ANGLE_POOL)]
    angle_name = angle["name"].format(md_zh=MONTH_DAY_ZH, md_en=MONTH_DAY_EN)
    angle_instruction = angle["instruction"]

    # 偶爾讓日文或越文也能借鏡英文日本/越南文化專欄靈感（僅作題材靈感，輸出仍必須為純正目標語言）
    cross_inspiration = [s for s in seeds["en"] if s["source"] in {
        "SoraNews24", "Unseen Japan", "Tokyo Weekender", "Spoon & Tamago", "FluentU Japanese", "Vietnam News Society"
    }][:3]

    prompt = f"""
你是一位擅長說故事、觀察細膩的多語專欄作家與語言教練。今天是 {TODAY_STR}（{MONTH_DAY_ZH} / {MONTH_DAY_EN}）。
請為「Daily Trilingual Digest（每日三語精選）」撰寫今天的 **英文（en）、日文（ja）、越南文（vi）** 三篇短文。

### 今日寫作切角：{angle_name}
{angle_instruction}

### 核心寫作要求（務必嚴格遵守）：
1. **拒絕空泛與說教**：
   - 絕對不要寫「這展現了文化之美」「隨著時代變遷」「令人深思」這類空洞套話。
   - 每篇必須鎖定 **單一具體事件、歷史同月同日真實故事、或具體的生活/飲食/節慶場景**，寫出清楚的「誰、在哪裡、做了什麼、有什麼具體細節或有趣轉折」。
   - 若引用歷史上 {MONTH_DAY_ZH} 的事件，必須是真實確切的歷史事件，不可杜撰年份或虛構人物。
2. **篇幅設定（約 150 字左右）**：
   - **英文（en）`content`**：約 **130～165 個英文單字（words）**，分成 2 個自然段落，敘事流暢、有畫面感。
   - **日文（ja）`content`**：約 **160～220 個日文字元（含標點，不含 `<ruby>` 標籤字元）**，自然道地的書面生活敘事，分成 2 個段落。
   - **越南文（vi）`content`**：約 **130～170 個越南文詞（words）**，自然道地、貼近日常，分成 2 個段落。
   - **繁體中文全譯 `translation`**：每篇皆附通順自然的繁體中文翻譯，約 **150～200 個中文字**。
3. **三語題材互補、不要三篇寫同一件事**：
   - 英文篇可從英文素材池挑選國際新聞、設計藝術或跨文化故事（也可結合今日切角）。
   - 日文篇從日文素材池（或結合日本季節/生活/歷史同月同日切角）撰寫純正日文短文。
   - 越南文篇從越南文素材池（或結合越南生活飲食/節慶/歷史同月同日切角）撰寫純正越南文短文。
4. **日文標音規則（ja）**：
   - 日文 `content` 中的常用漢字請加上 `<ruby>漢字<rt>ふりがな</rt></ruby>` 標音（片假名、平假名與數字不需加 ruby）。
   - `audio_text` 則提供「完全不含 HTML 標籤」的純日文文本供 TTS 朗讀。
5. **越南文純淨度規則（vi）**：
   - 越南文 `title`、`content`、`audio_text`、`vocab.word`、`vocab.example` **必須 100% 為純正越南文**，嚴禁夾雜任何中文字、日文假名或無關英文單字。
6. **精選詞彙（vocab）**：
   - 每種語言挑出 **4 個** 最值得學習的關鍵詞彙或片語，附上詞性（`pos`：如 n. / v. / adj. / adv. / phr.）、繁體中文釋義（`meaning`），以及一句與本文情境相關的短例句（`example`）與例句中文翻譯（`example_zh`）。

### 參考素材池（請從中挑選最具體的一則發揮，勿將多則硬湊成大雜燴）：
- **英文素材（EN Seeds）**：
{json.dumps(seeds["en"], ensure_ascii=False, indent=2)}

- **日文素材（JA Seeds）**：
{json.dumps(seeds["ja"], ensure_ascii=False, indent=2)}

- **越南文素材（VI Seeds）**：
{json.dumps(seeds["vi"], ensure_ascii=False, indent=2)}

- **亞洲生活文化補充靈感（僅供題材參考，請轉寫為對應目標語言）**：
{json.dumps(cross_inspiration, ensure_ascii=False, indent=2)}

### 輸出格式（必須為合法 JSON，勿加 Markdown 程式碼區塊以外的多餘說明）：
{{
  "date": "{TODAY_STR}",
  "angle": "{angle_name}",
  "en": {{
    "source_note": "參考來源名稱或歷史主題",
    "title": "具體有吸引力的英文標題",
    "content": "約 130-165 英文單字的正文（可用 \\n\\n 分兩段）",
    "audio_text": "供朗讀的純英文正文",
    "translation": "約 150-200 字的流暢繁體中文全譯",
    "vocab": [
      {{
        "word": "單字或片語",
        "pos": "n.",
        "meaning": "繁體中文釋義",
        "example": "英文例句",
        "example_zh": "例句繁體中文翻譯"
      }}
    ]
  }},
  "ja": {{
    "source_note": "參考來源名稱或歷史主題",
    "title": "具體有吸引力的日文標題（純文字，不加 ruby）",
    "content": "約 160-220 字元的日文正文（漢字附 <ruby>漢<rt>かん</rt></ruby> 標音，可用 \\n\\n 分兩段）",
    "audio_text": "供朗讀的純日文正文（不含任何 HTML 標籤）",
    "translation": "約 150-200 字的流暢繁體中文全譯",
    "vocab": [
      {{
        "word": "日文單字（可附假名讀音）",
        "pos": "名詞",
        "meaning": "繁體中文釋義",
        "example": "日文例句（純文字）",
        "example_zh": "例句繁體中文翻譯"
      }}
    ]
  }},
  "vi": {{
    "source_note": "參考來源名稱或歷史主題",
    "title": "具體有吸引力的純正越南文標題",
    "content": "約 130-170 詞的純正越南文正文（可用 \\n\\n 分兩段）",
    "audio_text": "供朗讀的純正越南文正文",
    "translation": "約 150-200 字的流暢繁體中文全譯",
    "vocab": [
      {{
        "word": "純正越南文單字或片語",
        "pos": "n.",
        "meaning": "繁體中文釋義",
        "example": "純正越南文例句",
        "example_zh": "例句繁體中文翻譯"
      }}
    ]
  }}
}}
"""

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        generation_config={
            "temperature": 0.75,
            "response_mime_type": "application/json",
        },
    )

    response = model.generate_content(prompt)
    raw_text = response.text.strip()
    raw_text = re.sub(r"^```json\s*|\s*```$", "", raw_text, flags=re.IGNORECASE).strip()
    data = json.loads(raw_text)

    # 後處理清洗
    if "ja" in data:
        if not data["ja"].get("audio_text"):
            data["ja"]["audio_text"] = strip_ruby_tags(data["ja"].get("content", ""))
        else:
            data["ja"]["audio_text"] = strip_ruby_tags(data["ja"]["audio_text"])

    if "vi" in data:
        data["vi"] = sanitize_vi_data(data["vi"])
        if not data["vi"].get("audio_text"):
            data["vi"]["audio_text"] = clean_vi_text(data["vi"].get("content", ""))

    return data


# ==========================================
# 6. Edge-TTS 語音生成
# ==========================================
VOICE_MAP = {
    "en": "en-US-JennyNeural",
    "ja": "ja-JP-NanamiNeural",
    "vi": "vi-VN-HoaiMyNeural",
}


async def synthesize_all_audio(data: dict):
    for lang, voice in VOICE_MAP.items():
        lang_obj = data.get(lang, {})
        text = lang_obj.get("audio_text") or strip_ruby_tags(lang_obj.get("content", ""))
        if not text:
            continue
        out_path = os.path.join(AUDIO_DIR, f"{TODAY_STR}_{lang}.mp3")
        try:
            communicate = edge_tts.Communicate(text, voice, rate="-5%")
            await communicate.save(out_path)
            print(f"🔊 語音生成完成: {out_path}")
        except Exception as e:
            print(f"⚠️ 語音生成失敗 [{lang}]: {e}")


# ==========================================
# 7. HTML 頁面與互動模組渲染
# ==========================================
ENGAGEMENT_SNIPPET = """
<!-- Firestore 讀者互動與熱門統計模組 -->
<script type="module">
  import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
  import { getFirestore, doc, getDoc, setDoc, updateDoc, increment } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

  const firebaseConfig = window.__FIREBASE_CONFIG__ || null;
  if (firebaseConfig) {
    const app = initializeApp(firebaseConfig);
    const db = getFirestore(app);
    const articleId = document.body.dataset.articleDate;
    if (articleId) {
      const ref = doc(db, "digest_stats", articleId);
      const viewKey = `viewed_${articleId}`;
      if (!localStorage.getItem(viewKey)) {
        localStorage.setItem(viewKey, "1");
        setDoc(ref, { views: increment(1), date: articleId }, { merge: true }).catch(() => {});
      }
      getDoc(ref).then((snap) => {
        if (snap.exists()) {
          const d = snap.data();
          const vEl = document.getElementById("stat-views");
          const lEl = document.getElementById("stat-likes");
          if (vEl) vEl.textContent = d.views || 0;
          if (lEl) lEl.textContent = d.likes || 0;
        }
      }).catch(() => {});

      const likeBtn = document.getElementById("btn-like");
      if (likeBtn) {
        const likeKey = `liked_${articleId}`;
        if (localStorage.getItem(likeKey)) likeBtn.classList.add("liked");
        likeBtn.addEventListener("click", async () => {
          if (localStorage.getItem(likeKey)) return;
          localStorage.setItem(likeKey, "1");
          likeBtn.classList.add("liked");
          const lEl = document.getElementById("stat-likes");
          if (lEl) lEl.textContent = (parseInt(lEl.textContent || "0", 10) + 1);
          await setDoc(ref, { likes: increment(1), date: articleId }, { merge: true }).catch(() => {});
        });
      }
    }
  }
</script>
"""


def format_paragraphs(text: str) -> str:
    parts = [p.strip() for p in text.split("\n") if p.strip()]
    return "".join(f"<p>{p}</p>" for p in parts)


def render_lang_section(lang_code: str, lang_label: str, section: dict, audio_rel_path: str) -> str:
    vocab_html = ""
    for v in section.get("vocab", []):
        vocab_html += f"""
        <li>
          <div class="vocab-head">
            <span class="vocab-word">{v.get('word', '')}</span>
            <span class="vocab-pos">{v.get('pos', '')}</span>
            <span class="vocab-meaning">{v.get('meaning', '')}</span>
          </div>
          <div class="vocab-ex">{v.get('example', '')}</div>
          <div class="vocab-ex-zh">{v.get('example_zh', '')}</div>
        </li>
        """

    source_badge = f"<span class='source-tag'>素材：{section.get('source_note', '')}</span>" if section.get("source_note") else ""

    return f"""
    <section class="lang-card" id="sec-{lang_code}">
      <div class="lang-header">
        <span class="lang-badge">{lang_label}</span>
        {source_badge}
      </div>
      <h2>{section.get('title', '')}</h2>
      <audio controls preload="none" src="{audio_rel_path}"></audio>
      <div class="article-body">
        {format_paragraphs(section.get('content', ''))}
      </div>
      <details class="translation-box" open>
        <summary>繁體中文全譯</summary>
        <div class="translation-text">
          {format_paragraphs(section.get('translation', ''))}
        </div>
      </details>
      <div class="vocab-box">
        <h3>重點詞彙</h3>
        <ul class="vocab-list">{vocab_html}</ul>
      </div>
    </section>
    """


def build_article_html(data: dict, is_archive: bool = False) -> str:
    audio_prefix = "../audio" if is_archive else "audio"
    home_link = "../index.html" if is_archive else "index.html"

    en_html = render_lang_section("en", "English 英文", data["en"], f"{audio_prefix}/{TODAY_STR}_en.mp3")
    ja_html = render_lang_section("ja", "日本語 日文", data["ja"], f"{audio_prefix}/{TODAY_STR}_ja.mp3")
    vi_html = render_lang_section("vi", "Tiếng Việt 越南文", data["vi"], f"{audio_prefix}/{TODAY_STR}_vi.mp3")

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Daily Trilingual Digest - {TODAY_STR}</title>
  <style>
    :root {{
      --bg: #f8f9fa; --card: #ffffff; --text: #1f2937; --muted: #6b7280;
      --accent: #2563eb; --border: #e5e7eb; --vocab-bg: #f3f4f6;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #111827; --card: #1f2937; --text: #f3f4f6; --muted: #9ca3af;
        --accent: #60a5fa; --border: #374151; --vocab-bg: #273244;
      }}
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans TC", sans-serif;
      background: var(--bg); color: var(--text); margin: 0; padding: 16px; line-height: 1.75;
    }}
    .container {{ max-width: 780px; margin: 0 auto; }}
    header {{ margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 12px; }}
    .top-nav {{ display: flex; justify-content: space-between; align-items: center; font-size: 0.92rem; }}
    .top-nav a {{ color: var(--accent); text-decoration: none; }}
    h1 {{ font-size: 1.5rem; margin: 8px 0 4px; }}
    .meta {{ color: var(--muted); font-size: 0.9rem; display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }}
    .lang-card {{
      background: var(--card); border: 1px solid var(--border); border-radius: 12px;
      padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }}
    .lang-header {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }}
    .lang-badge {{
      background: var(--accent); color: #fff; font-size: 0.8rem; font-weight: 600;
      padding: 2px 10px; border-radius: 999px;
    }}
    .source-tag {{ font-size: 0.8rem; color: var(--muted); }}
    h2 {{ font-size: 1.25rem; margin: 12px 0; }}
    audio {{ width: 100%; margin: 8px 0 14px; height: 38px; }}
    .article-body p {{ margin: 0 0 12px; font-size: 1.05rem; }}
    ruby rt {{ font-size: 0.62em; color: var(--muted); }}
    .translation-box {{
      background: var(--vocab-bg); border-radius: 8px; padding: 10px 14px; margin: 14px 0;
    }}
    .translation-box summary {{ cursor: pointer; font-weight: 600; font-size: 0.95rem; }}
    .translation-text p {{ margin: 8px 0 0; color: var(--text); font-size: 0.96rem; }}
    .vocab-box h3 {{ font-size: 1rem; margin: 14px 0 8px; }}
    .vocab-list {{ list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }}
    .vocab-list li {{ background: var(--vocab-bg); padding: 10px 12px; border-radius: 8px; }}
    .vocab-head {{ display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; }}
    .vocab-word {{ font-weight: 700; color: var(--accent); }}
    .vocab-pos {{ font-size: 0.8rem; color: var(--muted); }}
    .vocab-meaning {{ font-weight: 600; }}
    .vocab-ex {{ font-size: 0.92rem; margin-top: 4px; }}
    .vocab-ex-zh {{ font-size: 0.86rem; color: var(--muted); }}
    .engage-bar {{
      display: flex; gap: 14px; align-items: center; justify-content: flex-end;
      padding: 12px 0 24px; font-size: 0.92rem; color: var(--muted);
    }}
    #btn-like {{
      border: 1px solid var(--border); background: var(--card); color: var(--text);
      padding: 6px 14px; border-radius: 999px; cursor: pointer; font-size: 0.92rem;
    }}
    #btn-like.liked {{ border-color: #ef4444; color: #ef4444; font-weight: 600; }}
  </style>
</head>
<body data-article-date="{TODAY_STR}">
  <div class="container">
    <header>
      <div class="top-nav">
        <a href="{home_link}">← 返回首頁與歷史總覽</a>
        <span>{TODAY_STR}</span>
      </div>
      <h1>Daily Trilingual Digest 每日三語精選</h1>
      <div class="meta">
        <span>今日切角：{data.get('angle', '')}</span>
        <span>• 閱讀 <strong id="stat-views">-</strong></span>
      </div>
    </header>

    {en_html}
    {ja_html}
    {vi_html}

    <div class="engage-bar">
      <button id="btn-like" type="button">❤️ 喜歡這篇 (<span id="stat-likes">0</span>)</button>
    </div>
  </div>
  {ENGAGEMENT_SNIPPET}
</body>
</html>
"""


def update_manifest_and_pages(data: dict):
    # 1. 儲存今日 JSON 供 LINE 推播與歷史索引使用
    latest_json_path = os.path.join(OUTPUT_DIR, "latest.json")
    with open(latest_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    archive_json_path = os.path.join(ARCHIVE_DIR, f"{TODAY_STR}.json")
    with open(archive_json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 2. 儲存歷史歸檔 HTML
    archive_html_path = os.path.join(ARCHIVE_DIR, f"{TODAY_STR}.html")
    with open(archive_html_path, "w", encoding="utf-8") as f:
        f.write(build_article_html(data, is_archive=True))

    # 3. 更新歷史目錄 manifest.json（保留既有歷史紀錄並加上今日）
    manifest_path = os.path.join(OUTPUT_DIR, "manifest.json")
    manifest = []
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception:
            manifest = []

    manifest = [m for m in manifest if m.get("date") != TODAY_STR]
    manifest.insert(0, {
        "date": TODAY_STR,
        "angle": data.get("angle", ""),
        "en_title": data.get("en", {}).get("title", ""),
        "ja_title": data.get("ja", {}).get("title", ""),
        "vi_title": data.get("vi", {}).get("title", ""),
        "url": f"archive/{TODAY_STR}.html",
    })
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # 4. 同步寫出今日最新頁面 today.html（若你的 index.html 為動態讀取 manifest/latest.json 的看板首頁，則不會被覆蓋；若不存在 index.html 則一併建立）
    today_html_path = os.path.join(OUTPUT_DIR, "today.html")
    with open(today_html_path, "w", encoding="utf-8") as f:
        f.write(build_article_html(data, is_archive=False))

    index_html_path = os.path.join(OUTPUT_DIR, "index.html")
    if not os.path.exists(index_html_path):
        with open(index_html_path, "w", encoding="utf-8") as f:
            f.write(build_article_html(data, is_archive=False))


# ==========================================
# 8. 主程式進入點
# ==========================================
async def main():
    print(f"🚀 開始執行 Daily Trilingual Digest 生成流程 ({TODAY_STR})...")
    seeds = gather_rss_seeds()
    data = generate_trilingual_digest(seeds)
    await synthesize_all_audio(data)
    update_manifest_and_pages(data)
    print("🎉 今日三語精選、音檔與歸檔更新完成！")


if __name__ == "__main__":
    asyncio.run(main())
