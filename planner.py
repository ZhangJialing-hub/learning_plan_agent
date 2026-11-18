import json
from config import MODEL, PLAN_FILE, client


# 1. 调用模型生成计划
def create_plan(user_goal, days, max_hours, errors=None):

    messages = [
        {
            "role": "system",
            "content": f"""
你是一个学习计划规划助手。

根据用户目标生成学习计划。

严格遵守以下要求：
1. 必须正好安排 {days} 天，不能多也不能少。
2. day 字段从"第1天"连续编号到"第{days}天"，不能重复。
3. 每天学习时长必须大于0。
4. 每天学习时长不得超过 {max_hours} 小时。
5. 必须先确定每天的学习时长，再安排对应的学习任务。
6. 不允许为了安排更多学习内容而突破时间限制。
7. 如果学习内容较多，应该减少每天的任务量，而不是增加学习时长，也不能增加天数。

只返回合法 JSON，不要添加 Markdown 代码块。
hours 必须是大于0的数字，不得带单位。

格式：
{{
    "goal": "学习目标",
    "plan": [
        {{
            "day": "第1天",
            "task": "具体学习任务",
            "hours": 1.5
        }}
    ]
}}
""",
        },
        {"role": "user", "content": user_goal},
    ]

    if errors:
        messages.append(
            {
                "role": "user",
                "content": (
                    "上一次的计划没有通过检查，请根据以下错误重新生成完整计划：\n"
                    + "\n".join(errors)
                ),
            }
        )

    response = client.chat.completions.create(model=MODEL, messages=messages)

    return response.choices[0].message.content


# 2. 验证数据格式
def validate_plan_format(plan):

    if not isinstance(plan, dict):
        return False, ["计划必须是 JSON 对象"]

    if not isinstance(plan.get("goal"), str) or not plan["goal"].strip():
        return False, ["goal 必须是非空字符串"]

    if not isinstance(plan.get("plan"), list) or not plan["plan"]:
        return False, ["plan 必须是非空列表"]

    for index, item in enumerate(plan["plan"], start=1):

        if not isinstance(item, dict):
            return False, [f"第{index}项计划必须是对象"]

        for key in ("day", "task", "hours"):
            if key not in item:
                return False, [f"第{index}项计划缺少 {key} 字段"]

        if not isinstance(item["day"], str) or not item["day"].strip():
            return False, [f"第{index}项的 day 必须是非空字符串"]

        if not isinstance(item["task"], str) or not item["task"].strip():
            return False, [f"第{index}项的 task 必须是非空字符串"]

        hours = item["hours"]

        if isinstance(hours, bool) or not isinstance(hours, (int, float)):
            return False, [f"第{index}项的 hours 必须是数字"]

        if hours <= 0:
            return False, [f"第{index}项的 hours 必须大于0"]

    return True, []


# 3. 验证业务规则
def check_plan_days(plan, days):

    actual = len(plan["plan"])

    if actual != days:
        return False, [f"计划共安排了 {actual} 天，用户要求 {days} 天"]

    return True, []


def check_plan_hours(plan, max_hours):

    errors = []

    for item in plan["plan"]:
        if item["hours"] > max_hours:
            errors.append(
                f"{item['day']}安排了{item['hours']}小时，"
                f"每天最多允许{max_hours}小时"
            )

    return len(errors) == 0, errors


# 4. 生成、验证、反馈、重试
def run_agent(user_goal, days, max_hours):

    max_retries = 3
    errors = []

    for attempt in range(max_retries + 1):

        print(f"\n正在生成计划，第{attempt + 1}次...")

        try:
            content = create_plan(user_goal, days, max_hours, errors)
        except Exception as e:
            print("调用模型失败：", e)

            return {"success": False, "message": "调用模型失败", "errors": [str(e)]}

        # 第一层：JSON 解析
        try:
            plan = json.loads(content)
        except json.JSONDecodeError:
            errors = ["上一次返回的内容不是合法 JSON，请只返回合法 JSON。"]
            print("JSON 解析失败")
            continue

        # 第二层：数据格式
        is_valid, errors = validate_plan_format(plan)

        if not is_valid:
            print("数据格式检查失败：")
            for error in errors:
                print(error)
            continue

        # 第三层：业务规则（天数）
        is_valid, errors = check_plan_days(plan, days)

        if not is_valid:
            print("学习天数检查失败：")
            for error in errors:
                print(error)
            continue

        # 第四层：业务规则（每天时长）
        is_valid, errors = check_plan_hours(plan, max_hours)

        if not is_valid:
            print("学习时长检查失败：")
            for error in errors:
                print(error)
            continue

        # 所有检查通过
        print("\n计划验证通过！")
        print("学习目标：", plan["goal"])

        for item in plan["plan"]:
            print(f"{item['day']}：{item['task']}，" f"{item['hours']}小时")

        # 保存计划
        try:
            save_plan(plan)
        except Exception as e:
            return {
                "success": False,
                "message": "计划生成成功，但保存失败",
                "errors": [str(e)],
            }

        # 返回真实执行结果
        return {"success": True, "message": "学习计划生成并保存成功", "plan": plan}

    # 所有尝试都失败
    print("\n已达到最大尝试次数，计划仍未通过检查。")

    return {
        "success": False,
        "message": "学习计划生成失败，已达到最大尝试次数",
        "errors": errors,
    }


def save_plan(plan):

    with open(PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=4)
