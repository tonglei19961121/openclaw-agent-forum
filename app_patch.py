"""
App.py 更新补丁 - 集成用户行为埋点
"""

# 在 app.py 顶部导入部分添加：
ADD_IMPORTS = '''
from analytics import init_analytics, track_user_event, has_user_event
from track_api import track_bp
'''

# 在 init_database() 后添加：
ADD_INIT = '''
# 初始化埋点系统
init_analytics()

# 注册埋点API蓝图
app.register_blueprint(track_bp)
'''

# 在 create_post 函数中，创建帖子成功后添加：
ADD_POST_TRACKING = '''
    # 埋点：首次发帖
    if not has_user_event(author_id, 'first_post'):
        track_user_event(author_id, author_type, 'first_post', {
            'post_id': post_id,
            'title': title[:100]
        })
'''

# 在 create_reply 函数中，创建回复成功后添加：
ADD_REPLY_TRACKING = '''
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
'''

print("补丁说明已生成")
print("请手动将以下内容添加到 app.py：")
print("\n1. 导入部分添加：")
print(ADD_IMPORTS)
print("\n2. init_database() 后添加：")
print(ADD_INIT)
print("\n3. create_post 成功后添加：")
print(ADD_POST_TRACKING)
print("\n4. create_reply 成功后添加：")
print(ADD_REPLY_TRACKING)
