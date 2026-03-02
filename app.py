"""
Agent Forum - 多 Agent 协作论坛系统
主应用
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
import os
import sys
from datetime import datetime

from config import AGENTS, HUMAN_USER, HOST, PORT, DEBUG, SECRET_KEY
from database import (
    delete_post, can_delete_post, restore_post, get_deleted_posts,
    delete_reply, can_delete_reply, restore_reply,
    init_database, create_post, get_post, get_posts, get_post_count,
    create_reply, get_replies, get_reply_count,
    get_notifications, get_unread_count, mark_notification_read, mark_all_notifications_read,
    parse_mentions,
    get_db_connection
)

# 导入自然语言接口
try:
    from ai.natural_language import NaturalLanguageInterface
    nli = NaturalLanguageInterface(AGENTS)
except ImportError:
    nli = None

app = Flask(__name__)
app.secret_key = SECRET_KEY

# 添加 nl2br 过滤器
@app.template_filter('nl2br')
def nl2br_filter(text):
    """将换行符转换为 <br> 标签"""
    if text:
        return text.replace('\n', '\u003cbr\u003e')
    return text

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
    
    # 为每个帖子添加回复数
    for post in posts:
        post['reply_count'] = get_reply_count(post['id'])
    
    return render_template('index.html', 
                         posts=posts, 
                         page=page, 
                         total=total,
                         per_page=per_page,
                         agents=AGENTS,
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
    
    return render_template('post.html',
                         post=post,
                         replies=replies,
                         agents=AGENTS,
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
        if author_type == 'chairman':
            author_id = HUMAN_USER['id']
            author_name = HUMAN_USER['name']
        else:
            author_id = author_type  # agent_id
            author_name = AGENTS.get(author_type, {}).get('name', author_type)
        
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
    
    return render_template('new_post.html', agents=AGENTS, human=HUMAN_USER)


@app.route('/post/<int:post_id>/reply', methods=['POST'])
def reply_post(post_id):
    """回复帖子"""
    content = request.form.get('content', '').strip()
    author_type = request.form.get('author_type', 'human')
    
    if not content:
        return jsonify({'error': '回复内容不能为空'}), 400
    
    # 解析 @mentions
    mentioned_agents = parse_mentions(content)
    
    # 确定作者信息
    if author_type == 'chairman':
        author_id = HUMAN_USER['id']
        author_name = HUMAN_USER['name']
    else:
        author_id = author_type
        author_name = AGENTS.get(author_type, {}).get('name', author_type)
    
    reply_id = create_reply(
        post_id=post_id,
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
                         agents=AGENTS,
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
    before_hours = data.get('before_hours', request.form.get('before_hours', type=int))
    
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
    
    参数:
    - last_n: 只返回最近 N 条回复 (默认全部)
    - mention_only: 只返回 @ 指定 agent 的回复 (agent_id)
    """
    post = get_post(post_id)
    if not post:
        return jsonify({'error': '帖子不存在'}), 404
    
    post['tags'] = json.loads(post.get('tags') or '[]')
    post['mentioned_agents'] = json.loads(post.get('mentioned_agents') or '[]')
    post['reply_count'] = get_reply_count(post_id)
    
    # 获取参数
    last_n = request.args.get('last_n', type=int)
    mention_only = request.args.get('mention_only', type=str)
    
    replies = get_replies(post_id)
    
    # 过滤只包含 @ 指定 agent 的回复
    if mention_only:
        replies = [r for r in replies if mention_only in r.get('mentioned_agents', [])]
    
    # 只保留最近 N 条
    if last_n and last_n > 0:
        replies = replies[-last_n:]
    
    return jsonify({
        'post': post,
        'replies': replies,
        'total_replies': get_reply_count(post_id),
        'returned_replies': len(replies),
        'filters': {
            'last_n': last_n,
            'mention_only': mention_only
        }
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
    if author_id == 'human':
        author_name = HUMAN_USER['name']
        author_type = 'human'
    elif author_id in AGENTS:
        author_name = AGENTS[author_id]['name']
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
    """创建回复 API"""
    data = request.get_json()
    
    content = data.get('content', '').strip()
    author_id = data.get('author_id', 'human')
    
    if not content:
        return jsonify({'error': '回复内容不能为空'}), 400
    
    # 确定作者信息
    if author_id == 'human':
        author_name = HUMAN_USER['name']
        author_type = 'human'
    elif author_id in AGENTS:
        author_name = AGENTS[author_id]['name']
        author_type = author_id
    else:
        return jsonify({'error': '无效的 author_id'}), 400
    
    # 解析 @mentions
    mentioned_agents = parse_mentions(content)
    
    reply_id = create_reply(
        post_id=post_id,
        content=content,
        author_id=author_id,
        author_name=author_name,
        author_type=author_type,
        mentioned_agents=mentioned_agents
    )
    
    # Agent 回复后自动标记该帖子的通知为已读
    if author_id in AGENTS:
        from database import mark_notifications_read_by_post
        marked_count = mark_notifications_read_by_post(author_id, post_id)
        if marked_count > 0:
            print(f"[Agent {author_id}] 已标记 {marked_count} 条通知为已读")
    
    return jsonify({'success': True, 'reply_id': reply_id, 'mentioned_agents': mentioned_agents})


@app.route('/api/notifications')
def api_notifications():
    """获取通知 API"""
    recipient_id = request.args.get('recipient', 'human')
    unread_only = request.args.get('unread', 'false').lower() == 'true'
    
    notifs = get_notifications(recipient_id, unread_only=unread_only)
    unread_count = get_unread_count(recipient_id)
    
    return jsonify({
        'notifications': notifs,
        'unread_count': unread_count
    })


@app.route('/api/agents')
def api_agents():
    """获取 Agent 列表"""
    return jsonify({
        'agents': AGENTS,
        'human': HUMAN_USER
    })


# ============== 健康检查 ==============

@app.route('/health')
def health():
    """健康检查"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})


# ============== 自然语言接口 ==============

@app.route('/api/nli/parse', methods=['POST'])
def api_nli_parse():
    """自然语言解析 API
    
    请求体:
    {
        "text": "创建一个帖子：Q4 战略规划",
        "author_id": "chairman"
    }
    
    响应:
    {
        "action": "create_post",
        "params": {
            "title": "Q4 战略规划",
            "content": "Q4 战略规划",
            "author_id": "chairman",
            "mentioned_agents": []
        }
    }
    """
    if nli is None:
        return jsonify({'error': '自然语言接口未启用'}), 503
    
    data = request.get_json()
    text = data.get('text', '').strip()
    author_id = data.get('author_id', 'chairman')
    
    if not text:
        return jsonify({'error': 'text 不能为空'}), 400
    
    result = nli.parse(text, author_id)
    return jsonify(result)


@app.route('/api/nli/execute', methods=['POST'])
def api_nli_execute():
    """自然语言执行 API
    
    直接执行自然语言指令
    
    请求体:
    {
        "text": "创建一个帖子：Q4 战略规划 @ceo @cto",
        "author_id": "chairman"
    }
    """
    if nli is None:
        return jsonify({'error': '自然语言接口未启用'}), 503
    
    data = request.get_json()
    text = data.get('text', '').strip()
    author_id = data.get('author_id', 'chairman')
    
    if not text:
        return jsonify({'error': 'text 不能为空'}), 400
    
    # 数据库操作函数映射
    db_funcs = {
        'create_post': create_post,
        'create_reply': create_reply,
        'get_post': get_post,
        'get_posts': lambda **kwargs: get_posts(limit=kwargs.get('limit', 20)),
        'get_replies': get_replies,
        'get_notifications': get_notifications,
        'delete_post': lambda **kwargs: delete_post(kwargs['post_id'], kwargs['author_id']),
    }
    
    result = nli.execute(text, author_id, db_funcs)
    return jsonify(result)


@app.route('/api/nli/help', methods=['GET'])
def api_nli_help():
    """自然语言接口帮助"""
    return jsonify({
        'description': '自然语言接口支持以下指令',
        'examples': [
            {'text': '创建一个帖子：标题内容', 'action': 'create_post'},
            {'text': '回复帖子#123：回复内容', 'action': 'reply_post'},
            {'text': '查看通知', 'action': 'check_notifications'},
            {'text': '列出帖子', 'action': 'list_posts'},
            {'text': '删除帖子#123', 'action': 'delete_post'},
        ],
        'endpoints': {
            'parse': {'method': 'POST', 'path': '/api/nli/parse', 'description': '解析自然语言'},
            'execute': {'method': 'POST', 'path': '/api/nli/execute', 'description': '执行自然语言指令'},
        }
    })

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


if __name__ == '__main__':
    print(f"Agent Forum 启动中...")
    print(f"访问地址: http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=DEBUG, use_reloader=False)


@app.route("/analytics")
def analytics_dashboard():
    """数据看板页面"""
    return render_template("analytics_dashboard.html")
