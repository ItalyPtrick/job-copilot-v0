import type { InterviewStartResponse, InterviewAnswerResponse, InterviewEvaluateResponse } from '@/api/types'

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms))

export const mockStartResponse: InterviewStartResponse = {
  session_id: 'mock-session',
  question: {
    question: '请解释 Python 中的 GIL（全局解释器锁）是什么？它对多线程编程有什么影响？',
    category: 'Python 基础',
    difficulty: 'medium',
    difficulty_reason: '需要理解 CPython 实现细节',
    follow_up_hint: '可以追问如何绕过 GIL 限制',
    assessment_focus: '对 Python 运行时机制的理解深度',
  },
}

export const mockAnswerResponses: InterviewAnswerResponse[] = [
  {
    action: 'follow_up',
    reason: '回答涵盖了基本概念，需要深入追问',
    performance_signal: 'adequate',
    follow_up: '你提到了 GIL 会影响 CPU 密集型任务的并行性。那在实际项目中，你会用什么方式来绕过 GIL 的限制？请举一个具体的例子。',
  },
  {
    action: 'next_question',
    reason: '追问回答充分，进入下一题',
    performance_signal: 'good',
    question: {
      question: '请描述 FastAPI 的依赖注入系统是如何工作的？相比 Flask 有什么优势？',
      category: 'Web 框架',
      difficulty: 'medium',
      difficulty_reason: '需要对比两个框架的设计理念',
      follow_up_hint: '可以追问具体的依赖注入使用场景',
      assessment_focus: '对现代 Web 框架设计模式的理解',
    },
  },
  {
    action: 'complete',
    reason: '已完成所有题目',
    performance_signal: 'good',
  },
]

export const mockEvaluateResponse: InterviewEvaluateResponse = {
  overall_score: 7.5,
  summary: '候选人展现了扎实的 Python 基础和 Web 开发经验。对 GIL 机制有清晰理解，能结合实际场景给出解决方案。FastAPI 相关知识掌握良好，但在系统设计层面的深度可以进一步加强。',
  strengths: ['Python 基础扎实', 'Web 框架理解深入', '能结合实际项目举例'],
  improvements: ['系统设计思维', '性能优化经验', '分布式场景考虑不足'],
  items: [
    {
      question: '请解释 Python 中的 GIL（全局解释器锁）是什么？它对多线程编程有什么影响？',
      answer: '用户关于 GIL 的回答...',
      score: 8,
      feedback: '对 GIL 的概念解释清晰，能说明其对 CPU 密集型任务的影响，并给出了 multiprocessing 的替代方案。',
      category: 'Python 基础',
    },
    {
      question: '请描述 FastAPI 的依赖注入系统是如何工作的？相比 Flask 有什么优势？',
      answer: '用户关于 FastAPI 的回答...',
      score: 7,
      feedback: '能描述依赖注入的基本用法，但对其与 Flask 的对比不够深入，建议补充类型安全和自动文档生成方面的优势。',
      category: 'Web 框架',
    },
  ],
}

const answerIndexBySession = new Map<string, number>()

export async function getMockStartResponse(): Promise<InterviewStartResponse> {
  await delay(1500)
  const sessionId = `mock-session-${Date.now()}`
  answerIndexBySession.set(sessionId, 0)
  return { ...mockStartResponse, session_id: sessionId }
}

export async function getMockAnswerResponse(sessionId: string): Promise<InterviewAnswerResponse> {
  await delay(1500)
  const answerIndex = answerIndexBySession.get(sessionId) ?? 0
  const response = mockAnswerResponses[answerIndex] || mockAnswerResponses[mockAnswerResponses.length - 1]
  answerIndexBySession.set(sessionId, answerIndex + 1)
  return response
}

export async function getMockEvaluateResponse(sessionId: string): Promise<InterviewEvaluateResponse> {
  await delay(2000)
  answerIndexBySession.delete(sessionId)
  return mockEvaluateResponse
}
