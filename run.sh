#!/usr/bin/env bash
# 一键启动(在 WSL 里执行): docker基础设施 + 后端 + 前端
# Ctrl+C 一并停止前后端; 基础设施用 docker compose stop 单独停
cd "$(dirname "$0")" || exit 1

echo "[1/3] 启动基础设施 (MySQL/Redis/Milvus)..."
docker compose up -d || exit 1

echo "[2/3] 启动后端 (端口8000)..."
uv run --directory backend uvicorn app.main:app --reload --port 8000 &
BACK_PID=$!

echo "[3/3] 启动前端 (Vite)..."
[ -d frontend/node_modules ] || (cd frontend && npm install)
npm --prefix frontend run dev &
FRONT_PID=$!

trap 'kill $BACK_PID $FRONT_PID 2>/dev/null' EXIT
echo ""
echo "全部已启动: 后端 http://localhost:8000/docs | Attu http://localhost:8081"
echo "前端地址见下方 Vite 输出 (默认 http://localhost:5173), Ctrl+C 停止前后端"
wait
