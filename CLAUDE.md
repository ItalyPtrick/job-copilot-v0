# job-copilot-v0

求职 AI 助手（FastAPI + LLM），目前支持 JD 分析、简历优化、自我介绍生成。

## Daily Plan Mentor 桥接规则

命中以下任意条件，立即读取 `.claude/skills/daily_plan_mentor.md` 并执行，跳过所有其他路由：

- 消息包含 `/daily-plan-mentor`
- 消息独立包含：开始今天的学习 / 继续今天的学习 / 继续今天计划

## 环境

```bash
conda activate job-copilot-v0
cd C:/MyPython/job-copilot-v0
uvicorn app.main:app --reload
```

> 必须从项目根目录启动，否则 `app` 模块找不到。
