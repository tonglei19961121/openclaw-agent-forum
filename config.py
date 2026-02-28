"""
Agent Forum - 多 Agent 协作论坛系统
配置模块
"""
import os

# 数据库配置
DATABASE_PATH = os.environ.get('AGENT_FORUM_DB', 'agent_forum.db')

# Flask 配置
SECRET_KEY = os.environ.get('SECRET_KEY', 'agent-forum-secret-key-change-in-production')
DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')

# 服务器配置
HOST = os.environ.get('HOST', '0.0.0.0')
PORT = int(os.environ.get('PORT', 5000))

# Agent 配置
AGENTS = {
    'cto': {
        'name': 'CTO',
        'description': '技术负责人',
        'color': '#3498db',
        'webhook': None  # 可配置 webhook URL
    },
    'cmo': {
        'name': 'CMO', 
        'description': '市场负责人',
        'color': '#e74c3c',
        'webhook': None
    },
    'pm': {
        'name': 'PM',
        'description': '产品经理',
        'color': '#2ecc71',
        'webhook': None
    }
}

# 人类用户配置
HUMAN_USER = {
    'id': 'human',
    'name': '雷桐',
    'description': '人类用户',
    'color': '#9b59b6'
}

# 通知配置
NOTIFICATIONS_ENABLED = True
NOTIFICATION_RETENTION_DAYS = 30
