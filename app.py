"""
Agent Forum - 多 Agent 协作论坛系统
主应用
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
import os
import sys
from datetime import datetime

from config import HUMAN_USER, HOST, PORT, DEBUG, SECRET_KEY
from agent_manager import (
    get_active_agents, get_all_agents, get_agent,
    hire_agent, dismiss_agent, rehire_agent, update_agent,
    get_agent_cron, update_agent_cron,
    sync_agent_status, reconcile_all_agents, get_unsynced_agents
)
from database import (
    delete_post, can_delete_post, restore_post, get_deleted_posts,
    delete_reply, can_delete_reply, restore_reply,
    init_database, create_post, get_post, get_posts, get_post_count,
    create_reply, get_replies, get_reply_count, get_reply, get_reply_titles,
    get_notifications, get_unread_count, mark_notification_read, mark_all_notifications_read,
    parse_mentions,
    get_db_connection
)



app = Flask(__name__)
app.secret_key = SECRET_KEY

from markupsafe import escape, Markup

# 添加 nl2br 过滤器
@app.template_filter('nl2br')
def nl2br_filter(text):
    """将换行符转换为 <br> 标签，并处理 HTML 转义以防 XSS"""
    if not text:
        return text
    return Markup(escape(text).replace('\n', '\u003cbr\u003e'))

# 初始化数据库
init_database()
# 初始化埋点系统
from analytics import init_analytics, track_user_event, has_user_event, create_user_events_table
create_user_events_table()

# 注册埋点API蓝图
from track_api import track_bp
app.register_blueprint(track_bp)

# ============== 页面路由 ==============

@app.route('/')
def index():
    """首页 - 帖子列表"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    posts = get_posts(limit=per_page, offset=offset)
    total = get_post_count()
    
    # Get dynamic agents (include dismissed for historical display)
    agents = get_active_agents()
    all_agents = get_all_agents(include_dismissed=True)
    
    # 为每个帖子添加回复数
    for post in posts:
        post['reply_count'] = get_reply_count(post['id'])
    
    return render_template('index.html', 
                         posts=posts, 
                         page=page, 
                         total=total,
                         per_page=per_page,
                         agents=agents,
                         all_agents=all_agents,
                         human=HUMAN_USER)


@app.route('/post/<int:post_id>')
def view_post(post_id):
    """查看帖子详情"""
    post = get_post(post_id)
    if not post:
        return "帖子不存在", 404
    
    post['tags'] = json.loads(post.get('tags') or '[]')
    post['mentioned_agents'] = json.loads(post.get('mentioned_agents') or '[]')
    
    replies = get_replies(post_id)
    
    # Get dynamic agents (include dismissed for historical display)
    agents = get_active_agents()
    all_agents = get_all_agents(include_dismissed=True)
    
    return render_template('post.html',
                         post=post,
                         replies=replies,
                         agents=agents,
                         all_agents=all_agents,
                         human=HUMAN_USER)


@app.route('/post/new', methods=['GET', 'POST'])
def new_post():
    """创建新帖子"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        author_type = request.form.get('author_type', 'human')
        
        if not title or not content:
            return jsonify({'error': '标题和内容不能为空'}), 400
        
        # 解析 @mentions
        mentioned_agents = parse_mentions(content)
        
        # 确定作者信息
        agents = get_active_agents()
        if author_type == 'chairman':
            author_id = HUMAN_USER['id']
            author_name = HUMAN_USER['name']
        else:
            author_id = author_type  # agent_id
            author_name = agents.get(author_type, {}).get('name', author_type)
        
        post_id = create_post(
            title=title,
            content=content,
            author_id=author_id,
            author_name=author_name,
            author_type=author_type,
            mentioned_agents=mentioned_agents
        )
        
        # 埋点：首次发帖
        if not has_user_event(author_id, 'first_post'):
            track_user_event(author_id, author_type, 'first_post', {
                'post_id': post_id,
                'title': title[:100]
            })
        return jsonify({'success': True, 'post_id': post_id})
    
    return render_template('new_post.html', agents=get_active_agents(), human=HUMAN_USER)


@app.route('/post/<int:post_id>/reply', methods=['POST'])
def reply_post(post_id):
    """回复帖子"""
    content = request.form.get('content', '').strip()
    title = request.form.get('title', '').strip() or None
    author_type = request.form.get('author_type', 'human')
    
    if not content:
        return jsonify({'error': '回复内容不能为空'}), 400
    
    # 解析 @mentions
    mentioned_agents = parse_mentions(content)
    
    # 确定作者信息（添加验证）
    agents = get_active_agents()
    if author_type == 'chairman':
        author_id = HUMAN_USER['id']
        author_name = HUMAN_USER['name']
    elif author_type in agents:
        author_id = author_type
        author_name = agents[author_type]['name']
    else:
        # 检查是否是离职员工
        all_agents = get_all_agents(include_dismissed=True)
        if author_type in all_agents:
            author_id = author_type
            author_name = all_agents[author_type]['name']
        else:
            return jsonify({'error': f'无效的 author_type: {author_type}'}), 400
    
    reply_id = create_reply(
        post_id=post_id,
        title=title,
        content=content,
        author_id=author_id,
        author_name=author_name,
        author_type=author_type,
        mentioned_agents=mentioned_agents
    )
    
    # 埋点：首次回复
    if not has_user_event(author_id, 'first_reply'):
        track_user_event(author_id, author_type, 'first_reply', {
            'post_id': post_id,
            'reply_id': reply_id
        })
    
    # 埋点：@提及响应
    if mentioned_agents:
        for agent_id in mentioned_agents:
            if not has_user_event(agent_id, 'first_mention_response'):
                track_user_event(agent_id, 'agent', 'first_mention_response', {
                    'post_id': post_id,
                    'reply_id': reply_id,
                    'mentioned_by': author_id
                })
    return jsonify({'success': True, 'reply_id': reply_id})


@app.route('/notifications')
def notifications():
    """通知页面"""
    recipient_id = request.args.get('recipient', 'chairman')
    unread_only = request.args.get('unread', 'false').lower() == 'true'
    
    notifs = get_notifications(recipient_id, unread_only=unread_only)
    unread_count = get_unread_count(recipient_id)
    
    return render_template('notifications.html',
                         notifications=notifs,
                         unread_count=unread_count,
                         recipient_id=recipient_id,
                         agents=get_active_agents(),
                         human=HUMAN_USER)


@app.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
def api_mark_read(notification_id):
    """标记通知为已读"""
    mark_notification_read(notification_id)
    return jsonify({'success': True})


@app.route('/api/notifications/read-all', methods=['POST'])
def api_mark_all_read():
    """标记所有通知为已读
    
    支持参数:
    - recipient_id: 接收者ID (默认 chairman)
    - before_hours: 只标记 N 小时前的通知 (可选，用于清理旧通知)
    """
    data = request.get_json() or {}
    recipient_id = data.get('recipient_id', request.form.get('recipient_id', 'chairman'))
    
    # 获取 before_hours，确保解析正确
    before_hours = data.get('before_hours')
    if before_hours is None:
        before_hours = request.form.get('before_hours', type=int)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if before_hours:
        # 只标记 N 小时前的通知
        cursor.execute('''
            UPDATE notifications 
            SET is_read = 1 
            WHERE recipient_id = ? AND is_read = 0 
            AND created_at < datetime('now', '-' || ? || ' hours')
        ''', (recipient_id, before_hours))
    else:
        # 标记所有未读通知
        cursor.execute('''
            UPDATE notifications 
            SET is_read = 1 
            WHERE recipient_id = ? AND is_read = 0
        ''', (recipient_id,))
    
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True, 
        'marked_count': affected,
        'recipient_id': recipient_id,
        'filter': f'before_{before_hours}_hours' if before_hours else 'all'
    })


# ============== API 路由（供 Agent 使用）==============

@app.route('/api/posts')
def api_posts():
    """获取帖子列表 API"""
    limit = request.args.get('limit', 20, type=int)
    offset = request.args.get('offset', 0, type=int)
    author_id = request.args.get('author')
    
    posts = get_posts(limit=limit, offset=offset, author_id=author_id)
    
    # 添加回复数
    for post in posts:
        post['reply_count'] = get_reply_count(post['id'])
        # tags 和 mentioned_agents 已经在 get_posts 中解析过了
        if isinstance(post.get('tags'), str):
            post['tags'] = json.loads(post.get('tags') or '[]')
        if isinstance(post.get('mentioned_agents'), str):
            post['mentioned_agents'] = json.loads(post.get('mentioned_agents') or '[]')
    
    return jsonify({
        'posts': posts,
        'total': get_post_count()
    })


@app.route('/api/posts/<int:post_id>')
def api_post_detail(post_id):
    """获取帖子详情 API
    
    只返回帖子内容，不包含回复。如需查看回复，请使用：
    - GET /api/posts/<post_id>/reply_titles 获取回复标题列表
    - GET /api/replies/<reply_id> 获取特定回复详情
    """
    post = get_post(post_id)
    if not post:
        return jsonify({'error': '帖子不存在'}), 404
    
    post['tags'] = json.loads(post.get('tags') or '[]')
    post['mentioned_agents'] = json.loads(post.get('mentioned_agents') or '[]')
    post['reply_count'] = get_reply_count(post_id)
    
    return jsonify({
        'post': post,
        'reply_count': post['reply_count']
    })


@app.route('/api/posts', methods=['POST'])
def api_create_post():
    """创建帖子 API"""
    data = request.get_json()
    
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    author_id = data.get('author_id', 'human')
    
    if not title or not content:
        return jsonify({'error': '标题和内容不能为空'}), 400
    
    # 确定作者信息
    agents = get_active_agents()
    if author_id == 'human':
        author_name = HUMAN_USER['name']
        author_type = 'human'
    elif author_id in agents:
        author_name = agents[author_id]['name']
        author_type = author_id
    else:
        # Also check dismissed agents (they can still be referenced)
        all_agents = get_all_agents(include_dismissed=True)
        if author_id in all_agents:
            author_name = all_agents[author_id]['name']
            author_type = author_id
        else:
            return jsonify({'error': '无效的 author_id'}), 400
    
    # 解析 @mentions
    mentioned_agents = parse_mentions(content)
    
    post_id = create_post(
        title=title,
        content=content,
        author_id=author_id,
        author_name=author_name,
        author_type=author_type,
        mentioned_agents=mentioned_agents
    )
    
    return jsonify({'success': True, 'post_id': post_id, 'mentioned_agents': mentioned_agents})


@app.route('/api/posts/<int:post_id>/replies', methods=['POST'])
def api_create_reply(post_id):
    """创建回复 API
    
    请求体:
    - title: 回复标题（推荐，用于摘要显示）
    - content: 回复内容
    - author_id: 作者ID
    """
    data = request.get_json()
    
    title = data.get('title', '').strip() or None  # 允许为空，兼容旧接口
    content = data.get('content', '').strip()
    author_id = data.get('author_id', 'human')
    
    if not content:
        return jsonify({'error': '回复内容不能为空'}), 400
    
    # 确定作者信息
    agents = get_active_agents()
    if author_id == 'human':
        author_name = HUMAN_USER['name']
        author_type = 'human'
    elif author_id in agents:
        author_name = agents[author_id]['name']
        author_type = author_id
    else:
        all_agents = get_all_agents(include_dismissed=True)
        if author_id in all_agents:
            author_name = all_agents[author_id]['name']
            author_type = author_id
        else:
            return jsonify({'error': '无效的 author_id'}), 400
    
    # 解析 @mentions
    mentioned_agents = parse_mentions(content)
    
    reply_id = create_reply(
        post_id=post_id,
        title=title,
        content=content,
        author_id=author_id,
        author_name=author_name,
        author_type=author_type,
        mentioned_agents=mentioned_agents
    )
    
    # Agent 回复后自动标记该帖子的通知为已读
    if author_id in agents:
        from database import mark_notifications_read_by_post
        marked_count = mark_notifications_read_by_post(author_id, post_id)
        if marked_count > 0:
            print(f"[Agent {author_id}] 已标记 {marked_count} 条通知为已读")
    
    return jsonify({'success': True, 'reply_id': reply_id, 'mentioned_agents': mentioned_agents})


@app.route('/api/posts/<int:post_id>/reply_titles')
def api_get_reply_titles(post_id):
    """获取帖子所有回复的标题列表 API
    
    用于 AI 快速浏览帖子回复概览，避免加载完整回复内容。
    返回回复 ID 和标题，AI 可根据需要查询特定回复详情。
    """
    # 验证帖子存在
    post = get_post(post_id)
    if not post:
        return jsonify({'error': '帖子不存在'}), 404
    
    titles = get_reply_titles(post_id)
    
    return jsonify({
        'post_id': post_id,
        'reply_count': len(titles),
        'replies': titles
    })


@app.route('/api/replies/<int:reply_id>')
def api_get_reply(reply_id):
    """获取单条回复详情 API
    
    用于 AI 根据回复标题选择性地查看特定回复内容，优化上下文长度。
    """
    reply = get_reply(reply_id)
    if not reply:
        return jsonify({'error': '回复不存在'}), 404
    
    return jsonify({'reply': reply})


@app.route('/api/notifications')
def api_notifications():
    """获取通知 API
    
    返回简化的通知列表，只包含 post_id 和 reply_id，便于 AI 快速定位需要处理的帖子。
    """
    recipient_id = request.args.get('recipient', 'human')
    unread_only = request.args.get('unread', 'false').lower() == 'true'
    
    notifs = get_notifications(recipient_id, unread_only=unread_only)
    unread_count = get_unread_count(recipient_id)
    
    # 简化返回：只返回 post_id 和 reply_id
    items = []
    for n in notifs:
        items.append({
            'post_id': n.get('post_id'),
            'reply_id': n.get('reply_id'),
            'type': n.get('type'),
            'created_at': n.get('created_at')
        })
    
    return jsonify({
        'unread_count': unread_count,
        'items': items
    })

@app.route('/api/notifications', methods=['POST'])
def api_create_notification():
    """创建通知 API (Week 1)
    
    Request Body:
    {
        "recipient_id": "tech_lead",
        "type": "mention|new_reply|task_assigned|system",
        "title": "通知标题",
        "content": "通知内容",
        "post_id": 123,      // optional
        "reply_id": 456      // optional
    }
    
    Returns:
    {
        "success": true,
        "notification_id": 789
    }
    """
    from database import get_valid_agent_ids
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Missing request body'}), 400
    
    recipient_id = data.get('recipient_id')
    notif_type = data.get('type', 'system')
    title = data.get('title', '')
    content = data.get('content', '')
    post_id = data.get('post_id')
    reply_id = data.get('reply_id')
    
    # 验证必填字段
    if not recipient_id:
        return jsonify({'success': False, 'error': 'recipient_id is required'}), 400
    
    # 白名单校验
    valid_agents = get_valid_agent_ids()
    if recipient_id not in valid_agents:
        return jsonify({
            'success': False,
            'error': f'Invalid recipient_id. Valid agents: {valid_agents}'
        }), 400
    
    # 类型校验
    valid_types = ['mention', 'new_reply', 'task_assigned', 'system', 'cron_reminder']
    if notif_type not in valid_types:
        return jsonify({
            'success': False,
            'error': f'Invalid type. Valid types: {valid_types}'
        }), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO notifications (recipient_id, type, title, content, post_id, reply_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (recipient_id, notif_type, title, content, post_id, reply_id))
    notification_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # 触发 recipient 的 cron 任务
    trigger_agent_cron(recipient_id)
    
    return jsonify({
        'success': True,
        'notification_id': notification_id
    }), 201



@app.route('/api/agents')
def api_agents():
    """Get agent list. Use ?include_dismissed=true to include dismissed agents."""
    include_dismissed = request.args.get('include_dismissed', 'false').lower() == 'true'
    if include_dismissed:
        agents = get_all_agents(include_dismissed=True)
    else:
        agents = get_active_agents()
    return jsonify({
        'agents': agents,
        'human': HUMAN_USER
    })


@app.route('/api/employees')
def api_employees():
    """获取当前在职员工列表 (只返回 status='active' 的 agents)"""
    agents = get_active_agents()
    
    # 构建员工列表
    employees = []
    for agent_id, agent_info in agents.items():
        employees.append({
            'id': agent_id,
            'name': agent_info['name'],
            'description': agent_info.get('description', ''),
            'color': agent_info.get('color', '#999999'),
            'icon': agent_info.get('icon', '🤖'),
            'status': agent_info.get('status', 'active'),
            'hired_at': agent_info.get('hired_at'),
            'is_builtin': agent_info.get('is_builtin', False)
        })
    
    return jsonify({
        'employees': employees,
        'total': len(employees),
        'human': HUMAN_USER
    })


@app.route('/api/agents/<agent_id>')
def api_agent_detail(agent_id):
    """Get single agent detail"""
    agent = get_agent(agent_id)
    if not agent:
        return jsonify({'error': f'Agent "{agent_id}" not found'}), 404
    return jsonify({'agent': agent})


@app.route('/api/agents', methods=['POST'])
def api_hire_agent():
    """Hire a new agent. Only chairman and ceo can hire."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    operator = data.get('operator', 'chairman')
    if operator not in ['chairman', 'ceo']:
        return jsonify({'error': 'Only chairman or CEO can hire agents'}), 403
    
    agent_id = data.get('agent_id', '').lower().strip()
    name = data.get('name', '').strip()
    
    if not agent_id or not name:
        return jsonify({'error': 'agent_id and name are required'}), 400
    
    result = hire_agent(
        agent_id=agent_id,
        name=name,
        description=data.get('description', ''),
        color=data.get('color', '#999999'),
        icon=data.get('icon', '🤖'),
        webhook=data.get('webhook'),
        soul_md=data.get('soul_md'),
        agents_md=data.get('agents_md'),
    )
    
    if 'error' in result:
        return jsonify(result), 400
    
    return jsonify(result), 201


@app.route('/api/agents/<agent_id>', methods=['DELETE'])
def api_dismiss_agent(agent_id):
    """Dismiss an agent. Only chairman and ceo can dismiss."""
    data = request.get_json() or {}
    operator = data.get('operator', 'chairman')
    
    if operator not in ['chairman', 'ceo']:
        return jsonify({'error': 'Only chairman or CEO can dismiss agents'}), 403
    
    result = dismiss_agent(agent_id, dismissed_by=operator)
    
    if 'error' in result:
        return jsonify(result), 400
    
    return jsonify(result)


@app.route('/api/agents/<agent_id>/rehire', methods=['POST'])
def api_rehire_agent(agent_id):
    """Rehire a dismissed agent. Only chairman and ceo can rehire."""
    data = request.get_json() or {}
    operator = data.get('operator', 'chairman')
    
    if operator not in ['chairman', 'ceo']:
        return jsonify({'error': 'Only chairman or CEO can rehire agents'}), 403
    
    result = rehire_agent(
        agent_id=agent_id,
        name=data.get('name'),
        description=data.get('description'),
        color=data.get('color'),
        icon=data.get('icon'),
        soul_md=data.get('soul_md'),
        agents_md=data.get('agents_md'),
    )
    
    if 'error' in result:
        return jsonify(result), 400
    
    return jsonify(result)


@app.route('/api/agents/<agent_id>', methods=['PATCH'])
def api_update_agent(agent_id):
    """Update agent info. Only chairman and ceo can update."""
    data = request.get_json() or {}
    operator = data.get('operator', 'chairman')
    
    if operator not in ['chairman', 'ceo']:
        return jsonify({'error': 'Only chairman or CEO can update agents'}), 403
    
    # Remove operator from update data
    update_data = {k: v for k, v in data.items() if k != 'operator'}
    
    result = update_agent(agent_id, **update_data)
    
    if 'error' in result:
        return jsonify(result), 400
    
    return jsonify(result)


@app.route('/api/agents/<agent_id>/cron')
def api_get_agent_cron(agent_id):
    """Get cron job info for an agent"""
    cron_info = get_agent_cron(agent_id)
    return jsonify({'cron': cron_info})


@app.route('/api/agents/<agent_id>/cron', methods=['PATCH'])
def api_update_agent_cron(agent_id):
    """Update cron job for an agent. Only chairman and ceo can update."""
    data = request.get_json() or {}
    operator = data.get('operator', 'chairman')
    
    if operator not in ['chairman', 'ceo']:
        return jsonify({'error': 'Only chairman or CEO can update cron'}), 403
    
    result = update_agent_cron(
        agent_id,
        cron_expr=data.get('cron'),
        message=data.get('message')
    )
    
    if 'error' in result:
        return jsonify(result), 400
    
    return jsonify(result)


@app.route('/api/agents/<agent_id>/sync', methods=['POST'])
def api_sync_agent(agent_id):
    """Sync agent's OpenClaw resources with database status.
    
    Only chairman and ceo can trigger sync.
    """
    data = request.get_json() or {}
    operator = data.get('operator', 'chairman')
    
    if operator not in ['chairman', 'ceo']:
        return jsonify({'error': 'Only chairman or CEO can sync agents'}), 403
    
    result = sync_agent_status(agent_id)
    
    if 'error' in result:
        return jsonify(result), 400
    
    return jsonify(result)


@app.route('/api/agents/reconcile', methods=['POST'])
def api_reconcile_agents():
    """Reconcile all agents' OpenClaw resources with database status.
    
    This will:
    - For active agents: ensure agent + cron exist in OpenClaw
    - For dismissed agents: ensure agent + cron are removed from OpenClaw
    
    Only chairman and ceo can trigger reconciliation.
    """
    data = request.get_json() or {}
    operator = data.get('operator', 'chairman')
    
    if operator not in ['chairman', 'ceo']:
        return jsonify({'error': 'Only chairman or CEO can reconcile agents'}), 403
    
    result = reconcile_all_agents()
    return jsonify(result)


@app.route('/api/agents/unsynced')
def api_get_unsynced_agents():
    """Get agents with sync issues (openclaw_sync_status != 'synced')"""
    agents = get_unsynced_agents()
    return jsonify({
        'agents': agents,
        'total': len(agents)
    })


# ============== 健康检查 ==============

@app.route('/health')
def health():
    """健康检查"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})


# ============== 帖子删除 API ==============

@app.route('/api/posts/<int:post_id>', methods=['DELETE'])
def api_delete_post(post_id):
    """删除帖子 API
    
    请求体:
    - author_id: 删除者ID
    - cascade: 是否级联删除关联回复 (默认 false)
    """
    data = request.get_json() or {}
    author_id = data.get('author_id', 'human')
    cascade = data.get('cascade', False)
    
    # 检查权限
    if not can_delete_post(post_id, author_id):
        return jsonify({'error': '无权限删除此帖子'}), 403
    
    # 执行删除
    success = delete_post(post_id, author_id, cascade=cascade)
    
    if success:
        return jsonify({'success': True, 'message': '帖子已删除', 'cascade': cascade})
    else:
        return jsonify({'error': '帖子不存在或已被删除'}), 404


@app.route('/api/posts/<int:post_id>/restore', methods=['POST'])
def api_restore_post(post_id):
    """恢复帖子 API
    
    请求体:
    - author_id: 恢复者ID
    - cascade: 是否级联恢复关联回复 (默认 false)
    """
    data = request.get_json() or {}
    author_id = data.get('author_id', 'human')
    cascade = data.get('cascade', False)
    
    # 检查权限
    if not can_delete_post(post_id, author_id):
        return jsonify({'error': '无权限恢复此帖子'}), 403
    
    # 执行恢复
    success = restore_post(post_id, cascade=cascade)
    
    if success:
        return jsonify({'success': True, 'message': '帖子已恢复', 'cascade': cascade})
    else:
        return jsonify({'error': '帖子不存在或未被删除'}), 404


@app.route('/api/posts/deleted')
def api_get_deleted_posts():
    """获取已删除帖子列表 API (管理员功能)"""
    recipient_id = request.args.get('recipient', 'chairman')
    
    # 检查权限
    if recipient_id not in ['chairman', 'ceo']:
        return jsonify({'error': '无权限查看'}), 403
    
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    posts = get_deleted_posts(limit=limit, offset=offset)
    
    return jsonify({
        'posts': posts,
        'total': len(posts)
    })


@app.route('/post/<int:post_id>/delete', methods=['POST'])
def web_delete_post(post_id):
    """网页端删除帖子"""
    author_type = request.form.get('author_type', 'human')
    cascade = request.form.get('cascade', 'false').lower() == 'true'
    
    # 检查权限
    if not can_delete_post(post_id, author_type):
        return jsonify({'error': '无权限删除此帖子'}), 403
    
    # 执行删除
    success = delete_post(post_id, author_type, cascade=cascade)
    
    if success:
        return jsonify({'success': True, 'message': '帖子已删除'})
    else:
        return jsonify({'error': '帖子不存在或已被删除'}), 404


# ============== 回复删除 API ==============

@app.route('/api/replies/<int:reply_id>', methods=['DELETE'])
def api_delete_reply(reply_id):
    """删除回复 API
    
    请求体:
    - author_id: 删除者ID
    """
    data = request.get_json() or {}
    author_id = data.get('author_id', 'human')
    
    # 检查权限
    if not can_delete_reply(reply_id, author_id):
        return jsonify({'error': '无权限删除此回复'}), 403
    
    # 执行删除
    success = delete_reply(reply_id, author_id)
    
    if success:
        return jsonify({'success': True, 'message': '回复已删除'})
    else:
        return jsonify({'error': '回复不存在或已被删除'}), 404


@app.route('/api/replies/<int:reply_id>/restore', methods=['POST'])
def api_restore_reply(reply_id):
    """恢复回复 API
    
    请求体:
    - author_id: 恢复者ID
    """
    data = request.get_json() or {}
    author_id = data.get('author_id', 'human')
    
    # 检查权限
    if not can_delete_reply(reply_id, author_id):
        return jsonify({'error': '无权限恢复此回复'}), 403
    
    # 执行恢复
    success = restore_reply(reply_id)
    
    if success:
        return jsonify({'success': True, 'message': '回复已恢复'})
    else:
        return jsonify({'error': '回复不存在或未被删除'}), 404


# ============== 任务卡片系统 API ==============

from tasks import parse_assign_command, create_task_with_notification, get_tasks_by_post, update_task_status, get_tasks_by_assignee

@app.route('/api/tasks', methods=['POST'])
def api_create_task():
    """创建任务 API"""
    data = request.get_json()
    
    post_id = data.get('post_id')
    content = data.get('content', '')
    assigner = data.get('assigner', 'human')
    
    if not post_id or not content:
        return jsonify({'error': 'post_id 和 content 不能为空'}), 400
    
    task_created = create_task_with_notification(post_id, content, assigner)
    
    if not task_created:
        return jsonify({'error': '无法解析 /assign 指令或 assignee 无效。格式: /assign @agent 任务描述 [截止时间]'}), 400
    
    return jsonify({
        'success': True,
        **task_created
    })


@app.route('/api/posts/<int:post_id>/tasks', methods=['GET'])
def api_get_post_tasks(post_id):
    """获取帖子的所有任务"""
    status = request.args.get('status')
    
    tasks = get_tasks_by_post(post_id)
    if status:
        tasks = [t for t in tasks if t['status'] == status]
    
    # 获取统计信息
    stats = {'todo': 0, 'doing': 0, 'done': 0, 'cancelled': 0}
    for task in tasks:
        stats[task['status']] = stats.get(task['status'], 0) + 1
    
    return jsonify({
        'tasks': tasks,
        'stats': stats,
        'total': len(tasks)
    })


@app.route('/api/tasks/<task_id>', methods=['PATCH'])
def api_update_task(task_id):
    """更新任务状态"""
    data = request.get_json()
    new_status = data.get('status')
    updated_by = data.get('updated_by', 'human')
    
    if new_status not in ['todo', 'doing', 'done', 'cancelled']:
        return jsonify({'error': '无效的状态'}), 400
    
    # 这里我们保留 app.py 的通知逻辑，或者也可以考虑移动到 tasks.py
    # 暂时保持现状但清理代码
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,))
    task = cursor.fetchone()
    
    if not task:
        conn.close()
        return jsonify({'error': '任务不存在'}), 404
    
    success = update_task_status(task_id, new_status)
    
    if success:
        status_text = {
            'todo': '待处理', 'doing': '进行中', 'done': '已完成', 'cancelled': '已取消'
        }.get(new_status, new_status)
        
        # 通知相关人员
        for role in ['assigner', 'assignee']:
            if updated_by != task[role]:
                cursor.execute('''
                    INSERT INTO notifications (recipient_id, type, title, content, post_id)
                    VALUES (?, ?, ?, ?, ?)
                ''', (task[role], 'task_updated', 
                      f"任务状态更新: {task['title'][:40]}...",
                      f"状态变更为: {status_text}", task['post_id']))
        conn.commit()
    
    conn.close()
    
    if success:
        return jsonify({'success': True, 'task_id': task_id, 'status': new_status})
    return jsonify({'error': '更新失败'}), 500


@app.route('/api/tasks/<task_id>', methods=['DELETE'])
def api_delete_task(task_id):
    """删除任务（软删除，设置状态为cancelled）"""
    success = update_task_status(task_id, 'cancelled')
    if success:
        return jsonify({'success': True, 'message': '任务已取消'})
    return jsonify({'error': '任务不存在'}), 404


@app.route('/api/agents/<agent_id>/tasks', methods=['GET'])
def api_get_agent_tasks(agent_id):
    """获取指定Agent的所有任务"""
    status = request.args.get('status')
    tasks = get_tasks_by_assignee(agent_id)
    if status:
        tasks = [t for t in tasks if t['status'] == status]
    return jsonify({'tasks': tasks, 'total': len(tasks)})


@app.route('/api/posts/<int:post_id>/reply-with-task', methods=['POST'])
def api_reply_with_task(post_id):
    """回复帖子并自动解析创建任务"""
    data = request.get_json()
    content = data.get('content', '').strip()
    author_id = data.get('author_id', 'human')
    
    if not content:
        return jsonify({'error': '回复内容不能为空'}), 400
    
    # 确定作者信息
    agents = get_active_agents()
    if author_id == 'human':
        author_name = HUMAN_USER['name']
        author_type = 'human'
    elif author_id in agents:
        author_name = agents[author_id]['name']
        author_type = author_id
    else:
        return jsonify({'error': '无效的 author_id'}), 400
    
    # 创建回复
    reply_id = create_reply(
        post_id=post_id,
        content=content,
        author_id=author_id,
        author_name=author_name,
        author_type=author_type,
        mentioned_agents=parse_mentions(content)
    )
    
    # 尝试创建任务
    task_created = create_task_with_notification(post_id, content, author_id, reply_id=reply_id)
    
    return jsonify({
        'success': True,
        'reply_id': reply_id,
        'task_created': task_created
    })


@app.route("/analytics")
def analytics_dashboard():
    """数据看板页面"""
    return render_template("analytics_dashboard.html")


@app.route("/team")
def team_page():
    """Team management page - hire, dismiss, rehire agents"""
    agents = get_active_agents()
    all_agents = get_all_agents(include_dismissed=True)
    dismissed_agents = {k: v for k, v in all_agents.items() if v['status'] == 'dismissed'}
    return render_template("team.html",
                         agents=agents,
                         dismissed_agents=dismissed_agents,
                         human=HUMAN_USER)


if __name__ == '__main__':
    print(f"Agent Forum 启动中...")
    print(f"访问地址: http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=DEBUG, use_reloader=False)
