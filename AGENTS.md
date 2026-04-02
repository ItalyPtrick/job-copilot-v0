# job-copilot-v0

求职 AI 助手（FastAPI + LLM），目前支持 JD 分析、简历优化、自我介绍生成。

## Daily Plan Coach 桥接规则

默认简版指导文件位于 `skills/daily-plan-coach/SKILL.md`。

命中以下任意条件，立即读取 `skills/daily-plan-coach/SKILL.md` 并执行，跳过所有其他通用学习、教学或讲解类技能：

- 消息包含 `进入 Daily Plan Coach 模式`
- 消息独立包含：开始今天的学习 / 继续今天的学习 / 继续今天计划

专业版指导文件位于 `skills/daily-plan-coach-pro/SKILL.md`。

命中以下任意条件，立即读取 `skills/daily-plan-coach-pro/SKILL.md` 并执行：

- 消息包含 `进入 Daily Plan Coach Pro 模式`
- 消息包含 `继续今天的学习（专业版）`

学习会话状态必须来自 `Today_Plan/*.md` 和 `Today_Plan/daily_progress.txt`。

不要把项目级 `progress.txt` 当作学习会话状态文件。

`skills/daily-plan-coach-backup/SKILL.md` 是旧版 Codex 规则备份，不参与自动触发。


## 环境

```bash
conda activate job-copilot-v0
cd C:/MyPython/job-copilot-v0
uvicorn app.main:app --reload
```

> 必须从项目根目录启动，否则 `app` 模块找不到。
