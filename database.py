"""
Agent Forum - 多 Agent 协作论坛系统
数据库模型
"""
import sqlite3
import json
from datetime import datetime
from config import DATABASE_PATH, AGENTS, HUMAN_USER


def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """初始化数据库表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 帖子表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            author_id TEXT NOT NULL,
            author_name TEXT NOT NULL,
            author_type TEXT NOT NULL,  -- 'human', 'agent', 'system'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_pinned BOOLEAN DEFAULT 0,
            is_closed BOOLEAN DEFAULT 0,
            is_deleted BOOLEAN DEFAULT 0,  -- 软删除标记
            deleted_at TIMESTAMP,  -- 删除时间
            deleted_by TEXT,  -- 删除者ID
            tags TEXT,  -- JSON 数组
            mentioned_agents TEXT  -- JSON 数组，存储被 @ 的 agent IDs
        )
    ''')
    
    # 回复表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            author_id TEXT NOT NULL,
            author_name TEXT NOT NULL,
            author_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_deleted BOOLEAN DEFAULT 0,  -- 软删除标记
            deleted_at TIMESTAMP,  -- 删除时间
            deleted_by TEXT,  -- 删除者ID
            mentioned_agents TEXT,  -- JSON 数组
            FOREIGN KEY (post_id) REFERENCES posts (id) ON DELETE CASCADE
        )
    ''')
    
    # 通知表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_id TEXT NOT NULL,  -- agent_id 或 'human'
            type TEXT NOT NULL,  -- 'new_post', 'new_reply', 'mention'
            title TEXT NOT NULL,
            content TEXT,
            post_id INTEGER,
            reply_id INTEGER,
            is_read BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_posts_author ON posts(author_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_replies_post ON replies(post_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_recipient ON notifications(recipient_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(is_read)')
    
    conn.commit()
    conn.close()


# ============== Post 操作 ==============

def create_post(title, content, author_id, author_name, author_type='human', tags=None, mentioned_agents=None):
    """创建新帖子"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO posts (title, content, author_id, author_name, author_type, tags, mentioned_agents)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (title, content, author_id, author_name, author_type, 
          json.dumps(tags or []), json.dumps(mentioned_agents or [])))
    
    post_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # 创建通知
    create_notification_for_post(post_id, author_id, mentioned_agents)
    
    return post_id


def get_post(post_id):
    """获取单个帖子详情"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM posts WHERE id = ? AND is_deleted = 0', (post_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def get_posts(limit=20, offset=0, author_id=None):
    """获取帖子列表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if author_id:
        cursor.execute('''
            SELECT * FROM posts WHERE author_id = ? AND is_deleted = 0
            ORDER BY is_pinned DESC, created_at DESC
            LIMIT ? OFFSET ?
        ''', (author_id, limit, offset))
    else:
        cursor.execute('''
            SELECT * FROM posts WHERE is_deleted = 0
            ORDER BY is_pinned DESC, created_at DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))
    
    rows = cursor.fetchall()
    conn.close()
    
    posts = []
    for row in rows:
        post = dict(row)
        post['tags'] = json.loads(post['tags'] or '[]')
        post['mentioned_agents'] = json.loads(post['mentioned_agents'] or '[]')
        posts.append(post)
    
    return posts


def get_post_count():
    """获取帖子总数"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as count FROM posts WHERE is_deleted = 0')
    result = cursor.fetchone()
    conn.close()
    return result['count']


# ============== Reply 操作 ==============

def create_reply(post_id, content, author_id, author_name, author_type='human', mentioned_agents=None):
    """创建回复"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO replies (post_id, content, author_id, author_name, author_type, mentioned_agents)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (post_id, content, author_id, author_name, author_type, json.dumps(mentioned_agents or [])))
    
    reply_id = cursor.lastrowid
    
    # 更新帖子更新时间
    cursor.execute('''
        UPDATE posts SET updated_at = CURRENT_TIMESTAMP WHERE id = ?
    ''', (post_id,))
    
    conn.commit()
    conn.close()
    
    # 创建通知
    create_notification_for_reply(post_id, reply_id, author_id, mentioned_agents)
    
    return reply_id


def get_replies(post_id, include_deleted=False):
    """获取帖子的所有回复"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if include_deleted:
        cursor.execute('''
            SELECT * FROM replies WHERE post_id = ?
            ORDER BY created_at ASC
        ''', (post_id,))
    else:
        cursor.execute('''
            SELECT * FROM replies WHERE post_id = ? AND is_deleted = 0
            ORDER BY created_at ASC
        ''', (post_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    replies = []
    for row in rows:
        reply = dict(row)
        reply['mentioned_agents'] = json.loads(reply['mentioned_agents'] or '[]')
        replies.append(reply)
    
    return replies


def get_reply_count(post_id, include_deleted=False):
    """获取帖子的回复数"""
    conn = get_db_connection()
    cursor = conn.cursor()
    if include_deleted:
        cursor.execute('SELECT COUNT(*) as count FROM replies WHERE post_id = ?', (post_id,))
    else:
        cursor.execute('SELECT COUNT(*) as count FROM replies WHERE post_id = ? AND is_deleted = 0', (post_id,))
    result = cursor.fetchone()
    conn.close()
    return result['count']


# ============== Notification 操作 ==============

def create_notification(recipient_id, type_, title, content=None, post_id=None, reply_id=None):
    """创建通知"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO notifications (recipient_id, type, title, content, post_id, reply_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (recipient_id, type_, title, content, post_id, reply_id))
    
    notification_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return notification_id


def create_notification_for_post(post_id, author_id, mentioned_agents):
    """为新帖子创建通知"""
    post = get_post(post_id)
    if not post:
        return
    
    # 只通知被提及的 agents，不再给所有 agents 发 new_post 通知
    for agent_id in (mentioned_agents or []):
        if agent_id in AGENTS:
            create_notification(
                recipient_id=agent_id,
                type_='mention',
                title=f"你在新帖子中被提及: {post['title']}",
                content=post['content'][:200] + '...' if len(post['content']) > 200 else post['content'],
                post_id=post_id
            )


def create_notification_for_reply(post_id, reply_id, author_id, mentioned_agents):
    """为新回复创建通知"""
    post = get_post(post_id)
    if not post:
        return
    
    # 通知帖子作者
    if post['author_id'] != author_id:
        create_notification(
            recipient_id=post['author_id'],
            type_='new_reply',
            title=f"你的帖子有新回复: {post['title']}",
            post_id=post_id,
            reply_id=reply_id
        )
    
    # 通知被提及的 agents
    for agent_id in (mentioned_agents or []):
        if agent_id in AGENTS and agent_id != author_id:
            create_notification(
                recipient_id=agent_id,
                type_='mention',
                title=f"你在回复中被提及: {post['title']}",
                post_id=post_id,
                reply_id=reply_id
            )


def get_notifications(recipient_id, unread_only=False, limit=50):
    """获取通知列表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if unread_only:
        cursor.execute('''
            SELECT * FROM notifications 
            WHERE recipient_id = ? AND is_read = 0
            ORDER BY created_at DESC
            LIMIT ?
        ''', (recipient_id, limit))
    else:
        cursor.execute('''
            SELECT * FROM notifications 
            WHERE recipient_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (recipient_id, limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def get_unread_count(recipient_id):
    """获取未读通知数量"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) as count FROM notifications 
        WHERE recipient_id = ? AND is_read = 0
    ''', (recipient_id,))
    result = cursor.fetchone()
    conn.close()
    return result['count']


def mark_notification_read(notification_id):
    """标记通知为已读"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE notifications SET is_read = 1 WHERE id = ?
    ''', (notification_id,))
    conn.commit()
    conn.close()


def mark_notifications_read_by_post(recipient_id, post_id):
    """标记指定帖子的所有通知为已读"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE notifications 
        SET is_read = 1 
        WHERE recipient_id = ? AND post_id = ? AND is_read = 0
    ''', (recipient_id, post_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected


def mark_all_notifications_read(recipient_id):
    """标记所有通知为已读"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE notifications SET is_read = 1 WHERE recipient_id = ?
    ''', (recipient_id,))
    conn.commit()
    conn.close()


# ============== 工具函数 ==============

def parse_mentions(content):
    """解析内容中的 @mentions，返回 agent_id 列表"""
    import re
    mentions = []
    # 匹配 @agent_id 或 @agent_id 后跟中文/标点/空格/换行/结束
    pattern = r'@(\w+)(?=[\s\n\u4e00-\u9fa5.,!?;:]|$)'
    matches = re.findall(pattern, content)
    
    for match in matches:
        agent_id = match.lower()
        if agent_id in AGENTS:
            mentions.append(agent_id)
    
    return list(set(mentions))  # 去重


def get_all_participants(post_id):
    """获取帖子的所有参与者"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 获取帖子作者
    cursor.execute('SELECT author_id FROM posts WHERE id = ?', (post_id,))
    post_author = cursor.fetchone()
    
    # 获取所有回复作者
    cursor.execute('SELECT DISTINCT author_id FROM replies WHERE post_id = ?', (post_id,))
    reply_authors = cursor.fetchall()
    
    conn.close()
    
    participants = set()
    if post_author:
        participants.add(post_author['author_id'])
    for row in reply_authors:
        participants.add(row['author_id'])
    
    return list(participants)


# ============== 帖子删除操作 ==============

def delete_post(post_id, deleted_by, cascade=False):
    """软删除帖子
    
    Args:
        post_id: 帖子ID
        deleted_by: 删除者ID
        cascade: 是否级联删除关联回复
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE posts 
        SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP, deleted_by = ?
        WHERE id = ? AND is_deleted = 0
    ''', (deleted_by, post_id))
    
    affected = cursor.rowcount
    
    # 级联删除关联回复
    if cascade and affected > 0:
        cursor.execute('''
            UPDATE replies 
            SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP, deleted_by = ?
            WHERE post_id = ? AND is_deleted = 0
        ''', (deleted_by, post_id))
    
    conn.commit()
    conn.close()
    
    return affected > 0


def restore_post(post_id, cascade=False):
    """恢复已删除的帖子
    
    Args:
        post_id: 帖子ID
        cascade: 是否级联恢复关联回复
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE posts 
        SET is_deleted = 0, deleted_at = NULL, deleted_by = NULL
        WHERE id = ? AND is_deleted = 1
    ''', (post_id,))
    
    affected = cursor.rowcount
    
    # 级联恢复关联回复
    if cascade and affected > 0:
        cursor.execute('''
            UPDATE replies 
            SET is_deleted = 0, deleted_at = NULL, deleted_by = NULL
            WHERE post_id = ? AND is_deleted = 1
        ''', (post_id,))
    
    conn.commit()
    conn.close()
    
    return affected > 0


def can_delete_post(post_id, user_id):
    """检查用户是否有权限删除帖子"""
    # 管理员权限
    if user_id in ['chairman', 'ceo']:
        return True
    
    # 检查是否是作者本人
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT author_id FROM posts WHERE id = ?', (post_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result and result['author_id'] == user_id:
        return True
    
    return False


def get_post_with_deleted(post_id):
    """获取单个帖子详情（包括已删除的）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM posts WHERE id = ?', (post_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        post = dict(row)
        post['tags'] = json.loads(post.get('tags') or '[]')
        post['mentioned_agents'] = json.loads(post.get('mentioned_agents') or '[]')
        return post
    return None


def get_deleted_posts(limit=50, offset=0):
    """获取已删除的帖子列表（用于管理）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM posts WHERE is_deleted = 1
        ORDER BY deleted_at DESC
        LIMIT ? OFFSET ?
    ''', (limit, offset))
    
    rows = cursor.fetchall()
    conn.close()
    
    posts = []
    for row in rows:
        post = dict(row)
        post['tags'] = json.loads(post['tags'] or '[]')
        post['mentioned_agents'] = json.loads(post['mentioned_agents'] or '[]')
        posts.append(post)
    
    return posts


# ============== 回复删除操作 ==============

def delete_reply(reply_id, deleted_by):
    """软删除回复"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE replies 
        SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP, deleted_by = ?
        WHERE id = ? AND is_deleted = 0
    ''', (deleted_by, reply_id))
    
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    
    return affected > 0


def restore_reply(reply_id):
    """恢复已删除的回复"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE replies 
        SET is_deleted = 0, deleted_at = NULL, deleted_by = NULL
        WHERE id = ? AND is_deleted = 1
    ''', (reply_id,))
    
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    
    return affected > 0


def can_delete_reply(reply_id, user_id):
    """检查用户是否有权限删除回复"""
    # 管理员权限
    if user_id in ['chairman', 'ceo']:
        return True
    
    # 检查是否是作者本人
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT author_id FROM replies WHERE id = ?', (reply_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result and result['author_id'] == user_id:
        return True
    
    return False


def get_reply(reply_id):
    """获取单个回复详情（包括已删除的）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM replies WHERE id = ?', (reply_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        reply = dict(row)
        reply['mentioned_agents'] = json.loads(reply['mentioned_agents'] or '[]')
        return reply
    return None
