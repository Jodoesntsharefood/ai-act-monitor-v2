import os
import re
import json
import requests
from bs4 import BeautifulSoup

URL = "https://ai-act-standards.com/"
DATA_FILE = "data/latest.json"

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
EMAIL_TO = os.getenv("EMAIL_TO")


def fetch_html():
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    r = requests.get(URL, headers=headers, timeout=30)
    r.raise_for_status()

    with open("debug.html", "w", encoding="utf-8") as f:
        f.write(r.text)

    return r.text


def extract_number(soup, element_id):
    el = soup.find(id=element_id)

    if not el:
        return 0

    text = el.get_text(strip=True)

    match = re.search(r"\d+", text)

    if not match:
        return 0

    return int(match.group())


def extract_changelog(soup):
    rows = []

    tbody = soup.find("tbody", {"id": "changelog-body"})

    if not tbody:
        return rows

    trs = tbody.find_all("tr")

    for tr in trs:
        cols = tr.find_all("td")

        if len(cols) < 3:
            continue

        rows.append({
            "date": cols[0].get_text(" ", strip=True),
            "standard": cols[1].get_text(" ", strip=True),
            "change": cols[2].get_text(" ", strip=True),
        })

    return rows


def load_previous():
    if not os.path.exists(DATA_FILE):
        return None

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None


def save_current(data):
    os.makedirs("data", exist_ok=True)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("[DEBUG] latest.json saved")


def compare(old, new):
    changes = []

    metric_keys = [
        "total_standards",
        "stage_10",
        "stage_20",
        "stage_40",
        "stage_50",
        "stage_60",
        "ojeu"
    ]

    for key in metric_keys:
        old_val = old.get(key, 0)
        new_val = new.get(key, 0)

        if old_val != new_val:
            changes.append(
                f"{key}: {old_val} → {new_val}"
            )

    old_logs = old.get("changelog", [])
    new_logs = new.get("changelog", [])

    old_set = {
        json.dumps(x, sort_keys=True)
        for x in old_logs
    }

    added = []

    for item in new_logs:
        s = json.dumps(item, sort_keys=True)

        if s not in old_set:
            added.append(item)

    return changes, added


def send_email(subject, body):
    if not RESEND_API_KEY or not EMAIL_TO:
        print("[WARN] Email env vars missing")
        return

    payload = {
        "from": "AI Monitor <onboarding@resend.dev>",
        "to": [EMAIL_TO],
        "subject": subject,
        "html": f"<pre>{body}</pre>"
    }

    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }

    r = requests.post(
        "https://api.resend.com/emails",
        headers=headers,
        json=payload,
        timeout=30
    )

    print("[DEBUG] email status:", r.status_code)
    print("[DEBUG] email response:", r.text)


def main():
    print("Fetching website...")

    html = fetch_html()

    soup = BeautifulSoup(html, "html.parser")

    current = {
        "total_standards": extract_number(soup, "total-standards"),
        "stage_10": extract_number(soup, "stage-10-count"),
        "stage_20": extract_number(soup, "stage-20-count"),
        "stage_40": extract_number(soup, "stage-40-count"),
        "stage_50": extract_number(soup, "stage-50-count"),
        "stage_60": extract_number(soup, "stage-60-count"),
        "ojeu": extract_number(soup, "stage-cited-count"),
        "changelog": extract_changelog(soup)
    }

    print(json.dumps(current, indent=2))

    previous = load_previous()

    if previous is None:
        print("First run, saving baseline")

        save_current(current)

        send_email(
            "AI Act Monitor Initialized",
            json.dumps(current, indent=2, ensure_ascii=False)
        )

        return

    changes, new_logs = compare(previous, current)

    if not changes and not new_logs:
        print("No changes detected")

        save_current(current)

        return

    lines = []

    if changes:
        lines.append("=== METRIC CHANGES ===")

        for c in changes:
            lines.append(c)

    if new_logs:
        lines.append("")
        lines.append("=== NEW CHANGELOG ENTRIES ===")

        for item in new_logs:
            lines.append(
                f"{item['date']} | "
                f"{item['standard']} | "
                f"{item['change']}"
            )

    body = "\n".join(lines)

    print(body)

    send_email(
        "AI Act Standards Updated",
        body
    )

    save_current(current)


if __name__ == "__main__":
    main()
