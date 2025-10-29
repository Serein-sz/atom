import asyncio
import re
import json
from typing import Dict, List
from pathlib import Path
from time import perf_counter
from datetime import datetime, timedelta

import typer
import requests
from bs4 import BeautifulSoup  # pip install beautifulsoup4
from bs4.element import ResultSet, Tag
from rich.progress import Progress, TaskID, MofNCompleteColumn, TimeElapsedColumn
from rich.console import Console


from atom.entity import Commit, TaskGroup, Task

console = Console()


def fetch_repositories(host: str) -> list[str]:
    url = f"http://{host}/repositories"
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    repositories = soup.select(
        "body > div:nth-child(3) > div:nth-child(2) > table > tbody:nth-child(2) > tr"
    )
    result: list[str] = []
    for repository in repositories:
        a_tag = repository.select_one("td.left > span:nth-child(2) > a")
        if a_tag:
            result.append(a_tag.text)
    return result


def fetch_branches(host: str, repository: str) -> list[str]:
    url = f"http://{host}/branches/{repository}.git"
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    branches = soup.select(
        "body > div:nth-child(4) > div > table > tbody > tr > td:nth-child(2) > span > a"
    )
    result: list[str] = []
    for branch in branches:
        result.append(branch.attrs["href"])
    return result


async def fetch_repository_commits(
    progress: Progress, task: TaskID, host: str, repository: str, branch: str
) -> list[Commit]:
    url = f"http://{host}/{branch.replace('../', '')}"
    page = 1
    result: list[Commit] = []
    while True:
        page_url = f"{url}?pg={page}"
        resp = requests.get(page_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        commits: ResultSet[Tag] = soup.select(
            "body > div:nth-child(4) > div:nth-child(2) > table > tbody > tr.commit"
        )
        if not commits:
            break
        processed_commits = handle_current_page_commits(
            commits=commits, repository=repository
        )
        if not processed_commits:
            break
        result.extend(processed_commits)
        page += 1
        await asyncio.sleep(0.5)
    progress.update(task, advance=1)
    return result


def within_last_month(date_str: str, fmt: str = "%Y-%m-%d") -> bool:
    """
    date_str: 日期字符串，如 "2024-05-10"
    fmt:      与 date_str 对应的格式，默认 "%Y-%m-%d"
    返回值:   True/False
    """
    dt = datetime.strptime(date_str, fmt)
    cutoff = datetime.today().replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=30)
    return dt >= cutoff


def handle_current_page_commits(commits: ResultSet[Tag], repository: str):
    results: list[Commit] = []
    for commit in commits:
        date = commit.select_one("td.date > span").text
        if (
            ("以前" not in date) and date != "昨天" and date != "刚刚"
        ) and not within_last_month(date):
            break
        message = commit.select_one(
            "td.message.ellipsize > table > tr > td:nth-child(1) > span > a"
        ).text
        if message.startswith("Merge branch"):
            continue
        results.append(
            Commit(
                date=normalize_human_date(date),
                author=commit.select_one("td.hidden-phone.author > span > a").text,
                message=message,
                repository=repository,
            )
        )
    return results


def normalize_human_date(text: str, now: datetime | None = None) -> str:
    """
    把「N 小时以前」「N 天以前」等字符串转换为 yyyy-MM-dd HH:mm:ss
    如果 text 已经是 yyyy-MM-dd 格式，则保持不变。
    """
    now = now or datetime.now()
    text = text.strip()
    if text == "刚刚":
        return now.strftime("%Y-%m-%d")

    # 1) 已经是 yyyy-MM-dd 或 yyyy-MM-dd HH:mm:ss
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}( \d{2}:\d{2}:\d{2})?", text):
        return text if ":" in text else f"{text} 00:00:00"

    # 2) N 小时以前
    m = re.match(r"(\d+)\s*小时以前", text)
    if m:
        delta = timedelta(hours=int(m.group(1)))
        return (now - delta).strftime("%Y-%m-%d")

    # 3) N 天以前
    m = re.match(r"(\d+)\s*天以前", text)
    if m:
        delta = timedelta(days=int(m.group(1)))
        return (now - delta).strftime("%Y-%m-%d")

    # 4) 其它情况直接返回原串（或抛错）
    return text


def save_commits_by_author(
    repo_commits: Dict[str, List[Commit]], out_dir: Path | str = "D:/.authors"
) -> None:
    """
    把每个 author 的所有 commit 写进 out_dir/<author>.json
    如果同一个 author 在多个 repo 出现，会被合并到同一个文件
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(exist_ok=True)

    # 先按 author 聚合
    author_map: Dict[str, List[Dict]] = {}
    for _, commits in repo_commits.items():
        for c in commits:
            author_map.setdefault(c.author, []).append(c.to_dict())

    for author, commits in author_map.items():
        if "\\" in author:
            continue
        file_path = out_dir / f"{author}.json"
        with file_path.open("w", encoding="utf-8") as fp:
            json.dump(commits, fp, ensure_ascii=False, indent=2)


async def dump_info():
    start = perf_counter()
    hosts = ["192.168.2.240:9999", "192.168.2.111:19999"]

    triples = []
    for host in hosts:
        for repo in fetch_repositories(host):
            for branch in fetch_branches(host, repo):
                triples.append((host, repo, branch))
    # 2️⃣ 用 rich 创建进度条
    with Progress(
        *Progress.get_default_columns(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,  # 完成后自动隐藏
    ) as progress:
        task = progress.add_task("[cyan]Fetching commits...", total=len(triples))
        tasks = [
            fetch_repository_commits(progress, task, h, r, b) for h, r, b in triples
        ]
        repository_dict = {}
        for coroutine in asyncio.as_completed(tasks):
            commits = await coroutine
            if commits:
                repo_name = commits[0].repository
                repository_dict[repo_name] = commits
    end = perf_counter()
    save_commits_by_author(repository_dict)
    typer.secho(message=f"cost: {end - start} ...", fg=typer.colors.GREEN)


def load_commits_by_author(
    author: str, in_dir: Path | str = "D:/.authors"
) -> List[Commit]:
    """
    根据 author 名读取对应的 commit 列表
    文件不存在则返回 []
    """
    file_path = Path(in_dir) / f"{author}.json"
    if not file_path.exists():
        return []

    with file_path.open(encoding="utf-8") as fp:
        data: List[Dict] = json.load(fp)
    return [Commit.from_dict(item) for item in data]


def group_commits_to_task_groups(commits: list[Commit]) -> List[TaskGroup]:
    """
    将原始 commit 列表 -> List[TaskGroup]
    """
    # 1. 把 commit 按 (date, repository) 聚合
    day_repo_tasks: dict[str, dict[str, list[str]]] = {}
    for c in commits:
        day = c.date  # 去掉时间后缀
        day = day.replace(" 00:00:00", "")
        repo = c.repository
        day_repo_tasks.setdefault(day, {}).setdefault(repo, []).append(c.message)
    # 2. 生成 Task，并记录到 (week, day) 两层结构
    week_day_tasks: dict[str, dict[str, list[Task]]] = {}
    for day, repo_msgs in sorted(day_repo_tasks.items(), reverse=True):
        try:
            dt = datetime.strptime(day, "%Y-%m-%d")
            week_key = dt.strftime("%Y-W%V")
        except ValueError:
            week_key = datetime.today().strftime("%Y-W%V")

        task_list = [
            Task(date=day, repository=repo, tasks=msgs)
            for repo, msgs in sorted(repo_msgs.items())
        ]
        week_day_tasks.setdefault(week_key, {})[day] = task_list

    # 3. 组装 TaskGroup
    task_groups: list[TaskGroup] = []
    for week_key, day_tasks in sorted(week_day_tasks.items(), reverse=True):
        # 把多天合并，保持天倒序
        tasks_this_week = [
            task for day in sorted(day_tasks, reverse=True) for task in day_tasks[day]
        ]
        task_groups.append(TaskGroup(week=week_key, tasks=tasks_this_week))

    return task_groups
