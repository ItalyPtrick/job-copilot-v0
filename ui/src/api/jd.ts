import { request } from './client'
import type { TaskResult } from './types'
import { mockJDResult } from '@/mocks/jd'

interface JDAnalysisResult {
  hard_requirements: string[]
  core_skills: string[]
  bonus_skills: string[]
}

export async function analyzeJD(jdText: string, targetRole: string) {
  return request<TaskResult<JDAnalysisResult>>(
    '/api/task',
    {
      method: 'POST',
      body: {
        task_type: 'jd_analyze',
        payload: { jd_text: jdText, target_role: targetRole },
      },
    },
    () => mockJDResult
  )
}
