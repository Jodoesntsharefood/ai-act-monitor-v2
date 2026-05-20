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
# 1. 自适应抓取核心
# =========================
def fetch_current_status():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(URL, wait_until="networkidle")
        page.wait_for_timeout(3000)

        html = page.content()
        browser.close()

    # -------- DEBUG（关键）--------
    print(f"[DEBUG] HTML size: {len(html)}")

    soup = BeautifulSoup(html, "lxml")

    # =========================
    # Layer 1: JSON / Next.js
    # =========================
    next_data = extract_next_data(html)
    if next_data:
        print("[MODE] NEXT_DATA")
        return parse_next_data(next_data)

    # =========================
    # Layer 2: Card / DOM 模式
    # =========================
    cards = soup.select(
        ".card, .standard, .item, .row, .flex, article, li, div"
    )

    results = {}

    for c in cards:
        text = c.get_text(" ", strip=True)

        name = extract_name(text)
        status = extract_status(text)

        if name and status:
            results[name] = {"status": status}

    if results:
        print(f"[MODE] CARD | {len(results)} items")
        return results

    # =========================
    # Layer 3: Table fallback
    # =========================
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

            if i == 0:
                headers = values
                continue

            if len(values) != len(headers):
                continue

            item = dict(zip(headers, values))

            name = find_field(item, ["standard", "name", "reference", "title"])
            status = find_field(item, ["status", "stage", "state", "development"])

            if name and status:
                results[name] = {"status": status}

    print(f"[MODE] TABLE | {len(results)} items")
    return results


# =========================
# 2. Next.js JSON 提取
# =========================
def extract_next_data(html):
    match = re.search(
        r'__NEXT_DATA__.*?>(.*?)</script>',
        html,
        re.DOTALL
    )
    if not match:
        return None

    try:
        return json.loads(match.group(1))
    except:
        return None


def parse_next_data(data):
    """
    如果网站是 Next.js，这里做兜底解析
    （目前保持通用结构）
    """
    results = {}

    try:
        # 尝试递归找 list/dict 里的标准数据
        def walk(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    walk(v)
            elif isinstance(obj, list):
                for i in obj:
                    walk(i)
            elif isinstance(obj, str):
                if "EN " in obj or "ISO " in obj:
                    results[obj] = {"status": "unknown"}

        walk(data)

    except:
        pass

    return results


# =========================
# 3. 文本解析辅助
# =========================
def extract_name(text):
    patterns = [
        r"(EN\s?\d+[\w\-]*)",
        r"(prEN\s?\d+[\w\-]*)",
        r"(ISO\s?\d+[\w\-]*)",
    ]

    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1)

    return None


def extract_status(text):
    keywords = [
        "Draft",
        "Approved",
        "Final",
        "Stage",
        "Voting",
        "Published",
        "Development",
    ]

    for k in keywords:
        if k.lower() in text.lower():
            return k

    return None


def find_field(item, keys):
    for k, v in item.items():
        for key in keys:
            if key.lower() in k.lower():
                return v
    return None


# =========================
# 4. 状态存取
# =========================
def load_previous_status():
    if not Path(DATA_FILE).exists():
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_status(data):
    Path("data").mkdir(exist_ok=True)

    tmp = DATA_FILE + ".tmp"

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    os.replace(tmp, DATA_FILE)


# =========================
# 5. diff
# =========================
def compare(old, new):
    changes = []

    old_keys = set(old.keys())
    new_keys = set(new.keys())

    for k in new_keys - old_keys:
        changes.append({
            "type": "NEW",
            "name": k,
            "new": new[k]["status"]
        })

    for k in old_keys - new_keys:
        changes.append({
            "type": "REMOVED",
            "name": k,
            "old": old[k]["status"]
        })

    for k in old_keys & new_keys:
        if old[k]["status"] != new[k]["status"]:
            changes.append({
                "type": "CHANGED",
                "name": k,
                "old": old[k]["status"],
                "new": new[k]["status"]
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


# =========================
# 7. main
# =========================
def main():
    print("Fetching...")

    current = fetch_current_status()

    print(f"[INFO] extracted: {len(current)}")

    previous = load_previous_status()

    if not previous:
        print("First run → save snapshot")
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
