import os, json, asyncio
from datetime import datetime, timezone, timedelta
import google.generativeai as genai
import edge_tts

now = datetime.now(timezone(timedelta(hours=8)))
d_str = now.strftime("%Y-%m-%d")
d_disp = now.strftime("%Y.%m.%d")
w_str = ["一", "二", "三", "四", "五", "六", "日"][now.weekday()]

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-3.8-flash")

prompt = f"""為 {d_disp} ({w_str}) 生成三則生活文化新聞（每篇約3~4句）：英文(en)、日文(ja)、越南文(vi)。
日文 title_html 與 article_html 漢字須加 <ruby>漢字<rt>かな</rt></ruby>；title_plain 與 article_plain 為純日文無標籤。
嚴格回傳純 JSON（無 markdown）：
{{"en":{{"tag":"ISSUE NO. 01 • 分類 • 主題","title":"英文標題","subtitle":"中文副標","article":"英文內文","vocab":["<strong>詞1</strong>：解釋","<strong>詞2</strong>：解釋","<strong>詞3</strong>：解釋","<strong>詞4</strong>：解釋","<strong>詞5</strong>：解釋","<strong>詞6</strong>：解釋"],"translation":"<strong>中文標題</strong><br>中文全譯"}},"ja":{{"tag":"ISSUE NO. 02 • JAPAN CULTURE • 主題","title_html":"含ruby標題","title_plain":"純日文標題","subtitle":"中文副標","article_html":"含ruby內文","article_plain":"純日文內文","vocab":["<strong>詞1</strong>：解釋","<strong>詞2</strong>：解釋","<strong>詞3</strong>：解釋","<strong>詞4</strong>：解釋","<strong>詞5</strong>：解釋","<strong>詞6</strong>：解釋"],"translation":"<strong>中文標題</strong><br>中文全譯"}},"vi":{{"tag":"ISSUE NO. 03 • VIETNAM LIFESTYLE • 主題","title":"越南文標題","subtitle":"中文副標","article":"越南文內文","vocab":["<strong>詞1</strong>：解釋","<strong>詞2</strong>：解釋","<strong>詞3</strong>：解釋","<strong>詞4</strong>：解釋","<strong>詞5</strong>：解釋","<strong>詞6</strong>：解釋"],"translation":"<strong>中文標題</strong><br>中文全譯"}}}}"""

raw = model.generate_content(prompt).text.strip()
if raw.startswith("```"):
    raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
data = json.loads(raw)

os.makedirs("audio", exist_ok=True)
async def make_audio():
    v_map = {"en": ("en-US-JennyNeural", data["en"]["article"]), "ja": ("ja-JP-NanamiNeural", data["ja"]["article_plain"]), "vi": ("vi-VN-HoaiMyNeural", data["vi"]["article"])}
    for k, (v, t) in v_map.items():
        await edge_tts.Communicate(t, v, rate="-8%").save(f"audio/{d_str}-{k}.mp3")
asyncio.run(make_audio())

def make_card(lang, title, sub, art, voc, trans, label):
    v_li = "".join([f"<li>{x}</li>" for x in voc])
    return f'<article class="card" data-lang="{lang}"><span class="tag">{data[lang]["tag"]}</span><h2>{title}</h2><p class="subtitle">{sub}</p><span class="section-label">🔊 真人發音朗讀 • {label}</span><audio controls preload="none" src="audio/{d_str}-{lang}.mp3"></audio><span class="section-label">ARTICLE • {label}報導</span><p class="article-text">{art}</p><span class="section-label">VOCABULARY & PHRASES 核心詞彙</span><ul class="vocab-list">{v_li}</ul><span class="section-label">TRANSLATION 中文全譯</span><p class="translation">{trans}</p></article>'

cards_html = (
    make_card("en", data["en"]["title"], data["en"]["subtitle"], data["en"]["article"], data["en"]["vocab"], data["en"]["translation"], "英文") +
    make_card("ja", data["ja"]["title_html"], data["ja"]["subtitle"], data["ja"]["article_html"], data["ja"]["vocab"], data["ja"]["translation"], "日文") +
    make_card("vi", data["vi"]["title"], data["vi"]["subtitle"], data["vi"]["article"], data["vi"]["vocab"], data["vi"]["translation"], "越南文")
)

css = ':root{--bg:#f4f5f7;--card:#fff;--text:#1f2937;--muted:#6b7280;--en:#2563eb;--ja:#dc2626;--vi:#059669;--border:#e5e7eb}*{box-sizing:border-box;margin:0;padding:0}body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans TC",sans-serif;background:var(--bg);color:var(--text);line-height:1.7;padding:16px}.container{max-width:680px;margin:0 auto}header{text-align:center;padding:20px 0 12px}.nav-top{text-align:left;margin-bottom:12px}.back-btn{text-decoration:none;color:var(--muted);font-size:.9rem;font-weight:500}h1{font-size:1.5rem;margin-bottom:4px}.date-badge{font-size:.9rem;color:var(--muted)}input.lang-radio{display:none}.filter-bar{display:flex;justify-content:center;gap:8px;margin:14px 0 24px;flex-wrap:wrap;position:sticky;top:10px;z-index:10;background:rgba(244,245,247,.92);backdrop-filter:blur(6px);padding:8px;border-radius:12px}.filter-btn{border:1px solid var(--border);background:#fff;color:var(--text);padding:8px 14px;border-radius:20px;font-size:.9rem;font-weight:600;cursor:pointer}#opt-all:checked~.filter-bar label[for="opt-all"],#opt-en:checked~.filter-bar label[for="opt-en"],#opt-ja:checked~.filter-bar label[for="opt-ja"],#opt-vi:checked~.filter-bar label[for="opt-vi"]{background:#1f2937;color:#fff;border-color:#1f2937}#opt-en:checked~.cards-wrapper .card:not([data-lang="en"]),#opt-ja:checked~.cards-wrapper .card:not([data-lang="ja"]),#opt-vi:checked~.cards-wrapper .card:not([data-lang="vi"]){display:none}.card{background:var(--card);border-radius:16px;padding:24px;margin-bottom:24px;box-shadow:0 2px 8px rgba(0,0,0,.04);border-top:4px solid #ccc}.card[data-lang="en"]{border-top-color:var(--en)}.card[data-lang="ja"]{border-top-color:var(--ja)}.card[data-lang="vi"]{border-top-color:var(--vi)}.tag{font-size:.75rem;font-weight:700;color:var(--muted);margin-bottom:8px;display:block}h2{font-size:1.25rem;line-height:1.4;margin-bottom:8px}.subtitle{font-size:.95rem;color:var(--muted);margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid var(--border)}audio{width:100%;height:40px;margin:8px 0 14px;border-radius:20px}.section-label{font-size:.75rem;font-weight:700;color:var(--muted);display:block;margin-top:16px}.article-text{font-size:1.05rem;margin-top:6px;text-align:justify}ruby rt{font-size:.6em;color:#555}.vocab-list{list-style:none;background:#f9fafb;padding:14px 16px;border-radius:10px;font-size:.95rem;margin-top:8px}.vocab-list li{margin-bottom:6px}.translation{font-size:.95rem;color:#374151;margin-top:8px;text-align:justify}'

page = f'<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Daily Trilingual Digest - {d_disp}</title><style>{css}</style></head><body><div class="container"><div class="nav-top"><a href="index.html" class="back-btn">← 返回日期目錄</a></div><header><h1>Daily Trilingual Digest</h1><div class="date-badge">{d_disp} ({w_str}) • 每日三語精選新聞</div></header><input type="radio" name="lang" id="opt-all" class="lang-radio" checked><input type="radio" name="lang" id="opt-en" class="lang-radio"><input type="radio" name="lang" id="opt-ja" class="lang-radio"><input type="radio" name="lang" id="opt-vi" class="lang-radio"><div class="filter-bar"><label for="opt-all" class="filter-btn">全部閱讀</label><label for="opt-en" class="filter-btn">🇺🇸 英文</label><label for="opt-ja" class="filter-btn">🇯🇵 日文</label><label for="opt-vi" class="filter-btn">🇻🇳 越南文</label></div><div class="cards-wrapper">{cards_html}</div></div></body></html>'

with open(f"{d_str}.html", "w", encoding="utf-8") as f:
    f.write(page)

new_card = f'<a href="{d_str}.html" class="digest-item"><div class="item-header"><span class="item-date">{d_disp} ({w_str})</span><span class="item-arrow">閱讀全文 →</span></div><ul class="topic-list"><li><span class="lang-badge bg-en">EN</span><div class="title-group"><span class="orig-title">{data["en"]["title"]}</span><span class="zh-title">{data["en"]["subtitle"]}</span></div></li><li><span class="lang-badge bg-ja">JA</span><div class="title-group"><span class="orig-title">{data["ja"]["title_html"]}</span><span class="zh-title">{data["ja"]["subtitle"]}</span></div></li><li><span class="lang-badge bg-vi">VI</span><div class="title-group"><span class="orig-title">{data["vi"]["title"]}</span><span class="zh-title">{data["vi"]["subtitle"]}</span></div></li></ul></a>\n'

with open("index.html", "r", encoding="utf-8") as f:
    idx = f.read()

marker = "<!-- ====== 每天新增的日期卡片請貼在下方這一行之後 ====== -->"
if f"{d_str}.html" not in idx and marker in idx:
    idx = idx.replace(marker, marker + "\n" + new_card, 1)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(idx)
