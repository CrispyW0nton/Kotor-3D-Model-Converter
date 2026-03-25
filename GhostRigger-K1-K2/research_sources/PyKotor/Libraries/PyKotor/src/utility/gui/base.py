from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from utility.string_util import normalize_string


@dataclass
class UserCommunication:
    widget: Any | None = None

    def input(self, prompt: str) -> str:
        return input(prompt)

    def print(self, *args: str):
        print(*args)

    def messagebox(self, title: str, message: str, *args, **kwargs):
        print(f"[Message] - {title}: {message}")

    def askquestion(self, title: str, message: str, *args, **kwargs) -> bool:
        print(f"{title}\n{message}")
        while True:
            response = normalize_string(input("(y/N)"))
            if response in {"yes", "y"}:
                return True
            if response in {"no", "n"}:
                return False
            print("Invalid input. Please enter 'yes' or 'no'")

    def update_status(self, message: str, *args, **kwargs):
        print(f"Status update: {message}")
