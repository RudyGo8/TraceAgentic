'''
@create_time: 2026/02/02
@Author: GeChao
@File: chat.py
'''
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default_session"


class RetrievedChunk(BaseModel):
    filename: str
    page_number: Optional[str | int] = None
    text: Optional[str] = None
    score: Optional[float] = None


class RagTrace(BaseModel):
    model_config = ConfigDict(extra="allow")
    tool_used: bool = False
    tool_name: str = ""
    query: Optional[str] = None
    expanded_query: Optional[str] = None
    retrieval_stage: Optional[str] = None
    grade_score: Optional[str] = None
    rewrite_strategy: Optional[str] = None
    token_usage: Optional[dict[str, Any]] = None
    retrieved_chunks: Optional[list[dict[str, Any]]] = None


class MessageInfo(BaseModel):
    type: str
    content: str
    timestamp: str
    rag_trace: Optional[RagTrace] = None


class SessionMessagesResponse(BaseModel):
    messages: list[MessageInfo]


class SessionInfo(BaseModel):
    session_id: str
    title: str = ""
    updated_at: str
    message_count: int


class SessionListResponse(BaseModel):
    sessions: list[SessionInfo]


class SessionDeleteResponse(BaseModel):
    session_id: str
    message: str
