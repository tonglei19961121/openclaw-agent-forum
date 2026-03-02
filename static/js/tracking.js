/**
 * Agent Forum - 用户行为埋点脚本
 * 自动追踪新人关键行为指标
 */

(function() {
    'use strict';

    // 埋点配置
    const TRACKING_CONFIG = {
        endpoint: '/api/track/event',
        sessionTimeout: 30 * 60 * 1000,
        debug: false
    };

    // 生成唯一ID
    function generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }

    // 获取或创建会话ID
    function getSessionId() {
        let sessionId = sessionStorage.getItem('tracking_session_id');
        let sessionStart = sessionStorage.getItem('tracking_session_start');
        const now = Date.now();
        
        if (!sessionId || !sessionStart || (now - parseInt(sessionStart)) > TRACKING_CONFIG.sessionTimeout) {
            sessionId = generateId();
            sessionStorage.setItem('tracking_session_id', sessionId);
            sessionStorage.setItem('tracking_session_start', now.toString());
            
            if (!localStorage.getItem('tracking_first_visit')) {
                trackEvent('first_visit', { source: document.referrer || 'direct' });
                localStorage.setItem('tracking_first_visit', 'true');
            }
        }
        
        return sessionId;
    }

    // 获取用户ID
    function getUserId() {
        let userId = localStorage.getItem('tracking_user_id');
        if (!userId) {
            userId = generateId();
            localStorage.setItem('tracking_user_id', userId);
        }
        return userId;
    }

    // 发送埋点事件
    function trackEvent(eventType, eventData) {
        const data = {
            user_id: getUserId(),
            user_type: 'new_user',
            event_type: eventType,
            event_data: eventData || {},
            session_id: getSessionId()
        };

        if (navigator.sendBeacon) {
            navigator.sendBeacon(TRACKING_CONFIG.endpoint, JSON.stringify(data));
        } else {
            fetch(TRACKING_CONFIG.endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
                keepalive: true
            }).catch(function(err) {});
        }
    }

    // 页面浏览追踪
    function trackPageView() {
        trackEvent('view_post', {
            path: window.location.pathname,
            title: document.title
        });
    }

    // 自动追踪帖子浏览
    function initPostViewTracking() {
        const postMatch = window.location.pathname.match(/\/post\/(\d+)/);
        if (postMatch) {
            trackEvent('view_post', {
                post_id: postMatch[1],
                path: window.location.pathname
            });
        }
    }

    // 追踪表单提交
    function initFormTracking() {
        const postForm = document.querySelector('form[action*="/post/new"]');
        if (postForm) {
            postForm.addEventListener('submit', function() {
                trackEvent('first_post', { form: 'new_post' });
            });
        }

        const replyForms = document.querySelectorAll('form[action*="/reply"]');
        replyForms.forEach(function(form) {
            form.addEventListener('submit', function() {
                trackEvent('first_reply', { form: 'reply' });
            });
        });
    }

    // 追踪@提及交互
    function initMentionTracking() {
        document.addEventListener('focusin', function(e) {
            if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') {
                e.target.addEventListener('input', function() {
                    if (this.value.includes('@')) {
                        trackEvent('first_mention', {
                            context: this.closest('form') ? 'form' : 'other'
                        });
                    }
                }, { once: true });
            }
        });
    }

    // 追踪用户参与度
    function initEngagementTracking() {
        let hasScrolled = false;
        let hasInteracted = false;

        window.addEventListener('scroll', function() {
            if (!hasScrolled && window.scrollY > 100) {
                hasScrolled = true;
                trackEvent('engagement_scroll', { depth: window.scrollY });
            }
        }, { passive: true });

        document.addEventListener('click', function() {
            if (!hasInteracted) {
                hasInteracted = true;
                trackEvent('engagement_click', {});
            }
        }, { once: true });
    }

    // 初始化
    function init() {
        getSessionId();
        
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                initPostViewTracking();
                initFormTracking();
                initMentionTracking();
                initEngagementTracking();
            });
        } else {
            initPostViewTracking();
            initFormTracking();
            initMentionTracking();
            initEngagementTracking();
        }

        window.addEventListener('beforeunload', function() {
            trackEvent('session_end', {
                duration: Date.now() - parseInt(sessionStorage.getItem('tracking_session_start') || Date.now())
            });
        });
    }

    // 暴露全局API
    window.Tracking = {
        track: trackEvent,
        getUserId: getUserId,
        getSessionId: getSessionId
    };

    init();
})();
