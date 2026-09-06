#!/bin/bash
# Æsirian Core 启动脚本
# 启动 FastAPI 后端服务器 + 静态文件预览
# 用法: bash run.sh

echo "✦ Æsirian Core — 启动中..."

# 检查 Python
PYTHON=$(which python3 || which python)
if [ -z "$PYTHON" ]; then
    echo "✗ 需要 Python 3.10+"
    exit 1
fi
echo "  Python: $($PYTHON --version)"

# 切换到项目目录
cd "$(dirname "$0")"
echo "  目录: $(pwd)"

# 检查依赖
$PYTHON -c "import fastapi" 2>/dev/null || {
    echo "  → 安装依赖..."
    pip install fastapi uvicorn pydantic --break-system-packages
}

# 启动后端 (后台)
echo "  → 启动 FastAPI 后端 (端口 8765)..."
$PYTHON -m uvicorn bridge.api_server:app --host 127.0.0.1 --port 8765 --reload &
BACKEND_PID=$!
echo "  后端 PID: $BACKEND_PID"

# 等待启动
sleep 2

# 验证
$PYTHON -c "
import urllib.request, json
try:
    r = urllib.request.urlopen('http://127.0.0.1:8765/health')
    data = json.loads(r.read())
    print(f'  状态: {data[\"status\"]}')
    print(f'  引擎: {list(data[\"engines\"].keys())}')
    print('✅ 后端就绪')
except Exception as e:
    print(f'✗ 后端启动失败: {e}')
"

echo ""
echo "✦ API 地址: http://127.0.0.1:8765"
echo "✦ 文档:     http://127.0.0.1:8765/docs"
echo "✦ 停止:     kill $BACKEND_PID"
echo ""
echo "按 Ctrl+C 停止服务器"
wait $BACKEND_PID
