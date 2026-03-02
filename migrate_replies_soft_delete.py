"""
数据库迁移脚本 - 为回复表添加软删除字段
"""
import sqlite3
import sys
sys.path.insert(0, '/root/.openclaw/workspace/openclaw-agent-forum')

from config import DATABASE_PATH

def migrate():
    """执行迁移"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print("🔄 开始数据库迁移...")
    
    # 检查字段是否已存在
    cursor.execute("PRAGMA table_info(replies)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'is_deleted' in columns:
        print("✅ 字段已存在，跳过迁移")
        conn.close()
        return
    
    # 添加新字段
    print("📦 添加软删除字段到 replies 表...")
    
    cursor.execute('''
        ALTER TABLE replies 
        ADD COLUMN is_deleted BOOLEAN DEFAULT 0
    ''')
    print("   ✅ is_deleted")
    
    cursor.execute('''
        ALTER TABLE replies 
        ADD COLUMN deleted_at TIMESTAMP
    ''')
    print("   ✅ deleted_at")
    
    cursor.execute('''
        ALTER TABLE replies 
        ADD COLUMN deleted_by TEXT
    ''')
    print("   ✅ deleted_by")
    
    conn.commit()
    conn.close()
    
    print("✅ 迁移完成!")

if __name__ == '__main__':
    migrate()
