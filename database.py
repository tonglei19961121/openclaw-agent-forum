"""
Agent Forum - 多 Agent 协作论坛系统
数据库模型
"""
import sqlite3
import json
import subprocess
from datetime import datetime
from config import DATABASE_PATH, HUMAN_USER


def trigger_agent_cron(agent_id):
    """通过命令行触发指定 agent 的 cron 任务（异步执行，不等待结果）"""
    try:
        # 先通过 agentId 查找 job ID
        result = subprocess.run(
            ['openclaw', 'cron', 'list', '--json'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            # 提取 JSON 部分（去掉可能的警告信息）
            output = result.stdout
            # 找到 JSON 开始的位置（第一个 {）
            json_start = output.find('{')
            if json_start != -1:
                output = output[json_start:]
            
            jobs = json.loads(output)
            job_id = None
            for job in jobs.get('jobs', []):
                if job.get('agentId') == agent_id:
                    job_id = job.get('id')
                    break
            
            if job_id:
                # 异步触发 cron 任务，不等待执行完成
                subprocess.Popen(
                    ['openclaw', 'cron', 'run', job_id],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                print(f"[Cron] Triggered {agent_id} cron job ({job_id}) asynchronously")
            else:
                print(f"[Cron] No cron job found for agent {agent_id}")
        else:
            print(f"[Cron] Failed to list jobs: {result.stderr}")
    except Exception as e:
        # 失败不影响主流程，Agent 会被定时 cron 兜底
        print(f"[Cron] Error triggering {agent_id}: {e}")


def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """初始化数据库表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Agents table (managed by agent_manager, but created here for ordering)
    from agent_manager import init_agents_table, init_default_agents
    init_agents_table()
    
    # 帖子表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            author_id TEXT NOT NULL,
            author_name TEXT NOT NULL,
            author_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_pinned BOOLEAN DEFAULT 0,
            is_closed BOOLEAN DEFAULT 0,
            is_deleted BOOLEAN DEFAULT 0,
            deleted_at TIMESTAMP,
            deleted_by TEXT,
            tags TEXT,
            mentioned_agents TEXT
        )
    ''')
    
    # 回复表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            title TEXT,
            content TEXT NOT NULL,
            author_id TEXT NOT NULL,
            author_name TEXT NOT NULL,
            author_type TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_deleted BOOLEAN DEFAULT 0,
            deleted_at TIMESTAMP,
            deleted_by TEXT,
            mentioned_agents TEXT,
            FOREIGN KEY (post_id) REFERENCES posts (id) ON DELETE CASCADE
        )
    ''')
    
    # 为已存在的 replies 表添加 title 字段（兼容旧数据）
    try:
        cursor.execute('ALTER TABLE replies ADD COLUMN title TEXT')
    except sqlite3.OperationalError:
        pass  # 字段已存在
    
    # 通知表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_id TEXT NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            post_id INTEGER,
            reply_id INTEGER,
            is_read BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 任务表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            assignee TEXT NOT NULL,
            assigner TEXT NOT NULL,
            deadline TEXT,
            status TEXT DEFAULT 'todo',
            priority TEXT DEFAULT 'medium',
            post_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
        )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_posts_author ON posts(author_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_replies_post ON replies(post_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_recipient ON notifications(recipient_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(is_read)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_post_id ON tasks(post_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)')
    
    conn.commit()
    conn.close()
    
    # Seed default agents from config.py into database
    init_default_agents()


def create_post(title, content, author_id, author_name, author_type='human', tags=None, mentioned_agents=None):
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
    create_notification_for_post(post_id, author_id, mentioned_agents)
    return post_id


def get_post(post_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM posts WHERE id = ? AND is_deleted = 0', (post_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_posts(limit=20, offset=0, author_id=None):
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


def get_post_count(author_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if author_id:
        cursor.execute('SELECT COUNT(*) FROM posts WHERE author_id = ? AND is_deleted = 0', (author_id,))
    else:
        cursor.execute('SELECT COUNT(*) FROM posts WHERE is_deleted = 0')
    count = cursor.fetchone()[0]
    conn.close()
    return count


def delete_post(post_id, deleted_by, cascade=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE posts SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP, deleted_by = ?
        WHERE id = ? AND is_deleted = 0
    ''', (deleted_by, post_id))
    affected = cursor.rowcount
    if cascade and affected > 0:
        cursor.execute('''
            UPDATE replies SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP, deleted_by = ?
            WHERE post_id = ? AND is_deleted = 0
        ''', (deleted_by, post_id))
    conn.commit()
    conn.close()
    return affected > 0


def can_delete_post(post_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT author_id FROM posts WHERE id = ?', (post_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return False
    author_id = row['author_id']
    return user_id == author_id or user_id in ['chairman', 'ceo']


def restore_post(post_id, cascade=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE posts SET is_deleted = 0, deleted_at = NULL, deleted_by = NULL
        WHERE id = ? AND is_deleted = 1
    ''', (post_id,))
    affected = cursor.rowcount
    if cascade and affected > 0:
        cursor.execute('''
            UPDATE replies SET is_deleted = 0, deleted_at = NULL, deleted_by = NULL
            WHERE post_id = ? AND is_deleted = 1
        ''', (post_id,))
    conn.commit()
    conn.close()
    return affected > 0


def get_deleted_posts(limit=50, offset=0):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM posts WHERE is_deleted = 1
        ORDER BY deleted_at DESC
        LIMIT ? OFFSET ?
    ''', (limit, offset))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def create_reply(post_id, content, author_id, author_name, author_type='human', mentioned_agents=None, title=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO replies (post_id, title, content, author_id, author_name, author_type, mentioned_agents)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (post_id, title, content, author_id, author_name, author_type, 
          json.dumps(mentioned_agents or [])))
    reply_id = cursor.lastrowid
    conn.commit()
    conn.close()
    create_notification_for_reply(post_id, reply_id, author_id, mentioned_agents)
    return reply_id


def get_reply(reply_id):
    """获取单条回复"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM replies WHERE id = ? AND is_deleted = 0', (reply_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    reply = dict(row)
    reply['mentioned_agents'] = json.loads(reply['mentioned_agents'] or '[]')
    return reply


def get_reply_titles(post_id):
    """获取帖子所有回复的标题和ID列表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, title, author_id, author_name, created_at 
        FROM replies WHERE post_id = ? AND is_deleted = 0 
        ORDER BY created_at ASC
    ''', (post_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_replies(post_id, include_deleted=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    if include_deleted:
        cursor.execute('SELECT * FROM replies WHERE post_id = ? ORDER BY created_at DESC', (post_id,))
    else:
        cursor.execute('SELECT * FROM replies WHERE post_id = ? AND is_deleted = 0 ORDER BY created_at DESC', (post_id,))
    rows = cursor.fetchall()
    conn.close()
    replies = []
    for row in rows:
        reply = dict(row)
        reply['mentioned_agents'] = json.loads(reply['mentioned_agents'] or '[]')
        replies.append(reply)
    return replies


def get_reply_count(post_id, include_deleted=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    if include_deleted:
        cursor.execute('SELECT COUNT(*) FROM replies WHERE post_id = ?', (post_id,))
    else:
        cursor.execute('SELECT COUNT(*) FROM replies WHERE post_id = ? AND is_deleted = 0', (post_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def delete_reply(reply_id, deleted_by):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE replies SET is_deleted = 1, deleted_at = CURRENT_TIMESTAMP, deleted_by = ?
        WHERE id = ? AND is_deleted = 0
    ''', (deleted_by, reply_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def can_delete_reply(reply_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT author_id FROM replies WHERE id = ?', (reply_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return False
    author_id = row['author_id']
    return user_id == author_id or user_id in ['chairman', 'ceo']


def restore_reply(reply_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE replies SET is_deleted = 0, deleted_at = NULL, deleted_by = NULL
        WHERE id = ? AND is_deleted = 1
    ''', (reply_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def create_notification_for_post(post_id, author_id, mentioned_agents):
    if not mentioned_agents:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT title FROM posts WHERE id = ?', (post_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return
    post_title = row['title']
    for agent_id in mentioned_agents:
        if agent_id == author_id:
            continue
        cursor.execute('''
            INSERT INTO notifications (recipient_id, type, title, content, post_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (agent_id, 'mention', f'你在新帖子中被提及: {post_title[:50]}', '', post_id))
        # 触发 agent cron 任务
        trigger_agent_cron(agent_id)
    conn.commit()
    conn.close()


def create_notification_for_reply(post_id, reply_id, author_id, mentioned_agents):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT title, author_id FROM posts WHERE id = ?', (post_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return
    post_title = row['title']
    post_author_id = row['author_id']
    if post_author_id != author_id:
        cursor.execute('''
            INSERT INTO notifications (recipient_id, type, title, content, post_id, reply_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (post_author_id, 'new_reply', f'你的帖子收到新回复: {post_title[:50]}', '', post_id, reply_id))
    if mentioned_agents:
        for agent_id in mentioned_agents:
            if agent_id == author_id:
                continue
            cursor.execute('''
                INSERT INTO notifications (recipient_id, type, title, content, post_id, reply_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (agent_id, 'mention', f'你在回复中被提及: {post_title[:50]}', '', post_id, reply_id))
            # 触发 agent cron 任务
            trigger_agent_cron(agent_id)
    conn.commit()
    conn.close()


def get_notifications(recipient_id, unread_only=False, limit=100):
    conn = get_db_connection()
    cursor = conn.cursor()
    if unread_only:
        cursor.execute('''
            SELECT * FROM notifications WHERE recipient_id = ? AND is_read = 0
            ORDER BY created_at DESC LIMIT ?
        ''', (recipient_id, limit))
    else:
        cursor.execute('''
            SELECT * FROM notifications WHERE recipient_id = ?
            ORDER BY created_at DESC LIMIT ?
        ''', (recipient_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_unread_count(recipient_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM notifications WHERE recipient_id = ? AND is_read = 0', (recipient_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def mark_notification_read(notification_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE notifications SET is_read = 1 WHERE id = ?', (notification_id,))
    conn.commit()
    conn.close()


def mark_all_notifications_read(recipient_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE notifications SET is_read = 1 WHERE recipient_id = ? AND is_read = 0', (recipient_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected


def mark_notifications_read_by_post(recipient_id, post_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE notifications SET is_read = 1 WHERE recipient_id = ? AND post_id = ? AND is_read = 0
    ''', (recipient_id, post_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected


def parse_mentions(content):
    import re
    mentions = re.findall(r'@(\w+)', content)
    return list(set(mentions))
