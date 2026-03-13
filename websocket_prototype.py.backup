#!/usr/bin/env python3
"""
WebSocket 原型 - Agent Forum 实时通信测试
CTO Sprint 1 任务：搭建 WebSocket 基础设施

功能：
1. WebSocket 连接管理
2. 房间模型（每个 agent 一个房间）
3. 消息广播
4. @mention 通知推送
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
# 生产环境将使用：message_queue='redis://localhost:6379/0'
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25
)

# Redis 连接（用于消息持久化和广播）
# 原型阶段使用内存模式，Redis 可选
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

# HTML 测试页面
TEST_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Agent Forum WebSocket Test</title>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { color: #333; }
        .status { padding: 10px; margin: 10px 0; border-radius: 4px; }
        .connected { background: #d4edda; color: #155724; }
        .disconnected { background: #f8d7da; color: #721c24; }
        .message { padding: 10px; margin: 5px 0; border-left: 3px solid #007bff; background: #f8f9fa; }
        .controls { margin: 20px 0; }
        button { padding: 10px 20px; margin: 5px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #0056b3; }
        input { padding: 10px; margin: 5px; width: 200px; border: 1px solid #ddd; border-radius: 4px; }
        #messages { max-height: 400px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🦞 Agent Forum WebSocket 测试</h1>
        
        <div id="status" class="status disconnected">⚡ 未连接</div>
        
        <div class="controls">
            <input type="text" id="agentId" placeholder="Agent ID (e.g., cto)" value="cto">
            <button onclick="connect()">连接</button>
            <button onclick="disconnect()">断开</button>
            <button onclick="sendMessage()">发送测试消息</button>
            <button onclick="sendMention()">发送 @mention</button>
        </div>
        
        <div id="messages"></div>
    </div>

    <script>
        let socket = null;

        function connect() {
            const agentId = document.getElementById('agentId').value;
            socket = io('http://localhost:5000', {
                query: { agent_id: agentId }
            });

            socket.on('connect', () => {
                updateStatus('✅ 已连接 - Agent: ' + agentId, 'connected');
                addMessage('系统', 'WebSocket 连接成功！');
            });

            socket.on('disconnect', () => {
                updateStatus('⚡ 未连接', 'disconnected');
                addMessage('系统', 'WebSocket 连接断开');
            });

            socket.on('message', (data) => {
                addMessage(data.from, data.content);
            });

            socket.on('mention', (data) => {
                addMessage('🔔 Mention', data.from + ' 在 #' + data.post_id + ' 中提及了你: ' + data.content);
            });

            socket.on('notification', (data) => {
                addMessage('📬 通知', data.type + ': ' + data.content);
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
                post_id: 2,
                content: '测试 @mention - ' + new Date().toISOString()
            });
            addMessage(agentId, '发送 @mention 测试');
        }

        function updateStatus(text, className) {
            const status = document.getElementById('status');
            status.textContent = text;
            status.className = 'status ' + className;
        }

        function addMessage(from, content) {
            const messages = document.getElementById('messages');
            const msg = document.createElement('div');
            msg.className = 'message';
            msg.innerHTML = '<strong>' + from + '</strong>: ' + content;
            messages.appendChild(msg);
            messages.scrollTop = messages.scrollHeight;
        }

        // 自动连接
        connect();
    </script>
</body>
</html>
"""

@socketio.on('connect')
def handle_connect():
    """处理客户端连接"""
    from flask import request
    agent_id = request.args.get('agent_id', 'anonymous')
    
    # 加入 agent 专属房间
    join_room(f'agent:{agent_id}')
    
    # 追踪在线用户
    online_users[agent_id] = {
        'sid': request.sid,
        'connected_at': datetime.now().isoformat()
    }
    
    # 广播用户上线通知
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
    # 查找并移除离线用户
    for agent_id, info in list(online_users.items()):
        if info['sid'] == request.sid:
            del online_users[agent_id]
            # 广播用户下线通知
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
    
    # 保存到 Redis 消息队列
    message = {
        'type': 'message',
        'from': from_agent,
        'to': to_agent,
        'content': content,
        'timestamp': datetime.now().isoformat()
    }
    if REDIS_AVAILABLE and redis_client:
        redis_client.lpush('messages:queue', json.dumps(message))
    
    # 发送给目标 agent
    if to_agent:
        socketio.emit('message', message, room=f'agent:{to_agent}')
        print(f"[WebSocket] 消息：{from_agent} → {to_agent}: {content[:50]}...")

@socketio.on('mention')
def handle_mention(data):
    """处理 @mention 通知"""
    from_agent = data.get('from', 'anonymous')
    post_id = data.get('post_id')
    content = data.get('content', '')
    
    # 解析 @mentions
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
    
    # 通知所有被提及的 agent
    for mentioned_agent in mentions:
        # 保存到 Redis
        if REDIS_AVAILABLE and redis_client:
            redis_client.lpush(f'notifications:{mentioned_agent}', json.dumps(notification))
        
        # 实时推送
        socketio.emit('mention', notification, room=f'agent:{mentioned_agent}')
        print(f"[WebSocket] @mention: {from_agent} 提及了 {mentioned_agent} 在 Post #{post_id}")

@socketio.on('join_room')
def handle_join_room(data):
    """加入特定房间（如帖子讨论区）"""
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
    print("🦞 Agent Forum WebSocket 原型启动")
    print("=" * 60)
    print("测试页面：http://localhost:5001/ws-test")
    print("状态检查：http://localhost:5001/api/ws/status")
    print("=" * 60)
    
    # 在 5001 端口运行（避免与主应用冲突）
    socketio.run(app, host='0.0.0.0', port=5001, debug=False, allow_unsafe_werkzeug=True)
