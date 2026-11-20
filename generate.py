import asyncio
import json
import os
import random
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import edge_tts

# 依穩定度與能力排列模型，避免單一模型逾時拖慢整體執行
MODELS = [
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
]

MAX_ATTEMPTS_PER_MODEL = 3

THEME_POOL = [
    "當地生活與日常習慣",
    "文化與藝術傳統",
    "國際趣聞與跨國交流",
    "飲食、旅遊與城市風景",
]

now = datetime.now(timezone(timedelta(hours=8)))
d_str = now.strftime("%Y-%m-%d")
d_disp = now.strftime("%Y.%m.%d")
w_str = ["一", "二", "三", "四", "五", "六", "日"][now.weekday()]


def fetch_rss_seeds(limit: int = 6) -> list[str]:
    """抓取公開 RSS 標題與摘要作為真實素材參考（失敗時回傳空清單）"""
    rss_urls = [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www3.nhk.or.jp/rss/news/cat0.xml",
    ]
    seeds = []
    for url in rss_urls:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (TrilingualDigestBot/1.0)"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                xml_data = resp.read()
            root = ET.fromstring(xml_data)
            for item in root.findall(".//item")[:limit]:
                title = (item.findtext("title") or "").strip()
                desc = re.sub(r"<[^>]+>", "", item.findtext("description") or "").strip()
                if title:
                    seeds.append(f"- {title}：{desc[:120]}")
        except Exception as e:
            print(f"[WARN] 抓取 RSS 素材失敗 ({url}): {e}")
    return seeds[:limit]


rng = random.Random(d_str)
daily_themes = {
    "en": rng.choice(THEME_POOL),
    "ja": rng.choice(THEME_POOL),
    "vi": rng.choice(THEME_POOL + ["越南生活文化與國際連結"]),
}
print(
    f"[INFO] 今日隨機主題分配 -> EN: {daily_themes['en']} | "
    f"JA: {daily_themes['ja']} | VI: {daily_themes['vi']}"
)

seeds = fetch_rss_seeds(limit=6)
seed_block = (
    "以下為今日參考的真實新聞/文化素材，請優先挑選適合生活、文化或國際趣聞的題材改寫（每篇約3~4句）：\n"
    + "\n".join(seeds)
    if seeds
    else "今日未取得外部新聞列表，請撰寫貼近真實日常的生活文化短文（每篇約3~4句）。"
)

prompt = f"""為 {d_disp} ({w_str}) 生成三則短文（每篇約3~4句），涵蓋國際、生活與文化面向：英文(en)、日文(ja)、越南文(vi)。
今日主題方向建議：
- 英文(en)：{daily_themes['en']}
- 日文(ja)：{daily_themes['ja']}
- 越南文(vi)：{daily_themes['vi']}（兼顧越南生活/文化，並適度融入近年越南的國際連結或交流視角，風格自然易讀）

{seed_block}

規則：
1. 事實與防腦補：若有提供參考素材，請優先依據素材改寫；若缺乏特定細節，請以真實日常與文化角度描述，嚴禁自行編造未提及的具體數字、統計、得獎紀錄或虛構事件。
2. 日文 title_html、article_html 與 vocab 中的所有漢字皆須加 <ruby>漢字<rt>かな</rt></ruby>；title_plain 與 article_plain 為純日文無標籤。
3. 三種語言的 vocab 陣列各提供 6 個核心詞彙，每個詞彙皆須明確標註詞性（英文用 (n.)/(v.)/(adj.)/(phr.) 等，日文與越南文用 (名詞)/(動詞)/(形容詞)/(片語) 等），格式如 "<strong>詞彙</strong> (詞性)：中文解釋"。
4. 越南文 (vi) 的 title、article 與 vocab 中每個詞彙的詞彙本體（<strong>...</strong> 內）必須是純越南文，嚴禁夾雜任何中文字；中文只能出現在 subtitle、詞彙冒號後的中文解釋與 translation 中。
嚴格回傳純 JSON（無 markdown）：
{{"en":{{"tag":"ISSUE NO. 01 • {daily_themes['en']}","title":"英文標題","subtitle":"中文副標","article":"英文內文","vocab":["<strong>word</strong> (n.)：解釋","<strong>word2</strong> (v.)：解釋","<strong>word3</strong> (adj.)：解釋","<strong>word4</strong> (phr.)：解釋","<strong>word5</strong> (n.)：解釋","<strong>word6</strong> (v.)：解釋"],"translation":"<strong>中文標題</strong><br>中文全譯"}},"ja":{{"tag":"ISSUE NO. 02 • {daily_themes['ja']}","title_html":"含ruby標題","title_plain":"純日文標題","subtitle":"中文副標","article_html":"含ruby內文","article_plain":"純日文內文","vocab":["<strong><ruby>詞<rt>かな</rt></ruby></strong> (名詞)：解釋","<strong>詞2</strong> (動詞)：解釋","<strong>詞3</strong> (形容詞)：解釋","<strong>詞4</strong> (名詞)：解釋","<strong>詞5</strong> (動詞)：解釋","<strong>詞6</strong> (片語)：解釋"],"translation":"<strong>中文標題</strong><br>中文全譯"}},"vi":{{"tag":"ISSUE NO. 03 • {daily_themes['vi']}","title":"越南文標題","subtitle":"中文副標","article":"越南文內文","vocab":["<strong>từ 1</strong> (名詞)：解釋","<strong>từ 2</strong> (動詞)：解釋","<strong>từ 3</strong> (形容詞)：解釋","<strong>từ 4</strong> (片語)：解釋","<strong>từ 5</strong> (名詞)：解釋","<strong>từ 6</strong> (動詞)：解釋"],"translation":"<strong>中文標題</strong><br>中文全譯"}}}}"""


def clean_vi_text(text: str) -> str:
    if not isinstance(text, str):
        return text
    cleaned = text
    # 常見越中混字防呆：例如「thủ都」應為「thủ đô」
    cleaned = re.sub(r"\bthủ都\b", "thủ đô", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("thủ都", "thủ đô")
    # 移除其餘誤混在純越南文欄位中的中文字
    cleaned = re.sub(r"[\u4e00-\u9fff]+", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def sanitize_vi_data(vi_obj: dict) -> dict:
    if not isinstance(vi_obj, dict):
        return vi_obj

    for field in ("title", "article"):
        if field in vi_obj and isinstance(vi_obj[field], str):
            original = vi_obj[field]
            fixed = clean_vi_text(original)
            if fixed != original:
                print(f"[WARN] 越南文 {field} 觸發防呆清理：'{original}' -> '{fixed}'")
                vi_obj[field] = fixed

    if isinstance(vi_obj.get("vocab"), list):
        new_vocab = []
        for item in vi_obj["vocab"]:
            if isinstance(item, str):
                fixed_item = re.sub(
                    r"(<strong>)(.*?)(</strong>)",
                    lambda m: m.group(1) + clean_vi_text(m.group(2)) + m.group(3),
                    item,
                    count=1,
                )
                if fixed_item != item:
                    print(f"[WARN] 越南文詞彙觸發防呆清理：'{item}' -> '{fixed_item}'")
                new_vocab.append(fixed_item)
            else:
                new_vocab.append(item)
        vi_obj["vocab"] = new_vocab

    return vi_obj


def clean_json_text(raw_text: str) -> str:
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return text


def call_single_model(api_key: str, model_name: str, prompt_text: str) -> str:
    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore

        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt_text,
            config=types.GenerateContentConfig(
                temperature=0.7,
                response_mime_type="application/json",
            ),
        )
        return (getattr(resp, "text", None) or "").strip()
    except ImportError:
        import google.generativeai as genai_legacy  # type: ignore

        genai_legacy.configure(api_key=api_key)
        legacy_model = genai_legacy.GenerativeModel(
            model_name,
            generation_config=genai_legacy.GenerationConfig(
                temperature=0.7,
                response_mime_type="application/json",
            ),
        )
        resp = legacy_model.generate_content(prompt_text)
        return (getattr(resp, "text", None) or "").strip()


def generate_digest_data(prompt_text: str) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("找不到環境變數 GEMINI_API_KEY")

    last_error = None

    for model_name in MODELS:
        for attempt in range(1, MAX_ATTEMPTS_PER_MODEL + 1):
            try:
                print(f"[INFO] 嘗試使用模型：{model_name}（第 {attempt}/{MAX_ATTEMPTS_PER_MODEL} 次）")
                raw = call_single_model(api_key, model_name, prompt_text)
                if not raw:
                    raise RuntimeError(f"模型 {model_name} 回傳空白內容")

                cleaned = clean_json_text(raw)
                parsed = json.loads(cleaned)

                for lang_key in ("en", "ja", "vi"):
                    if lang_key not in parsed:
                        raise ValueError(f"回傳 JSON 缺少欄位：{lang_key}")

                parsed["vi"] = sanitize_vi_data(parsed["vi"])
                print(f"[SUCCESS] 已成功透過 {model_name} 取得並解析三語新聞資料")
                return parsed

            except Exception as e:
                last_error = e
                err_str = str(e)
                print(f"[WARN] 模型 {model_name}（第 {attempt} 次）發生錯誤：{err_str}")

                is_model_not_found = (
                    "404" in err_str
                    or "no longer available" in err_str.lower()
                    or "not found" in err_str.lower()
                )
                is_daily_quota = (
                    "PerDay" in err_str
                    or "Daily" in err_str
                    or "quota_value" in err_str
                    or bool(re.search(r"seconds:\s*\d{4,}", err_str))
                )

                if is_model_not_found:
                    print(f"[INFO] {model_name} 無法使用或已下線，立即切換下一個模型...")
                    break

                if is_daily_quota:
                    print(f"[INFO] {model_name} 疑似已達每日配額上限，立即切換下一個模型...")
                    break

                if attempt < MAX_ATTEMPTS_PER_MODEL:
                    sleep_sec = 3 * attempt
                    print(f"[INFO] 等待 {sleep_sec} 秒後重試 {model_name}...")
                    time.sleep(sleep_sec)
                    continue

                print(f"[INFO] {model_name} 已達最大重試次數，切換下一個模型...")
                break

    raise RuntimeError(f"所有候選模型皆無法成功生成資料，最後錯誤：{last_error}")


data = generate_digest_data(prompt)
print(
    f"[INFO] 標題預覽 -> EN: {data['en']['title']} | "
    f"JA: {data['ja']['title_plain']} | VI: {data['vi']['title']}"
)

os.makedirs("audio", exist_ok=True)


async def make_audio():
    v_map = {
        "en": ("en-US-JennyNeural", data["en"]["article"]),
        "ja": ("ja-JP-NanamiNeural", data["ja"]["article_plain"]),
        "vi": ("vi-VN-HoaiMyNeural", data["vi"]["article"]),
    }
    for k, (v, t) in v_map.items():
        await edge_tts.Communicate(t, v, rate="-8%").save(f"audio/{d_str}-{k}.mp3")
        await asyncio.sleep(0.5)


asyncio.run(make_audio())


def make_card(lang, title, sub, art, voc, trans, label):
    v_li = "".join([f"<li>{x}</li>" for x in voc])
    return (
        f'<article class="card" data-lang="{lang}">'
        f'<span class="tag">{data[lang]["tag"]}</span>'
        f"<h2>{title}</h2>"
        f'<p class="subtitle">{sub}</p>'
        f'<span class="section-label">🔊 真人發音朗讀 • {label}</span>'
        f'<audio controls preload="none" src="audio/{d_str}-{lang}.mp3"></audio>'
        f'<span class="section-label">ARTICLE • {label}報導</span>'
        f'<p class="article-text">{art}</p>'
        f'<span class="section-label">VOCABULARY & PHRASES 核心詞彙</span>'
        f'<ul class="vocab-list">{v_li}</ul>'
        f'<span class="section-label">TRANSLATION 中文全譯</span>'
        f'<p class="translation">{trans}</p>'
        f"</article>"
    )


cards_html = (
    make_card("en", data["en"]["title"], data["en"]["subtitle"], data["en"]["article"], data["en"]["vocab"], data["en"]["translation"], "英文")
    + make_card("ja", data["ja"]["title_html"], data["ja"]["subtitle"], data["ja"]["article_html"], data["ja"]["vocab"], data["ja"]["translation"], "日文")
    + make_card("vi", data["vi"]["title"], data["vi"]["subtitle"], data["vi"]["article"], data["vi"]["vocab"], data["vi"]["translation"], "越南文")
)

css = ':root{--bg:#f4f5f7;--card:#fff;--text:#1f2937;--muted:#6b7280;--en:#2563eb;--ja:#dc2626;--vi:#059669;--border:#e5e7eb}*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans TC",sans-serif;background:var(--bg);color:var(--text);line-height:1.7;padding:16px}.container{max-width:680px;margin:0 auto}header{text-align:center;padding:20px 0 12px}.nav-top{text-align:left;margin-bottom:12px}.back-btn{text-decoration:none;color:var(--muted);font-size:.9rem;font-weight:500}h1{font-size:1.5rem;margin-bottom:4px}.date-badge{font-size:.9rem;color:var(--muted)}input.lang-radio{display:none}.filter-bar{display:flex;justify-content:center;gap:8px;margin:14px 0 24px;flex-wrap:wrap;position:sticky;top:10px;z-index:10;background:rgba(244,245,247,.92);backdrop-filter:blur(6px);padding:8px;border-radius:12px}.filter-btn{border:1px solid var(--border);background:#fff;color:var(--text);padding:8px 14px;border-radius:20px;font-size:.9rem;font-weight:600;cursor:pointer}#opt-all:checked~.filter-bar label[for="opt-all"],#opt-en:checked~.filter-bar label[for="opt-en"],#opt-ja:checked~.filter-bar label[for="opt-ja"],#opt-vi:checked~.filter-bar label[for="opt-vi"]{background:#1f2937;color:#fff;border-color:#1f2937}#opt-en:checked~.cards-wrapper .card:not([data-lang="en"]),#opt-ja:checked~.cards-wrapper .card:not([data-lang="ja"]),#opt-vi:checked~.cards-wrapper .card:not([data-lang="vi"]){display:none}.card{background:var(--card);border-radius:16px;padding:24px;margin-bottom:24px;box-shadow:0 2px 8px rgba(0,0,0,.04);border-top:4px solid #ccc}.card[data-lang="en"]{border-top-color:var(--en)}.card[data-lang="ja"]{border-top-color:var(--ja)}.card[data-lang="vi"]{border-top-color:var(--vi)}.tag{font-size:.75rem;font-weight:700;color:var(--muted);margin-bottom:8px;display:block}h2{font-size:1.25rem;line-height:1.4;margin-bottom:8px}.subtitle{font-size:.95rem;color:var(--muted);margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid var(--border)}audio{width:100%;height:40px;margin:8px 0 14px;border-radius:20px}.section-label{font-size:.75rem;font-weight:700;color:var(--muted);display:block;margin-top:16px}.article-text{font-size:1.05rem;margin-top:6px;text-align:justify}ruby rt{font-size:.6em;color:#555}.vocab-list{list-style:none;background:#f9fafb;padding:14px 16px;border-radius:10px;font-size:.95rem;margin-top:8px}.vocab-list li{margin-bottom:6px}.translation{font-size:.95rem;color:#374151;margin-top:8px;text-align:justify}'

ENGAGEMENT_SNIPPET = """<style>.digest-engage-bar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:18px;padding-top:14px;border-top:1px dashed var(--border);font-size:.9rem;color:var(--muted)}.digest-views{display:inline-flex;align-items:center;gap:4px}.digest-like-btn{display:inline-flex;align-items:center;gap:6px;padding:6px 14px;border-radius:999px;border:1px solid var(--border);background:#fff;color:var(--text);font-size:.9rem;font-weight:600;cursor:pointer;transition:all .15s ease}.digest-like-btn:hover{border-color:#ef4444;color:#ef4444}.digest-like-btn.liked{background:#fef2f2;border-color:#ef4444;color:#dc2626}</style><script type="module">
  import { initializeApp } from "https://www.gstatic.com/firebasejs/11.0.1/firebase-app.js";
  import {
    getFirestore,
    doc,
    getDoc,
    runTransaction
  } from "https://www.gstatic.com/firebasejs/11.0.1/firebase-firestore.js";

  const firebaseConfig = {
    apiKey: "AIzaSyBKzdhel0LCAXv9qoGOdVMQ_K_KhBRpdzk",
    authDomain: "personal-account-124.firebaseapp.com",
    projectId: "personal-account-124",
    storageBucket: "personal-account-124.firebasestorage.app",
    messagingSenderId: "531857933748",
    appId: "1:531857933748:web:e7d6afe199bf507f885ee1",
    measurementId: "G-Z9MVZ43E4J"
  };

  const app = initializeApp(firebaseConfig);
  const db = getFirestore(app);

  const urlParams = new URLSearchParams(window.location.search);
  const presetLang = urlParams.get("lang");
  if (["en", "ja", "vi"].includes(presetLang)) {
    const radio = document.getElementById(`opt-${presetLang}`);
    if (radio) radio.checked = true;
  }

  function getArticleDate() {
    const fileMatch = window.location.pathname.match(/(\\d{4}-\\d{2}-\\d{2})\\.html$/);
    if (fileMatch) return fileMatch[1];

    const titleMatch = document.title.match(/(\\d{4})\\.(\\d{2})\\.(\\d{2})/);
    if (titleMatch) return `${titleMatch[1]}-${titleMatch[2]}-${titleMatch[3]}`;

    return new Date().toISOString().slice(0, 10);
  }

  function getCleanHeadingText(card) {
    const h2 = card.querySelector("h2");
    if (!h2) return "";
    const clone = h2.cloneNode(true);
    clone.querySelectorAll("rt").forEach((rt) => rt.remove());
    return clone.textContent.replace(/\\s+/g, " ").trim();
  }

  function calcScore(likes, views) {
    return (Number(likes) || 0) * 5 + (Number(views) || 0);
  }

  const dateStr = getArticleDate();
  const cards = document.querySelectorAll(".cards-wrapper .card[data-lang]");

  cards.forEach((card) => {
    const lang = card.getAttribute("data-lang");
    if (!["en", "ja", "vi"].includes(lang)) return;

    const docId = `${dateStr}_${lang}`;
    const docRef = doc(db, "digest_articles", docId);
    const viewedKey = `digest_viewed_${docId}`;
    const likedKey = `digest_liked_${docId}`;

    const title = getCleanHeadingText(card);
    const subtitle = card.querySelector(".subtitle")?.textContent.trim() || "";
    const articleUrl = `${dateStr}.html?lang=${lang}`;

    const bar = document.createElement("div");
    bar.className = "digest-engage-bar";

    const viewsSpan = document.createElement("span");
    viewsSpan.className = "digest-views";
    viewsSpan.textContent = "👁️ 載入中...";

    const likeBtn = document.createElement("button");
    likeBtn.type = "button";
    likeBtn.className = "digest-like-btn";
    const isInitiallyLiked = localStorage.getItem(likedKey) === "1";
    if (isInitiallyLiked) likeBtn.classList.add("liked");
    likeBtn.innerHTML = `<span class="heart">${isInitiallyLiked ? "❤️" : "🤍"}</span><span class="like-count">0</span>`;

    bar.appendChild(viewsSpan);
    bar.appendChild(likeBtn);
    card.appendChild(bar);

    const likeCountSpan = likeBtn.querySelector(".like-count");
    const heartSpan = likeBtn.querySelector(".heart");

    function renderStats(data) {
      const views = Number(data?.views) || 0;
      const likes = Number(data?.likes) || 0;
      viewsSpan.textContent = `👁️ ${views} 次閱讀`;
      likeCountSpan.textContent = String(likes);
    }

    getDoc(docRef).then((snap) => {
      if (snap.exists()) {
        renderStats(snap.data());
      } else {
        renderStats({ views: 0, likes: 0 });
      }
    }).catch((err) => {
      console.error("讀取文章統計失敗:", err);
      viewsSpan.textContent = "👁️ —";
    });

    let dwellTimer = null;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && entry.intersectionRatio >= 0.4) {
            if (localStorage.getItem(viewedKey) === "1") {
              observer.unobserve(card);
              return;
            }
            dwellTimer = setTimeout(async () => {
              if (localStorage.getItem(viewedKey) === "1") return;
              localStorage.setItem(viewedKey, "1");
              observer.unobserve(card);

              try {
                const updated = await runTransaction(db, async (tx) => {
                  const snap = await tx.get(docRef);
                  const current = snap.exists() ? snap.data() : {};
                  const nextViews = (Number(current.views) || 0) + 1;
                  const nextLikes = Number(current.likes) || 0;
                  const nextScore = calcScore(nextLikes, nextViews);

                  const payload = {
                    id: docId,
                    date: dateStr,
                    lang,
                    title,
                    subtitle,
                    url: articleUrl,
                    views: nextViews,
                    likes: nextLikes,
                    score: nextScore
                  };
                  tx.set(docRef, payload, { merge: true });
                  return payload;
                });
                renderStats(updated);
              } catch (err) {
                console.error("更新閱覽數失敗:", err);
              }
            }, 1500);
          } else if (dwellTimer) {
            clearTimeout(dwellTimer);
            dwellTimer = null;
          }
        });
      },
      { threshold: [0.4] }
    );
    observer.observe(card);

    likeBtn.addEventListener("click", async () => {
      likeBtn.disabled = true;
      const currentlyLiked = localStorage.getItem(likedKey) === "1";
      const delta = currentlyLiked ? -1 : 1;

      try {
        const updated = await runTransaction(db, async (tx) => {
          const snap = await tx.get(docRef);
          const current = snap.exists() ? snap.data() : {};
          const nextViews = Number(current.views) || 0;
          const nextLikes = Math.max(0, (Number(current.likes) || 0) + delta);
          const nextScore = calcScore(nextLikes, nextViews);

          const payload = {
            id: docId,
            date: dateStr,
            lang,
            title,
            subtitle,
            url: articleUrl,
            views: nextViews,
            likes: nextLikes,
            score: nextScore
          };
          tx.set(docRef, payload, { merge: true });
          return payload;
        });

        if (delta > 0) {
          localStorage.setItem(likedKey, "1");
          likeBtn.classList.add("liked");
          heartSpan.textContent = "❤️";
        } else {
          localStorage.removeItem(likedKey);
          likeBtn.classList.remove("liked");
          heartSpan.textContent = "🤍";
        }
        renderStats(updated);
      } catch (err) {
        console.error("更新按讚數失敗:", err);
      } finally {
        likeBtn.disabled = false;
      }
    });
  });
</script>"""

page = f'<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Daily Trilingual Digest - {d_disp}</title><style>{css}</style></head><body><div class="container"><div class="nav-top"><a href="index.html" class="back-btn">← 返回日期目錄</a></div><header><h1>Daily Trilingual Digest</h1><div class="date-badge">{d_disp} ({w_str}) • 每日三語精選新聞</div></header><input type="radio" name="lang" id="opt-all" class="lang-radio" checked><input type="radio" name="lang" id="opt-en" class="lang-radio"><input type="radio" name="lang" id="opt-ja" class="lang-radio"><input type="radio" name="lang" id="opt-vi" class="lang-radio"><div class="filter-bar"><label for="opt-all" class="filter-btn">全部閱讀</label><label for="opt-en" class="filter-btn">🇺🇸 英文</label><label for="opt-ja" class="filter-btn">🇯🇵 日文</label><label for="opt-vi" class="filter-btn">🇻🇳 越南文</label></div><div class="cards-wrapper">{cards_html}</div></div></body></html>'

if "</body>" in page:
    page = page.replace("</body>", ENGAGEMENT_SNIPPET + "</body>", 1)

with open(f"{d_str}.html", "w", encoding="utf-8") as f:
    f.write(page)

new_card = (
    f'<a href="{d_str}.html" class="digest-item">'
    f'<div class="item-header"><span class="item-date">{d_disp} ({w_str})</span><span class="item-arrow">閱讀全文 →</span></div>'
    f'<ul class="topic-list">'
    f'<li><span class="lang-badge bg-en">EN</span><div class="title-group"><span class="orig-title">{data["en"]["title"]}</span><span class="zh-title">{data["en"]["subtitle"]}</span></div></li>'
    f'<li><span class="lang-badge bg-ja">JA</span><div class="title-group"><span class="orig-title">{data["ja"]["title_html"]}</span><span class="zh-title">{data["ja"]["subtitle"]}</span></div></li>'
    f'<li><span class="lang-badge bg-vi">VI</span><div class="title-group"><span class="orig-title">{data["vi"]["title"]}</span><span class="zh-title">{data["vi"]["subtitle"]}</span></div></li>'
    f"</ul></a>\n"
)

with open("index.html", "r", encoding="utf-8") as f:
    idx = f.read()

marker = "<!-- ====== 每天新增的日期卡片請貼在下方這一行之後 ====== -->"
is_manual_run = os.environ.get("IS_MANUAL_RUN", "").strip().lower() == "true"

if is_manual_run and f"{d_str}.html" in idx:
    card_pattern = re.compile(
        rf'\s*<a\b[^>]*href="{re.escape(d_str)}\.html"[^>]*class="digest-item"[^>]*>.*?</a>\s*',
        flags=re.DOTALL | re.IGNORECASE,
    )
    idx = card_pattern.sub("\n\n", idx, count=1)
    print(f"[INFO] 手動執行模式：已移除既有 {d_str} 卡片，準備覆蓋為最新內容")

if f"{d_str}.html" not in idx and marker in idx:
    idx = idx.replace(marker, marker + "\n" + new_card, 1)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(idx)
    print(f"[INFO] 已更新 index.html 中的 {d_str} 卡片")
