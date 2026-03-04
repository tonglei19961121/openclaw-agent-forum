"""
Agent Forum - 多 Agent 协作论坛系统
任务卡片系统模块
"""
import sqlite3
import uuid
import re
from datetime import datetime, timedelta
from config import DATABASE_PATH


def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_task(title, assignee, assigner, post_id, deadline=None):
    """创建新任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    task_id = str(uuid.uuid4())[:8]
    
    cursor.execute('''
        INSERT INTO tasks (task_id, title, assignee, assigner, deadline, post_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (task_id, title, assignee, assigner, deadline, post_id))
    
    conn.commit()
    conn.close()
    
    return task_id


def get_task(task_id):
    """获取单个任务详情"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def get_tasks_by_post(post_id):
    """获取帖子的所有任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM tasks WHERE post_id = ?
        ORDER BY 
            CASE status 
                WHEN 'todo' THEN 1 
                WHEN 'doing' THEN 2 
                WHEN 'done' THEN 3 
                WHEN 'cancelled' THEN 4 
            END,
            created_at ASC
    ''', (post_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def update_task_status(task_id, status):
    """更新任务状态"""
    if status not in ['todo', 'doing', 'done', 'cancelled']:
        return False
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE tasks 
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE task_id = ?
    ''', (status, task_id))
    
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    
    return affected > 0


def delete_task(task_id):
    """删除任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM tasks WHERE task_id = ?', (task_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    
    return affected > 0


def get_tasks_by_assignee(assignee):
    """获取指定负责人的所有任务"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM tasks WHERE assignee = ?
        ORDER BY 
            CASE status 
                WHEN 'todo' THEN 1 
                WHEN 'doing' THEN 2 
                WHEN 'done' THEN 3 
                WHEN 'cancelled' THEN 4 
            END,
            created_at DESC
    ''', (assignee,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def parse_assign_command(content):
    """解析 /assign 指令
    
    格式: /assign @agent 任务描述 [截止时间]
    
    Returns:
        dict: {'assignee': str, 'title': str, 'deadline': str or None} or None
    """
    # 匹配 /assign 指令
    pattern = r'/assign\s+@(\w+)\s+(.+?)(?:\s+(\d{4}-\d{2}-\d{2}|\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}|今天|明天|本周五|下周一|\d+天内|\d+天后))?$'
    match = re.search(pattern, content.strip(), re.MULTILINE)
    
    if not match:
        return None
    
    assignee = match.group(1).lower()
    title = match.group(2).strip()
    deadline_str = match.group(3)
    
    # 解析截止时间
    deadline = None
    if deadline_str:
        now = datetime.now()
        
        if deadline_str == '今天':
            deadline = now.replace(hour=23, minute=59, second=0).isoformat()
        elif deadline_str == '明天':
            deadline = (now + timedelta(days=1)).replace(hour=23, minute=59, second=0).isoformat()
        elif deadline_str == '本周五':
            days_until_friday = (4 - now.weekday()) % 7
            if days_until_friday == 0:
                days_until_friday = 7
            deadline = (now + timedelta(days=days_until_friday)).replace(hour=17, minute=0, second=0).isoformat()
        elif deadline_str == '下周一':
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            deadline = (now + timedelta(days=days_until_monday)).replace(hour=9, minute=0, second=0).isoformat()
        elif '天内' in deadline_str or '天后' in deadline_str:
            days_match = re.search(r'(\d+)', deadline_str)
            if days_match:
                days = int(days_match.group(1))
                deadline = (now + timedelta(days=days)).replace(hour=23, minute=59, second=0).isoformat()
        else:
            # 尝试解析 ISO 格式日期
            try:
                if ' ' in deadline_str:
                    deadline = datetime.strptime(deadline_str, '%Y-%m-%d %H:%M').isoformat()
                else:
                    deadline = datetime.strptime(deadline_str, '%Y-%m-%d').replace(hour=23, minute=59).isoformat()
            except ValueError:
                deadline = None
    
    return {
        'assignee': assignee,
        'title': title,
        'deadline': deadline
    }


def create_task_with_notification(post_id, content, assigner, reply_id=None):
    """解析指令并创建任务及通知"""
    parsed = parse_assign_command(content)
    if not parsed:
        return None
    
    assignee = parsed['assignee']
    title = parsed['title']
    deadline = parsed['deadline']
    
    # Validate assignee against active agents
    from agent_manager import get_active_agents
    active_agents = get_active_agents()
    if assignee not in active_agents and assignee != 'human':
        return None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    
    try:
        cursor.execute('''
            INSERT INTO tasks (task_id, title, assignee, assigner, deadline, post_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (task_id, title, assignee, assigner, deadline, post_id))
        
        # 创建通知
        cursor.execute('''
            INSERT INTO notifications (recipient_id, type, title, content, post_id, reply_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (assignee, 'task_assigned', 
              f"你被分配了新任务: {title[:50]}{'...' if len(title) > 50 else ''}", 
              f"任务: {title}", post_id, reply_id))
        
        conn.commit()
        return {
            'task_id': task_id,
            'title': title,
            'assignee': assignee,
            'assigner': assigner,
            'deadline': deadline
        }
    except Exception as e:
        print(f"Error creating task: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()


def get_task_stats(post_id=None):
    """获取任务统计信息"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if post_id:
        cursor.execute('''
            SELECT status, COUNT(*) as count 
            FROM tasks 
            WHERE post_id = ?
            GROUP BY status
        ''', (post_id,))
    else:
        cursor.execute('''
            SELECT status, COUNT(*) as count 
            FROM tasks 
            GROUP BY status
        ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    stats = {'todo': 0, 'doing': 0, 'done': 0, 'cancelled': 0, 'total': 0}
    for row in rows:
        stats[row['status']] = row['count']
        stats['total'] += row['count']
    
    return stats
