#!/bin/bash
# Agent Forum 启动脚本

cd "$(dirname "$0")"

echo "Agent Forum 启动中..."
echo "访问地址: http://localhost:5000"
echo ""

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -q -r requirements.txt

# 启动应用
python app.py
