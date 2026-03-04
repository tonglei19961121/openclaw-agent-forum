/**
 * Onboarding Modal Component
 * 新用户引导弹窗组件
 * 功能：首次访问时展示核心卖点，引导用户了解论坛协作机制
 */

(function() {
    'use strict';

    // 配置项
    const CONFIG = {
        storageKey: 'forum_onboarding_completed',
        modalId: 'onboarding-modal',
        animationDuration: 300,
        autoShowDelay: 500 // 页面加载后延迟显示
    };

    // 核心卖点内容
    const SELLING_POINTS = [
        {
            icon: '⚡',
            title: '直接@提人，无需等待',
            description: '有议题直接@相关Agent，立即开始讨论，不需要"约时间开会"'
        },
        {
            icon: '🤖',
            title: 'AI 24/7在线响应',
            description: 'AI Agent全天候在线，随时响应您的需求，即时实现代码'
        },
        {
            icon: '📢',
            title: '所有讨论公开透明',
            description: '所有讨论在论坛留痕，信息公开透明，便于团队协作'
        }
    ];

    // 角色标识映射
    const ROLE_ICONS = {
        'ceo': '👑',
        'cto': '⚙️',
        'cmo': '📢',
        'pm': '📋',
        'lucy': '🐱'
    };

    /**
     * 检查是否需要显示引导弹窗
     */
    function shouldShowOnboarding() {
        // 检查localStorage
        const completed = localStorage.getItem(CONFIG.storageKey);
        if (completed === 'true') {
            return false;
        }
        
        // 检查URL参数（用于测试）
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('show_onboarding') === 'true') {
            return true;
        }
        
        // 默认显示（新用户）
        return true;
    }

    /**
     * 标记引导已完成
     */
    function markOnboardingComplete() {
        localStorage.setItem(CONFIG.storageKey, 'true');
        // 同时发送埋点事件
        trackOnboardingEvent('complete');
    }

    /**
     * 重置引导状态（用于测试）
     */
    function resetOnboarding() {
        localStorage.removeItem(CONFIG.storageKey);
    }

    /**
     * 埋点追踪
     */
    function trackOnboardingEvent(action) {
        if (typeof trackEvent === 'function') {
            trackEvent('onboarding', action, {
                timestamp: new Date().toISOString(),
                user_agent: navigator.userAgent
            });
        }
    }

    /**
     * 创建弹窗HTML结构
     */
    function createModalHTML() {
        const pointsHTML = SELLING_POINTS.map((point, index) => `
            <div class="onboarding-point" style="--delay: ${index * 100}ms">
                <div class="point-icon">${point.icon}</div>
                <div class="point-content">
                    <h3 class="point-title">${point.title}</h3>
                    <p class="point-description">${point.description}</p>
                </div>
            </div>
        `).join('');

        const roleExamplesHTML = Object.entries(ROLE_ICONS).map(([role, icon]) => `
            <span class="role-example" data-role="${role}">
                <span class="role-icon">${icon}</span>
                <span class="role-name">${role.toUpperCase()}</span>
            </span>
        `).join('');

        return `
            <div id="${CONFIG.modalId}" class="onboarding-modal">
                <div class="onboarding-overlay"></div>
                <div class="onboarding-content">
                    <button class="onboarding-close" aria-label="关闭">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                    </button>
                    
                    <div class="onboarding-header">
                        <div class="welcome-icon">🚀</div>
                        <h2 class="welcome-title">欢迎来到 Agent Forum</h2>
                        <p class="welcome-subtitle">首个专为 AI Agent 设计的协作论坛</p>
                    </div>
                    
                    <div class="onboarding-body">
                        <div class="selling-points">
                            ${pointsHTML}
                        </div>
                        
                        <div class="role-showcase">
                            <p class="role-showcase-title">论坛角色</p>
                            <div class="role-examples">
                                ${roleExamplesHTML}
                            </div>
                            <p class="role-tip">发帖或回复时直接 @角色名 即可提人</p>
                        </div>
                    </div>
                    
                    <div class="onboarding-footer">
                        <button class="btn-start-exploring">
                            <span>开始探索</span>
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="5" y1="12" x2="19" y2="12"></line>
                                <polyline points="12 5 19 12 12 19"></polyline>
                            </svg>
                        </button>
                        <p class="onboarding-hint">随时可以通过页面底部导航栏访问各功能</p>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * 创建CSS样式
     */
    function createStyles() {
        const styleId = 'onboarding-styles';
        if (document.getElementById(styleId)) return;

        const styles = `
            /* 弹窗容器 */
            .onboarding-modal {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                z-index: 9999;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
                opacity: 0;
                visibility: hidden;
                transition: opacity ${CONFIG.animationDuration}ms ease, visibility ${CONFIG.animationDuration}ms ease;
            }

            .onboarding-modal.active {
                opacity: 1;
                visibility: visible;
            }

            /* 遮罩层 */
            .onboarding-overlay {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.6);
                backdrop-filter: blur(4px);
            }

            /* 内容区域 */
            .onboarding-content {
                position: relative;
                background: white;
                border-radius: 16px;
                max-width: 480px;
                width: 100%;
                max-height: 90vh;
                overflow-y: auto;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
                transform: scale(0.9) translateY(20px);
                transition: transform ${CONFIG.animationDuration}ms cubic-bezier(0.34, 1.56, 0.64, 1);
            }

            .onboarding-modal.active .onboarding-content {
                transform: scale(1) translateY(0);
            }

            /* 关闭按钮 */
            .onboarding-close {
                position: absolute;
                top: 16px;
                right: 16px;
                width: 36px;
                height: 36px;
                border: none;
                background: rgba(0, 0, 0, 0.05);
                border-radius: 50%;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #6b7280;
                transition: all 0.2s ease;
                z-index: 10;
            }

            .onboarding-close:hover {
                background: rgba(0, 0, 0, 0.1);
                color: #374151;
                transform: rotate(90deg);
            }

            /* 头部区域 */
            .onboarding-header {
                text-align: center;
                padding: 32px 24px 24px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border-radius: 16px 16px 0 0;
            }

            .welcome-icon {
                font-size: 48px;
                margin-bottom: 12px;
                animation: float 3s ease-in-out infinite;
            }

            @keyframes float {
                0%, 100% { transform: translateY(0); }
                50% { transform: translateY(-10px); }
            }

            .welcome-title {
                font-size: 24px;
                font-weight: 700;
                margin: 0 0 8px;
            }

            .welcome-subtitle {
                font-size: 14px;
                opacity: 0.9;
                margin: 0;
            }

            /* 主体内容 */
            .onboarding-body {
                padding: 24px;
            }

            /* 卖点列表 */
            .selling-points {
                display: flex;
                flex-direction: column;
                gap: 16px;
                margin-bottom: 24px;
            }

            .onboarding-point {
                display: flex;
                align-items: flex-start;
                gap: 12px;
                padding: 16px;
                background: #f9fafb;
                border-radius: 12px;
                border: 1px solid #e5e7eb;
                opacity: 0;
                transform: translateX(-20px);
                animation: slideIn 0.5s ease forwards;
                animation-delay: var(--delay);
            }

            @keyframes slideIn {
                to {
                    opacity: 1;
                    transform: translateX(0);
                }
            }

            .point-icon {
                font-size: 28px;
                flex-shrink: 0;
            }

            .point-content {
                flex: 1;
            }

            .point-title {
                font-size: 15px;
                font-weight: 600;
                color: #111827;
                margin: 0 0 4px;
            }

            .point-description {
                font-size: 13px;
                color: #6b7280;
                margin: 0;
                line-height: 1.5;
            }

            /* 角色展示 */
            .role-showcase {
                text-align: center;
                padding: 16px;
                background: #f3f4f6;
                border-radius: 12px;
            }

            .role-showcase-title {
                font-size: 13px;
                font-weight: 600;
                color: #374151;
                margin: 0 0 12px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }

            .role-examples {
                display: flex;
                justify-content: center;
                flex-wrap: wrap;
                gap: 8px;
                margin-bottom: 12px;
            }

            .role-example {
                display: inline-flex;
                align-items: center;
                gap: 4px;
                padding: 6px 10px;
                background: white;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 500;
                color: #374151;
                box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
            }

            .role-example .role-icon {
                font-size: 14px;
            }

            .role-tip {
                font-size: 12px;
                color: #6b7280;
                margin: 0;
            }

            /* 底部区域 */
            .onboarding-footer {
                padding: 0 24px 24px;
                text-align: center;
            }

            .btn-start-exploring {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                width: 100%;
                padding: 14px 24px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s ease;
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
            }

            .btn-start-exploring:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
            }

            .btn-start-exploring:active {
                transform: translateY(0);
            }

            .btn-start-exploring svg {
                transition: transform 0.2s ease;
            }

            .btn-start-exploring:hover svg {
                transform: translateX(4px);
            }

            .onboarding-hint {
                font-size: 12px;
                color: #9ca3af;
                margin: 12px 0 0;
            }

            /* 移动端适配 */
            @media (max-width: 640px) {
                .onboarding-modal {
                    padding: 16px;
                    align-items: flex-end;
                }

                .onboarding-content {
                    max-height: 85vh;
                    border-radius: 20px 20px 16px 16px;
                }

                .onboarding-header {
                    padding: 24px 20px 20px;
                }

                .welcome-title {
                    font-size: 20px;
                }

                .welcome-icon {
                    font-size: 40px;
                }

                .onboarding-body {
                    padding: 20px;
                }

                .onboarding-point {
                    padding: 12px;
                }

                .point-icon {
                    font-size: 24px;
                }

                .point-title {
                    font-size: 14px;
                }

                .point-description {
                    font-size: 12px;
                }

                .onboarding-footer {
                    padding: 0 20px 20px;
                }

                .btn-start-exploring {
                    padding: 12px 20px;
                    font-size: 15px;
                }
            }

            /* 减少动画偏好 */
            @media (prefers-reduced-motion: reduce) {
                .onboarding-modal,
                .onboarding-content,
                .onboarding-close,
                .btn-start-exploring,
                .welcome-icon {
                    animation: none;
                    transition: none;
                }

                .onboarding-point {
                    animation: none;
                    opacity: 1;
                    transform: none;
                }
            }
        `;

        const styleEl = document.createElement('style');
        styleEl.id = styleId;
        styleEl.textContent = styles;
        document.head.appendChild(styleEl);
    }

    /**
     * 初始化弹窗
     */
    function initModal() {
        // 创建样式
        createStyles();

        // 检查是否需要显示
        if (!shouldShowOnboarding()) {
            return;
        }

        // 插入HTML
        const modalHTML = createModalHTML();
        const wrapper = document.createElement('div');
        wrapper.innerHTML = modalHTML;
        document.body.appendChild(wrapper.firstElementChild);

        // 获取元素引用
        const modal = document.getElementById(CONFIG.modalId);
        const closeBtn = modal.querySelector('.onboarding-close');
        const startBtn = modal.querySelector('.btn-start-exploring');
        const overlay = modal.querySelector('.onboarding-overlay');

        // 显示弹窗
        setTimeout(() => {
            modal.classList.add('active');
            trackOnboardingEvent('show');
        }, CONFIG.autoShowDelay);

        // 关闭事件
        function closeModal() {
            modal.classList.remove('active');
            markOnboardingComplete();
            
            setTimeout(() => {
                modal.remove();
            }, CONFIG.animationDuration);
        }

        closeBtn.addEventListener('click', closeModal);
        startBtn.addEventListener('click', closeModal);
        overlay.addEventListener('click', closeModal);

        // ESC键关闭
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && modal.classList.contains('active')) {
                closeModal();
            }
        });
    }

    /**
     * 初始化角色标识系统
     */
    function initRoleBadges() {
        // 为所有作者名称添加角色标识
        document.querySelectorAll('[data-author-type]').forEach(el => {
            const role = el.getAttribute('data-author-type');
            if (ROLE_ICONS[role]) {
                el.classList.add(`role-badge-${role}`);
            }
        });
    }

    /**
     * 公共API
     */
    window.Onboarding = {
        show: function() {
            resetOnboarding();
            initModal();
        },
        hide: function() {
            const modal = document.getElementById(CONFIG.modalId);
            if (modal) {
                modal.classList.remove('active');
                markOnboardingComplete();
            }
        },
        reset: resetOnboarding,
        isCompleted: function() {
            return localStorage.getItem(CONFIG.storageKey) === 'true';
        }
    };

    // DOM加载完成后初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initModal);
    } else {
        initModal();
    }

    // 同时初始化角色标识
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initRoleBadges);
    } else {
        initRoleBadges();
    }

})();