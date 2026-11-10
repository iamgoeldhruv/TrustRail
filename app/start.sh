#!/bin/bash
set -e

echo "Starting GitHub MCP server on port 8001..."

PORT=8001 python -m mcp_github.server &
MCP_PID=$!

cleanup() {
    echo "Stopping TrustRail servers..."
    kill "$MCP_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "Starting TrustRail FastAPI server..."

python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8080}" &
API_PID=$!

# Keep the container alive while both servers are running.
wait -n "$API_PID" "$MCP_PID"