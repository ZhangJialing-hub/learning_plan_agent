import json
import os
from config import PLAN_FILE


def load_plan():

    # 1. 判断文件是否存在
    if not os.path.exists(PLAN_FILE):
        print("还没有保存过学习计划")
        return None

    # 2. 读取 JSON 文件，文件损坏时不让主流程崩溃
    try:
        with open(PLAN_FILE, "r", encoding="utf-8") as f:
            plan = json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        print("读取学习计划失败：", e)
        return None

    # 3. 校验基本结构
    if (
        not isinstance(plan, dict)
        or not isinstance(plan.get("goal"), str)
        or not isinstance(plan.get("plan"), list)
    ):
        print("学习计划文件结构不正确")
        return None

    # 4. 输出学习目标
    print("\n当前学习计划")
    print("学习目标：", plan["goal"])

    # 5. 遍历并输出每天的任务
    for item in plan["plan"]:
        if not isinstance(item, dict):
            continue
        print(
            f"{item.get('day', '未知')}："
            f"{item.get('task', '')}，"
            f"{item.get('hours', '')}小时"
        )

    return plan


if __name__ == "__main__":
    load_plan()
