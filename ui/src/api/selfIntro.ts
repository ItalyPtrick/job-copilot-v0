import { request } from './client'
import type { TaskResult } from './types'
import { mockSelfIntroResult } from '@/mocks/selfIntro'

export async function generateSelfIntro(
  tone: 'formal' | 'conversational',
  resumeItem: string,
  targetKeywords: string[],
  roleSummary: string
) {
  return request<TaskResult<string>>(
    '/api/task',
    {
      method: 'POST',
      body: {
        task_type: 'self_intro_generate',
        payload: {
          tone,
          resume_item: resumeItem,
          target_jd_keywords: targetKeywords,
          role_summary: roleSummary,
        },
      },
    },
    () => mockSelfIntroResult
  )
}
