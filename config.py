import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

MODEL = "deepseek-flash"

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)