"""
@create_time: 2025/08/14
@Author: GeChao
@File: main.py
"""

import asyncio
from contextlib import asynccontextmanager

from app.core.database import init_db
from app.utils.log import get_logger, setup_logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

setup_logging()
logger = get_logger(__name__)

from app.api.routes.auth import router_r1 as auth_router_r1
from app.api.routes.chat import router_r1 as chat_router_r1
from app.api.routes.document import router_r1 as document_router_r1
from app.api.routes.version import router_r1 as version_router_r1
from app.core.version import get_app_version
from app.tools.mcp_gateway import mcp_client_manager

# # 前端dist
# FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
# FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动阶段预热数据库和 MCP 客户端，避免首个请求承担初始化开销。
    init_db()
    # 后台监听mcp server，实现热插拔
    await mcp_client_manager.initialize()
    mcp_watch_task = asyncio.create_task(
        mcp_client_manager.watch_config_loop(interval_seconds=30)
    )
    try:
        yield
    finally:
        mcp_watch_task.cancel()
        try:
            await mcp_watch_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="TraceAgentic",
    version=get_app_version(),
    description=__doc__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_request(request: Request, call_next):
    # 统一记录请求和响应状态，便于排查流式接口、鉴权和文档管理问题。
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code} {request.url}")
    return response


app.include_router(auth_router_r1)
app.include_router(chat_router_r1)
app.include_router(document_router_r1)
app.include_router(version_router_r1)

# if FRONTEND_DIST_DIR.exists():
#     # 生产部署时由 FastAPI 直接托管前端打包产物。
#     app.mount("/", StaticFiles(directory=str(FRONTEND_DIST_DIR), html=True), name="frontend")
# else:
#     logger.warning("Frontend dist not found at %s, skip static mount.", FRONTEND_DIST_DIR)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_config={"version": 1, "disable_existing_loggers": False},
    )
