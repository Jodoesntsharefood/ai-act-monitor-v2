import json
import os
from pathlib import Path

import resend
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

URL = "https://ai-act-standards.com/"
DATA_FILE = "data/latest.json"

resend.api_key = os.environ["RESEND_API_KEY"]
EMAIL_TO = os.environ["EMAIL_TO"]


# -----------------------------
# 1. 抓取（Playwright渲染版）
# -----------------------------
def fetch_current_status():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(URL, wait_until="networkidle")

        # 等页面渲染（关键）
        page.wait_for_timeout(3000)

        html = page.content()
        with open("debug.html", "w", encoding="utf-8") as f:
            f.write(html)

        print("DEBUG HTML saved")
        browser.close()

    soup = BeautifulSoup(html, "lxml")

    standards = {}

    tables = soup.find_all("table")

    print(f"[DEBUG] tables found: {len(tables)}")

    for table in tables:
        rows = table.find_all("tr")

        headers = []

        for i, row in enumerate(rows):
            cols = row.find_all(["td", "th"])
            values = [c.get_text(" ", strip=True) for c in cols]

            if not values:
                continue

            # header行
            if i == 0:
                headers = values
                continue

            if len(headers) != len(values):
                continue

            item = dict(zip(headers, values))

            name = (
                item.get("Standard")
                or item.get("Name")
                or item.get("Title")
                or item.get("Reference")
            )

            status = (
                item.get("Status")
                or item.get("Stage")
                or item.get("State")
            )

            if name and status:
                standards[name] = {
                    "status": status,
                    "raw": item,
                }

    print(f"[DEBUG] standards extracted: {len(standards)}")

    return standards


# -----------------------------
# 2. 读取历史
# -----------------------------
def load_previous_status():
    if not Path(DATA_FILE).exists():
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("⚠️ corrupted json, resetting")
        return {}


# -----------------------------
# 3. 保存快照（防损坏写法）
# -----------------------------
def save_status(data):
    Path("data").mkdir(exist_ok=True)

    tmp = DATA_FILE + ".tmp"

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    os.replace(tmp, DATA_FILE)


# -----------------------------
# 4. diff
# -----------------------------
def compare(old, new):
    changes = []

    old_keys = set(old.keys())
    new_keys = set(new.keys())

    # 新增
    for k in new_keys - old_keys:
        changes.append({
            "type": "NEW",
            "name": k,
            "new": new[k]["status"]
        })

    # 删除
    for k in old_keys - new_keys:
        changes.append({
            "type": "REMOVED",
            "name": k,
            "old": old[k]["status"]
        })

    # 状态变化
    for k in old_keys & new_keys:
        if old[k]["status"] != new[k]["status"]:
            changes.append({
                "type": "CHANGED",
                "name": k,
                "old": old[k]["status"],
                "new": new[k]["status"]
            })

    return changes


# -----------------------------
# 5. email
# -----------------------------
def send_email(subject, html):
    resend.Emails.send({
        "from": "onboarding@resend.dev",
        "to": [EMAIL_TO],
        "subject": subject,
        "html": html,
    })


def build_html(changes):
    rows = ""

    for c in changes:
        if c["type"] == "NEW":
            rows += f"<tr><td>NEW</td><td>{c['name']}</td><td>-</td><td>{c['new']}</td></tr>"
        elif c["type"] == "REMOVED":
            rows += f"<tr><td>REMOVED</td><td>{c['name']}</td><td>{c['old']}</td><td>-</td></tr>"
        else:
            rows += f"<tr><td>CHANGED</td><td>{c['name']}</td><td>{c['old']}</td><td>{c['new']}</td></tr>"

    return f"""
    <h2>AI Act Standards Update</h2>
    <p>Changes detected: {len(changes)}</p>
    <table border="1" cellpadding="6">
        <tr>
            <th>Type</th><th>Name</th><th>Old</th><th>New</th>
        </tr>
        {rows}
    </table>
    """


# -----------------------------
# 6. main
# -----------------------------
def main():
    print("Fetching...")

    current = fetch_current_status()

    print(f"[INFO] current size: {len(current)}")

    previous = load_previous_status()

    # 第一次运行
    if not previous:
        print("First run → saving snapshot")
        save_status(current)
        return

    changes = compare(previous, current)

    if not changes:
        print("No changes")
        return

    print(f"Changes: {len(changes)}")

    html = build_html(changes)

    send_email(
        subject=f"AI Act Update ({len(changes)})",
        html=html
    )

    save_status(current)

    print("Done")


if __name__ == "__main__":
    main()
