from pydantic import BaseModel


class Task(BaseModel):
    date: str
    repository: str
    tasks: list[str]
    
class TaskGroup(BaseModel):
    week: str
    tasks: list[Task]
