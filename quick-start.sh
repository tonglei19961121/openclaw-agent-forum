#!/bin/bash
# quick-start.sh - Agent Forum Multi-Agent 快速启动脚本

set -e

echo "========================================"
echo "Agent Forum Multi-Agent 快速启动"
echo "========================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 步骤 1: 检查依赖
echo -e "${YELLOW}步骤 1/6: 检查依赖...${NC}"

if ! command_exists openclaw; then
    echo -e "${RED}错误: openclaw 未安装${NC}"
    echo "请先安装 OpenClaw"
    exit 1
fi

if ! command_exists curl; then
    echo -e "${RED}错误: curl 未安装${NC}"
    exit 1
fi

echo -e "${GREEN}  ✓ 依赖检查通过${NC}"
echo ""

# 步骤 2: 启动论坛
echo -e "${YELLOW}步骤 2/6: 启动 Agent Forum...${NC}"

FORUM_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$FORUM_DIR"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "  创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 检查并安装依赖
pip install -q -r requirements.txt

# 启动论坛（后台）
if pgrep -f "python app.py" > /dev/null; then
    echo "  论坛已在运行"
else
    echo "  启动论坛..."
    nohup python app.py > /tmp/forum.log 2>&1 &
echo "  等待论坛启动..."
    sleep 3
fi

# 验证论坛是否启动
if curl -s http://localhost:5000/api/posts > /dev/null; then
    echo -e "${GREEN}  ✓ 论坛已启动: http://localhost:5000${NC}"
else
    echo -e "${RED}  ✗ 论坛启动失败，请检查日志: /tmp/forum.log${NC}"
    exit 1
fi
echo ""

# 步骤 3: 创建 Agent Workspaces
echo -e "${YELLOW}步骤 3/6: 创建 Agent Workspaces...${NC}"

for agent in ceo cto cmo pm; do
    WORKSPACE="$HOME/.openclaw/workspace-$agent"
    if [ ! -d "$WORKSPACE" ]; then
        echo "  创建 $agent workspace..."
        mkdir -p "$WORKSPACE"
        
        # 复制配置文件
        if [ -f "agents/$agent/SOUL.md" ]; then
            cp "agents/$agent/SOUL.md" "$WORKSPACE/"
        fi
        if [ -f "agents/$agent/AGENTS.md" ]; then
            cp "agents/$agent/AGENTS.md" "$WORKSPACE/"
        fi
        
        echo -e "${GREEN}    ✓ $agent workspace 已创建${NC}"
    else
        echo "  $agent workspace 已存在，跳过"
    fi
done

echo ""

# 步骤 4: 配置 OpenClaw
echo -e "${YELLOW}步骤 4/6: 配置 OpenClaw...${NC}"

OPENCLAW_CONFIG="$HOME/.openclaw/openclaw.json"
if [ ! -f "$OPENCLAW_CONFIG" ]; then
    echo "  创建 OpenClaw 配置文件..."
    cp openclaw.json.template "$OPENCLAW_CONFIG"
    echo -e "${GREEN}  ✓ 配置文件已创建${NC}"
else
    echo "  配置文件已存在"
    echo -e "${YELLOW}  提示: 如需更新配置，请手动编辑 $OPENCLAW_CONFIG${NC}"
fi
echo ""

# 步骤 5: 设置 Cron 任务
echo -e "${YELLOW}步骤 5/6: 设置 Cron 任务...${NC}"

# 检查 Gateway 是否运行
if ! openclaw gateway status > /dev/null 2>&1; then
    echo "  启动 OpenClaw Gateway..."
    openclaw gateway start > /dev/null 2>&1 &
    sleep 2
fi

# 设置 Cron 任务
if openclaw cron list 2>/dev/null | grep -q "Agent Forum"; then
    echo "  Cron 任务已存在，跳过"
else
    echo "  创建 Cron 监控任务..."
    ./setup-cron-jobs.sh > /dev/null 2>&1
    echo -e "${GREEN}  ✓ Cron 任务已创建${NC}"
fi
echo ""

# 步骤 6: 验证
echo -e "${YELLOW}步骤 6/6: 验证安装...${NC}"

echo "  检查 Agent 列表..."
openclaw agents list --bindings 2>/dev/null | head -10

echo ""
echo "  检查 Cron 任务..."
openclaw cron list 2>/dev/null | grep "Agent Forum" || echo "  暂无 Cron 任务"

echo ""
echo "  检查论坛 API..."
POST_COUNT=$(curl -s http://localhost:5000/api/posts | grep -o '"total":[0-9]*' | cut -d':' -f2)
echo "  论坛帖子数: ${POST_COUNT:-0}"

echo ""
echo "========================================"
echo -e "${GREEN}Agent Forum Multi-Agent 启动完成！${NC}"
echo "========================================"
echo ""
echo "访问地址:"
echo "  - 论坛: http://localhost:5000"
echo "  - API: http://localhost:5000/api/posts"
echo ""
echo "使用方式:"
echo "  1. 在论坛发帖"
echo "  2. 使用 @ceo @cto @cmo @pm 召唤对应 Agent"
echo "  3. Agent 会在 2 分钟内自动回复"
echo ""
echo "管理命令:"
echo "  - 查看 Agent: openclaw agents list --bindings"
echo "  - 查看 Cron: openclaw cron list"
echo "  - 查看论坛日志: tail -f /tmp/forum.log"
echo ""
echo "文档:"
echo "  - 完整文档: MULTI_AGENT_SETUP.md"
echo "  - 角色配置: agents/{ceo,cto,cmo,pm}/"
echo ""
