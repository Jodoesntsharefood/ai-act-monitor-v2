import os
import json
import re
from pathlib import Path

import resend
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

URL = "https://ai-act-standards.com/"
DATA_FILE = "data/latest.json"

resend.api_key = os.environ["RESEND_API_KEY"]
EMAIL_TO = os.environ["EMAIL_TO"]


# =========================
# 1. 抓 HTML
# =========================
def fetch_html():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(URL, wait_until="networkidle")
        page.wait_for_timeout(4000)

        html = page.content()
        browser.close()

    return html


# =========================
# 2. 提取指标（精准版）
# =========================
def extract_metrics(soup):
    text = soup.get_text(" ", strip=True)

    def find(label):
        pattern = rf"{label}\s*[:\-]?\s*([0-9,]+)"
        m = re.search(pattern, text, re.IGNORECASE)
        return int(m.group(1).replace(",", "")) if m else 0

    metrics = {
        "total_standards": find("Total Standards"),

        "stage_10_10_99": find("Stage 10-10.99"),
        "stage_20_30_99": find("Stage 20-30.99"),
        "stage_40_40_99": find("Stage 40-40.99"),
        "stage_50_50_99": find("Stage 50-50.99"),
        "stage_60_plus": find("Stage 60\\+"),

        "ojeu": find("Cited in the OJEU"),
    }

    return metrics


# =========================
# 3. Changelog 提取（只抓新增行）
# =========================
def extract_changelog(soup):
    logs = []

    # 找 changelog 表格 / 列表
    elements = soup.select("table tr, .changelog tr, li")

    for e in elements:
        text = e.get_text(" ", strip=True)

        # 过滤太短的噪声
        if len(text) > 20:
            logs.append(text)

    # 去重 + 保序
    seen = set()
    unique = []

    for l in logs:
        if l not in seen:
            seen.add(l)
            unique.append(l)

    return unique


# =========================
# 4. 存取状态
# =========================
def load_previous():
    if not Path(DATA_FILE).exists():
        return {}
    try:
        return json.loads(Path(DATA_FILE).read_text(encoding="utf-8"))
    except:
        return {}


def save_current(data):
    Path("data").mkdir(exist_ok=True)
    Path(DATA_FILE).write_text(json.dumps(data, indent=2, ensure_ascii=False))


# =========================
# 5. diff（严格按你的指标）
# =========================
def diff(old, new):
    changes = []

    for k in [
        "total_standards",
        "stage_10_10_99",
        "stage_20_30_99",
        "stage_40_40_99",
        "stage_50_50_99",
        "stage_60_plus",
        "ojeu"
    ]:
        if old.get(k) != new.get(k):
            changes.append({
                "type": "METRIC_CHANGE",
                "metric": k,
                "old": old.get(k),
                "new": new.get(k)
            })

    old_logs = set(old.get("changelog", []))
    new_logs = set(new.get("changelog", []))

    added = list(new_logs - old_logs)

    if added:
        changes.append({
            "type": "CHANGELOG_NEW",
            "items": added
        })

    return changes


# =========================
# 6. email
# =========================
def send_email(subject, html):
    resp = resend.Emails.send({
        "from": "AI Monitor <onboarding@resend.dev>",
        "to": [EMAIL_TO],
        "subject": subject,
        "html": html,
    })

    print("EMAIL RESPONSE:", resp)


def build_email(changes):
    html = "<h2>AI Act Metrics Update</h2>"

    for c in changes:
        if c["type"] == "METRIC_CHANGE":
            html += f"""
            <p>
            <b>{c['metric']}</b><br>
            {c['old']} → {c['new']}
            </p>
            """

        if c["type"] == "CHANGELOG_NEW":
            html += "<h3>New Changelog Entries</h3><ul>"
            for i in c["items"]:
                html += f"<li>{i}</li>"
            html += "</ul>"

    return html


# =========================
# 7. main
# =========================
def main():
    print("Fetching...")

    html = fetch_html()
    soup = BeautifulSoup(html, "lxml")

    metrics = extract_metrics(soup)
    changelog = extract_changelog(soup)

    current = {
        **metrics,
        "changelog": changelog
    }

    print("[DEBUG] metrics:", metrics)
    print("[DEBUG] changelog items:", len(changelog))

    previous = load_previous()

    if not previous:
        print("First run → save snapshot")
        save_current(current)
        return

    changes = diff(previous, current)

    if not changes:
        print("No changes")
        return

    print("Changes detected:", len(changes))

    send_email(
        "AI Act Metrics Update",
        build_email(changes)
    )

    save_current(current)

    print("Done")


if __name__ == "__main__":
    main()
