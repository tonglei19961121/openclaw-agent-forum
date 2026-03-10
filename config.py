"""
Agent Forum - 多 Agent 协作论坛系统
配置模块
"""
import os

# 数据库配置
DATABASE_PATH = os.environ.get('AGENT_FORUM_DB', 'agent_forum.db')

# Flask 配置
SECRET_KEY = os.environ.get('SECRET_KEY', 'agent-forum-secret-key-change-in-production')
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')

# 服务器配置
HOST = os.environ.get('HOST', '0.0.0.0')
PORT = int(os.environ.get('PORT', 5000))

# Default Agent configuration is now read from agents/{agent_id}/CONFIG.json
# Use the /team page or API to manage agents dynamically.

# 人类用户配置（董事长）
HUMAN_USER = {
    'id': 'chairman',
    'name': '雷桐',
    'description': '董事长',
    'color': '#9b59b6'
}

# 通知配置
NOTIFICATIONS_ENABLED = True
NOTIFICATION_RETENTION_DAYS = 30
