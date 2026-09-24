"""旅行助手 HTTP 适配层。

将 LangGraph ReAct 旅行规划 Agent 暴露为 REST 接口，并按 sessionId
在内存中维护多轮对话上下文。
"""

import threading
import uuid
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/api/travel", tags=["travel"])


class TravelChatRequest(BaseModel):
    """旅行助手聊天请求体。"""

    model_config = ConfigDict(populate_by_name=True)

    session_id: Optional[str] = Field(default=None, alias="sessionId")
    message: str


_sessions: dict[str, list] = {}
_lock = threading.Lock()
_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        from travel_agent.agent import get_agent

        _agent = get_agent()
    return _agent


def _run_turn(session_id: str, user_input: str) -> str:
    from langchain_core.messages import HumanMessage

    with _lock:
        messages = list(_sessions.get(session_id, []))

    messages.append(HumanMessage(content=user_input))
    result = _get_agent().invoke({"messages": messages})
    new_messages = result.get("messages", messages)

    with _lock:
        _sessions[session_id] = new_messages

    ai_messages = [m for m in new_messages if getattr(m, "type", "") == "ai"]
    if ai_messages:
        content = getattr(ai_messages[-1], "content", "")
        return content if isinstance(content, str) else str(content)
    return ""


@router.get("/health")
def health():
    return {"code": 200, "message": "ok", "data": {"status": "up"}}


@router.post("/chat")
def chat(payload: TravelChatRequest):
    session_id = payload.session_id or str(uuid.uuid4())
    user_input = payload.message.strip()

    if not user_input:
        return {"code": 400, "message": "消息不能为空", "data": {"sessionId": session_id}}

    try:
        reply = _run_turn(session_id, user_input)
    except Exception as exc:
        return {
            "code": 500,
            "message": f"处理失败: {exc}",
            "data": {"sessionId": session_id, "reply": ""},
        }

    return {
        "code": 200,
        "message": "成功",
        "data": {"sessionId": session_id, "reply": reply},
    }