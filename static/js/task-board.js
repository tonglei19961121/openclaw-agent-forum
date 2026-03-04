/**
 * Agent Forum - 任务状态板组件
 */
(function() {
    'use strict';

    // 状态图标映射
    const statusIcons = {
        todo: '🟡',
        doing: '🔵',
        done: '✅',
        cancelled: '⛔'
    };

    // 状态文本映射
    const statusText = {
        todo: '待处理',
        doing: '进行中',
        done: '已完成',
        cancelled: '已取消'
    };

    // Agent 名称映射（从全局变量获取）
    function getAgentName(agentId) {
        if (window.AGENTS && window.AGENTS[agentId]) {
            return window.AGENTS[agentId].name;
        }
        return agentId;
    }

    // 加载任务列表
    async function loadTasks(postId) {
        const taskList = document.getElementById('task-list');
        const taskCount = document.getElementById('task-count');
        
        try {
            const response = await fetch(`/api/posts/${postId}/tasks`);
            const data = await response.json();
            
            if (data.tasks && data.tasks.length > 0) {
                renderTasks(data.tasks);
                taskCount.textContent = `(${data.stats.todo} 待处理 / ${data.stats.total} 总计)`;
            } else {
                taskList.innerHTML = `
                    <div class="task-empty">
                        <p>暂无任务分配</p>
                        <p class="task-hint">使用 <code>/assign @agent 任务描述</code> 创建任务</p>
                    </div>
                `;
                taskCount.textContent = '(0)';
            }
        } catch (error) {
            console.error('加载任务失败:', error);
            taskList.innerHTML = `
                <div class="task-error">
                    <p>加载任务失败</p>
                    <button onclick="location.reload()">重试</button>
                </div>
            `;
        }
    }

    // 渲染任务列表
    function renderTasks(tasks) {
        const taskList = document.getElementById('task-list');
        
        const html = tasks.map(task => `
            <div class="task-item task-${task.status}" data-task-id="${task.task_id}">
                <div class="task-status-icon">${statusIcons[task.status]}</div>
                <div class="task-content">
                    <div class="task-title">${escapeHtml(task.title)}</div>
                    <div class="task-meta">
                        <span class="task-assignee">@${getAgentName(task.assignee)}</span>
                        ${task.deadline ? `<span class="task-deadline">📅 ${formatDate(task.deadline)}</span>` : ''}
                        <span class="task-status">${statusText[task.status]}</span>
                    </div>
                </div>
                <div class="task-actions">
                    ${task.status !== 'done' ? `
                        <button class="task-btn task-btn-done" onclick="updateTaskStatus('${task.task_id}', 'done')" title="标记完成">
                            ✓
                        </button>
                    ` : ''}
                    ${task.status === 'todo' ? `
                        <button class="task-btn task-btn-doing" onclick="updateTaskStatus('${task.task_id}', 'doing')" title="开始处理">
                            ▶
                        </button>
                    ` : ''}
                </div>
            </div>
        `).join('');
        
        taskList.innerHTML = html;
    }

    // 更新任务状态
    window.updateTaskStatus = async function(taskId, status) {
        try {
            const response = await fetch(`/api/tasks/${taskId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ status })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // 重新加载任务列表
                const taskBoard = document.getElementById('task-board');
                const postId = taskBoard.dataset.postId;
                loadTasks(postId);
                
                // 显示提示
                if (window.App && window.App.showToast) {
                    window.App.showToast('任务状态已更新', 'success');
                }
            } else {
                if (window.App && window.App.showToast) {
                    window.App.showToast(data.error || '更新失败', 'error');
                }
            }
        } catch (error) {
            console.error('更新任务状态失败:', error);
            if (window.App && window.App.showToast) {
                window.App.showToast('网络错误', 'error');
            }
        }
    };

    // HTML 转义
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // 格式化日期
    function formatDate(dateStr) {
        const date = new Date(dateStr);
        const now = new Date();
        const diff = date - now;
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        
        if (days < 0) {
            return '已逾期';
        } else if (days === 0) {
            return '今天';
        } else if (days === 1) {
            return '明天';
        } else {
            return `${date.getMonth() + 1}/${date.getDate()}`;
        }
    }

    // 初始化
    document.addEventListener('DOMContentLoaded', function() {
        const taskBoard = document.getElementById('task-board');
        if (taskBoard) {
            const postId = taskBoard.dataset.postId;
            loadTasks(postId);
        }
    });
})();
