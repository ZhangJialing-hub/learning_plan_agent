import json
import os
from datetime import datetime

from config import MEMORY_FILE

MAX_HISTORY = 5

# 读取用户画像；文件不存在或损坏时返回空画像。
def load_profile():
    if not os.path.exists(MEMORY_FILE):
        return {"preferences": {}, "history": []}

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            profile = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"preferences": {}, "history": []}

    profile.setdefault("preferences", {})
    profile.setdefault("history", [])
    return profile


def save_profile(profile):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=4)


# 写入一条长期偏好，覆盖同名偏好
def remember(key, value):
    profile = load_profile()
    profile["preferences"][key] = value
    save_profile(profile)
    return profile["preferences"]


# 记录一次成功生成的任务，只保留最近若干条。
def add_history(goal, days, max_hours):
    profile = load_profile()
    profile["history"].append(
        {
            "goal": goal,
            "days": days,
            "max_hours": max_hours,
        }
    )
    profile["history"] = profile["history"][-MAX_HISTORY:]
    save_profile(profile)


# 返回最近的任务索引（最新在前），不含每天的具体内容。
def list_history():
    profile = load_profile()

    items = profile["history"][-MAX_HISTORY:]

    return [
        {
            "goal": item.get("goal", ""),
            "days": item.get("days"),
            "max_hours": item.get("max_hours"),
        }
        for item in reversed(items)
    ]


# 把画像转成可注入提示词的文本；没有记忆时返回空字符串。
def format_memory():
    profile = load_profile()

    lines = []

    preferences = profile["preferences"]
    if preferences:
        lines.append("已知用户偏好：")
        for key, value in preferences.items():
            lines.append(f"- {key}：{value}")

    if profile["history"]:
        lines.append(
            "注：用户过去有学习计划的历史记录，需要了解时请调用 list_history 工具。"
        )

    if not lines:
        return ""

    return "\n".join(lines) + "\n\n"
