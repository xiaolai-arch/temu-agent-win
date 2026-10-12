@echo off
rem 每日 TEMU 同步体检（只读）。由计划任务 TEMU-Agent-DailySyncCheck 每天 08:37 调用。
rem 前提：Windows 已登录（需要真实浏览器窗口与桌面）。
cd /d D:\temu-agent
call claude -p "按照 .claude/skills/temu-sync-check/SKILL.md 定义的流程执行每日同步体检任务（只读，不点任何同步按钮），完成后简短汇报。" --permission-mode bypassPermissions --output-format text >> logs\daily-scheduled.log 2>&1
