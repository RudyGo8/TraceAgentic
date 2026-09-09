'''
@create_time: 2026/4/27 下午3:59
@Author: GeChao
@File: retrieve_node.py
'''
from concurrent.futures import ThreadPoolExecutor
from typing import List

from app.rag.formatter import format_docs
from app.rag.pipeline import retrieve_documents, generate_hypothetical_document
from app.rag.state import RAGState
from app.rag.runtime import emit_rag_step


# 初始检索
def retrieve_initial(state: RAGState) -> RAGState:
    query = state["question"]
    emit_rag_step("🔍", "正在检索知识库...", f"查询: {query[:50]}")

    retrieved = retrieve_documents(query, top_k=5)
    results = retrieved.get("docs", [])
    retrieve_meta = retrieved.get("meta", {})
    context = format_docs(results)

    emit_rag_step(
        "🔎",
        "混合检索召回",
        (
            f"模式: {retrieve_meta.get('retrieval_mode', 'hybrid')}，"
            f"候选 {retrieve_meta.get('candidate_k', 0)}"
        ),
    )
    emit_rag_step(
        "🧩",
        "父子分块合并 (Auto-merge)",
        (
            f"启用: {bool(retrieve_meta.get('auto_merge_enabled'))}，"
            f"应用: {bool(retrieve_meta.get('auto_merge_applied'))}，"
            f"替换片段: {retrieve_meta.get('auto_merge_replaced_chunks', 0)}"
        ),
    )
    emit_rag_step(
        "✅",
        f"初次检索完成，保留 {len(results)} 个片段",
        f"重排: {bool(retrieve_meta.get('rerank_applied'))}"
    )

    rag_trace = {
        "tool_used": True,
        "tool_name": "search_knowledge_base",
        "query": query,
        "expanded_query": query,
        "retrieved_chunks": results,
        "initial_retrieved_chunks": results,
        "retrieval_stage": "initial",
        "rerank_enabled": retrieve_meta.get("rerank_enabled"),
        "rerank_applied": retrieve_meta.get("rerank_applied"),
        "rerank_model": retrieve_meta.get("rerank_model"),
        "rerank_endpoint": retrieve_meta.get("rerank_endpoint"),
        "rerank_error": retrieve_meta.get("rerank_error"),
        "retrieval_mode": retrieve_meta.get("retrieval_mode"),
        "candidate_k": retrieve_meta.get("candidate_k"),
        "leaf_retrieve_level": retrieve_meta.get("leaf_retrieve_level"),
        "auto_merge_enabled": retrieve_meta.get("auto_merge_enabled"),
        "auto_merge_applied": retrieve_meta.get("auto_merge_applied"),
        "auto_merge_threshold": retrieve_meta.get("auto_merge_threshold"),
        "auto_merge_replaced_chunks": retrieve_meta.get("auto_merge_replaced_chunks"),
        "auto_merge_steps": retrieve_meta.get("auto_merge_steps"),
    }
    return {
        "query": query,
        "docs": results,
        "context": context,
        "rag_trace": rag_trace,
    }


# 扩展检索节点
def retrieve_expanded(state: RAGState) -> RAGState:
    strategy = state.get("expansion_type") or "step_back"
    hyde_docs: List[dict] = []
    step_docs: List[dict] = []
    emit_rag_step("🔄", "使用扩展查询重新检索...", f"策略: {strategy}")

    def _hyde_pipeline():
        doc = state.get("hypothetical_doc") or generate_hypothetical_document(state["question"])
        return retrieve_documents(doc, top_k=5)

    def _stepback_pipeline():
        return retrieve_documents(state.get("expanded_query") or state["question"], top_k=5)

    # complex策略下两分支互不依赖,并行执行:耗时取max而非相加
    retrieved_hyde = retrieved_stepback = None
    if strategy == "complex":
        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_hyde = pool.submit(_hyde_pipeline)
            fut_step = pool.submit(_stepback_pipeline)
            retrieved_hyde, retrieved_stepback = fut_hyde.result(), fut_step.result()
    elif strategy == "hyde":
        retrieved_hyde = _hyde_pipeline()
    elif strategy == "step_back":
        retrieved_stepback = _stepback_pipeline()

    results: List[dict] = []
    rerank_applied_any = False
    rerank_enabled_any = False
    rerank_model = None
    rerank_endpoint = None
    rerank_errors = []
    retrieval_mode = None
    candidate_k = None
    leaf_retrieve_level = None
    auto_merge_enabled = None
    auto_merge_applied = False
    auto_merge_threshold = None
    auto_merge_replaced_chunks = 0
    auto_merge_steps = 0

    if retrieved_hyde is not None:
        hyde_docs = retrieved_hyde.get("docs", [])
        results.extend(hyde_docs)
        hyde_meta = retrieved_hyde.get("meta", {})
        emit_rag_step(
            "🧱",
            "HyDE 扩展检索",
            (
                f"L{hyde_meta.get('leaf_retrieve_level', 3)} 召回，"
                f"候选 {hyde_meta.get('candidate_k', 0)}，"
                f"合并替换 {hyde_meta.get('auto_merge_replaced_chunks', 0)}"
            ),
        )
        rerank_applied_any = rerank_applied_any or bool(hyde_meta.get("rerank_applied"))
        rerank_enabled_any = rerank_enabled_any or bool(hyde_meta.get("rerank_enabled"))
        rerank_model = rerank_model or hyde_meta.get("rerank_model")
        rerank_endpoint = rerank_endpoint or hyde_meta.get("rerank_endpoint")
        if hyde_meta.get("rerank_error"):
            rerank_errors.append(f"hyde:{hyde_meta.get('rerank_error')}")
        retrieval_mode = retrieval_mode or hyde_meta.get("retrieval_mode")
        candidate_k = candidate_k or hyde_meta.get("candidate_k")
        leaf_retrieve_level = leaf_retrieve_level or hyde_meta.get("leaf_retrieve_level")
        auto_merge_enabled = auto_merge_enabled if auto_merge_enabled is not None else hyde_meta.get("auto_merge_enabled")
        auto_merge_applied = auto_merge_applied or bool(hyde_meta.get("auto_merge_applied"))
        auto_merge_threshold = auto_merge_threshold or hyde_meta.get("auto_merge_threshold")
        auto_merge_replaced_chunks += int(hyde_meta.get("auto_merge_replaced_chunks") or 0)
        auto_merge_steps += int(hyde_meta.get("auto_merge_steps") or 0)

    if retrieved_stepback is not None:
        step_docs = retrieved_stepback.get("docs", [])
        results.extend(step_docs)
        # 仅保留用于融合的分支结果，避免重复追加。

        step_meta = retrieved_stepback.get("meta", {})
        emit_rag_step(
            "🧱",
            "Step-back 扩展检索",
            (
                f"L{step_meta.get('leaf_retrieve_level', 3)} 召回，"
                f"候选 {step_meta.get('candidate_k', 0)}，"
                f"合并替换 {step_meta.get('auto_merge_replaced_chunks', 0)}"
            ),
        )
        rerank_applied_any = rerank_applied_any or bool(step_meta.get("rerank_applied"))
        rerank_enabled_any = rerank_enabled_any or bool(step_meta.get("rerank_enabled"))
        rerank_model = rerank_model or step_meta.get("rerank_model")
        rerank_endpoint = rerank_endpoint or step_meta.get("rerank_endpoint")
        if step_meta.get("rerank_error"):
            rerank_errors.append(f"step_back:{step_meta.get('rerank_error')}")
        retrieval_mode = retrieval_mode or step_meta.get("retrieval_mode")
        candidate_k = candidate_k or step_meta.get("candidate_k")
        leaf_retrieve_level = leaf_retrieve_level or step_meta.get("leaf_retrieve_level")
        auto_merge_enabled = auto_merge_enabled if auto_merge_enabled is not None else step_meta.get("auto_merge_enabled")
        auto_merge_applied = auto_merge_applied or bool(step_meta.get("auto_merge_applied"))
        auto_merge_threshold = auto_merge_threshold or step_meta.get("auto_merge_threshold")
        auto_merge_replaced_chunks += int(step_meta.get("auto_merge_replaced_chunks") or 0)
        auto_merge_steps += int(step_meta.get("auto_merge_steps") or 0)

    # 执行 RRF 融合并去重
    rrf_k = 60
    rrf_scores = {}
    docs_by_key = {}
    # 仅融合真实分支结果；若分支为空则回退到初始结果集。
    source_lists = [hyde_docs, step_docs]
    if not any(source_lists):
        source_lists = [results]
    for ranked_docs in source_lists:
        for rank, item in enumerate(ranked_docs, 1):
            key = (item.get("filename"), item.get("page_number"),
                   item.get("text"))
            docs_by_key.setdefault(key, dict(item))
            rrf_scores[key] = rrf_scores.get(key, 0.0) + (1.0 / (rrf_k + rank))

    ranked_keys = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k],
                         reverse=True)
    deduped = []
    for idx, key in enumerate(ranked_keys, 1):
        item = docs_by_key[key]
        item["rrf_score"] = round(rrf_scores[key], 8)
        item["rrf_rank"] = idx
        deduped.append(item)

    context = format_docs(deduped)
    emit_rag_step("✅", f"扩展检索完成，共 {len(deduped)} 个片段")
    rag_trace = state.get("rag_trace", {}) or {}
    rag_trace.update({
        "expanded_query": state.get("expanded_query") or state["question"],
        "step_back_question": state.get("step_back_question", ""),
        "step_back_answer": state.get("step_back_answer", ""),
        "hypothetical_doc": state.get("hypothetical_doc", ""),
        "expansion_type": strategy,
        "retrieved_chunks": deduped,
        "expanded_retrieved_chunks": deduped,
        "retrieval_stage": "expanded",
        "rerank_enabled": rerank_enabled_any,
        "rerank_applied": rerank_applied_any,
        "rerank_model": rerank_model,
        "rerank_endpoint": rerank_endpoint,
        "rerank_error": "; ".join(rerank_errors) if rerank_errors else None,
        "retrieval_mode": retrieval_mode,
        "candidate_k": candidate_k,
        "leaf_retrieve_level": leaf_retrieve_level,
        "auto_merge_enabled": auto_merge_enabled,
        "auto_merge_applied": auto_merge_applied,
        "auto_merge_threshold": auto_merge_threshold,
        "auto_merge_replaced_chunks": auto_merge_replaced_chunks,
        "auto_merge_steps": auto_merge_steps,
        "rrf_k": rrf_k,
    })
    return {"docs": deduped, "context": context, "rag_trace": rag_trace}


