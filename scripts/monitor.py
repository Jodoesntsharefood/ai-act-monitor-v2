import requests
import json
import os
from bs4 import BeautifulSoup
from pathlib import Path
import resend

URL = "https://ai-act-standards.com/"
STATE_FILE = "latest.json"

# =========================
# RESEND
# =========================
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
EMAIL_TO = os.getenv("EMAIL_TO")

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


# =========================
# FETCH HTML
# =========================
def fetch_html():
    print("[DEBUG] Fetching HTML...")
    r = requests.get(URL, timeout=30)

    print(f"[DEBUG] Status code: {r.status_code}")
    print(f"[DEBUG] HTML length: {len(r.text)}")

    r.raise_for_status()

    Path("debug.html").write_text(r.text)

    print("[DEBUG] debug.html written")

    return r.text


# =========================
# EXTRACT STATS
# =========================
def extract_stats(soup):
    print("[DEBUG] Extracting stats...")

    stats = {}

    mapping = {
        "total": "total-standards",
        "stage10": "stage-10-count",
        "stage20": "stage-20-count",
        "stage40": "stage-40-count",
        "stage50": "stage-50-count",
        "stage60": "stage-60-count",
        "cited": "stage-cited-count",
    }

    for key, html_id in mapping.items():
        el = soup.find(id=html_id)

        if el:
            value = el.get_text(strip=True)
            print(f"[DEBUG] {html_id} -> {value}")

            try:
                stats[key] = int(value)
            except:
                stats[key] = 0
        else:
            print(f"[WARNING] Missing element: {html_id}")
            stats[key] = 0

    return stats


# =========================
# EXTRACT CHANGELOG
# =========================
def extract_changelog(soup):
    print("[DEBUG] Extracting changelog...")

    tbody = soup.find("tbody", {"id": "changelog-body"})

    if not tbody:
        print("[WARNING] changelog-body not found")
        return []

    rows = tbody.find_all("tr")

    print(f"[DEBUG] changelog rows found: {len(rows)}")

    logs = []

    for row in rows:
        cols = row.find_all("td")

        if len(cols) >= 3:
            item = {
                "date": cols[0].get_text(strip=True),
                "standard": cols[1].get_text(strip=True),
                "change": cols[2].get_text(strip=True),
            }

            logs.append(item)

    return logs


# =========================
# LOAD PREVIOUS
# =========================
def load_previous():
    print("[DEBUG] Loading previous state...")

    if not Path(STATE_FILE).exists():
        print("[DEBUG] latest.json does not exist")
        return None

    content = Path(STATE_FILE).read_text().strip()

    if not content:
        print("[WARNING] latest.json is empty")
        return None

    try:
        data = json.loads(content)
        print("[DEBUG] previous state loaded")
        return data

    except Exception as e:
        print("[ERROR] Failed loading latest.json")
        print(e)
        return None


# =========================
# SAVE STATE
# =========================
def save_state(data):
    print("[DEBUG] Saving latest.json...")

    payload = json.dumps(
        data,
        indent=2,
        ensure_ascii=False
    )

    Path(STATE_FILE).write_text(payload)

    print("[DEBUG] latest.json written")
    print(payload)


# =========================
# DIFF
# =========================
def diff(prev, curr):
    changes = []

    if not prev:
        print("[DEBUG] First run detected")

        return {
            "first_run": True,
            "changes": [],
            "new_logs": curr["changelog"]
        }

    # stats diff
    for k in curr["stats"]:
        old = prev["stats"].get(k)
        new = curr["stats"].get(k)

        if old != new:
            changes.append(
                f"{k}: {old} -> {new}"
            )

    # changelog diff
    prev_logs = {
        json.dumps(x, sort_keys=True)
        for x in prev.get("changelog", [])
    }

    new_logs = []

    for log in curr["changelog"]:
        s = json.dumps(log, sort_keys=True)

        if s not in prev_logs:
            new_logs.append(log)

    return {
        "first_run": False,
        "changes": changes,
        "new_logs": new_logs
    }


# =========================
# EMAIL
# =========================
def send_email(result, current):
    if not RESEND_API_KEY:
        print("[WARNING] Missing RESEND_API_KEY")
        return

    if not EMAIL_TO:
        print("[WARNING] Missing EMAIL_TO")
        return

    if (
        not result["changes"]
        and not result["new_logs"]
        and not result["first_run"]
    ):
        print("[DEBUG] No changes detected, skipping email")
        return

    print("[DEBUG] Sending email...")

    html = "<h2>AI Act Monitor Update</h2>"

    html += "<h3>Current Stats</h3>"
    html += "<table border='1' cellpadding='6'>"

    for k, v in current["stats"].items():
        html += f"<tr><td>{k}</td><td>{v}</td></tr>"

    html += "</table>"

    if result["changes"]:
        html += "<h3>Stats Changes</h3><ul>"

        for c in result["changes"]:
            html += f"<li>{c}</li>"

        html += "</ul>"

    if result["new_logs"]:
        html += "<h3>New Changelog Entries</h3><ul>"

        for log in result["new_logs"]:
            html += (
                f"<li>"
                f"{log['date']} | "
                f"{log['standard']} | "
                f"{log['change']}"
                f"</li>"
            )

        html += "</ul>"

    try:
        resend.Emails.send({
            "from": "onboarding@resend.dev",
            "to": EMAIL_TO,
            "subject": "AI Act Monitor Update",
            "html": html
        })

        print("[DEBUG] Email sent")

    except Exception as e:
        print("[ERROR] Email failed")
        print(e)


# =========================
# MAIN
# =========================
def main():
    html = fetch_html()

    soup = BeautifulSoup(html, "html.parser")

    stats = extract_stats(soup)
    changelog = extract_changelog(soup)

    print("[DEBUG] FINAL STATS:")
    print(stats)

    print("[DEBUG] CHANGELOG COUNT:")
    print(len(changelog))

    current = {
        "stats": stats,
        "changelog": changelog
    }

    previous = load_previous()

    result = diff(previous, current)

    print("[DEBUG] DIFF RESULT:")
    print(json.dumps(result, indent=2))

    save_state(current)

    send_email(result, current)

    print("[DEBUG] Script completed successfully")


if __name__ == "__main__":
    main()
