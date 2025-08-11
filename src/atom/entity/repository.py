from typing import Optional, Dict
from pydantic import BaseModel


class Commit(BaseModel):
    date: str
    author: str
    message: str
    repository: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "date": self.date,
            "author": self.author,
            "message": self.message,
            "repository": self.repository,
        }

    @staticmethod
    def from_dict(data: Dict) -> "Commit":
        return Commit(
            date=data["date"],
            author=data["author"],
            message=data["message"],
            repository=data["repository"],
        )
