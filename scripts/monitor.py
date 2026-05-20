import os
import json
from pathlib import Path
from collections import Counter

import resend
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

URL = "https://ai-act-standards.com/"
DATA_FILE = "data/latest.json"

resend.api_key = os.environ["RESEND_API_KEY"]
EMAIL_TO = os.environ["EMAIL_TO"]


# =========================
# 1. 抓取页面
# =========================
def fetch_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(URL, wait_until="networkidle")
        page.wait_for_timeout(3000)

        html = page.content()
        browser.close()

    return html


# =========================
# 2. 提取 Stage 统计
# =========================
def extract_stage_counts(soup):
    text = soup.get_text(" ", strip=True)

    # 常见 stage 关键词（按你网站情况可再加）
    stages = [
        "Draft",
        "Voting",
        "Approved",
        "Final",
        "Published",
        "Development"
    ]

    counts = {}

    for stage in stages:
        counts[stage] = text.count(stage)

    return counts


# =========================
# 3. 提取 Changelog
# =========================
def extract_changelog(soup):
    logs = []

    # 尝试找到 changelog 区域（通用写法）
    candidates = soup.select("li, .changelog, .log, .timeline, article")

    for c in candidates:
        t = c.get_text(" ", strip=True)

        if len(t) > 20:
            logs.append(t)

    # 去重
    return list(dict.fromkeys(logs))[:30]


# =========================
# 4. 状态加载/保存
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
# 5. diff
# =========================
def diff(old, new):
    changes = []

    if old.get("stages") != new.get("stages"):
        changes.append({
            "type": "STAGE_CHANGED",
            "old": old.get("stages"),
            "new": new.get("stages")
        })

    old_logs = set(old.get("changelog", []))
    new_logs = set(new.get("changelog", []))

    added = list(new_logs - old_logs)

    if added:
        changes.append({
            "type": "CHANGELOG_ADDED",
            "items": added
        })

    return changes


# =========================
# 6. email
# =========================
def send_email(subject, html):
    resend.Emails.send({
        "from": "onboarding@resend.dev",
        "to": [EMAIL_TO],
        "subject": subject,
        "html": html,
    })


def build_html(changes):
    html = "<h2>AI Act Update</h2>"

    for c in changes:
        if c["type"] == "STAGE_CHANGED":
            html += "<h3>Stage changes</h3>"
            html += f"<pre>{c['old']} → {c['new']}</pre>"

        if c["type"] == "CHANGELOG_ADDED":
            html += "<h3>New changelog</h3>"
            html += "<ul>"
            for i in c["items"]:
                html += f"<li>{i}</li>"
            html += "</ul>"

    return html


# =========================
# 7. main
# =========================
def main():
    print("Fetching...")

    html = fetch_page()
    soup = BeautifulSoup(html, "lxml")

    stages = extract_stage_counts(soup)
    changelog = extract_changelog(soup)

    current = {
        "stages": stages,
        "changelog": changelog
    }

    previous = load_previous()

    if not previous:
        print("First run → save")
        save_current(current)
        return

    changes = diff(previous, current)

    if not changes:
        print("No changes")
        return

    print(f"Changes: {len(changes)}")

    send_email(
        subject="AI Act Monitor Update",
        html=build_html(changes)
    )

    save_current(current)

    print("Done")


if __name__ == "__main__":
    main()
