#!/usr/bin/env bash
# Æsirian M3-1 四卡页「一键起」脚本（macOS/Linux）
# 起 mcp_server_fast.py --transport http (8765) -> 打开 pwa/four_cards.html
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT=8765
SERVER="$ROOT/mcp_server_fast.py"
PAGE="$ROOT/pwa/four_cards.html"
PYTHON="$ROOT/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON=python

if lsof -iTCP:$PORT -sTCP:LISTEN -P -n >/dev/null 2>&1; then
  echo "[run_fourcards] 端口 ${PORT} 已占用；若为本服务则直接复用。"
else
  echo "[run_fourcards] 启动 MCP HTTP 服务 @ http://127.0.0.1:${PORT}/mcp ..."
  (cd "$ROOT" && nohup "$PYTHON" "$SERVER" --transport http --port "$PORT" >/tmp/aesirian-mcp.log 2>&1 &)
  sleep 3
  curl -sf -X POST -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"boot","version":"1"}}}' \
    "http://127.0.0.1:${PORT}/mcp" >/dev/null || { echo "服务启动失败，见 /tmp/aesirian-mcp.log"; exit 1; }
  echo "[run_fourcards] 服务就绪。"
fi

if [ -f "$PAGE" ]; then
  echo "[run_fourcards] 打开 $PAGE"
  (command -v open >/dev/null && open "$PAGE") || (command -v xdg-open >/dev/null && xdg-open "$PAGE") || true
fi
echo "[run_fourcards] 完成：页面连接 http://127.0.0.1:${PORT}/mcp，点击「加载演示 · 洛阳星港」体验。"
