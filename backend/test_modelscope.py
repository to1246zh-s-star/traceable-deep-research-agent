import json
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("LLM_API_KEY", "").strip()
base_url = os.getenv("LLM_BASE_URL", "").strip()
model_id = os.getenv("LLM_MODEL_ID", "").strip()
timeout = float(os.getenv("LLM_TIMEOUT", "180"))

if not api_key:
    sys.exit("错误：LLM_API_KEY 未配置。")

if not base_url.startswith(("http://", "https://")):
    sys.exit(
        f"错误：LLM_BASE_URL 必须以 http:// 或 https:// 开头，"
        f"当前值为：{base_url!r}"
    )

if not model_id:
    sys.exit("错误：LLM_MODEL_ID 未配置。")

print(f"Base URL: {base_url}")
print(f"Model ID: {model_id}")
print(f"API Key loaded: yes, length={len(api_key)}")
print(f"API Key prefix: {api_key[:3]}***")
print("正在请求 ModelScope...")

client = OpenAI(
    api_key=api_key,
    base_url=base_url,
    timeout=timeout,
)

response = client.chat.completions.create(
    model=model_id,
    messages=[
        {
            "role": "system",
            "content": (
                "你是研究规划专家。"
                "你必须只返回合法的 JSON 数组，不要输出其他文字。"
            ),
        },
        {
            "role": "user",
            "content": (
                "将“开源大模型的发展趋势”拆分成3个研究任务。"
                "每个对象必须包含 title、intent、query。"
            ),
        },
    ],
    temperature=0.2,
    max_tokens=1000,
)

content = response.choices[0].message.content or ""
print("\n模型原始输出：")
print(content)

tasks = json.loads(content)

assert isinstance(tasks, list), "输出必须是数组"
assert len(tasks) == 3, f"预期3个任务，实际得到{len(tasks)}个"

for index, task in enumerate(tasks, start=1):
    assert isinstance(task, dict), f"第{index}个任务不是对象"
    missing = {"title", "intent", "query"} - task.keys()
    assert not missing, f"第{index}个任务缺少字段：{missing}"

print("\nPlanner JSON test: PASS")
