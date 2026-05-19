import type { TaskResult } from '@/api/types'

export const mockResumeOptimizeResult: TaskResult<string> = {
  status: 'success',
  task_type: 'resume_optimize',
  result:
    '使用 FastAPI 框架独立设计并实现了 RESTful API 服务，涵盖用户认证、数据 CRUD、异步任务调度等核心模块。通过引入 Pydantic 数据校验和 SQLAlchemy ORM，将接口响应时间优化至 50ms 以内，服务可用性达 99.5%。主导 CI/CD 流水线搭建（GitHub Actions + Docker），实现自动化测试覆盖率 85% 以上。',
  error: null,
  retriever_context: null,
  trace: null,
}

export const mockResumeOriginal =
  '负责公司后端开发工作，完成了一些功能模块。使用 Python 进行开发，参与了接口设计和数据库操作。'
