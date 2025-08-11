from typing import List
from datetime import datetime, timedelta

from langchain_core.tools import tool

from atom.entity import Commit, TaskGroup
from atom.utils import load_commits_by_author, group_commits_to_task_groups


@tool
def get_task(author: str, week: str) -> List[TaskGroup]:
    """
    Retrieve all task groups authored by a specified developer within a given ISO week.

    Parameters
    ----------
    author : str
        Exact name of the author whose work should be retrieved.
    week : str
        ISO-8601 week identifier, e.g. ``"2025-W32"``. Used to filter the returned
        task groups to only those that fall entirely within this week.

    Returns
    -------
    List[TaskGroup]
        All task groups authored by `author` whose `week` attribute matches the
        supplied `week` identifier. Returns an empty list if no matching groups
        are found.

    Notes
    -----
    Internally, the function loads the full set of commits for the requested
    author and then groups them into logical task groups based on commit
    metadata (e.g. issue keys, branch names). The resulting list is filtered to
    retain only those groups whose span falls within the specified week.
    """
    commits: List[Commit] = load_commits_by_author(author)
    task_group: List[TaskGroup] = group_commits_to_task_groups(commits)
    return [group for group in task_group if group.week == week]


@tool
def get_week(offset: int = 0) -> str:
    """
    Return an ISO-8601 week identifier for the specified week offset.

    Parameters
    ----------
    offset : int, optional
        Number of weeks to look back from the current week.
            - 0  -> current week
            - 1  -> previous week
            - 2  -> the week before last, etc.

    Returns
    -------
    str
        Week identifier in the form '2025-W32'.
    """
    # 计算目标周的星期一
    today = datetime.now().date()
    start_of_this_week = today - timedelta(days=today.weekday())  # 本周一
    start_of_target_week = start_of_this_week - timedelta(weeks=offset)

    # 获取 ISO 年份和周数
    year, week, _ = start_of_target_week.isocalendar()
    return f"{year}-W{week:02d}"
