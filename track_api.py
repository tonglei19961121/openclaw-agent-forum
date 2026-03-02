"""
Agent Forum - 用户行为埋点API路由
"""
from flask import Blueprint, request, jsonify
from analytics import (
    track_user_event, has_user_event,
    get_new_user_metrics, get_user_onboarding_funnel,
    get_daily_active_users, get_agent_response_metrics,
    init_analytics
)

# 创建蓝图
track_bp = Blueprint('track', __name__, url_prefix='/api/track')


@track_bp.route('/event', methods=['POST'])
def track_event():
    """记录用户行为事件"""
    data = request.get_json() or request.form.to_dict()
    
    user_id = data.get('user_id')
    user_type = data.get('user_type', 'new_user')
    event_type = data.get('event_type')
    event_data = data.get('event_data', {})
    session_id = data.get('session_id')
    
    if not user_id or not event_type:
        return jsonify({'error': 'user_id and event_type are required'}), 400
    
    # 对于首次事件，检查是否已记录，避免重复
    if event_type.startswith('first_') and has_user_event(user_id, event_type):
        return jsonify({'success': True, 'message': 'Event already recorded', 'duplicate': True})
    
    track_user_event(user_id, user_type, event_type, event_data, session_id)
    
    return jsonify({'success': True, 'message': 'Event tracked successfully'})


@track_bp.route('/metrics/new-users', methods=['GET'])
def new_user_metrics():
    """获取新人指标"""
    days = request.args.get('days', 7, type=int)
    metrics = get_new_user_metrics(days)
    return jsonify(metrics)


@track_bp.route('/metrics/funnel', methods=['GET'])
def onboarding_funnel():
    """获取用户onboarding漏斗"""
    days = request.args.get('days', 7, type=int)
    funnel = get_user_onboarding_funnel(days)
    return jsonify(funnel)


@track_bp.route('/metrics/dau', methods=['GET'])
def daily_active_users():
    """获取每日活跃用户数"""
    days = request.args.get('days', 7, type=int)
    dau = get_daily_active_users(days)
    return jsonify(dau)


@track_bp.route('/metrics/agent-response', methods=['GET'])
def agent_response_metrics():
    """获取Agent响应指标"""
    days = request.args.get('days', 7, type=int)
    metrics = get_agent_response_metrics(days)
    return jsonify(metrics)


@track_bp.route('/init', methods=['POST'])
def init_tracking():
    """初始化埋点系统"""
    init_analytics()
    return jsonify({'success': True, 'message': 'Analytics initialized'})
