"""用户历史偏好 — 持久化、加载、行为洞察提取。"""
"""User history — persist past trip preferences and extract behavioral insights."""

import json
import os
from collections import Counter
from datetime import datetime
from typing import Optional

from .models.preference import TravelPreference


HISTORY_DIR = "data"
HISTORY_FILE = os.path.join(HISTORY_DIR, "user_history.json")


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def load_history() -> list[dict]:
    """Load all saved trip preferences from the history file.

    Returns an empty list if the file does not exist.
    """
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_preference(pref: TravelPreference, plan_summary: str = "") -> None:
    """将旅行偏好追加写入 data/user_history.json。"""
    """Append a completed trip preference to the history file."""
    os.makedirs(HISTORY_DIR, exist_ok=True)

    history = load_history()

    entry = {
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "destination": pref.destination,
        "departure": pref.departure,
        "start_date": pref.start_date,
        "end_date": pref.end_date,
        "travelers": pref.travelers,
        "budget_range": pref.budget_range,
        "interests": pref.interests,
        "must_see": pref.must_see,
        "avoid": pref.avoid,
        "accommodation_type": pref.accommodation_type,
        "transport_preference": pref.transport_preference,
        "plan_summary": plan_summary[:200] if plan_summary else "",
    }
    history.append(entry)

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------

def build_history_context() -> Optional[str]:
    """分析历史记录并生成用户行为洞察，供 planner 参考。"""
    """Analyze history and return a concise context string for the planner LLM.

    Returns None if there is no history to speak of.
    """
    history = load_history()
    if not history:
        return None

    # --- destination frequency ---
    dest_counter: Counter[str] = Counter()
    for h in history:
        dest = h.get("destination") or ""
        if dest:
            dest_counter[dest] += 1

    # --- interest frequency ---
    interest_counter: Counter[str] = Counter()
    for h in history:
        interests = h.get("interests") or []
        for tag in interests:
            interest_counter[tag] += 1

    # --- accommodation preference ---
    accom_counter: Counter[str] = Counter()
    for h in history:
        acc = h.get("accommodation_type") or ""
        if acc:
            accom_counter[acc] += 1

    # --- budget ---
    budgets: list[tuple[int, int]] = []
    for h in history:
        br = h.get("budget_range")
        if br and len(br) == 2:
            budgets.append((br[0], br[1]))

    # --- build markdown ---
    lines: list[str] = []

    lines.append(f"历史记录数：{len(history)} 次旅行")

    if dest_counter:
        top_dest = dest_counter.most_common(3)
        lines.append("曾去过的目的地: " + "、".join(
            f"{d}（{c}次）" for d, c in top_dest
        ))

    if interest_counter:
        top_int = interest_counter.most_common(5)
        lines.append("偏好兴趣标签: " + "、".join(
            f"{t}（{c}次）" for t, c in top_int
        ))

    if accom_counter:
        top_acc = accom_counter.most_common(3)
        lines.append("住宿偏好: " + "、".join(
            f"{a}（{c}次）" for a, c in top_acc
        ))

    if budgets:
        avg_min = sum(b[0] for b in budgets) // len(budgets)
        avg_max = sum(b[1] for b in budgets) // len(budgets)
        lines.append(f"历史预算均值约: {avg_min:,} - {avg_max:,} 元")

    context = "\n".join(f"- {line}" for line in lines)
    return (
        "【用户历史偏好（请参考）】\n"
        f"{context}\n\n"
        "在推荐行程时，请考虑用户的历史偏好：优先推荐与历史兴趣匹配的景点类型，"
        "避开用户历史中已多次造访的目的地（除非用户主动要求重游），"
        "尊重用户的住宿偏好（除非用户本次明确要求改变）。"
    )
