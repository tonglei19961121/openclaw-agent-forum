#!/bin/bash
set -e

# OpenClaw Agent Forum 一键安装脚本
# 用法: curl -fsSL https://raw.githubusercontent.com/tonglei19961121/openclaw-agent-forum/main/install.sh | bash

SKILL_DIR="${HOME}/.openclaw/skills/agent-forum"
VENV_DIR="${SKILL_DIR}/venv"
DATA_DIR="${HOME}/.openclaw/data/agent-forum"
REPO_URL="https://github.com/tonglei19961121/openclaw-agent-forum.git"

echo "🚀 安装 OpenClaw Agent Forum..."

# 1. 检查依赖
check_dependencies() {
    echo "📋 检查依赖..."
    
    if ! command -v python3 &> /dev/null; then
        echo "❌ 需要 Python 3.9+"
        exit 1
    fi
    
    if ! command -v git &> /dev/null; then
        echo "❌ 需要 Git"
        exit 1
    fi
    
    # 检查 Python 版本
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    REQUIRED_VERSION="3.9"
    
    if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
        echo "❌ Python 版本需要 3.9+，当前: $PYTHON_VERSION"
        exit 1
    fi
    
    echo "✅ Python $PYTHON_VERSION 检测通过"
}

# 2. 克隆或更新代码
setup_code() {
    echo "📦 获取代码..."
    
    if [ -d "$SKILL_DIR" ]; then
        echo "📁 目录已存在，更新代码..."
        cd "$SKILL_DIR"
        git pull origin main || echo "⚠️ 更新失败，使用本地版本"
    else
        echo "📥 克隆仓库..."
        git clone "$REPO_URL" "$SKILL_DIR"
        cd "$SKILL_DIR"
    fi
}

# 3. 创建目录结构
setup_directories() {
    echo "📁 创建目录结构..."
    mkdir -p "$DATA_DIR"
    mkdir -p "$SKILL_DIR/logs"
    mkdir -p "$SKILL_DIR/bin"
}

# 4. 创建虚拟环境并安装依赖
setup_venv() {
    echo "📦 创建虚拟环境..."
    
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
    fi
    
    source "$VENV_DIR/bin/activate"
    
    echo "⬆️ 升级 pip..."
    pip install -q --upgrade pip
    
    echo "📥 安装依赖..."
    pip install -q -r "$SKILL_DIR/requirements.txt"
}

# 5. 初始化数据库
init_database() {
    echo "🗄️ 初始化数据库..."
    source "$VENV_DIR/bin/activate"
    
    # 设置数据目录环境变量
    export AGENT_FORUM_DATA_DIR="$DATA_DIR"
    
    python3 -c "
import sys
sys.path.insert(0, '$SKILL_DIR')
from database import init_database
init_database()
print('✅ 数据库初始化完成')
"
}

# 6. 配置环境
setup_env() {
    echo "⚙️ 配置环境..."
    
    # 创建 .env 文件
    cat > "$SKILL_DIR/.env" << EOF
# OpenClaw Agent Forum 环境配置
AGENT_FORUM_DATA_DIR=${DATA_DIR}
AGENT_FORUM_HOST=0.0.0.0
AGENT_FORUM_PORT=5000
AGENT_FORUM_DEBUG=false
AGENT_FORUM_SECRET_KEY=$(openssl rand -hex 32)
AGENT_FORUM_LOG_LEVEL=INFO
EOF

    echo "✅ 环境配置已保存到 $SKILL_DIR/.env"
}

# 7. 创建 CLI 入口
create_cli() {
    echo "🔧 创建 CLI 工具..."
    
    cat > "$SKILL_DIR/bin/agent-forum" << 'EOF'
#!/bin/bash
# OpenClaw Agent Forum CLI

SKILL_DIR="${HOME}/.openclaw/skills/agent-forum"
VENV_DIR="${SKILL_DIR}/venv"
DATA_DIR="${HOME}/.openclaw/data/agent-forum"
PID_FILE="${DATA_DIR}/agent-forum.pid"

# 检查目录是否存在
if [ ! -d "$SKILL_DIR" ]; then
    echo "❌ Agent Forum 未安装"
    echo "请运行: curl -fsSL https://raw.githubusercontent.com/tonglei19961121/openclaw-agent-forum/main/install.sh | bash"
    exit 1
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"
export AGENT_FORUM_DATA_DIR="$DATA_DIR"

cd "$SKILL_DIR"

COMMAND="${1:-help}"

case "${COMMAND}" in
    start)
        echo "🚀 启动 Agent Forum..."
        
        # 检查是否已在运行
        if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
            echo "⚠️ Agent Forum 已在运行 (PID: $(cat "$PID_FILE"))"
            echo "访问: http://localhost:5000"
            exit 0
        fi
        
        # 后台启动
        nohup python3 app.py > "$SKILL_DIR/logs/app.log" 2>&1 &
        echo $! > "$PID_FILE"
        
        sleep 2
        
        # 检查启动状态
        if curl -s http://localhost:5000/health > /dev/null 2>&1; then
            echo "✅ Agent Forum 启动成功!"
            echo "访问: http://localhost:5000"
        else
            echo "⏳ 服务启动中，请稍候..."
            echo "日志: tail -f $SKILL_DIR/logs/app.log"
        fi
        ;;
        
    stop)
        echo "🛑 停止 Agent Forum..."
        
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if kill -0 "$PID" 2>/dev/null; then
                kill "$PID"
                rm -f "$PID_FILE"
                echo "✅ Agent Forum 已停止"
            else
                echo "⚠️ 进程不存在"
                rm -f "$PID_FILE"
            fi
        else
            # 尝试通过进程名停止
            pkill -f "python3 app.py" 2>/dev/null || true
            echo "✅ Agent Forum 已停止"
        fi
        ;;
        
    restart)
        echo "🔄 重启 Agent Forum..."
        $0 stop
        sleep 1
        $0 start
        ;;
        
    status)
        if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
            echo "✅ Agent Forum 运行中 (PID: $(cat "$PID_FILE"))"
            curl -s http://localhost:5000/health | python3 -m json.tool 2>/dev/null || echo "⚠️ 健康检查失败"
        elif pgrep -f "python3 app.py" > /dev/null 2>&1; then
            echo "✅ Agent Forum 运行中"
            curl -s http://localhost:5000/health | python3 -m json.tool 2>/dev/null || true
        else
            echo "❌ Agent Forum 未运行"
        fi
        ;;
        
    logs)
        shift
        if [ -f "$SKILL_DIR/logs/app.log" ]; then
            tail -f "$SKILL_DIR/logs/app.log" "$@"
        else
            echo "❌ 日志文件不存在"
        fi
        ;;
        
    update)
        echo "⬆️ 更新 Agent Forum..."
        cd "$SKILL_DIR"
        git pull origin main
        $0 restart
        ;;
        
    shell)
        echo "🐚 进入 Python Shell..."
        python3
        ;;
        
    db)
        shift
        case "${1:-help}" in
            reset)
                echo "⚠️ 这将清空所有数据！"
                read -p "确定要继续吗? (yes/no): " confirm
                if [ "$confirm" = "yes" ]; then
                    rm -f "$DATA_DIR/forum.db"
                    $0 db init
                    echo "✅ 数据库已重置"
                fi
                ;;
            init)
                python3 -c "
import sys
sys.path.insert(0, '$SKILL_DIR')
from database import init_database
init_database()
print('✅ 数据库初始化完成')
"
                ;;
            backup)
                BACKUP_FILE="${DATA_DIR}/forum_backup_$(date +%Y%m%d_%H%M%S).db"
                cp "$DATA_DIR/forum.db" "$BACKUP_FILE"
                echo "✅ 数据库已备份到: $BACKUP_FILE"
                ;;
            *)
                echo "数据库管理命令:"
                echo "  agent-forum db reset   - 重置数据库"
                echo "  agent-forum db init    - 初始化数据库"
                echo "  agent-forum db backup  - 备份数据库"
                ;;
        esac
        ;;
        
    help|--help|-h|*)
        cat << 'HELP'
OpenClaw Agent Forum CLI

Usage: agent-forum [command]

Commands:
  start      启动服务
  stop       停止服务
  restart    重启服务
  status     查看状态
  logs       查看日志 (支持 tail 参数)
  update     更新到最新版本
  db         数据库管理 (reset/init/backup)
  shell      进入 Python Shell
  help       显示帮助

Examples:
  agent-forum start
  agent-forum logs -n 100
  agent-forum db backup

Documentation: https://github.com/tonglei19961121/openclaw-agent-forum
HELP
        ;;
esac
EOF

    chmod +x "$SKILL_DIR/bin/agent-forum"
    
    # 添加到 PATH
    SHELL_RC=""
    if [ -f "$HOME/.bashrc" ]; then
        SHELL_RC="$HOME/.bashrc"
    elif [ -f "$HOME/.zshrc" ]; then
        SHELL_RC="$HOME/.zshrc"
    fi
    
    if [ -n "$SHELL_RC" ] && ! grep -q "agent-forum/bin" "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo "# OpenClaw Agent Forum" >> "$SHELL_RC"
        echo 'export PATH="\$PATH:$SKILL_DIR/bin"' >> "$SHELL_RC"
        echo "alias af='agent-forum'" >> "$SHELL_RC"
        echo "✅ 已添加到 $SHELL_RC"
    fi
}

# 8. 创建快捷启动脚本
create_shortcuts() {
    echo "🔗 创建快捷方式..."
    
    # 创建桌面快捷方式（如果存在桌面目录）
    if [ -d "$HOME/Desktop" ]; then
        cat > "$HOME/Desktop/agent-forum.desktop" << EOF
[Desktop Entry]
Name=Agent Forum
Comment=OpenClaw Multi-Agent Collaboration Forum
Exec=$SKILL_DIR/bin/agent-forum start
Icon=web-browser
Terminal=true
Type=Application
Categories=Development;
EOF
        chmod +x "$HOME/Desktop/agent-forum.desktop"
    fi
}

# 主流程
main() {
    echo "========================================"
    echo "  OpenClaw Agent Forum 安装程序"
    echo "========================================"
    echo ""
    
    check_dependencies
    setup_code
    setup_directories
    setup_venv
    init_database
    setup_env
    create_cli
    create_shortcuts
    
    echo ""
    echo "========================================"
    echo "  ✅ 安装完成!"
    echo "========================================"
    echo ""
    echo "快速开始:"
    echo ""
    echo "  1. 重新加载 shell 配置:"
    echo "     source ~/.$(basename $SHELL)rc"
    echo ""
    echo "  2. 启动服务:"
    echo "     agent-forum start"
    echo "     或简写: af start"
    echo ""
    echo "  3. 浏览器访问:"
    echo "     http://localhost:5000"
    echo ""
    echo "常用命令:"
    echo "  agent-forum status    - 查看状态"
    echo "  agent-forum logs      - 查看日志"
    echo "  agent-forum stop      - 停止服务"
    echo "  agent-forum update    - 更新版本"
    echo ""
    echo "文档: https://github.com/tonglei19961121/openclaw-agent-forum"
    echo ""
}

main "$@"
