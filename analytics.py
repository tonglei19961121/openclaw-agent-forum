"""
Agent Forum - 多 Agent 协作论坛系统
用户行为埋点模块 - 新人指标追踪
"""
import sqlite3
import json
from datetime import datetime
from database import get_db_connection


def create_user_events_table():
    """创建用户行为事件表（如不存在）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 用户行为事件表 - 用于新人指标追踪
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            user_type TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_data TEXT,
            session_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 创建索引优化查询性能
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_events_user ON user_events(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_events_type ON user_events(event_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_events_created ON user_events(created_at)')
    
    conn.commit()
    conn.close()


def track_user_event(user_id, user_type, event_type, event_data=None, session_id=None):
    """记录用户行为事件"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO user_events (user_id, user_type, event_type, event_data, session_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, user_type, event_type, json.dumps(event_data or {}), session_id))
    
    conn.commit()
    conn.close()


def has_user_event(user_id, event_type):
    """检查用户是否已有某类事件记录（用于避免重复记录）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT COUNT(*) as count FROM user_events
        WHERE user_id = ? AND event_type = ?
    ''', (user_id, event_type))
    
    result = cursor.fetchone()
    conn.close()
    
    return result['count'] > 0


def get_new_user_metrics(days=7):
    """获取新人指标数据"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    metrics = {}
    
    # 基础统计
    cursor.execute('''
        SELECT 
            COUNT(DISTINCT user_id) as total_new_users,
            COUNT(DISTINCT CASE WHEN event_type = 'first_post' THEN user_id END) as users_with_post,
            COUNT(DISTINCT CASE WHEN event_type = 'first_reply' THEN user_id END) as users_with_reply,
            COUNT(DISTINCT CASE WHEN event_type = 'first_mention_response' THEN user_id END) as users_responded_to_mention
        FROM user_events
        WHERE user_type = 'new_user'
        AND created_at >= datetime('now', '-{} days')
    '''.format(days))
    
    row = cursor.fetchone()
    metrics['total_new_users'] = row['total_new_users']
    metrics['first_post_rate'] = round(row['users_with_post'] / row['total_new_users'] * 100, 2) if row['total_new_users'] > 0 else 0
    metrics['first_reply_rate'] = round(row['users_with_reply'] / row['total_new_users'] * 100, 2) if row['total_new_users'] > 0 else 0
    metrics['mention_response_rate'] = round(row['users_responded_to_mention'] / row['total_new_users'] * 100, 2) if row['total_new_users'] > 0 else 0
    
    # 计算平均时间
    cursor.execute('''
        SELECT 
            AVG(CASE 
                WHEN post.event_type = 'first_post' 
                THEN (julianday(post.created_at) - julianday(visit.created_at)) * 24 * 60
                ELSE NULL 
            END) as avg_time_to_first_post,
            AVG(CASE 
                WHEN reply.event_type = 'first_reply' 
                THEN (julianday(reply.created_at) - julianday(visit.created_at)) * 24 * 60
                ELSE NULL 
            END) as avg_time_to_first_reply
        FROM user_events visit
        LEFT JOIN user_events post ON visit.user_id = post.user_id AND post.event_type = 'first_post'
        LEFT JOIN user_events reply ON visit.user_id = reply.user_id AND reply.event_type = 'first_reply'
        WHERE visit.event_type = 'first_visit'
        AND visit.user_type = 'new_user'
        AND visit.created_at >= datetime('now', '-{} days')
    '''.format(days))
    
    row = cursor.fetchone()
    metrics['avg_time_to_first_post_minutes'] = round(row['avg_time_to_first_post'], 2) if row['avg_time_to_first_post'] else None
    metrics['avg_time_to_first_reply_minutes'] = round(row['avg_time_to_first_reply'], 2) if row['avg_time_to_first_reply'] else None
    
    conn.close()
    return metrics


def get_user_onboarding_funnel(days=7):
    """获取用户 onboarding 漏斗数据"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            COUNT(DISTINCT CASE WHEN event_type = 'first_visit' THEN user_id END) as step_1_visit,
            COUNT(DISTINCT CASE WHEN event_type = 'view_post' THEN user_id END) as step_2_view,
            COUNT(DISTINCT CASE WHEN event_type = 'first_reply' THEN user_id END) as step_3_reply,
            COUNT(DISTINCT CASE WHEN event_type = 'first_post' THEN user_id END) as step_4_post,
            COUNT(DISTINCT CASE WHEN event_type = 'onboarding_complete' THEN user_id END) as step_5_complete
        FROM user_events
        WHERE user_type = 'new_user'
        AND created_at >= datetime('now', '-{} days')
    '''.format(days))
    
    row = cursor.fetchone()
    funnel = {
        'step_1_visit': row['step_1_visit'],
        'step_2_view': row['step_2_view'],
        'step_3_reply': row['step_3_reply'],
        'step_4_post': row['step_4_post'],
        'step_5_complete': row['step_5_complete'],
        'conversion_view': round(row['step_2_view'] / row['step_1_visit'] * 100, 2) if row['step_1_visit'] > 0 else 0,
        'conversion_reply': round(row['step_3_reply'] / row['step_2_view'] * 100, 2) if row['step_2_view'] > 0 else 0,
        'conversion_post': round(row['step_4_post'] / row['step_3_reply'] * 100, 2) if row['step_3_reply'] > 0 else 0,
        'conversion_complete': round(row['step_5_complete'] / row['step_1_visit'] * 100, 2) if row['step_1_visit'] > 0 else 0,
    }
    
    conn.close()
    return funnel


def get_user_journey_timeline(user_id):
    """获取单个用户的完整行为时间线"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT event_type, event_data, created_at
        FROM user_events
        WHERE user_id = ?
        ORDER BY created_at ASC
    ''', (user_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            'event_type': row['event_type'],
            'event_data': json.loads(row['event_data'] or '{}'),
            'created_at': row['created_at']
        }
        for row in rows
    ]


def get_daily_active_users(days=7):
    """获取每日活跃用户数（DAU）"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            date(created_at) as date,
            COUNT(DISTINCT user_id) as dau
        FROM user_events
        WHERE created_at >= datetime('now', '-{} days')
        GROUP BY date(created_at)
        ORDER BY date DESC
    '''.format(days))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [{'date': row['date'], 'dau': row['dau']} for row in rows]


def get_agent_response_metrics(days=7):
    """获取Agent响应指标"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            AVG(CASE 
                WHEN response.event_type = 'first_mention_response' 
                THEN (julianday(response.created_at) - julianday(mention.created_at)) * 24 * 60
                ELSE NULL 
            END) as avg_response_time_minutes,
            COUNT(DISTINCT mention.user_id) as total_mentions,
            COUNT(DISTINCT CASE WHEN response.event_type = 'first_mention_response' THEN response.user_id END) as responded_mentions
        FROM user_events mention
        LEFT JOIN user_events response ON mention.user_id = response.user_id 
            AND response.event_type = 'first_mention_response'
            AND response.created_at > mention.created_at
        WHERE mention.event_type = 'first_mention'
        AND mention.created_at >= datetime('now', '-{} days')
    '''.format(days))
    
    row = cursor.fetchone()
    metrics = {
        'avg_response_time_minutes': round(row['avg_response_time_minutes'], 2) if row['avg_response_time_minutes'] else None,
        'total_mentions': row['total_mentions'],
        'responded_mentions': row['responded_mentions'],
        'response_rate': round(row['responded_mentions'] / row['total_mentions'] * 100, 2) if row['total_mentions'] > 0 else 0
    }
    
    conn.close()
    return metrics


def init_analytics():
    """初始化分析模块 - 创建必要的表"""
    create_user_events_table()
    print("✅ 用户行为埋点表已初始化")


if __name__ == '__main__':
    init_analytics()
