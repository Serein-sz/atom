from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent

from atom.tools import get_task, get_week

model = init_chat_model(
    base_url="https://api.moonshot.cn/v1",
    model="openai:kimi-k2-0711-preview",
    temperature=0,
    # model="ollama:qwen3:4b",
    # base_url="http://192.168.2.250:11434",
)

task_agent = create_react_agent(
    model=model,
    tools=[get_task, get_week],
    prompt="""
        1. 先通过 `get_week` 取得 ISO-8601 周标识，例如 `2025-W32`；  
        2. 用第一步获得的周标识调用 `get_task(author, week)` 查询任务。若返回空列表，明确告知“本周暂无任务”，严禁编造，并不要假造任务示例；  
        3. 若存在任务，使用markdown按以下三步输出：  
            • 摘要：一句话概括本周核心工作内容；  
            • 合并：将相似任务聚合为同一条目，避免重复；  
            • 时间：给出每项（或每组）任务对应的最早和最晚执行日期（格式：`MM-DD`～`MM-DD`）。
    """,
)
