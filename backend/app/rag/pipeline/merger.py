from collections import Counter

from app.core.config import AUTO_MERGE_ENABLED, AUTO_MERGE_THRESHOLD, LEAF_RETRIEVE_LEVEL
from app.services.parent_chunk_store import parent_chunk_store
from app.utils.log import get_logger
logger = get_logger(__name__)


# 将配置中的字符串“true”、“false“ 转换为布尔值
def _parse_bool(value) -> bool:
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(value)

# 默认同一父块至少出现2次子块才进行合并
AUTO_MERGE_ENABLED_VALUE = _parse_bool(AUTO_MERGE_ENABLED)
AUTO_MERGE_THRESHOLD_VALUE = int(AUTO_MERGE_THRESHOLD) if AUTO_MERGE_THRESHOLD else 2
# 叶子节点为3
LEAF_RETRIEVE_LEVEL_VALUE = int(LEAF_RETRIEVE_LEVEL) if LEAF_RETRIEVE_LEVEL else 3


# 自动合并子块
def auto_merge_chunks(results: list[dict], top_k: int = 5):
    auto_merge_applied = False
    auto_merge_replaced_chunks = 0
    auto_merge_steps = 0

    if AUTO_MERGE_ENABLED_VALUE and results:
        try:
            # 统计次数
            parent_counts = Counter(
                item.get("parent_chunk_id", "") for item in results if item.get("parent_chunk_id")
            )
            merged_results = []
            # 记录已被合并的索引
            used_indices = set()

            for i, item in enumerate(results):
                if i in used_indices:
                    continue

                parent_id = item.get("parent_chunk_id", "")

                # 判断当前子块是否需要合并
                should_merge = (parent_id and parent_counts.get(parent_id, 0) >= AUTO_MERGE_THRESHOLD_VALUE )
                if should_merge:
                    parent_doc = parent_chunk_store.get_chunk(parent_id)
                    if parent_doc:
                        # 父文档的完整文本替换当前子块的文本
                        item["text"] = parent_doc.get("text", item.get("text", ""))
                        item["parent_retrieved"] = True
                        for j in range(i + 1, len(results)):
                            # 该父块对应的后续所有子块标记为已使用
                            if results[j].get("parent_chunk_id") == parent_id:
                                used_indices.add(j)
                        auto_merge_applied = True
                        auto_merge_replaced_chunks += 1
                        auto_merge_steps = 1

                merged_results.append(item)

            results = merged_results
        except Exception as exc:
            logger.warning("auto_merge_failed error=%s", exc)

    # 截取前 tok条
    results = results[:top_k]
    for index, item in enumerate(results):
        item["final_rank"] = index + 1

    meta = {
        "leaf_retrieve_level": LEAF_RETRIEVE_LEVEL_VALUE,
        "auto_merge_enabled": AUTO_MERGE_ENABLED_VALUE,
        "auto_merge_applied": auto_merge_applied,
        "auto_merge_threshold": AUTO_MERGE_THRESHOLD_VALUE,
        "auto_merge_replaced_chunks": auto_merge_replaced_chunks,
        "auto_merge_steps": auto_merge_steps,
    }
    return results, meta
