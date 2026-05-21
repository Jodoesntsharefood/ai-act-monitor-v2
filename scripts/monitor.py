name: AI Act Monitor

on:
  schedule:
    - cron: "0 */6 * * *"

  workflow_dispatch:

jobs:
  monitor:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install resend

      - name: Run monitor
        env:
          RESEND_API_KEY: ${{ secrets.RESEND_API_KEY }}
          EMAIL_TO: ${{ secrets.EMAIL_TO }}
        run: |
          python scripts/monitor.py

      - name: DEBUG FILES
        run: |
          echo "===== ROOT FILES ====="
          ls -al

          echo "===== latest.json ====="
          cat latest.json || true

          echo "===== debug.html size ====="
          wc -c debug.html || true

      - name: Upload latest.json
        uses: actions/upload-artifact@v4
        with:
          name: latest-json
          path: latest.json

      - name: Upload debug.html
        uses: actions/upload-artifact@v4
        with:
          name: debug-html
          path: debug.html
