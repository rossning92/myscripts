from typing import List, NotRequired, TypedDict, cast

from typing import List, NotRequired, TypedDict, cast

from ai.utils.message import Message
from utils.jsonutil import load_json, save_json


class Session(TypedDict):
    messages: List[Message]
    title: NotRequired[str]


def normalize_session(data: object) -> Session:
    if isinstance(data, list):
        messages = cast(List[Message], data)
        session: Session = {"messages": messages}
        if messages:
            title = messages[0].pop("conversation_title", None)
            if isinstance(title, str) and title:
                session["title"] = title
        return session
    if isinstance(data, dict) and isinstance(data.get("messages"), list):
        session = cast(Session, data)
        messages = session["messages"]
        if messages:
            title = messages[0].pop("conversation_title", None)
            if "title" not in session and isinstance(title, str) and title:
                session["title"] = title
        return session
    raise ValueError("session must be a message list or an object with messages")


def load_session(path: str) -> Session:
    return normalize_session(load_json(path, default=[]))


def save_session(path: str, session: Session) -> None:
    save_json(path, session)
