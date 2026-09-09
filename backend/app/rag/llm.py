'''
@create_time: 2026/4/27 下午3:58
@Author: GeChao
@File: llm.py
'''
from functools import lru_cache

from langchain.chat_models import init_chat_model

from app.core.config import ARK_API_KEY, BASE_URL, EXPAND_MODEL, GRADE_MODEL, ROUTER_MODEL


@lru_cache(maxsize=4)
def _cached_model(model_name: str, temperature: float):
    return init_chat_model(
        model=model_name,
        model_provider="openai",
        api_key=ARK_API_KEY,
        base_url=BASE_URL,
        temperature=temperature,
        stream_usage=True,
    )


def _get_grader_model():
    return _cached_model(GRADE_MODEL, 0) if ARK_API_KEY and GRADE_MODEL else None


def _get_router_model():
    # 问题改写节点:受限短文本生成,小模型即可(ROUTER_MODEL优先,回退REWRITE_MODEL)
    return _cached_model(ROUTER_MODEL, 0) if ARK_API_KEY and ROUTER_MODEL else None


def _get_default_model():
    # 查询扩展(HyDE/stepback):小模型生成假设文档
    return _cached_model(EXPAND_MODEL, 0.3)
