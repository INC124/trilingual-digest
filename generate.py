import asyncio
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
import edge_tts

# 依優先順序排列模型：主模型在前，配額受限或失敗時自動往後備援
MODELS = [
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",
]

now = datetime.now(timezone(timedelta(hours=8)))
d_str = now.strftime("%Y-%m-%d")
d_disp = now.strftime("%Y.%m.%d")
w_str = ["一", "二", "三", "四", "五", "六", "日"][now.weekday()]

prompt = f"""為 {d_disp} ({w_str}) 生成三則生活文化新聞（每篇約3~4句）：英文(en)、日文(ja)、越南文(vi)。
規則：
1. 日文 title_html、article_html 與 vocab 中的所有漢字皆須加 <ruby>漢字<rt>かな</rt></ruby>；title_plain 與 article_plain 為純日文無標籤。
2. 三種語言的 vocab 陣列各提供 6 個核心詞彙，每個詞彙皆須明確標註詞性（英文用 (n.)/(v.)/(adj.)/(phr.) 等，日文與越南文用 (名詞)/(動詞)/(形容詞)/(片語) 等），格式如 "<strong>詞彙</strong> (詞性)：中文解釋"。
嚴格回傳純 JSON（無 markdown）：
{{"en":{{"tag":"ISSUE NO. 01 • 分類 • 主題","title":"英文標題","subtitle":"中文副標","article":"英文內文","vocab":["<strong>word</strong> (n.)：解釋","<strong>word2</strong> (v.)：解釋","<strong>word3</strong> (adj.)：解釋","<strong>word4</strong> (phr.)：解釋","<strong>word5</strong> (n.)：解釋","<strong>word6</strong> (v.)：解釋"],"translation":"<strong>中文標題</strong><br>中文全譯"}},"ja":{{"tag":"ISSUE NO. 02 • JAPAN CULTURE • 主題","title_html":"含ruby標題","title_plain":"純日文標題","subtitle":"中文副標","article_html":"含ruby內文","article_plain":"純日文內文","vocab":["<strong><ruby>詞<rt>かな</rt></ruby></strong> (名詞)：解釋","<strong>詞2</strong> (動詞)：解釋","<strong>詞3</strong> (形容詞)：解釋","<strong>詞4</strong> (名詞)：解釋","<strong>詞5</strong> (動詞)：解釋","<strong>詞6</strong> (片語)：解釋"],"translation":"<strong>中文標題</strong><br>中文全譯"}},"vi":{{"tag":"ISSUE NO. 03 • VIETNAM LIFESTYLE • 主題","title":"越南文標題","subtitle":"中文副標","article":"越南文內文","vocab":["<strong>từ 1</strong> (名詞)：解釋","<strong>từ 2</strong> (動詞)：解釋","<strong>từ 3</strong> (形容詞)：解釋","<strong>từ 4</strong> (片語)：解釋","<strong>từ 5</strong> (名詞)：解釋","<strong>từ 6</strong> (動詞)：解釋"],"translation":"<strong>中文標題</strong><br>中文全譯"}}}}"""


def clean_json_text(raw_text: str) -> str:
    text = raw_text.strip()
    # 移除開頭與結尾的 ```json 或 ```
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()
    # 若前後仍有雜訊文字，嘗試擷取最外層 {...}
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return text


def call_single_model(api_key: str, model_name: str, prompt_text: str) -> str:
    # 優先使用新版 google-genai SDK，若未安裝則退回舊版 google-generativeai
    try:
        from google import genai  # type: ignore

        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt_text,
        )
        return (getattr(resp, "text", None) or "").strip()
    except ImportError:
        import google.generativeai as genai_legacy  # type: ignore

        genai_legacy.configure(api_key=api_key)
        legacy_model = genai_legacy.GenerativeModel(model_name)
        resp = legacy_model.generate_content(prompt_text)
        return (getattr(resp, "text", None) or "").strip()


def generate_digest_data(prompt_text: str) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("找不到環境變數 GEMINI_API_KEY")

    last_error = None

    for model_name in MODELS:
        # 每個模型最多重試 2 次（主要應對短暫 RPM / 503）
        for attempt in range(1, 3):
            try:
                print(f"[INFO] 嘗試使用模型：{model_name}（第 {attempt} 次）")
                raw = call_single_model(api_key, model_name, prompt_text)
                if not raw:
                    raise RuntimeError(f"模型 {model_name} 回傳空白內容")

                cleaned = clean_json_text(raw)
                parsed = json.loads(cleaned)

                # 基本欄位檢查
                for lang_key in ("en", "ja", "vi"):
                    if lang_key not in parsed:
                        raise ValueError(f"回傳 JSON 缺少欄位：{lang_key}")

                print(f"[SUCCESS] 已成功透過 {model_name} 取得並解析三語新聞資料")
                return parsed

            except Exception as e:
                last_error = e
                err_str = str(e)
                print(f"[WARN] 模型 {model_name} 發生錯誤：{err_str}")

                # 判斷是否為每日配額耗盡（例如 quota_value 限制或 retry_delay 很長）
                is_daily_quota = (
                    "PerDay" in err_str
                    or "Daily" in err_str
                    or "quota_value" in err_str
                    or bool(re.search(r"seconds:\s*\d{4,}", err_str))
                )
                is_rate_limit = (
                    "429" in err_str
                    or "RESOURCE_EXHAUSTED" in err_str
                    or "503" in err_str
                    or "UNAVAILABLE" in err_str
                )

                if is_daily_quota:
                    print(f"[INFO] {model_name} 疑似已達每日配額上限，立即切換下一個模型...")
                    break

                if is_rate_limit and attempt < 2:
                    sleep_sec = 5 * attempt
                    print(f"[INFO] 遇到速率限制或忙碌，等待 {sleep_sec} 秒後重試...")
                    time.sleep(sleep_sec)
                    continue

                # JSON 解析失敗或其他錯誤，跳出目前模型改試下一個模型
                break

    raise RuntimeError(f"所有候選模型皆無法成功生成資料，最後錯誤：{last_error}")


data = generate_digest_data(prompt)

os.makedirs("audio", exist_ok=True)


async def make_audio():
    v_map = {
        "en": ("en-US-JennyNeural", data["en"]["article"]),
        "ja": ("ja-JP-NanamiNeural", data["ja"]["article_plain"]),
        "vi": ("vi-VN-HoaiMyNeural", data["vi"]["article"]),
    }
    for k, (v, t) in v_map.items():
        await edge_tts.Communicate(t, v, rate="-8%").save(f"audio/{d_str}-{k}.mp3")
        await asyncio.sleep(1)


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

page = f'<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Daily Trilingual Digest - {d_disp}</title><style>{css}</style></head><body><div class="container"><div class="nav-top"><a href="index.html" class="back-btn">← 返回日期目錄</a></div><header><h1>Daily Trilingual Digest</h1><div class="date-badge">{d_disp} ({w_str}) • 每日三語精選新聞</div></header><input type="radio" name="lang" id="opt-all" class="lang-radio" checked><input type="radio" name="lang" id="opt-en" class="lang-radio"><input type="radio" name="lang" id="opt-ja" class="lang-radio"><input type="radio" name="lang" id="opt-vi" class="lang-radio"><div class="filter-bar"><label for="opt-all" class="filter-btn">全部閱讀</label><label for="opt-en" class="filter-btn">🇺🇸 英文</label><label for="opt-ja" class="filter-btn">🇯🇵 日文</label><label for="opt-vi" class="filter-btn">🇻🇳 越南文</label></div><div class="cards-wrapper">{cards_html}</div></div></body></html>'

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
if f"{d_str}.html" not in idx and marker in idx:
    idx = idx.replace(marker, marker + "\n" + new_card, 1)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(idx)
