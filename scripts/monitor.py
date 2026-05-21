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
# 抓取数据
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

    print("[INFO] scraped:", data)
    return data


# -----------------------------
# 读取旧数据
# -----------------------------
def load_old():
    if not os.path.exists(DATA_FILE):
        return None
    with open(DATA_FILE, "r") as f:
        return json.load(f)


# -----------------------------
# 保存
# -----------------------------
def save(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


# -----------------------------
# 计算变化
# -----------------------------
def diff(old, new):
    if not old:
        return {}

    changes = {}
    for k in new:
        if k in old and old[k] != new[k]:
            changes[k] = (old[k], new[k])
    return changes


# -----------------------------
# HTML Dashboard Email
# -----------------------------
def build_email_html(data, changes):
    def row(label, key):
        old, new = changes.get(key, (None, data[key]))

        if old is None:
            arrow = ""
            color = ""
        elif new > old:
            arrow = "🟢 ↑"
            color = "style='color:green'"
        elif new < old:
            arrow = "🔴 ↓"
            color = "style='color:red'"
        else:
            arrow = ""
            color = ""

        return f"""
        <tr>
            <td>{label}</td>
            <td {color}><b>{new}</b> {arrow}</td>
        </tr>
        """

    return f"""
    <html>
    <body style="font-family: Arial; background:#f6f6f6; padding:20px;">

        <div style="max-width:700px; margin:auto; background:white; padding:20px; border-radius:10px;">

            <h2>📊 AI Act Monitor Dashboard</h2>

            <p>
                🔗 Source: 
                <a href="{URL}" target="_blank">{URL}</a>
            </p>

            <hr>

            <h3>📌 Standards Overview</h3>

            <table border="1" cellpadding="8" cellspacing="0" width="100%" style="border-collapse: collapse;">
                <tr><th>Metric</th><th>Value</th></tr>

                {row("Total Standards", "total_standards")}
                {row("Stage 10", "stage_10")}
                {row("Stage 20", "stage_20")}
                {row("Stage 40", "stage_40")}
                {row("Stage 50", "stage_50")}
                {row("Stage 60", "stage_60")}
                {row("OJEU", "ojeu")}
            </table>

            <hr>

            <h3>📝 Changes</h3>
            <p>
                {format_changes(changes)}
            </p>

            <hr>

            <p style="font-size:12px;color:gray;">
                Generated at {data['timestamp']}
            </p>

        </div>

    </body>
    </html>
    """


# -----------------------------
# 格式化变化
# -----------------------------
def format_changes(changes):
    if not changes:
        return "No changes"

    html = "<ul>"
    for k, (old, new) in changes.items():
        html += f"<li><b>{k}</b>: {old} → {new}</li>"
    html += "</ul>"
    return html


# -----------------------------
# 发送邮件
# -----------------------------
def send_email(html):
    print("[DEBUG] EMAIL_TO:", EMAIL_TO)
    print("[DEBUG] EMAIL_FROM:", EMAIL_FROM)

    payload = {
        "from": EMAIL_FROM,
        "to": [EMAIL_TO],
        "subject": "📊 AI Act Monitor Dashboard Update",
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
# main
# -----------------------------
def main():
    new_data = fetch_data()
    old_data = load_old()

    changes = diff(old_data, new_data)

    save(new_data)

    html = build_email_html(new_data, changes)
    send_email(html)

    print("[DONE]")


if __name__ == "__main__":
    main()
