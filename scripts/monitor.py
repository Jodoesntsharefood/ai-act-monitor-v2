import requests
import json
from bs4 import BeautifulSoup
from pathlib import Path

URL = "https://ai-act-standards.com/"
STATE_FILE = "latest.json"


# -----------------------------
# 1. 获取页面
# -----------------------------
def fetch_html():
    r = requests.get(URL, timeout=30)
    r.raise_for_status()
    return r.text


# -----------------------------
# 2. 提取 dashboard 数字
# -----------------------------
def extract_stats(html):
    def get(id_):
        import re
        m = re.search(rf'id="{id_}">(\d+)<', html)
        return int(m.group(1)) if m else 0

    return {
        "total": get("total-standards"),
        "stage10": get("stage-10-count"),
        "stage20": get("stage-20-count"),
        "stage40": get("stage-40-count"),
        "stage50": get("stage-50-count"),
        "stage60": get("stage-60-count"),
        "cited": get("stage-cited-count"),
    }


# -----------------------------
# 3. 提取 changelog
# -----------------------------
def extract_changelog(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("#changelog-body tr")

    logs = []
    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 3:
            logs.append({
                "date": cols[0].get_text(strip=True),
                "standard": cols[1].get_text(strip=True),
                "change": cols[2].get_text(strip=True),
            })
    return logs


# -----------------------------
# 4. load state
# -----------------------------
def load_previous():
    if not Path(STATE_FILE).exists():
        return None
    try:
        return json.loads(Path(STATE_FILE).read_text())
    except:
        return None


# -----------------------------
# 5. save state
# -----------------------------
def save_state(data):
    Path(STATE_FILE).write_text(json.dumps(data, indent=2))


# -----------------------------
# 6. diff logic
# -----------------------------
def diff(prev, curr):
    if not prev:
        return {
            "type": "first_run",
            "message": "First run, snapshot saved."
        }

    changes = []

    # stats diff
    for k in curr["stats"]:
        if prev["stats"].get(k) != curr["stats"].get(k):
            changes.append({
                "field": k,
                "before": prev["stats"].get(k),
                "after": curr["stats"].get(k)
            })

    # changelog diff（新增行）
    prev_logs = set(
        (x["date"], x["standard"], x["change"])
        for x in prev.get("changelog", [])
    )

    new_logs = [
        x for x in curr["changelog"]
        if (x["date"], x["standard"], x["change"]) not in prev_logs
    ]

    return {
        "type": "update",
        "stats_changes": changes,
        "new_changelog": new_logs
    }


# -----------------------------
# 7. main
# -----------------------------
def main():
    print("Fetching page...")

    html = fetch_html()

    stats = extract_stats(html)
    changelog = extract_changelog(html)

    current = {
        "stats": stats,
        "changelog": changelog
    }

    previous = load_previous()
    result = diff(previous, current)

    print("\n===== CURRENT STATS =====")
    print(json.dumps(stats, indent=2))

    print("\n===== DIFF =====")
    print(json.dumps(result, indent=2))

    save_state(current)


if __name__ == "__main__":
    main()
