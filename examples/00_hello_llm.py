"""任务 00：环境验证脚本

跑通它 = Python 环境 + DeepSeek API key + 网络 三者全部就绪。

步骤：
1. 复制 .env.example 为 .env，填入你的 DEEPSEEK_API_KEY
2. pip install -r requirements.txt
3. python examples/00_hello_llm.py
"""
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY", "")
if not api_key or api_key.startswith("sk-在这里"):
    sys.exit("❌ 请先把 .env.example 复制为 .env，并填入真实 DEEPSEEK_API_KEY")

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

resp = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "你是一位简洁的助手。"},
        {"role": "user", "content": "用一句话向电子小白解释什么是 GaN HEMT。"},
    ],
    max_tokens=120,
)

print("✅ API 调用成功！模型回复：")
print(resp.choices[0].message.content)
print(f"\n本次消耗 token: {resp.usage.total_tokens}")
print("环境验证通过，可以进入任务 01（LangGraph 入门）。")
