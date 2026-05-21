import requests
import json
import os
from bs4 import BeautifulSoup
from datetime import datetime

URL = "https://ai-act-standards.com/"
DATA_FILE = "latest.json"

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_FROM = os.getenv("EMAIL_FROM", EMAIL_TO)


# -----------------------------
# 1. 抓网页 + 解析关键数据
# -----------------------------
def fetch_data():
    print("[INFO] Fetching website...")

    r = requests.get(URL, timeout=30)
    soup = BeautifulSoup(r.text, "html.parser")

    def get(id_):
        el = soup.find(id=id_)
        return int(el.text.strip()) if el else 0

    data = {
        "total_standards": get("total-standards"),
        "stage_10": get("stage-10-count"),
        "stage_20": get("stage-20-count"),
        "stage_40": get("stage-40-count"),
        "stage_50": get("stage-50-count"),
        "stage_60": get("stage-60-count"),
        "ojeu": get("stage-cited-count"),
        "timestamp": datetime.utcnow().isoformat()
    }

    print("[INFO] scraped data:", data)
    return data


# -----------------------------
# 2. 读取旧数据
# -----------------------------
def load_old():
    if not os.path.exists(DATA_FILE):
        return None
    with open(DATA_FILE, "r") as f:
        return json.load(f)


# -----------------------------
# 3. 保存数据
# -----------------------------
def save(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


# -----------------------------
# 4. diff
# -----------------------------
def diff(old, new):
    if not old:
        return "First run - no previous data"

    changes = []
    for k in new:
        if k in old and old[k] != new[k]:
            changes.append(f"{k}: {old[k]} → {new[k]}")

    return "<br>".join(changes) if changes else "No changes"


# -----------------------------
# 5. HTML email
# -----------------------------
def build_email_html(data, changes):
    return f"""
    <html>
    <body style="font-family: Arial;">
        <h2>AI Act Monitor Update</h2>

        <p><b>Total Standards:</b> {data['total_standards']}</p>
        <p><b>Stage 10:</b> {data['stage_10']}</p>
        <p><b>Stage 20:</b> {data['stage_20']}</p>
        <p><b>Stage 40:</b> {data['stage_40']}</p>
        <p><b>Stage 50:</b> {data['stage_50']}</p>
        <p><b>Stage 60:</b> {data['stage_60']}</p>
        <p><b>OJEU:</b> {data['ojeu']}</p>

        <hr>

        <h3>Changes</h3>
        <p>{changes}</p>

        <hr>

        <p>
            🔗 <a href="https://ai-act-standards.com/" target="_blank">
            Open Dashboard</a>
        </p>

        <small>Generated at {data['timestamp']}</small>
    </body>
    </html>
    """


# -----------------------------
# 6. send email (Resend)
# -----------------------------
def send_email(html):
    if not RESEND_API_KEY:
        print("[WARN] No RESEND_API_KEY")
        return

    payload = {
        "from": EMAIL_FROM,
        "to": EMAIL_TO,
        "subject": "AI Act Monitor Update",
        "html": html
    }

    r = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload
    )

    print("[INFO] email status:", r.status_code)
    print("[INFO] email response:", r.text)


# -----------------------------
# MAIN
# -----------------------------
def main():
    new_data = fetch_data()
    old_data = load_old()

    changes = diff(old_data, new_data)

    save(new_data)

    html = build_email_html(new_data, changes)
    send_email(html)

    print("[DONE] monitoring complete")


if __name__ == "__main__":
    main()
