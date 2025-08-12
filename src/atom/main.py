import asyncio
from typing import List

import typer
from dotenv import load_dotenv
from rich import print
from rich.markdown import Markdown

from .entity.task import TaskGroup
from .utils.git import (
    dump_info,
    load_commits_by_author,
    group_commits_to_task_groups,
)

from .agents import task_agent

load_dotenv()

app = typer.Typer()


@app.command()
def dump():
    asyncio.run(dump_info())


@app.command()
def task(
    offset: int = 0,
    author: str = "王强",
):
    commits = load_commits_by_author(author)
    task_group: List[TaskGroup] = group_commits_to_task_groups(commits)
    for task in task_group[0 : offset + 1]:
        print(task)


@app.command()
def summary(message: str | None = None):
    result = task_agent.invoke(
        input={
            "messages": [
                {
                    "role": "user",
                    "content": "请总结本周 王强 的任务" if not message else message,
                }
            ]
        }
    )
    md = Markdown(result.get("messages")[-1].content)
    print(md)


if __name__ == "__main__":
    app()
