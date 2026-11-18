import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz

# 1. 取得環境變數
channel_id = os.environ.get('LINE_CHANNEL_ID')
channel_secret = os.environ.get('LINE_CHANNEL_SECRET')
user_id = os.environ.get('LINE_USER_ID') # 如果你有順便把 User ID 存進 Secrets，也可以讀取它

# 2. 取得台灣時區的當天日期與網址
taiwan_tz = pytz.timezone('Asia/Taipei')
today = datetime.now(taiwan_tz)
date_str = today.strftime('%Y-%m-%d')
target_url = f'https://inc124.github.io/trilingual-digest/{date_str}.html'

print(f"正在抓取目標網頁：{target_url}")

# 3. 抓取網頁並解析三語標題
titles = {"EN": "無", "JA": "無", "VI": "無"}
try:
    response = requests.get(target_url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 依照你的網頁結構尋找各語言標題 (範例會根據 span 標籤尋找 EN, JA, VI)
        for li in soup.find_all('li'):
            lang_span = li.find('span')
            if lang_span:
                lang_text = lang_span.text.strip()
                # 尋找語言標籤後方的標題文字
                title_spans = li.find_all('span')
                if len(title_spans) >= 2:
                    article_title = title_spans[1].text.strip()
                    if lang_text == 'EN':
                        titles['EN'] = article_title
                    elif lang_text == 'JA':
                        titles['JA'] = article_title
                    elif lang_text == 'VI':
                        titles['VI'] = article_title
    else:
        print("警告：無法讀取今日網頁，將以純連結發送通知。")
except Exception as e:
    print(f"解析網頁發生錯誤: {e}")

# 4. 組裝 LINE 推播訊息
message_text = (
    f"🌅 早安！今天的 Daily Trilingual Digest（{date_str}）文章已準備好囉：\n\n"
    f"🇬🇧 EN: {titles['EN']}\n"
    f"🇯🇵 JA: {titles['JA']}\n"
    f"🇻🇳 VI: {titles['VI']}\n\n"
    f"👉 立即閱讀全文：\n{target_url}"
)

# 5. 自動向 LINE API 交換短效期 Access Token
token_url = 'https://api.line.me/v2/oauth/accessToken'
token_payload = {
    'grant_type': 'client_credentials',
    'client_id': channel_id,
    'client_secret': channel_secret
}
token_res = requests.post(token_url, data=token_payload)

if token_res.status_code != 200:
    raise Exception(f"取得 LINE Token 失敗: {token_res.text}")

access_token = token_res.json().get('access_token')

# 6. 發送 LINE 推播訊息
line_api_url = 'https://api.line.me/v2/bot/message/push'
headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {access_token}'
}
payload = {
    "to": user_id, # 若你還沒把 User ID 存到 Secrets，也可以直接把字串填在這裡，例如 "Uxxxxxxxx..."
    "messages": [
        {
            "type": "text",
            "text": message_text
        }
    ]
}

line_res = requests.post(line_api_url, headers=headers, json=payload)
if line_res.status_code == 200:
    print("LINE 通知發送成功！")
else:
    print(f"LINE 通知發送失敗: {line_res.text}")
