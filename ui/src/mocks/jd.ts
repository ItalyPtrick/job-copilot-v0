import type { TaskResult } from '@/api/types'

interface JDAnalysisResult {
  hard_requirements: string[]
  core_skills: string[]
  bonus_skills: string[]
}

export const mockJDResult: TaskResult<JDAnalysisResult> = {
  status: 'success',
  task_type: 'jd_analyze',
  result: {
    hard_requirements: [
      '熟悉 Python 基础语法',
      '了解 Git 版本控制',
      '有 Web 后端开发经验',
      '熟悉 RESTful API 设计',
    ],
    core_skills: ['Python', 'Git', 'FastAPI', 'SQL', 'Linux'],
    bonus_skills: ['Docker', 'CI/CD', 'Redis', 'LangChain'],
  },
  error: null,
  retriever_context: null,
  trace: null,
}
