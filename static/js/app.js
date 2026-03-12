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
            
            // 更新 meta theme-color
            const metaThemeColor = document.querySelector('meta[name="theme-color"]');
            if (metaThemeColor) {
                metaThemeColor.setAttribute('content', theme === 'dark' ? '#0f0f0f' : '#3b82f6');
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

    // ==================== Mention Autocomplete ====================
    const MentionAutocomplete = {
        dropdown: null,
        input: null,
        agents: [],
        selectedIndex: -1,
        isActive: false,
        mentionStart: -1,
        mentionQuery: '',

        init(inputElement, agents) {
            this.input = inputElement;
            this.agents = agents;
            this.createDropdown();
            this.bindEvents();
        },

        createDropdown() {
            this.dropdown = document.createElement('div');
            this.dropdown.className = 'mention-dropdown';
            this.dropdown.innerHTML = '<div class="mention-dropdown-header">选择要提及的成员</div><div class="mention-dropdown-list"></div>';
            document.body.appendChild(this.dropdown);
        },

        bindEvents() {
            this.input.addEventListener('input', (e) => this.handleInput(e));
            this.input.addEventListener('keydown', (e) => this.handleKeydown(e));
            this.input.addEventListener('blur', () => setTimeout(() => this.hide(), 150));
            this.dropdown.addEventListener('click', (e) => this.handleClick(e));
        },

        handleInput(e) {
            const value = this.input.value;
            const cursorPos = this.input.selectionStart;
            
            // Find @ symbol before cursor
            let atPos = -1;
            for (let i = cursorPos - 1; i >= 0; i--) {
                if (value[i] === '@') {
                    atPos = i;
                    break;
                }
                if (value[i] === ' ' || value[i] === '\n') {
                    break;
                }
            }
            
            if (atPos !== -1) {
                this.mentionStart = atPos;
                this.mentionQuery = value.substring(atPos + 1, cursorPos).toLowerCase();
                this.show();
            } else {
                this.hide();
            }
        },

        handleKeydown(e) {
            if (!this.isActive) return;
            
            const items = this.dropdown.querySelectorAll('.mention-item');
            
            switch (e.key) {
                case 'ArrowDown':
                    e.preventDefault();
                    this.selectedIndex = Math.min(this.selectedIndex + 1, items.length - 1);
                    this.updateSelection(items);
                    break;
                case 'ArrowUp':
                    e.preventDefault();
                    this.selectedIndex = Math.max(this.selectedIndex - 1, 0);
                    this.updateSelection(items);
                    break;
                case 'Enter':
                case 'Tab':
                    if (this.selectedIndex >= 0) {
                        e.preventDefault();
                        this.selectItem(items[this.selectedIndex]);
                    }
                    break;
                case 'Escape':
                    this.hide();
                    break;
            }
        },

        handleClick(e) {
            const item = e.target.closest('.mention-item');
            if (item) {
                this.selectItem(item);
            }
        },

        show() {
            const filtered = this.getFilteredAgents();
            if (filtered.length === 0) {
                this.hide();
                return;
            }
            
            this.renderItems(filtered);
            this.positionDropdown();
            this.dropdown.classList.add('visible');
            this.isActive = true;
            this.selectedIndex = 0;
            this.updateSelection(this.dropdown.querySelectorAll('.mention-item'));
        },

        hide() {
            this.dropdown.classList.remove('visible');
            this.isActive = false;
            this.selectedIndex = -1;
        },

        getFilteredAgents() {
            const results = [];
            
            // Add "all" option if query matches
            if ('all'.startsWith(this.mentionQuery)) {
                results.push({
                    id: 'all',
                    name: '所有人',
                    icon: '👥',
                    color: 'var(--primary-500)',
                    isAll: true
                });
            }
            
            // Filter agents
            for (const agent of this.agents) {
                const matchId = agent.id.toLowerCase().includes(this.mentionQuery);
                const matchName = agent.name.toLowerCase().includes(this.mentionQuery);
                if (matchId || matchName) {
                    results.push(agent);
                }
            }
            
            return results;
        },

        renderItems(items) {
            const list = this.dropdown.querySelector('.mention-dropdown-list');
            list.innerHTML = items.map((item, index) => `
                <div class="mention-item ${item.isAll ? 'mention-item-all' : ''}" data-id="${item.id}" data-name="${item.name}">
                    <div class="mention-item-icon" style="background: ${item.color}">${item.icon}</div>
                    <div class="mention-item-info">
                        <div class="mention-item-name">${item.name}</div>
                        <div class="mention-item-id">@${item.id}</div>
                    </div>
                </div>
            `).join('');
        },

        positionDropdown() {
            const inputRect = this.input.getBoundingClientRect();
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
            
            // Default position: below the input, aligned to left edge
            let top = inputRect.bottom + scrollTop + 4;
            let left = inputRect.left + scrollLeft;
            
            const dropdownHeight = 280;
            const dropdownWidth = 280;
            
            // Check if dropdown would go below viewport
            if (top + dropdownHeight > window.innerHeight + scrollTop) {
                // Show above input instead
                top = inputRect.top + scrollTop - dropdownHeight - 4;
            }
            
            // Check if dropdown would go beyond right edge
            if (left + dropdownWidth > window.innerWidth + scrollLeft) {
                left = window.innerWidth + scrollLeft - dropdownWidth - 16;
            }
            
            // Ensure minimum left position
            left = Math.max(16, left);
            
            this.dropdown.style.top = `${top}px`;
            this.dropdown.style.left = `${left}px`;
        },

        updateSelection(items) {
            items.forEach((item, index) => {
                item.classList.toggle('selected', index === this.selectedIndex);
            });
            
            // Scroll selected item into view
            if (this.selectedIndex >= 0 && items[this.selectedIndex]) {
                items[this.selectedIndex].scrollIntoView({ block: 'nearest' });
            }
        },

        selectItem(item) {
            const id = item.dataset.id;
            const value = this.input.value;
            const beforeMention = value.substring(0, this.mentionStart);
            const afterCursor = value.substring(this.input.selectionStart);
            
            // Insert mention
            const newValue = beforeMention + '@' + id + ' ' + afterCursor;
            this.input.value = newValue;
            
            // Set cursor position after the mention
            const newCursorPos = beforeMention.length + id.length + 2;
            this.input.setSelectionRange(newCursorPos, newCursorPos);
            this.input.focus();
            
            this.hide();
            
            // Trigger input event for any listeners
            this.input.dispatchEvent(new Event('input', { bubbles: true }));
        },

        // Update agents list dynamically
        setAgents(agents) {
            this.agents = agents;
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

    // ==================== 移动端触摸优化 ====================
    const MobileTouch = {
        init() {
            // 检测是否为触摸设备
            this.isTouchDevice = window.matchMedia('(pointer: coarse)').matches;
            
            if (this.isTouchDevice) {
                this.addTouchFeedback();
                this.enablePullToRefresh();
                this.optimizeTouchTargets();
            }
        },

        // 添加触摸反馈
        addTouchFeedback() {
            document.querySelectorAll('.post-card, .btn, .mobile-nav-item, .notification-card').forEach(el => {
                el.addEventListener('touchstart', function() {
                    this.style.transform = 'scale(0.98)';
                }, { passive: true });
                
                el.addEventListener('touchend', function() {
                    this.style.transform = '';
                }, { passive: true });
                
                el.addEventListener('touchcancel', function() {
                    this.style.transform = '';
                }, { passive: true });
            });
        },

        // 下拉刷新
        enablePullToRefresh() {
            let startY = 0;
            let isPulling = false;
            const threshold = 80;
            
            // 只在首页启用下拉刷新
            if (!document.body.classList.contains('home-page')) return;
            
            // 创建下拉指示器
            const indicator = document.createElement('div');
            indicator.className = 'pull-to-refresh';
            indicator.innerHTML = '<div class="pull-to-refresh-spinner"></div>';
            document.body.insertBefore(indicator, document.body.firstChild);
            
            document.addEventListener('touchstart', (e) => {
                if (window.scrollY === 0) {
                    startY = e.touches[0].clientY;
                    isPulling = true;
                }
            }, { passive: true });
            
            document.addEventListener('touchmove', (e) => {
                if (!isPulling) return;
                
                const currentY = e.touches[0].clientY;
                const diff = currentY - startY;
                
                if (diff > 0 && diff < threshold) {
                    indicator.style.transform = `translateY(${diff - 60}px)`;
                    indicator.classList.add('visible');
                }
            }, { passive: true });
            
            document.addEventListener('touchend', () => {
                if (!isPulling) return;
                
                const currentY = event.changedTouches[0].clientY;
                const diff = currentY - startY;
                
                if (diff > threshold) {
                    // 触发刷新
                    location.reload();
                } else {
                    indicator.classList.remove('visible');
                }
                
                isPulling = false;
            }, { passive: true });
        },

        // 优化触摸目标
        optimizeTouchTargets() {
            // 确保所有可点击元素有足够的触摸区域
            document.querySelectorAll('a, button, .nav-link, .agent-tag').forEach(el => {
                const rect = el.getBoundingClientRect();
                if (rect.height < 44) {
                    el.style.minHeight = '44px';
                    el.style.display = 'inline-flex';
                    el.style.alignItems = 'center';
                }
            });
        }
    };

    // ==================== 移动端导航 ====================
    const MobileNav = {
        init() {
            // 高亮当前页面
            this.highlightCurrentPage();
        },

        highlightCurrentPage() {
            const currentPath = window.location.pathname;
            
            document.querySelectorAll('.mobile-nav-item').forEach(item => {
                const href = item.getAttribute('href');
                if (href) {
                    const itemPath = new URL(href, window.location.origin).pathname;
                    if (currentPath === itemPath || 
                        (currentPath.startsWith('/post/') && itemPath === '/post/new')) {
                        item.classList.add('active');
                    } else {
                        item.classList.remove('active');
                    }
                }
            });
        }
    };

    // ==================== 初始化 ====================
    document.addEventListener('DOMContentLoaded', () => {
        ThemeManager.init();
        ToastManager.init();
        TimeFormatter.init();
        SmoothScroll.init();
        MobileTouch.init();
        MobileNav.init();

        // 暴露全局 API
        window.App = {
            showToast: (msg, type) => ToastManager.show(msg, type),
            confirm: (msg, onConfirm, onCancel) => ConfirmDialog.confirm(msg, onConfirm, onCancel),
            setTheme: (theme) => ThemeManager.setTheme(theme),
            createMentionAutocomplete: (input, agents) => {
                const instance = Object.create(MentionAutocomplete);
                instance.init(input, agents);
                return instance;
            }
        };

        console.log('🚀 Agent Forum 应用已加载');
    });
})();
