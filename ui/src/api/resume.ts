import { request } from './client'
import type { TaskResult } from './types'
import { mockResumeOptimizeResult } from '@/mocks/resume'

export type ResumeOptimizeResult = string | { optimized: string }

export async function optimizeResume(
  resumeItem: string,
  targetKeywords: string[],
  roleSummary: string
) {
  return request<TaskResult<ResumeOptimizeResult>>(
    '/api/task',
    {
      method: 'POST',
      body: {
        task_type: 'resume_optimize',
        payload: {
          resume_item: resumeItem,
          target_jd_keywords: targetKeywords,
          role_summary: roleSummary,
        },
      },
    },
    () => mockResumeOptimizeResult
  )
}
