@echo off
chcp 65001 >nul
echo ============================================
echo   TraceAgentic 一键启动
echo ============================================
echo [1/3] 启动基础设施 (MySQL/Redis/Milvus)...
wsl -d Ubuntu-24.04 --cd /home/rudy/projects/TraceAgentic -- docker compose up -d
echo [2/3] 启动后端 (端口8000, 新窗口)...
start "TraceAgentic-backend" wsl -d Ubuntu-24.04 --cd /home/rudy/projects/TraceAgentic/backend -- uv run uvicorn app.main:app --reload --port 8000
echo [3/3] 启动前端 (Vite, 新窗口)...
start "TraceAgentic-frontend" wsl -d Ubuntu-24.04 --cd /home/rudy/projects/TraceAgentic/frontend -- npm run dev
echo.
echo 全部已启动:
echo   后端API文档: http://localhost:8000/docs
echo   Attu管理台:  http://localhost:8081
echo   前端地址:    见前端窗口打印 (默认 http://localhost:5173)
echo.
echo 停止: 关闭两个弹出的窗口, 再执行 docker compose stop
pause
