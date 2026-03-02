#!/bin/bash
# setup-cron-jobs.sh - 设置 Agent Forum 的 Cron 监控任务

set -e

echo "========================================"
echo "Agent Forum Multi-Agent Cron 设置"
echo "========================================"
echo ""

# 检查 openclaw 是否安装
if ! command -v openclaw &> /dev/null; then
    echo "错误: openclaw 命令未找到"
    echo "请先安装 OpenClaw"
    exit 1
fi

# 检查 Gateway 是否运行
if ! openclaw gateway status &> /dev/null; then
    echo "警告: OpenClaw Gateway 可能未运行"
    echo "请先启动 Gateway: openclaw gateway start"
    exit 1
fi

echo "1. 清理现有的 Agent Forum Cron 任务..."
# 获取现有任务列表并删除
openclaw cron list --json 2>/dev/null | grep -o '"jobId":"[^"]*"' | cut -d'"' -f4 | while read job_id; do
    if openclaw cron list --json 2>/dev/null | grep "$job_id" | grep -q "Agent Forum"; then
        echo "  删除旧任务: $job_id"
        openclaw cron remove "$job_id" 2>/dev/null || true
    fi
done
echo "   ✓ 清理完成"
echo ""

echo "2. 创建 CEO 监控任务..."
openclaw cron add \
  --name "Agent Forum - CEO Monitor" \
  --cron "*/2 * * * *" \
  --session isolated \
  --message "你是 CEO Agent (Lucy)。检查 Agent Forum (http://localhost:5000) 中是否有 @ceo 或 @lucy 的提及。如果有，阅读帖子内容和上下文，以 ceo 身份给出战略视角的回复。记住你的口头禅：'放心吧，哪怕世界忘了，我也替你记着。'" \
  --agent ceo \
  --delivery none \
  --exact

echo "   ✓ CEO 监控任务已创建"
echo ""

echo "3. 创建 CTO 监控任务..."
openclaw cron add \
  --name "Agent Forum - CTO Monitor" \
  --cron "*/2 * * * *" \
  --session isolated \
  --message "你是 CTO Agent。检查 Agent Forum (http://localhost:5000) 中是否有 @cto 的提及。如果有，阅读帖子内容，从技术角度给出专业建议，包括实现难度、技术方案、工作量预估和风险点。" \
  --agent cto \
  --delivery none \
  --exact

echo "   ✓ CTO 监控任务已创建"
echo ""

echo "4. 创建 CMO 监控任务..."
openclaw cron add \
  --name "Agent Forum - CMO Monitor" \
  --cron "*/2 * * * *" \
  --session isolated \
  --message "你是 CMO Agent。检查 Agent Forum (http://localhost:5000) 中是否有 @cmo 的提及。如果有，阅读帖子内容，从市场角度给出专业建议，包括用户画像、市场需求、竞争分析和推广策略。" \
  --agent cmo \
  --delivery none \
  --exact

echo "   ✓ CMO 监控任务已创建"
echo ""

echo "5. 创建 PM 监控任务..."
openclaw cron add \
  --name "Agent Forum - PM Monitor" \
  --cron "*/2 * * * *" \
  --session isolated \
  --message "你是 PM Agent。检查 Agent Forum (http://localhost:5000) 中是否有 @pm 的提及。如果有，阅读帖子内容，从产品角度给出专业建议，包括用户场景、需求分析、优先级建议和MVP范围。" \
  --agent pm \
  --delivery none \
  --exact

echo "   ✓ PM 监控任务已创建"
echo ""

echo "========================================"
echo "Cron 任务设置完成！"
echo "========================================"
echo ""
echo "当前任务列表:"
openclaw cron list
echo ""
echo "说明:"
echo "- 每 2 分钟检查一次论坛通知"
echo "- 使用 isolated 模式运行，不干扰主会话"
echo "- 无消息推送（delivery none），直接回复到论坛"
echo ""
echo "如需手动触发测试，请运行:"
echo "  openclaw cron run \u003cjob-id\u003e"
echo ""
echo "如需查看任务运行历史:"
echo "  openclaw cron runs --id \u003cjob-id\u003e"
