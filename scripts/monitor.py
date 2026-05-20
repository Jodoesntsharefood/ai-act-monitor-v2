import requests
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup

URL = "https://ai-act-standards.com/data.js"
STATE_FILE = "latest.json"


# -------------------------
# 1. 获取 data.js
# -------------------------
def fetch_js():
    r = requests.get(URL, timeout=30)
    r.raise_for_status()
    return r.text


# -------------------------
# 2. 从 JS 提取变量
# -------------------------
def extract_variable(js, name):
    pattern = rf"const {name}\s*=\s*(\[\s*\{{.*?\}}\s*\]);"
    match = re.search(pattern, js, re.S)
    if not match:
        return []
    return json.loads(match.group(1))


def extract_number_blocks(js):
    """
    直接抓 dashboard numbers（fallback）
    """
    def find(id_name):
        m = re.search(rf'id="{id_name}">(\d+)<', js)
        return int(m.group(1)) if m else 0

    return {
        "total": find("total-standards"),
        "stage10": find("stage-10-count"),
        "stage20": find("stage-20-count"),
        "stage40": find("stage-40-count"),
        "stage50": find("stage-50-count"),
        "stage60": find("stage-60-count"),
        "cited": find("stage-cited-count"),
    }


# -------------------------
# 3. 加载历史
# -------------------------
def load_previous():
    if not Path(STATE_FILE).exists():
        return None
    try:
        return json.loads(Path(STATE_FILE).read_text())
    except:
        return None


# -------------------------
# 4. 保存
# -------------------------
def save_state(data):
    Path(STATE_FILE).write_text(json.dumps(data, indent=2))


# -------------------------
# 5. diff
# -------------------------
def diff(prev, curr):
    if not prev:
        return "First run"

    changes = []

    for k in curr["stats"]:
        if prev["stats"].get(k) != curr["stats"].get(k):
            changes.append(f"{k}: {prev['stats'].get(k)} → {curr['stats'].get(k)}")

    new_logs = [
        x for x in curr["changelog"]
        if x not in prev.get("changelog", [])
    ]

    return {
        "stats_changes": changes,
        "new_changelog": new_logs
    }


# -------------------------
# 6. 主逻辑
# -------------------------
def main():
    print("Fetching data.js...")

    js = fetch_js()

    # 👉 不再解析 HTML DOM！
    stats = extract_number_blocks(js)

    # changelog（来自 JS）
    changelog = extract_variable(js, "changelog")

    current = {
        "stats": stats,
        "changelog": changelog
    }

    previous = load_previous()
    changes = diff(previous, current)

    print("\n===== CURRENT STATS =====")
    print(json.dumps(stats, indent=2))

    print("\n===== CHANGES =====")
    print(changes)

    save_state(current)


if __name__ == "__main__":
    main()
