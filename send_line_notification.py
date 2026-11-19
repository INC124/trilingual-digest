from datetime import datetime
import os
from bs4 import BeautifulSoup
import pytz
import requests

# 1. 取得環境變數
channel_id = os.environ.get("LINE_CHANNEL_ID")
channel_secret = os.environ.get("LINE_CHANNEL_SECRET")
user_id = os.environ.get("LINE_USER_ID")

if not channel_id or not channel_secret:
  raise Exception("缺少環境變數 LINE_CHANNEL_ID 或 LINE_CHANNEL_SECRET")

if not user_id or not user_id.strip():
  raise Exception(
      "缺少環境變數 LINE_USER_ID（請到 GitHub Repository Secrets 新增"
      " LINE_USER_ID）"
  )

user_id = user_id.strip()

# 2. 取得台灣時區的當天日期與網址
taiwan_tz = pytz.timezone("Asia/Taipei")
today = datetime.now(taiwan_tz)
date_str = today.strftime("%Y-%m-%d")
target_url = f"https://inc124.github.io/trilingual-digest/{date_str}.html"

print(f"正在抓取目標網頁：{target_url}")

# 3. 抓取網頁並解析三語標題
titles = {"EN": "無", "JA": "無", "VI": "無"}
try:
  response = requests.get(target_url, timeout=15)
  if response.status_code == 200:
    soup = BeautifulSoup(response.text, "html.parser")

    for li in soup.find_all("li"):
      lang_span = li.find("span")
      if lang_span:
        lang_text = lang_span.text.strip()
        title_spans = li.find_all("span")
        if len(title_spans) >= 2:
          article_title = title_spans[1].text.strip()
          if lang_text == "EN":
            titles["EN"] = article_title
          elif lang_text == "JA":
            titles["JA"] = article_title
          elif lang_text == "VI":
            titles["VI"] = article_title
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
token_url = "https://api.line.me/v2/oauth/accessToken"
token_payload = {
    "grant_type": "client_credentials",
    "client_id": channel_id,
    "client_secret": channel_secret,
}
token_res = requests.post(token_url, data=token_payload, timeout=15)

if token_res.status_code != 200:
  raise Exception(f"取得 LINE Token 失敗: {token_res.text}")

access_token = token_res.json().get("access_token")

# 6. 發送 LINE 推播訊息
line_api_url = "https://api.line.me/v2/bot/message/push"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {access_token}",
}
payload = {
    "to": user_id,
    "messages": [{"type": "text", "text": message_text}],
}

line_res = requests.post(line_api_url, headers=headers, json=payload, timeout=15)
if line_res.status_code == 200:
  print("LINE 通知發送成功！")
else:
  raise Exception(f"LINE 通知發送失敗: {line_res.text}")
