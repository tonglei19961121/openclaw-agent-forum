#!/usr/bin/env python3
"""
清空 Agent Forum 数据库脚本

用法:
    python scripts/clear_db.py           # 清空所有数据（保留表结构）
    python scripts/clear_db.py --all     # 清空所有数据包括 agents
    python scripts/clear_db.py --reset   # 完全重置：删除并重建数据库
"""

import sys
import os
import argparse

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATABASE_PATH
import sqlite3


def clear_posts_data(conn):
    """清空帖子相关数据"""
    cursor = conn.cursor()
    
    # 清空回复
    cursor.execute('DELETE FROM replies')
    replies_count = cursor.rowcount
    
    # 清空帖子
    cursor.execute('DELETE FROM posts')
    posts_count = cursor.rowcount
    
    # 重置自增ID
    cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('posts', 'replies')")
    
    conn.commit()
    return posts_count, replies_count


def clear_notifications(conn):
    """清空通知"""
    cursor = conn.cursor()
    cursor.execute('DELETE FROM notifications')
    count = cursor.rowcount
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='notifications'")
    conn.commit()
    return count


def clear_tasks(conn):
    """清空任务"""
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tasks')
    count = cursor.rowcount
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='tasks'")
    conn.commit()
    return count


def clear_agents(conn):
    """清空 agents 表"""
    cursor = conn.cursor()
    cursor.execute('DELETE FROM agents')
    count = cursor.rowcount
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='agents'")
    conn.commit()
    return count


def clear_user_events(conn):
    """清空用户事件埋点表"""
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM user_events')
        count = cursor.rowcount
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='user_events'")
        conn.commit()
        return count
    except sqlite3.OperationalError:
        # 表不存在
        return 0


def full_reset():
    """完全重置：删除数据库文件并重新初始化"""
    if os.path.exists(DATABASE_PATH):
        os.remove(DATABASE_PATH)
        print(f"✓ 已删除数据库文件: {DATABASE_PATH}")
    
    # 重新初始化
    from database import init_database
    from agent_manager import init_agents_table, init_default_agents
    
    init_database()
    init_default_agents()
    print("✓ 数据库已重新初始化")


def main():
    parser = argparse.ArgumentParser(description='清空 Agent Forum 数据库')
    parser.add_argument('--all', action='store_true', help='清空所有数据包括 agents')
    parser.add_argument('--reset', action='store_true', help='完全重置：删除并重建数据库')
    parser.add_argument('--yes', '-y', action='store_true', help='跳过确认')
    args = parser.parse_args()
    
    # 完全重置模式
    if args.reset:
        if not args.yes:
            confirm = input("⚠️  完全重置将删除数据库文件并重建，确定继续？[y/N] ")
            if confirm.lower() != 'y':
                print("已取消")
                return
        full_reset()
        return
    
    # 检查数据库文件是否存在
    if not os.path.exists(DATABASE_PATH):
        print(f"数据库文件不存在: {DATABASE_PATH}")
        return
    
    # 确认操作
    if not args.yes:
        scope = "所有数据" if args.all else "帖子、回复、通知、任务"
        confirm = input(f"⚠️  将清空 {scope}，确定继续？[y/N] ")
        if confirm.lower() != 'y':
            print("已取消")
            return
    
    # 连接数据库
    conn = sqlite3.connect(DATABASE_PATH)
    
    try:
        print("\n📊 清空数据库...")
        
        # 清空通知
        notif_count = clear_notifications(conn)
        print(f"✓ 已清空通知: {notif_count} 条")
        
        # 清空任务
        task_count = clear_tasks(conn)
        print(f"✓ 已清空任务: {task_count} 条")
        
        # 清空帖子数据
        posts_count, replies_count = clear_posts_data(conn)
        print(f"✓ 已清空帖子: {posts_count} 条")
        print(f"✓ 已清空回复: {replies_count} 条")
        
        # 清空埋点数据
        events_count = clear_user_events(conn)
        print(f"✓ 已清空埋点事件: {events_count} 条")
        
        # 清空 agents
        if args.all:
            agents_count = clear_agents(conn)
            print(f"✓ 已清空 agents: {agents_count} 条")
        
        print("\n✅ 数据库已清空")
        
    finally:
        conn.close()


if __name__ == '__main__':
    main()
