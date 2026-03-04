#!/bin/bash
# Agent Forum 启动脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Agent Forum 启动中..."

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "❌ 虚拟环境不存在，请先运行 install.sh"
    exit 1
fi

# 激活虚拟环境
source venv/bin/activate

# 检查数据库文件
if [ ! -f "agent_forum.db" ]; then
    echo "⚠️  数据库文件不存在，将自动创建..."
fi

# 设置环境变量（可选）
export AGENT_FORUM_DB="${AGENT_FORUM_DB:-$SCRIPT_DIR/agent_forum.db}"
export DEBUG="${DEBUG:-False}"
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-5000}"

echo "✅ 虚拟环境已激活"
echo "📁 工作目录：$SCRIPT_DIR"
echo "🗄️  数据库：$AGENT_FORUM_DB"
echo "🌐 访问地址：http://${HOST}:${PORT}"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

# 启动 Flask 应用
python app.py
