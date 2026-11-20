import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

MODEL = "deepseek-flash"

# 计划和画像固定放在项目目录，不受启动目录影响
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLAN_FILE = os.path.join(BASE_DIR, "study_plan.json")
MEMORY_FILE = os.path.join(BASE_DIR, "user_profile.json")

API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()

if not API_KEY:
    raise SystemExit(
        "未找到 DEEPSEEK_API_KEY：请在项目根目录创建 .env 文件，"
        "并写入 DEEPSEEK_API_KEY=你的密钥"
    )

client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")
