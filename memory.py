import json
import os

from config import MEMORY_FILE

MAX_HISTORY = 5
MAX_KEY_LENGTH = 50
MAX_VALUE_LENGTH = 200


def _single_line(text, limit):
    """压缩换行和多余空白，并截断到指定长度，避免污染提示词。"""
    return " ".join(str(text).split())[:limit]


# 读取用户画像；文件不存在、损坏或结构不正确时返回空画像。
def load_profile():
    empty = {"preferences": {}, "history": []}

    if not os.path.exists(MEMORY_FILE):
        return empty

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            profile = json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return empty

    # 顶层不是对象时按空画像处理
    if not isinstance(profile, dict):
        return empty

    # 字段类型不正确时重置，避免后续读写崩溃
    if not isinstance(profile.get("preferences"), dict):
        profile["preferences"] = {}

    if not isinstance(profile.get("history"), list):
        profile["history"] = []

    return profile


def save_profile(profile):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=4)


# 写入一条长期偏好，覆盖同名偏好
def remember(key, value):
    key = _single_line(key, MAX_KEY_LENGTH)
    value = _single_line(value, MAX_VALUE_LENGTH)

    if not key or not value:
        raise ValueError("偏好名称和内容不能为空")

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

    history = [item for item in profile["history"] if isinstance(item, dict)]
    items = history[-MAX_HISTORY:]

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
    preference_lines = []
    for key, value in preferences.items():
        safe_key = _single_line(key, MAX_KEY_LENGTH)
        safe_value = _single_line(value, MAX_VALUE_LENGTH)
        if safe_key and safe_value:
            preference_lines.append(f"- {safe_key}：{safe_value}")

    if preference_lines:
        lines.append("已知用户偏好：")
        lines.extend(preference_lines)

    if profile["history"]:
        lines.append(
            "注：用户过去有学习计划的历史记录，需要了解时请调用 list_history 工具。"
        )

    if not lines:
        return ""

    return "\n".join(lines) + "\n\n"
