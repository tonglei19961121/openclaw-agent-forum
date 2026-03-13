#!/usr/bin/env python3
"""
WebSocket 原型 - Agent Forum 实时通信测试 (UI 优化版)
CTO Sprint 1 任务：搭建 WebSocket 基础设施 + 前端美化

功能：
1. WebSocket 连接管理
2. 房间模型（每个 agent 一个房间）
3. 消息广播
4. @mention 通知推送

UI 优化：
- 现代化渐变背景 + 卡片式设计
- 响应式布局，支持移动端
- 流畅动画过渡效果
- 语义化颜色系统
- 更好的视觉层次
"""

from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit, join_room, leave_room
import redis
import json
import time
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'agent-forum-secret-key'

# WebSocket 配置（内存模式 - 原型阶段）
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25
)

# Redis 连接
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    redis_client.ping()
    REDIS_AVAILABLE = True
    print("[WebSocket] ✅ Redis 已连接")
except Exception as e:
    print(f"[WebSocket] ⚠️ Redis 未可用，使用内存模式：{e}")
    redis_client = None
    REDIS_AVAILABLE = False

# 在线用户追踪
online_users = {}

# HTML 测试页面 - UI 优化版
TEST_PAGE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Forum WebSocket Test</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        :root {
            --primary: #6366f1;
            --primary-dark: #4f46e5;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --bg-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            --card-bg: rgba(255, 255, 255, 0.95);
            --shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
            --radius: 16px;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--bg-gradient);
            min-height: 100vh;
            padding: 20px;
            line-height: 1.6;
        }

        .container {
            max-width: 900px;
            margin: 0 auto;
            background: var(--card-bg);
            padding: 32px;
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            backdrop-filter: blur(10px);
        }

        header {
            text-align: center;
            margin-bottom: 32px;
            padding-bottom: 24px;
            border-bottom: 2px solid #e5e7eb;
        }

        h1 {
            font-size: 2rem;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 8px;
        }

        .subtitle {
            color: #6b7280;
            font-size: 0.95rem;
        }

        .status {
            padding: 12px 20px;
            margin: 20px 0;
            border-radius: 12px;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
        }

        .status.connected {
            background: linear-gradient(135deg, #d1fae5, #a7f3d0);
            color: #065f46;
            border: 1px solid #6ee7b7;
        }

        .status.disconnected {
            background: linear-gradient(135deg, #fee2e2, #fecaca);
            color: #991b1b;
            border: 1px solid #fca5a5;
        }

        .controls {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin: 24px 0;
            padding: 20px;
            background: #f9fafb;
            border-radius: 12px;
        }

        input[type="text"] {
            flex: 1;
            min-width: 200px;
            padding: 12px 16px;
            border: 2px solid #e5e7eb;
            border-radius: 8px;
            font-size: 1rem;
            transition: all 0.2s;
        }

        input[type="text"]:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
        }

        button {
            padding: 12px 24px;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 0.95rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
        }

        button:hover {
            background: var(--primary-dark);
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
        }

        button:active {
            transform: translateY(0);
        }

        button.secondary {
            background: #6b7280;
            box-shadow: 0 2px 8px rgba(107, 114, 128, 0.3);
        }

        button.secondary:hover {
            background: #4b5563;
        }

        #messages {
            max-height: 400px;
            overflow-y: auto;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 16px;
            margin: 24px 0;
            background: white;
        }

        .message {
            padding: 12px 16px;
            margin: 8px 0;
            border-left: 4px solid var(--primary);
            background: linear-gradient(135deg, #f5f3ff, #ede9fe);
            border-radius: 8px;
            animation: slideIn 0.3s ease;
        }

        .message.mention {
            border-left-color: var(--warning);
            background: linear-gradient(135deg, #fef3c7, #fde68a);
        }

        .message.system {
            border-left-color: var(--success);
            background: linear-gradient(135deg, #d1fae5, #a7f3d0);
        }

        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateX(-10px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }

        .message strong {
            color: var(--primary-dark);
        }

        .timestamp {
            font-size: 0.75rem;
            color: #9ca3af;
            float: right;
        }

        /* 滚动条美化 */
        #messages::-webkit-scrollbar {
            width: 8px;
        }

        #messages::-webkit-scrollbar-track {
            background: #f1f1f1;
            border-radius: 4px;
        }

        #messages::-webkit-scrollbar-thumb {
            background: var(--primary);
            border-radius: 4px;
        }

        #messages::-webkit-scrollbar-thumb:hover {
            background: var(--primary-dark);
        }

        /* 响应式 */
        @media (max-width: 640px) {
            .container {
                padding: 20px;
            }

            h1 {
                font-size: 1.5rem;
            }

            .controls {
                flex-direction: column;
            }

            input[type="text"] {
                width: 100%;
            }

            button {
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🦞 Agent Forum WebSocket 测试</h1>
            <p class="subtitle">实时通信基础设施 · 原型版本</p>
        </header>

        <div id="status" class="status disconnected">
            <span>⚡</span>
            <span>未连接</span>
        </div>

        <div class="controls">
            <input type="text" id="agentId" placeholder="Agent ID (e.g., cto, designer)" value="designer">
            <button onclick="connect()">🔌 连接</button>
            <button onclick="disconnect()" class="secondary">❌ 断开</button>
            <button onclick="sendMessage()">📤 发送消息</button>
            <button onclick="sendMention()">🔔 发送 @mention</button>
        </div>

        <div id="messages"></div>
    </div>

    <script>
        let socket = null;

        function connect() {
            const agentId = document.getElementById('agentId').value.trim();
            if (!agentId) {
                alert('请输入 Agent ID');
                return;
            }

            socket = io('http://localhost:5000', {
                query: { agent_id: agentId }
            });

            socket.on('connect', () => {
                updateStatus('✅ 已连接 - Agent: ' + agentId, 'connected');
                addMessage('系统', 'WebSocket 连接成功！欢迎加入 Agent Forum', 'system');
            });

            socket.on('disconnect', () => {
                updateStatus('⚡ 未连接', 'disconnected');
                addMessage('系统', 'WebSocket 连接断开', 'system');
            });

            socket.on('message', (data) => {
                addMessage(data.from, data.content);
            });

            socket.on('mention', (data) => {
                addMessage('🔔 Mention', data.from + ' 在 #' + data.post_id + ' 中提及了你：' + data.content, 'mention');
            });

            socket.on('notification', (data) => {
                addMessage('📬 通知', data.type + ': ' + data.content, 'system');
            });
        }

        function disconnect() {
            if (socket) {
                socket.disconnect();
                socket = null;
            }
        }

        function sendMessage() {
            if (!socket) { alert('请先连接'); return; }
            const agentId = document.getElementById('agentId').value;
            socket.emit('message', {
                from: agentId,
                to: 'po',
                content: '测试消息 - ' + new Date().toISOString()
            });
            addMessage(agentId, '发送测试消息到 po');
        }

        function sendMention() {
            if (!socket) { alert('请先连接'); return; }
            const agentId = document.getElementById('agentId').value;
            socket.emit('mention', {
                from: agentId,
                post_id: 5,
                content: '测试 @mention - ' + new Date().toISOString()
            });
            addMessage(agentId, '发送 @mention 测试');
        }

        function updateStatus(text, className) {
            const status = document.getElementById('status');
            status.innerHTML = '<span>' + (className === 'connected' ? '✅' : '⚡') + '</span><span>' + text + '</span>';
            status.className = 'status ' + className;
        }

        function addMessage(from, content, type = '') {
            const messages = document.getElementById('messages');
            const msg = document.createElement('div');
            msg.className = 'message ' + type;
            const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            msg.innerHTML = '<strong>' + from + '</strong>: ' + content + '<span class="timestamp">' + time + '</span>';
            messages.appendChild(msg);
            messages.scrollTop = messages.scrollHeight;
        }

        // 自动连接
        window.addEventListener('DOMContentLoaded', () => {
            connect();
        });
    </script>
</body>
</html>
"""

@socketio.on('connect')
def handle_connect():
    """处理客户端连接"""
    from flask import request
    agent_id = request.args.get('agent_id', 'anonymous')
    
    join_room(f'agent:{agent_id}')
    
    online_users[agent_id] = {
        'sid': request.sid,
        'connected_at': datetime.now().isoformat()
    }
    
    socketio.emit('notification', {
        'type': 'user_online',
        'content': f'{agent_id} 已上线',
        'agent_id': agent_id
    }, room='global')
    
    print(f"[WebSocket] {agent_id} 已连接 (SID: {request.sid})")
    emit('connected', {'agent_id': agent_id, 'message': '欢迎加入 Agent Forum!'})

@socketio.on('disconnect')
def handle_disconnect():
    """处理客户端断开"""
    from flask import request
    for agent_id, info in list(online_users.items()):
        if info['sid'] == request.sid:
            del online_users[agent_id]
            socketio.emit('notification', {
                'type': 'user_offline',
                'content': f'{agent_id} 已下线',
                'agent_id': agent_id
            }, room='global')
            print(f"[WebSocket] {agent_id} 已断开")
            break

@socketio.on('message')
def handle_message(data):
    """处理点对点消息"""
    from_agent = data.get('from', 'anonymous')
    to_agent = data.get('to')
    content = data.get('content', '')
    
    message = {
        'type': 'message',
        'from': from_agent,
        'to': to_agent,
        'content': content,
        'timestamp': datetime.now().isoformat()
    }
    if REDIS_AVAILABLE and redis_client:
        redis_client.lpush('messages:queue', json.dumps(message))
    
    if to_agent:
        socketio.emit('message', message, room=f'agent:{to_agent}')
        print(f"[WebSocket] 消息：{from_agent} → {to_agent}: {content[:50]}...")

@socketio.on('mention')
def handle_mention(data):
    """处理 @mention 通知"""
    from_agent = data.get('from', 'anonymous')
    post_id = data.get('post_id')
    content = data.get('content', '')
    
    import re
    mentions = re.findall(r'@(\w+)', content)
    
    notification = {
        'type': 'mention',
        'from': from_agent,
        'post_id': post_id,
        'content': content,
        'mentioned_agents': mentions,
        'timestamp': datetime.now().isoformat()
    }
    
    for mentioned_agent in mentions:
        if REDIS_AVAILABLE and redis_client:
            redis_client.lpush(f'notifications:{mentioned_agent}', json.dumps(notification))
        socketio.emit('mention', notification, room=f'agent:{mentioned_agent}')
        print(f"[WebSocket] @mention: {from_agent} 提及了 {mentioned_agent} 在 Post #{post_id}")

@socketio.on('join_room')
def handle_join_room(data):
    """加入特定房间"""
    from flask import request
    room = data.get('room')
    agent_id = request.args.get('agent_id', 'anonymous')
    
    if room:
        join_room(room)
        print(f"[WebSocket] {agent_id} 加入房间：{room}")

@socketio.on('broadcast')
def handle_broadcast(data):
    """广播消息到全局"""
    content = data.get('content', '')
    from_agent = data.get('from', 'system')
    
    message = {
        'type': 'broadcast',
        'from': from_agent,
        'content': content,
        'timestamp': datetime.now().isoformat()
    }
    
    socketio.emit('broadcast', message, room='global')
    print(f"[WebSocket] 广播：{from_agent}: {content[:50]}...")

@app.route('/ws-test')
def test_page():
    """WebSocket 测试页面"""
    return render_template_string(TEST_PAGE)

@app.route('/api/ws/status')
def ws_status():
    """WebSocket 状态检查"""
    redis_connected = False
    if REDIS_AVAILABLE and redis_client:
        try:
            redis_connected = redis_client.ping()
        except:
            redis_connected = False
    
    return {
        'online_users': online_users,
        'online_count': len(online_users),
        'redis_connected': redis_connected,
        'mode': 'redis' if redis_connected else 'memory'
    }

if __name__ == '__main__':
    print("=" * 60)
    print("🦞 Agent Forum WebSocket 原型启动 (UI 优化版)")
    print("=" * 60)
    print("测试页面：http://localhost:5001/ws-test")
    print("状态检查：http://localhost:5001/api/ws/status")
    print("=" * 60)
    
    socketio.run(app, host='0.0.0.0', port=5001, debug=False, allow_unsafe_werkzeug=True)
