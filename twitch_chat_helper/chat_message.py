from dataclasses import dataclass


@dataclass
class ChatMessage:
    author_name: str
    content: str
    unix_time_ms: int
