from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core.cache import cache
from app.core.database import SessionLocal
from app.models.db_chat_message import ChatMessage
from app.models.db_chat_session import ChatSession
from app.models.db_user import User
from app.utils.log import get_logger

logger = get_logger(__name__)


class ConversationStorage:
    # 生成redis等缓存的键名，分别用于具体会话的消息列表
    @staticmethod
    def _messages_cache_key(user_id: str, session_id: str) -> str:
        return f"chat_messages:{user_id}:{session_id}"

    # 用户的所有会话列表
    @staticmethod
    def _sessions_cache_key(user_id: str) -> str:
        return f"chat_sessions:{user_id}"
    # 将数据库中的字典格式消息转换为HumanMessage、AIMessage、SystemMessage
    @staticmethod
    def _to_langchain_messages(records: list[dict]) -> list:
        messages = []
        for msg_data in records:
            msg_type = msg_data.get("type")
            content = msg_data.get("content", "")
            if msg_type == "human":
                messages.append(HumanMessage(content=content))
            elif msg_type == "ai":
                messages.append(AIMessage(content=content))
            elif msg_type == "system":
                messages.append(SystemMessage(content=content))
        return messages

    def save( self, user_id: str, session_id: str, messages: list, metadata: dict | None = None, extra_message_data: list | None = None):
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == user_id).first()
            if not user:
                return

            # 查询 ChatSession 会话记录
            session = (
                db.query(ChatSession)
                .filter(ChatSession.user_id == user.id, ChatSession.session_id == session_id)
                .first()
            )
            if not session:
                session = ChatSession(user_id=user.id, session_id=session_id, metadata_json=metadata or {})
                db.add(session)
                db.flush()
            else:
                # 若已存在，更新元数据
                session.metadata_json = metadata or {}

            incoming_rows: list[dict] = []
            for idx, msg in enumerate(messages):
                rag_trace = None
                # 遍历传入的 message 列表, idx索引，msg为消息对象
                if extra_message_data and idx < len(extra_message_data):
                    extra = extra_message_data[idx] or {}
                    rag_trace = extra.get("rag_trace")
                incoming_rows.append(
                    {
                        "message_type": msg.type,
                        "content": str(msg.content),
                        "rag_trace": rag_trace,
                    }
                )
            # 从数据库查询该会话已保存的所有历史消息记录
            existing_rows = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_ref_id == session.id)
                .order_by(ChatMessage.id.asc())
                .all()
            )

            # 判断类型与内容是否相同
            def _same_message(lhs: dict, rhs: ChatMessage) -> bool:
                return lhs["message_type"] == rhs.message_type and lhs["content"] == rhs.content

            # 历史消息数量不超过本次消息数量，且历史消息是本次消息列表的前缀
            can_append = (
                len(existing_rows) <= len(incoming_rows)
                and all(_same_message(incoming_rows[idx], row) for idx, row in enumerate(existing_rows))
            )

            now = datetime.now()
            if can_append:
                for idx in range(len(existing_rows), len(incoming_rows)):
                    payload = incoming_rows[idx]
                    # 创建新的 ChatMessage 记录并新增部分加入数据库会话
                    db.add(
                        ChatMessage(
                            session_ref_id=session.id,
                            message_type=payload["message_type"],
                            content=payload["content"],
                            rag_trace=payload["rag_trace"],
                        )
                    )
            else:
                # 删除该会话所有已存在的消息记录
                db.query(ChatMessage).filter(ChatMessage.session_ref_id == session.id).delete(synchronize_session=False)
                # 将本次全部消息重新插入数据库：全量覆盖
                for payload in incoming_rows:
                    db.add(
                        ChatMessage(
                            session_ref_id=session.id,
                            message_type=payload["message_type"],
                            content=payload["content"],
                            rag_trace=payload["rag_trace"],
                        )
                    )

            session.update_time = now
            db.commit()
            cache.delete(self._messages_cache_key(user_id, session_id))
            cache.delete(self._sessions_cache_key(user_id))
        except Exception:
            db.rollback()
            logger.exception("Failed to save conversation user_id=%s session_id=%s", user_id, session_id)
            raise
        finally:
            db.close()

    def load(self, user_id: str, session_id: str) -> list:
        # 先读缓存，命中后再转回 LangChain message 对象。
        cached = cache.get_json(self._messages_cache_key(user_id, session_id))
        if cached is not None:
            return self._to_langchain_messages(cached)

        # 缓存未命中时调用，获取原始字典
        records = self.get_session_messages(user_id, session_id)
        return self._to_langchain_messages(records)

    # 提取 session_id 列表返回
    def list_sessions(self, user_id: str) -> list:
        return [item["session_id"] for item in self.list_session_infos(user_id)]

    # 获取用户所有会话摘要信息
    def list_session_infos(self, user_id: str) -> list[dict]:
        cached = cache.get_json(self._sessions_cache_key(user_id))
        if cached is not None:
            return cached

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == user_id).first()
            if not user:
                return []

            sessions = (
                db.query(ChatSession)
                .filter(ChatSession.user_id == user.id)
                .order_by(ChatSession.update_time.desc())
                .all()
            )
            result = []
            for session in sessions:
                # 列表页只展示摘要信息：session_id、更新时间、消息数。
                count = db.query(ChatMessage).filter(ChatMessage.session_ref_id == session.id).count()
                first_user_message = (
                    db.query(ChatMessage.content)
                    .filter(
                        ChatMessage.session_ref_id == session.id,
                        ChatMessage.message_type == "human",
                    )
                    .order_by(ChatMessage.id.asc())
                    .first()
                )
                title = (first_user_message[0] if first_user_message else "") or ""
                result.append(
                    {
                        "session_id": session.session_id,
                        "title": title[:30],
                        "updated_at": session.update_time.isoformat() if session.update_time else "",
                        "message_count": count,
                    }
                )
            cache.set_json(self._sessions_cache_key(user_id), result)
            return result
        except Exception:
            logger.exception("Failed to list sessions user_id=%s", user_id)
            return []
        finally:
            db.close()
    def get_session_messages(self, user_id: str, session_id: str) -> list[dict]:
        cached = cache.get_json(self._messages_cache_key(user_id, session_id))
        if cached is not None:
            return cached

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == user_id).first()
            if not user:
                return []
            session = (
                db.query(ChatSession)
                .filter(ChatSession.user_id == user.id, ChatSession.session_id == session_id)
                .first()
            )
            if not session:
                return []

            # 查询用户和会话
            rows = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_ref_id == session.id)
                .order_by(ChatMessage.id.asc())
                .all()
            )
            result = [
                {
                    "type": row.message_type,
                    "content": row.content,
                    "timestamp": row.create_time.isoformat() if row.create_time else "",
                    "rag_trace": row.rag_trace,
                }
                for row in rows
            ]
            cache.set_json(self._messages_cache_key(user_id, session_id), result)
            return result
        except Exception:
            logger.exception("Failed to get session messages user_id=%s session_id=%s", user_id, session_id)
            return []
        finally:
            db.close()
    def delete_session(self, user_id: str, session_id: str) -> bool:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == user_id).first()
            if not user:
                return False
            session = (
                db.query(ChatSession)
                .filter(ChatSession.user_id == user.id, ChatSession.session_id == session_id)
                .first()
            )
            if not session:
                return False

            db.delete(session)
            db.commit()
            cache.delete(self._messages_cache_key(user_id, session_id))
            cache.delete(self._sessions_cache_key(user_id))
            return True
        except Exception:
            logger.exception("Failed to delete session user_id=%s session_id=%s", user_id, session_id)
            return False
        finally:
            db.close()


conversation_service = ConversationStorage()
