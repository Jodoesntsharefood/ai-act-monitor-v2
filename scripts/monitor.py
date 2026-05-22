import os
import re
import json
import requests

URL = "https://ai-act-standards.com/data.js"

DATA_FILE = "data/latest.json"

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
EMAIL_TO = os.getenv("EMAIL_TO")

# =========================
# 测试模式
# True = 每次都发邮件
# False = 只有变化才发
# =========================
FORCE_EMAIL = True


def fetch_js():
    r = requests.get(URL, timeout=30)

    r.raise_for_status()

    with open("debug_data.js", "w", encoding="utf-8") as f:
        f.write(r.text)

    return r.text


def js_object_to_json(js_text):
    """
    JS object -> valid JSON
    """

    js_text = re.sub(r",(\s*[}\]])", r"\1", js_text)

    js_text = re.sub(
        r'([{,]\s*)([A-Za-z0-9_]+)\s*:',
        r'\1"\2":',
        js_text
    )

    js_text = re.sub(r"'", '"', js_text)

    return js_text


def extract_array(js, var_name):
    pattern = rf"const\s+{var_name}\s*=\s*(\[[\s\S]*?\]);"

    match = re.search(pattern, js)

    if not match:
        print(f"[ERROR] cannot find {var_name}")
        return []

    raw = match.group(1)

    cleaned = js_object_to_json(raw)

    try:
        return json.loads(cleaned)

    except Exception as e:
        print(f"[ERROR] parsing {var_name}")
        print(e)

        with open(f"debug_{var_name}.txt", "w", encoding="utf-8") as f:
            f.write(cleaned)

        return []


def calculate_metrics(standards, normrefs):
    all_items = standards + [
        r for r in normrefs if "stage" in r
    ]

    counts = {
        "total_standards": len(all_items),
        "stage_10": 0,
        "stage_20": 0,
        "stage_40": 0,
        "stage_50": 0,
        "stage_60": 0,
        "ojeu": 0
    }

    for item in all_items:
        stage = item.get("stage", 0)

        if stage >= 60:
            counts["stage_60"] += 1
        elif stage >= 50:
            counts["stage_50"] += 1
        elif stage >= 40:
            counts["stage_40"] += 1
        elif stage >= 20:
            counts["stage_20"] += 1
        elif stage >= 10:
            counts["stage_10"] += 1

    return counts


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

    print("[INFO] latest.json updated")


def compare(old, new):
    metric_changes = []

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
            metric_changes.append(
                f"{key}: {old_val} → {new_val}"
            )

    old_logs = {
        json.dumps(x, sort_keys=True)
        for x in old.get("changelog", [])
    }

    new_entries = []

    for item in new.get("changelog", []):
        s = json.dumps(item, sort_keys=True)

        if s not in old_logs:
            new_entries.append(item)

    return metric_changes, new_entries


def send_email(subject, body):
    if not RESEND_API_KEY or not EMAIL_TO:
        print("[WARN] Missing email env vars")
        return

    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "from": "AI Monitor <onboarding@resend.dev>",
        "to": [EMAIL_TO],
        "subject": subject,
        "html": f"<pre>{body}</pre>"
    }

    r = requests.post(
        "https://api.resend.com/emails",
        headers=headers,
        json=payload,
        timeout=30
    )

    print("[INFO] email status:", r.status_code)
    print("[INFO] email response:", r.text)


def main():
    print("Fetching data.js...")

    js = fetch_js()

    standards = extract_array(js, "standards")
    normrefs = extract_array(js, "normativeReferences")
    changelog = extract_array(js, "changelog")

    print("[INFO] standards:", len(standards))
    print("[INFO] normrefs:", len(normrefs))
    print("[INFO] changelog:", len(changelog))

    metrics = calculate_metrics(
        standards,
        normrefs
    )

    current = {
        **metrics,
        "changelog": changelog
    }

    print(json.dumps(current, indent=2))

    previous = load_previous()

    if previous is None or previous == {}:
        print("First run")

        save_current(current)

        send_email(
            "AI Act Monitor Initialized",
            json.dumps(current, indent=2, ensure_ascii=False)
        )

        return

    metric_changes, new_entries = compare(
        previous,
        current
    )

    # ====================================
    # 正常模式：无变化不发邮件
    # FORCE_EMAIL=True 时跳过这里
    # ====================================
    if (
        not metric_changes
        and not new_entries
        and not FORCE_EMAIL
    ):
        print("No changes detected")

        save_current(current)

        return

    lines = []

    if FORCE_EMAIL:
        lines.append("TEST MODE ENABLED")
        lines.append("")

    if metric_changes:
        lines.append("=== METRIC CHANGES ===")

        for c in metric_changes:
            lines.append(c)

    if new_entries:
        lines.append("")
        lines.append("=== NEW CHANGELOG ENTRIES ===")

        for item in new_entries:
            lines.append(
                f"{item.get('date')} | "
                f"{item.get('standard')} | "
                f"{item.get('description')}"
            )

    # 没变化但强制测试
    if FORCE_EMAIL and not metric_changes and not new_entries:
        lines.append("No actual changes.")
        lines.append("This is a forced test email.")

    body = "\n".join(lines)

    print(body)

    send_email(
        "AI Act Standards Monitor",
        body
    )

    save_current(current)


if __name__ == "__main__":
    main()
