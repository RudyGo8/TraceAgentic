'''
@create_time: 2025/09/03
@Author: GeChao
@File: config.py
'''
import os
from dotenv import load_dotenv

load_dotenv()

# mysql
MYSQL_USERNAME = os.getenv("MYSQL_USERNAME", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "123456")
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3308"))
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "rag_mysql")

# redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_KEY_PREFIX = os.getenv("REDIS_KEY_PREFIX", "rag_agent")
REDIS_CACHE_TTL_SECONDS = int(os.getenv("REDIS_CACHE_TTL_SECONDS", "300"))

# milvus
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "rag_embeddings")

# 通用模型
ARK_API_KEY = os.getenv("ARK_API_KEY", "")
MODEL = os.getenv("MODEL")
BASE_URL = os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
GRADE_MODEL = os.getenv("GRADE_MODEL", "qwen-plus")
# RAG辅助任务(改写/扩展/路由)用小模型,不配置则跟随MODEL
REWRITE_MODEL = os.getenv("REWRITE_MODEL", MODEL)
EXPAND_MODEL = os.getenv("EXPAND_MODEL", MODEL)
ROUTER_MODEL = os.getenv("ROUTER_MODEL") or REWRITE_MODEL
# 主模型失败时兜底
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "")
# 主模型思考模式(知识问答场景检索内容已锚定答案,默认关闭提速)
MAIN_MODEL_THINKING = os.getenv("MAIN_MODEL_THINKING", "false").lower() == "true"
# 评测裁判模型(独立家族,避免自我偏好)
EVAL_MODEL = os.getenv("EVAL_MODEL", GRADE_MODEL)

# 向量模型
EMBEDDER = os.getenv("EMBEDDER", "text-embedding-v2")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1536"))


# RAGAS 测评
RAGAS_API_KEY = os.getenv("RAGAS_API_KEY", ARK_API_KEY)
RAGAS_BASE_URL = os.getenv("RAGAS_BASE_URL", BASE_URL)
RAGAS_LLM_MODEL = os.getenv("RAGAS_LLM_MODEL") or EVAL_MODEL
RAGAS_EMBEDDING_MODEL = os.getenv("RAGAS_EMBEDDING_MODEL", EMBEDDER)

# merge
AUTO_MERGE_ENABLED = os.getenv("AUTO_MERGE_ENABLED", "true")
AUTO_MERGE_THRESHOLD = os.getenv("AUTO_MERGE_THRESHOLD", "2")
LEAF_RETRIEVE_LEVEL = os.getenv("LEAF_RETRIEVE_LEVEL", "3")

# jwt 鉴权
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))
ADMIN_INVITE_CODE = os.getenv("ADMIN_INVITE_CODE", "")
PASSWORD_PBKDF2_ROUNDS = int(os.getenv("PASSWORD_PBKDF2_ROUNDS", "310000"))

# mcp权限
MCP_ENABLED = os.getenv("MCP_ENABLED", "false").lower() == "true"

# 循环限制
AGENT_RECURSION_LIMIT = max(8, int(os.getenv("AGENT_RECURSION_LIMIT", "16")))
