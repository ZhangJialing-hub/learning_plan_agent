import json

from config import MODEL, client
from memory1 import add_history, format_memory, list_history, remember
from planner import run_agent
from storage import load_plan

# 定义 Agent 可以使用的工具
tools = [
    {
        "type": "function",
        "function": {
            "name": "create_plan",
            "description": "根据用户目标生成学习计划",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "用户的学习目标，不需要包含天数",
                    },
                    "days": {"type": "integer", "description": "用户要求的学习天数"},
                    "max_hours": {
                        "type": "number",
                        "description": "每天最多学习多少小时",
                    },
                },
                "required": ["goal", "days", "max_hours"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "view_plan",
            "description": "查看当前保存的那一份学习计划的完整内容",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_history",
            "description": "查看用户过去制定过哪些学习计划（只含目标、天数、每天时长、时间，不含每天的具体任务）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember_preference",
            "description": "记住用户的长期偏好，跨会话保存。例如每天最多学习几个小时、偏好的学习方向",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "偏好名称，例如：每天最多学习时长",
                    },
                    "value": {"type": "string", "description": "偏好内容，例如：2"},
                },
                "required": ["key", "value"],
            },
        },
    },
]


def show_execution_summary(completed_steps, failed_steps):

    if completed_steps:
        print("\n已经成功完成的工具：")
        for item in completed_steps:
            print(f"- {item['name']}：{item['summary']}")

    if failed_steps:
        print("\n执行失败的工具：")
        for item in failed_steps:
            print(f"- {item['name']}：{item['summary']}")

    if not completed_steps and not failed_steps:
        print("\n本次没有执行任何工具。")


def ask_agent(user_input):

    memory_text = format_memory()

    messages = [
        {
            "role": "system",
            "content": f"""你是一个学习计划助手。
根据用户需求选择合适的工具：
1. 用户想制定、生成学习计划时，调用 create_plan。
2. 用户想查看"当前保存的那份计划的内容"时，调用 view_plan。
3. 用户想了解"过去制定过哪些计划 / 历史记录"时，调用 list_history。
4. 用户要你记住某项长期偏好时，调用 remember_preference。
5. 如果用户没有提出这四种需求，不要调用工具，直接说明目前只能生成计划、查看当前计划、查看历史记录或记住偏好。
6. 不要在结尾问用户需不需要更进一步做其他事情。

注意 view_plan 与 list_history 的区别：
- view_plan 返回当前保存的最新一份计划，包含每天的具体任务。
- list_history 返回最近若干次任务的索引（目标、天数、时长、时间），不包含每天的具体内容。
- 用户问"以前做过什么""历史计划""制定过哪些计划"时，必须调用 list_history，不要用 view_plan 代替。

{memory_text}调用 create_plan 时：
- goal 只描述学习目标；学习天数单独放入 days 参数。
- days 必须是用户提出的正整数天数；用户没说时，先询问用户，不要猜测。
- max_hours 优先使用用户本次提出的时长；用户没说时，使用"已知用户偏好"中的时长并说明；两者都没有，才询问用户，不要猜测。

当用户明确要求制定学习计划时：
1. 只要用户明确要求制定学习计划，并且已经具备学习目标、学习天数和每天最大学习时长，就必须先调用 create_plan。
2. 不要自行判断用户提供的参数是否合理。
3. 如果工具返回参数错误，仔细阅读错误信息。
4. 如果能够通过修正参数解决，可以再次调用工具。
5. 如果无法解决，停止调用工具，向用户说明失败原因。
6. 不要把执行失败的任务说成已经成功完成。
""",
        },
        {"role": "user", "content": user_input},
    ]

    # 记录成功和失败的工具
    completed_steps = []
    failed_steps = []

    # 最大模型请求轮数
    MAX_STEPS = 5
    MAX_TOOL_ATTEMPTS = 2

    # 记录每个工具在本次请求中实际执行了多少次
    tool_attempts = {}
    total_tool_calls = 0
    MAX_TOTAL_TOOL_CALLS = 10

    for step in range(MAX_STEPS):

        print(f"\n--- Agent 第 {step + 1} 轮 ---")

        # 1. 请求模型进行判断
        response = client.chat.completions.create(
            model=MODEL, messages=messages, tools=tools, tool_choice="auto"
        )

        message = response.choices[0].message

        # 2. 如果模型没有调用工具，直接回答
        if not message.tool_calls:
            print("\nAgent：", message.content)

            show_execution_summary(completed_steps, failed_steps)

            return

        # 3. 保存模型的工具调用消息
        messages.append(message.model_dump(exclude_none=True))

        # 4. 逐个执行模型要求的工具
        for tool_call in message.tool_calls:

            function_name = tool_call.function.name
            print("\n模型选择的工具：", function_name)

            # 初始化当前工具的执行状态
            tool_status = {"name": function_name, "success": False, "summary": ""}

            # 检查本次请求的工具总调用次数
            if total_tool_calls >= MAX_TOTAL_TOOL_CALLS:
                result = "执行失败：已达到本次请求的工具调用总次数上限"

                tool_status["summary"] = result
                failed_steps.append(tool_status)

                messages.append(
                    {"role": "tool", "tool_call_id": tool_call.id, "content": result}
                )

                print("工具执行结果：", result)
                continue

            # 记录本次工具调用
            total_tool_calls += 1

            # 检查工具是否已经达到最大执行次数
            attempts = tool_attempts.get(function_name, 0)

            if attempts >= MAX_TOOL_ATTEMPTS:
                result = f"执行失败：工具 {function_name} 已达到最大执行次数"

                tool_status["summary"] = result
                failed_steps.append(tool_status)

                messages.append(
                    {"role": "tool", "tool_call_id": tool_call.id, "content": result}
                )

                print("工具执行结果：", result)
                continue

            # 尚未达到上限，记录本次执行
            tool_attempts[function_name] = attempts + 1

            try:
                arguments = json.loads(tool_call.function.arguments)

                print("模型提供的参数：", arguments)

                # 根据工具名称选择 Python 函数
                if function_name == "create_plan":

                    goal = arguments.get("goal")
                    days = arguments.get("days")
                    max_hours = arguments.get("max_hours")

                    # 检查学习目标是否合法
                    if not isinstance(goal, str) or not goal.strip():
                        result = "执行失败：学习目标不能为空"
                        tool_status["summary"] = result

                    # 检查学习天数是否合法
                    elif (
                        isinstance(days, bool)
                        or not isinstance(days, (int, float))
                        or days <= 0
                        or int(days) != days
                    ):
                        result = "执行失败：学习天数必须是正整数"
                        tool_status["summary"] = result

                    # 检查每天的学习时长是否合法
                    elif (
                        isinstance(max_hours, bool)
                        or not isinstance(max_hours, (int, float))
                        or max_hours <= 0
                    ):
                        result = "执行失败：学习时长参数不合法"
                        tool_status["summary"] = result

                    else:
                        # 调用学习计划生成函数
                        tool_result = run_agent(goal, int(days), max_hours)

                        result = json.dumps(tool_result, ensure_ascii=False)

                        # 根据工具实际返回结果判断是否成功
                        if (
                            isinstance(tool_result, dict)
                            and tool_result.get("success") is True
                        ):
                            tool_status["success"] = True
                            tool_status["summary"] = tool_result.get(
                                "message", "学习计划生成成功"
                            )

                            # 记录历史任务，写入失败不影响本次结果
                            try:
                                add_history(goal, int(days), max_hours)
                            except OSError:
                                pass
                        else:
                            tool_status["summary"] = (
                                tool_result.get("message", "学习计划生成失败")
                                if isinstance(tool_result, dict)
                                else "工具返回结果格式不正确"
                            )

                elif function_name == "view_plan":

                    # 读取当前保存的学习计划
                    plan = load_plan()

                    if plan is None:
                        result = "目前没有保存过学习计划。"
                        tool_status["summary"] = result

                    else:
                        result = json.dumps(plan, ensure_ascii=False)

                        tool_status["success"] = True
                        tool_status["summary"] = "学习计划读取成功"

                elif function_name == "list_history":

                    # 读取历史任务索引（最新在前）
                    items = list_history()

                    if not items:
                        result = "还没有历史记录：用户还没有成功生成过学习计划。"
                        tool_status["summary"] = result

                    else:
                        result = json.dumps(
                            {"count": len(items), "items": items}, ensure_ascii=False
                        )

                        tool_status["success"] = True
                        tool_status["summary"] = f"读取到 {len(items)} 条历史记录"

                elif function_name == "remember_preference":

                    key = arguments.get("key")
                    value = arguments.get("value")

                    if not isinstance(key, str) or not key.strip():
                        result = "执行失败：偏好名称不能为空"
                        tool_status["summary"] = result

                    elif not isinstance(value, str) or not value.strip():
                        result = "执行失败：偏好内容不能为空"
                        tool_status["summary"] = result

                    else:
                        remember(key.strip(), value.strip())

                        result = f"已记住：{key.strip()} = {value.strip()}"
                        tool_status["success"] = True
                        tool_status["summary"] = result

                else:
                    result = "执行失败：未知工具。"
                    tool_status["summary"] = result

            except Exception as e:
                result = f"工具执行失败：{str(e)}"
                tool_status["summary"] = result

            # 根据工具执行状态记录成功或失败
            if tool_status["success"]:
                completed_steps.append(tool_status)
            else:
                failed_steps.append(tool_status)

            # 5. 把工具执行结果交还给模型
            messages.append(
                {"role": "tool", "tool_call_id": tool_call.id, "content": str(result)}
            )

            print("工具执行结果：", result)

    # 6. 达到最大执行轮数后停止
    print("\nAgent：达到最大执行步数，任务停止。")

    messages.append(
        {
            "role": "system",
            "content": """
工具调用轮数已经达到上限。
请根据之前的对话和工具执行结果，
向用户总结已经完成的任务和未完成的任务。
不要再次调用工具，也不要声称没有执行过的任务已经完成。
""",
        }
    )

    final_response = client.chat.completions.create(model=MODEL, messages=messages)

    print("\nAgent：", final_response.choices[0].message.content)

    show_execution_summary(completed_steps, failed_steps)


# 退出词表：整句匹配，不做包含匹配
EXIT_WORDS = {
    "退出",
    "结束",
    "再见",
    "拜拜",
    "不聊了",
    "走了",
    "挂了",
    "我要走了",
    "就这样" "exit",
    "quit",
    "bye",
    "q",
}

# 允许句末出现的语气词，去掉后再匹配，例如"退出吧""拜拜啦"
TRAILING_PARTICLES = "吧啦了啊呀哦嘛"


def normalize_input(text):
    """统一大小写、去掉空白和句末标点，便于比较。"""
    text = text.strip().lower()
    text = text.replace(" ", "").replace("\u3000", "")
    return text.rstrip("。.!！?？~～,，")


# 判断是否要求退出
def is_exit_command(text):
    text = normalize_input(text)

    if not text:
        return False

    # 命令式：/exit、/quit、/q
    if text.startswith("/"):
        return text[1:] in {"exit", "quit", "q"}

    # 自然语言：去掉句末语气词后整句匹配
    return text.rstrip(TRAILING_PARTICLES) in EXIT_WORDS


def main():
    while True:

        try:
            user_input = input("\n你：").strip()
        except (KeyboardInterrupt, EOFError):
            # Ctrl+C / Ctrl+D 属于正常退出，不打印报错
            print("\nAgent 已退出，再见！")
            break

        if not user_input:
            continue

        if is_exit_command(user_input):
            print("Agent 已退出，再见！")
            break

        try:
            ask_agent(user_input)

        except KeyboardInterrupt:
            print("\n已中断当前请求，Agent 已退出，再见！")
            break

        except Exception as e:
            print("运行出错：", e)


if __name__ == "__main__":
    main()
