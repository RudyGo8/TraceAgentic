'''
@create_time: 2026/4/28 上午12:16
@Author: GeChao
@File: rag_tools.py
'''

from langchain_core.tools import tool

from app.rag.formatter import format_docs
from app.rag.runtime import (
    get_knowledge_tool_call_this_turn,
    increase_knowledge_tool_calls_this_turn,
    set_last_rag_context)


@tool("search_knowledge_base")
def search_knowledge_base(query: str) -> str:
    """在企业知识库(用户上传的PDF/Word/Excel文档)中检索与query相关的内容。凡涉及文档、标准、规范、条款、技术指标、试验方法、精密度、参数定义等问题必须先调用本工具,禁止凭模型记忆回答文档内容。query应为适合语义检索的自然语言问句。"""
    calls_this_turn = get_knowledge_tool_call_this_turn()
    if calls_this_turn >= 1:
        return (
            "本轮已经调用过知识库了 "
            "请基于已有结果直接回答"
        )

    increase_knowledge_tool_calls_this_turn()

    from app.rag import run_rag_graph

    rag_result = run_rag_graph(query)

    docs = rag_result.get("docs", []) if isinstance(rag_result, dict) else []
    rag_trace = rag_result.get("rag_trace", {}) if isinstance(rag_result, dict) else {}
    if rag_trace:
        set_last_rag_context({"rag_trace": rag_trace})

    if not docs:
        return "没有找到相关文档"

    formatted = format_docs(docs)
    return "检索块:\n" + "\n\n---\n\n".join(formatted)


@tool("list_knowledge_documents")
def list_knowledge_documents() -> str:
    """列出知识库中已入库的全部文档清单(文件名、类型、切块数)。当用户询问知识库里有什么文档、有哪些资料、上传过什么文件时使用;不要用它检索文档内容。"""
    from app.services.milvus_service import milvus_service

    milvus_service.init_collection()
    results = milvus_service.query(output_fields=["filename", "file_type"], limit=10000)

    stats: dict[str, dict] = {}
    for item in results:
        name = item.get("filename", "")
        entry = stats.setdefault(name, {"file_type": item.get("file_type", ""), "chunks": 0})
        entry["chunks"] += 1

    if not stats:
        return "知识库当前为空,尚未上传任何文档"

    lines = [f"- {name}({info['file_type']}, {info['chunks']}个知识块)" for name, info in stats.items()]
    return "知识库现有文档:\n" + "\n".join(lines)
