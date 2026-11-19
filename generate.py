import asyncio
import os
from datetime import datetime, timedelta, timezone
import edge_tts

# 【測試開關】True = 使用假資料不呼叫 Gemini；False = 恢復真實呼叫 Gemini
USE_MOCK_DATA = True

now = datetime.now(timezone(timedelta(hours=8)))
d_str = now.strftime("%Y-%m-%d")
d_disp = now.strftime("%Y.%m.%d")
w_str = ["一", "二", "三", "四", "五", "六", "日"][now.weekday()]

MOCK_DATA = {
    "en": {
        "tag": "ISSUE NO. 01 • TEST • LIFESTYLE",
        "title": "Morning Coffee Rituals Boost Focus",
        "subtitle": "【測試資料】早晨咖啡儀式有助提升專注力",
        "article": "Many people start their morning with a warm cup of coffee. A calm routine helps set a steady pace for the day. Sharing a quiet moment before work can also improve overall mood.",
        "vocab": [
            "<strong>ritual</strong> (n.)：例行儀式",
            "<strong>focus</strong> (v.)：專注",
            "<strong>steady</strong> (adj.)：穩定的",
            "<strong>set a pace</strong> (phr.)：設定節奏",
            "<strong>routine</strong> (n.)：日常作息",
            "<strong>improve</strong> (v.)：改善",
        ],
        "translation": "<strong>【測試】早晨咖啡儀式有助提升專注力</strong><br>許多人以一杯溫暖的咖啡開啟早晨。平靜的日常作息有助於為一天設定穩定的節奏。在工作前享受片刻寧靜，也能改善整體心情。",
    },
    "ja": {
        "tag": "ISSUE NO. 02 • TEST • JAPAN CULTURE",
        "title_html": "【<ruby>測試<rt>てすと</rt></ruby>】<ruby>朝<rt>あさ</rt></ruby>の<ruby>散歩<rt>さんぽ</rt></ruby>と<ruby>季節感<rt>きせつかん</rt></ruby>",
        "title_plain": "【テスト】朝の散歩と季節感",
        "subtitle": "【測試資料】晨間散步與感受季節變化",
        "article_html": "<ruby>朝<rt>あさ</rt></ruby>の<ruby>空気<rt>くうき</rt></ruby>を<ruby>吸<rt>す</rt></ruby>いながら<ruby>歩<rt>ある</rt></ruby>くと、<ruby>気分<rt>きぶん</rt></ruby>がすっきりします。<ruby>季節<rt>きせつ</rt></ruby>の<ruby>変化<rt>へんか</rt></ruby>に<ruby>気<rt>き</rt></ruby>づくことも<ruby>毎日<rt>まいにち</rt></ruby>の<ruby>楽<rt>たの</rt></ruby>しみです。",
        "article_plain": "朝の空気を吸いながら歩くと、気分がすっきりします。季節の変化に気づくことも毎日の楽しみです。",
        "vocab": [
            "<strong><ruby>散歩<rt>さんぽ</rt></ruby></strong> (名詞)：散步",
            "<strong><ruby>空気<rt>くうき</rt></ruby></strong> (名詞)：空氣",
            "<strong>すっきりする</strong> (片語)：感到清爽、舒暢",
            "<strong><ruby>季節<rt>きせつ</rt></ruby></strong> (名詞)：季節",
            "<strong><ruby>変化<rt>へんか</rt></ruby></strong> (名詞)：變化",
            "<strong><ruby>気<rt>き</rt></ruby>づく</strong> (動詞)：察覺、注意到",
        ],
        "translation": "<strong>【測試】晨間散步與感受季節變化</strong><br>呼吸著早晨的空氣散步，會讓心情變得清爽。察覺季節的變化也是每天的樂趣之一。",
    },
    "vi": {
        "tag": "ISSUE NO. 03 • TEST • VIETNAM LIFESTYLE",
        "title": "Thoi Quen Doc Sach Buoi Sang",
        "subtitle": "【測試資料】早晨閱讀的習慣",
        "article": "Doc sach vao buoi sang giup tinh than thu thai hon. Chi can danh ra vai phut yen tinh truoc khi bat dau cong viec. Day la mot thoi quen tot cho suc khoe tinh than.",
        "vocab": [
            "<strong>thói quen</strong> (名詞)：習慣",
            "<strong>đọc sách</strong> (片語)：閱讀",
            "<strong>buổi sáng</strong> (名詞)：早晨",
            "<strong>thư thái</strong> (形容詞)：放鬆、自在",
            "<strong>bắt đầu</strong> (動詞)：開始",
            "<strong>tinh thần</strong> (名詞)：精神、心靈",
        ],
        "translation": "<strong>【測試】早晨閱讀的習慣</strong><br>在早晨閱讀有助於讓心情更加放鬆。只要在開始工作前留出幾分鐘的寧靜時光，這就是對心理健康很有益的習慣。",
    },
}


def generate_digest_data() -> dict:
    if USE_MOCK_DATA:
        print("[MOCK] 使用測試假資料，不呼叫 Gemini API")
        return MOCK_DATA
    raise RuntimeError("目前設定為非測試模式，請改用正式版 generate.py")


data = generate_digest_data()

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
