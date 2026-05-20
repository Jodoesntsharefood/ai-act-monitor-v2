import json
import os
from pathlib import Path

import requests
import resend
from bs4 import BeautifulSoup

URL = "https://ai-act-standards.com/"
DATA_FILE = "data/latest.json"

RESEND_API_KEY = os.environ["RESEND_API_KEY"]
EMAIL_TO = os.environ["EMAIL_TO"]

resend.api_key = RESEND_API_KEY


def fetch_current_status():
    """
    提取结构化标准数据
    """

    response = requests.get(
        URL,
        timeout=30,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        },
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    standards = {}

    # 抓取所有表格
    tables = soup.find_all("table")

    for table in tables:

        rows = table.find_all("tr")

        headers = []

        for idx, row in enumerate(rows):

            cols = row.find_all(["th", "td"])

            values = [
                col.get_text(" ", strip=True)
                for col in cols
            ]

            if not values:
                continue

            # 第一行作为 header
            if idx == 0:
                headers = values
                continue

            # 跳过不完整行
            if len(values) != len(headers):
                continue

            item = dict(zip(headers, values))

            # 自动识别标准名称字段
            standard_name = (
                item.get("Standard")
                or item.get("Title")
                or item.get("Name")
                or item.get("Reference")
            )

            # 自动识别状态字段
            status = (
                item.get("Status")
                or item.get("Stage")
                or item.get("State")
            )

            if not standard_name or not status:
                continue

            standards[standard_name] = {
                "status": status,
                "raw": item,
            }

    return standards


def load_previous_status():

    if not Path(DATA_FILE).exists():
        return {}

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_status(status):

    Path("data").mkdir(exist_ok=True)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(
            status,
            f,
            ensure_ascii=False,
            indent=2,
        )


def compare_status(old, new):
    """
    精准比较状态变化
    """

    changes = []

    old_keys = set(old.keys())
    new_keys = set(new.keys())

    # 新增标准
    added = new_keys - old_keys

    for key in sorted(added):
        changes.append({
            "type": "NEW",
            "standard": key,
            "new_status": new[key]["status"],
        })

    # 删除标准
    removed = old_keys - new_keys

    for key in sorted(removed):
        changes.append({
            "type": "REMOVED",
            "standard": key,
            "old_status": old[key]["status"],
        })

    # 状态变化
    common = old_keys & new_keys

    for key in sorted(common):

        old_status = old[key]["status"]
        new_status = new[key]["status"]

        if old_status != new_status:

            changes.append({
                "type": "STATUS_CHANGED",
                "standard": key,
                "old_status": old_status,
                "new_status": new_status,
            })

    return changes


def build_email_html(changes):

    rows = []

    for change in changes:

        if change["type"] == "NEW":

            rows.append(f"""
            <tr>
                <td>NEW</td>
                <td>{change['standard']}</td>
                <td>-</td>
                <td>{change['new_status']}</td>
            </tr>
            """)

        elif change["type"] == "REMOVED":

            rows.append(f"""
            <tr>
                <td>REMOVED</td>
                <td>{change['standard']}</td>
                <td>{change['old_status']}</td>
                <td>-</td>
            </tr>
            """)

        elif change["type"] == "STATUS_CHANGED":

            rows.append(f"""
            <tr>
                <td>STATUS_CHANGED</td>
                <td>{change['standard']}</td>
                <td>{change['old_status']}</td>
                <td>{change['new_status']}</td>
            </tr>
            """)

    html = f"""
    <h2>AI Act Standards 更新</h2>

    <p>
        检测到 <strong>{len(changes)}</strong> 个变化
    </p>

    <table border="1" cellpadding="8" cellspacing="0">
        <tr>
            <th>Type</th>
            <th>Standard</th>
            <th>Old Status</th>
            <th>New Status</th>
        </tr>

        {''.join(rows)}

    </table>

    <br>

    <p>
        来源:
        <a href="https://ai-act-standards.com/">
            ai-act-standards.com
        </a>
    </p>
    """

    return html


def send_email(subject, html):

    resend.Emails.send({
        "from": "onboarding@resend.dev",
        "to": [EMAIL_TO],
        "subject": subject,
        "html": html,
    })


def main():

    print("Fetching current standards...")

    current = fetch_current_status()

    print(f"Fetched {len(current)} standards")

    previous = load_previous_status()

    # 第一次运行
    if not previous:

        print("First run - saving snapshot")

        save_status(current)

        return

    changes = compare_status(previous, current)

    # 没变化
    if not changes:

        print("No status changes detected")

        return

    print(f"Detected {len(changes)} changes")

    html = build_email_html(changes)

    send_email(
        subject=f"AI Act Standards Updated ({len(changes)} changes)",
        html=html,
    )

    save_status(current)

    print("Notification sent")


if __name__ == "__main__":
    main()
