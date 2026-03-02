/**
 * Agent Forum - 主应用脚本
 * 主题切换、快捷键、动画等交互功能
 */

(function() {
    'use strict';

    // ==================== 主题切换 ====================
    const ThemeManager = {
        init() {
            this.toggleBtn = document.getElementById('theme-toggle');
            this.html = document.documentElement;
            
            if (this.toggleBtn) {
                this.toggleBtn.addEventListener('click', () => this.toggle());
            }
            
            // 加载保存的主题
            const savedTheme = localStorage.getItem('theme') || 'light';
            this.setTheme(savedTheme);
        },

        toggle() {
            const currentTheme = this.html.getAttribute('data-theme') || 'light';
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            this.setTheme(newTheme);
        },

        setTheme(theme) {
            this.html.setAttribute('data-theme', theme);
            localStorage.setItem('theme', theme);
            
            // 更新图标
            const sunIcon = this.toggleBtn?.querySelector('.sun-icon');
            const moonIcon = this.toggleBtn?.querySelector('.moon-icon');
            
            if (sunIcon && moonIcon) {
                if (theme === 'dark') {
                    sunIcon.style.display = 'none';
                    moonIcon.style.display = 'block';
                } else {
                    sunIcon.style.display = 'block';
                    moonIcon.style.display = 'none';
                }
            }
        }
    };

    // ==================== Toast 通知 ====================
    const ToastManager = {
        container: null,

        init() {
            this.container = document.createElement('div');
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        },

        show(message, type = 'info', duration = 3000) {
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.innerHTML = `
                <span>${message}</span>
            `;
            
            this.container.appendChild(toast);
            
            // 自动移除
            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(100%)';
                setTimeout(() => toast.remove(), 300);
            }, duration);
        }
    };

    // ==================== 时间格式化 ====================
    const TimeFormatter = {
        init() {
            this.updateTimes();
            // 每分钟更新一次
            setInterval(() => this.updateTimes(), 60000);
        },

        updateTimes() {
            document.querySelectorAll('[data-timestamp]').forEach(el => {
                const timestamp = el.getAttribute('data-timestamp');
                if (timestamp) {
                    el.textContent = this.formatTime(timestamp);
                }
            });
        },

        formatTime(timestamp) {
            const date = new Date(timestamp);
            const now = new Date();
            const diff = Math.floor((now - date) / 1000);

            if (diff < 60) return '刚刚';
            if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
            if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
            if (diff < 604800) return `${Math.floor(diff / 86400)} 天前`;
            
            return date.toLocaleDateString('zh-CN');
        }
    };

    // ==================== 平滑滚动 ====================
    const SmoothScroll = {
        init() {
            document.querySelectorAll('a[href^="#"]').forEach(anchor => {
                anchor.addEventListener('click', (e) => {
                    const targetId = anchor.getAttribute('href');
                    if (targetId === '#') return;
                    
                    const target = document.querySelector(targetId);
                    if (target) {
                        e.preventDefault();
                        target.scrollIntoView({ behavior: 'smooth' });
                    }
                });
            });
        }
    };

    // ==================== 确认对话框 ====================
    const ConfirmDialog = {
        confirm(message, onConfirm, onCancel) {
            if (window.confirm(message)) {
                onConfirm?.();
            } else {
                onCancel?.();
            }
        }
    };

    // ==================== 初始化 ====================
    document.addEventListener('DOMContentLoaded', () => {
        ThemeManager.init();
        ToastManager.init();
        TimeFormatter.init();
        SmoothScroll.init();

        // 暴露全局 API
        window.App = {
            showToast: (msg, type) => ToastManager.show(msg, type),
            confirm: (msg, onConfirm, onCancel) => ConfirmDialog.confirm(msg, onConfirm, onCancel),
            setTheme: (theme) => ThemeManager.setTheme(theme)
        };

        console.log('🚀 Agent Forum 应用已加载');
    });
})();
