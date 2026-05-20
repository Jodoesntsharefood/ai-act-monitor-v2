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
# 1. 抓页面
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
# 2. 提取指标（核心）
# =========================
def extract_metrics(soup):
    text = soup.get_text(" ", strip=True)

    def find_number(pattern):
        m = re.search(pattern, text)
        return int(m.group(1)) if m else 0

    metrics = {
        # Stage 分布
        "stage_10": find_number(r"Stage\s*10[^0-9]*(\d+)"),
        "stage_20": find_number(r"Stage\s*20[^0-9]*(\d+)"),
        "stage_40": find_number(r"Stage\s*40[^0-9]*(\d+)"),
        "stage_50": find_number(r"Stage\s*50[^0-9]*(\d+)"),
        "stage_60": find_number(r"Stage\s*60[^0-9]*(\d+)"),

        # 总数
        "total": find_number(r"Total\s*standards[^0-9]*(\d+)"),

        # OJEU
        "ojeu": find_number(r"OJEU[^0-9]*(\d+)")
    }

    return metrics


# =========================
# 3. Changelog 提取
# =========================
def extract_changelog(soup):
    logs = []

    # 优先找 changelog 区域
    candidates = soup.select("li, article, .timeline, .log, .changelog")

    for c in candidates:
        t = c.get_text(" ", strip=True)

        if len(t) > 30:
            logs.append(t)

    # 去重
    return list(dict.fromkeys(logs))[:30]


# =========================
# 4. 状态存储
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
# 5. diff（指标级）
# =========================
def diff(old, new):
    changes = []

    # 指标变化
    for k in ["stage_10", "stage_20", "stage_40", "stage_50", "stage_60", "total", "ojeu"]:
        if old.get(k) != new.get(k):
            changes.append({
                "type": "METRIC_CHANGE",
                "metric": k,
                "old": old.get(k),
                "new": new.get(k)
            })

    # changelog 新增
    old_logs = set(old.get("changelog", []))
    new_logs = set(new.get("changelog", []))

    added = list(new_logs - old_logs)

    if added:
        changes.append({
            "type": "CHANGELOG",
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
            html += f"<p><b>{c['metric']}</b>: {c['old']} → {c['new']}</p>"

        if c["type"] == "CHANGELOG":
            html += "<h3>Changelog</h3><ul>"
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
    print("[DEBUG] changelog size:", len(changelog))

    previous = load_previous()

    if not previous:
        print("First run → save snapshot")
        save_current(current)
        return

    changes = diff(previous, current)

    if not changes:
        print("No changes")
        return

    print("Changes:", len(changes))

    send_email(
        "AI Act Metrics Update",
        build_email(changes)
    )

    save_current(current)

    print("Done")


if __name__ == "__main__":
    main()
