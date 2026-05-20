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
    抓取网站当前标准状态
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

    results = []

    # 提取页面中的所有表格
    tables = soup.find_all("table")

    for table in tables:
        rows = table.find_all("tr")

        for row in rows:
            cols = row.find_all(["td", "th"])

            values = [
                col.get_text(" ", strip=True)
                for col in cols
            ]

            if values:
                results.append(values)

    return results


def load_previous_status():
    """
    读取上一次快照
    """

    if not Path(DATA_FILE).exists():
        return None

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_status(status):
    """
    保存最新快照
    """

    Path("data").mkdir(exist_ok=True)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(
            status,
            f,
            ensure_ascii=False,
            indent=2,
        )


def generate_diff(old, new):
    """
    生成变化内容
    """

    old_set = set(
        json.dumps(x, ensure_ascii=False)
        for x in (old or [])
    )

    new_set = set(
        json.dumps(x, ensure_ascii=False)
        for x in new
    )

    added = sorted(new_set - old_set)
    removed = sorted(old_set - new_set)

    lines = []

    if added:
        lines.append("=== 新增 / 更新 ===\n")

        for item in added:
            lines.append(item)

    if removed:
        lines.append("\n=== 删除 / 旧状态 ===\n")

        for item in removed:
            lines.append(item)

    return "\n".join(lines)


def send_email(subject, body):
    """
    使用 Resend 发送邮件
    """

    resend.Emails.send({
        "from": "onboarding@resend.dev",
        "to": [EMAIL_TO],
        "subject": subject,
        "text": body,
    })


def main():
    print("Fetching current status...")

    current = fetch_current_status()

    print(f"Fetched {len(current)} rows")

    previous = load_previous_status()

    # 第一次运行
    if previous is None:
        print("First run, saving snapshot")

        save_status(current)

        return

    # 比较变化
    if current != previous:
        print("Changes detected")

        diff = generate_diff(previous, current)

        send_email(
            subject="AI Act Standards Changed",
            body=diff,
        )

        save_status(current)

        print("Email sent")
    else:
        print("No changes detected")


if __name__ == "__main__":
    main()
