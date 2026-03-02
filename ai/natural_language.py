"""
自然语言接口 - AI 可以用自然语言操作论坛
"""
import re
from typing import Dict, Any, List

class NaturalLanguageInterface:
    """自然语言接口处理器"""
    
    def __init__(self, agents_config=None):
        self.agents = agents_config or {}
        self.patterns = {
            'create_post': [
                r'(?:创建|发起|新建)(?:一个)?(?:帖子|讨论).*?[:：]\s*(.+)',
                r'(?:发|写)(?:一个)?(?:帖子|讨论).*?[:：]\s*(.+)',
                r'(?:post|create).*?(?:about|on|titled)[:\s]*(.+)',
            ],
            'reply_post': [
                r'(?:回复|回答)(?:帖子)?[#]?\s*(\d+).*?[:：]\s*(.+)',
                r'在(?:帖子)?[#]?\s*(\d+)\s*(?:下)?回复[:：]\s*(.+)',
                r'(?:reply|respond)\s+(?:to\s+)?(?:post\s*)?#?(\d+)[:\s]*(.+)',
            ],
            'check_notifications': [
                r'(?:查看|检查)(?:我的)?(?:通知|消息)',
                r'(?:有|有没有)(?:什么)?(?:新)?(?:通知|消息)',
                r'(?:check|view)\s+(?:my\s+)?notifications',
            ],
            'list_posts': [
                r'(?:列出|查看|获取)(?:所有)?(?:最近)?(?:的)?(?:帖子|讨论)',
                r'(?:显示|展示)(?:帖子|讨论)(?:列表)?',
                r'(?:list|show|get)\s+(?:all\s+)?(?:recent\s+)?posts',
            ],
            'delete_post': [
                r'(?:删除|移除)(?:帖子)?[#]?\s*(\d+)',
                r'(?:delete|remove)\s+(?:post\s*)?#?(\d+)',
            ],
            'view_post': [
                r'(?:查看|打开|显示)(?:帖子)?[#]?\s*(\d+)',
                r'(?:view|open|show)\s+(?:post\s*)?#?(\d+)',
            ],
        }
    
    def parse(self, text: str, author_id: str) -> Dict[str, Any]:
        """
        解析自然语言指令
        
        Args:
            text: 自然语言文本
            author_id: 执行者ID
            
        Returns:
            解析结果，包含 action 和参数
        """
        text = text.strip()
        
        # 尝试匹配各种模式
        for action, patterns in self.patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if match:
                    return self._handle_match(action, match, author_id, text)
        
        # 没有匹配到，返回需要澄清
        return {
            'action': 'clarify',
            'message': '我不确定你想做什么。你可以说：\n'
                      '- "创建一个帖子：标题..."\n'
                      '- "回复帖子#123：内容..."\n'
                      '- "查看通知"\n'
                      '- "列出最近的帖子"\n'
                      '- "删除帖子#123"'
        }
    
    def _handle_match(self, action: str, match, author_id: str, full_text: str) -> Dict[str, Any]:
        """处理匹配结果"""
        
        if action == 'create_post':
            content = match.group(1).strip()
            # 尝试提取标题
            lines = content.split('\n', 1)
            title = lines[0][:100]  # 限制标题长度
            body = lines[1] if len(lines) > 1 else content
            
            # 解析 @提及
            mentions = self._parse_mentions(body)
            
            return {
                'action': 'create_post',
                'params': {
                    'title': title,
                    'content': body,
                    'author_id': author_id,
                    'mentioned_agents': mentions
                }
            }
        
        elif action == 'reply_post':
            post_id = int(match.group(1))
            content = match.group(2).strip()
            mentions = self._parse_mentions(content)
            
            return {
                'action': 'reply_post',
                'params': {
                    'post_id': post_id,
                    'content': content,
                    'author_id': author_id,
                    'mentioned_agents': mentions
                }
            }
        
        elif action == 'check_notifications':
            return {
                'action': 'check_notifications',
                'params': {
                    'recipient_id': author_id,
                    'unread_only': True
                }
            }
        
        elif action == 'list_posts':
            return {
                'action': 'list_posts',
                'params': {
                    'limit': 20,
                    'unread_only': False
                }
            }
        
        elif action == 'delete_post':
            post_id = int(match.group(1))
            return {
                'action': 'delete_post',
                'params': {
                    'post_id': post_id,
                    'author_id': author_id
                }
            }
        
        elif action == 'view_post':
            post_id = int(match.group(1))
            return {
                'action': 'view_post',
                'params': {
                    'post_id': post_id
                }
            }
        
        return {'action': 'unknown'}
    
    def _parse_mentions(self, text: str) -> List[str]:
        """解析 @提及"""
        mentions = []
        pattern = r'@(\w+)'
        for match in re.finditer(pattern, text):
            agent_id = match.group(1).lower()
            if agent_id in self.agents or agent_id in ['ceo', 'cto', 'cmo', 'pm', 'lucy']:
                mentions.append(agent_id)
        return list(set(mentions))
    
    def execute(self, text: str, author_id: str, db_funcs: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析并执行自然语言指令
        
        Args:
            text: 自然语言文本
            author_id: 执行者ID
            db_funcs: 数据库操作函数字典
            
        Returns:
            执行结果
        """
        parsed = self.parse(text, author_id)
        
        if parsed['action'] == 'clarify':
            return parsed
        
        action = parsed['action']
        params = parsed.get('params', {})
        
        try:
            if action == 'create_post':
                post_id = db_funcs['create_post'](**params)
                return {
                    'success': True,
                    'action': action,
                    'post_id': post_id,
                    'message': f'帖子创建成功，ID: {post_id}'
                }
            
            elif action == 'reply_post':
                reply_id = db_funcs['create_reply'](**params)
                return {
                    'success': True,
                    'action': action,
                    'reply_id': reply_id,
                    'message': f'回复创建成功，ID: {reply_id}'
                }
            
            elif action == 'check_notifications':
                notifications = db_funcs['get_notifications'](**params)
                return {
                    'success': True,
                    'action': action,
                    'count': len(notifications),
                    'notifications': notifications
                }
            
            elif action == 'list_posts':
                posts = db_funcs['get_posts'](**params)
                return {
                    'success': True,
                    'action': action,
                    'count': len(posts),
                    'posts': posts
                }
            
            elif action == 'view_post':
                post = db_funcs['get_post'](params['post_id'])
                if post:
                    replies = db_funcs['get_replies'](params['post_id'])
                    return {
                        'success': True,
                        'action': action,
                        'post': post,
                        'replies': replies
                    }
                else:
                    return {
                        'success': False,
                        'error': '帖子不存在'
                    }
            
            elif action == 'delete_post':
                success = db_funcs['delete_post'](**params)
                return {
                    'success': success,
                    'action': action,
                    'message': '帖子已删除' if success else '删除失败'
                }
            
            else:
                return {
                    'success': False,
                    'error': f'未知操作: {action}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


# 便捷函数
def parse_natural_language(text: str, author_id: str, agents_config=None) -> Dict[str, Any]:
    """解析自然语言指令"""
    interface = NaturalLanguageInterface(agents_config)
    return interface.parse(text, author_id)


# 使用示例
if __name__ == '__main__':
    # 测试自然语言接口
    interface = NaturalLanguageInterface()
    
    test_cases = [
        "创建一个帖子：Q4 战略规划\n@ceo @cto 请讨论技术方向",
        "回复帖子#123：同意这个方案",
        "查看我的通知",
        "列出最近的帖子",
        "删除帖子#456",
    ]
    
    for text in test_cases:
        print(f"\n输入: {text}")
        result = interface.parse(text, "chairman")
        print(f"解析: {result}")
