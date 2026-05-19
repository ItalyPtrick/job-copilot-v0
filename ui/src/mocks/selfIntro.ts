import type { TaskResult } from '@/api/types'

export const mockSelfIntroResult: TaskResult<string> = {
  status: 'success',
  task_type: 'self_intro_generate',
  result:
    '您好，我是一名专注于 Python 后端开发的工程师，拥有 FastAPI 和微服务架构的实践经验。' +
    '在上一段实习中，我独立完成了基于 LangChain 的 RAG 问答系统搭建，涵盖文档解析、向量检索和流式输出全链路。' +
    '同时我熟悉 Docker 容器化部署和 CI/CD 流程，能够快速将原型推进到生产环境。' +
    '我对贵司的技术栈非常感兴趣，期待能在团队中贡献自己的后端工程能力。',
  error: null,
  retriever_context: null,
  trace: null,
}
