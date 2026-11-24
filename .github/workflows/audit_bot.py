name: Daily Financial Audit Bot

on:
  schedule:
    # 台灣時間 (UTC+8) 每天 23:00 對應 UTC 15:00
    - cron: "0 15 * * *"
  workflow_dispatch:

jobs:
  run-audit-bot:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install firebase-admin requests pytz

      - name: Run audit_bot.py
        env:
          FIREBASE_SERVICE_ACCOUNT_JSON: ${{ secrets.FIREBASE_SERVICE_ACCOUNT_JSON }}
          LINE_CHANNEL_ACCESS_TOKEN: ${{ secrets.LINE_CHANNEL_ACCESS_TOKEN }}
          LINE_USER_ID: ${{ secrets.LINE_USER_ID }}
          FIRESTORE_COLLECTION: expenses
        run: python audit_bot.py
