import { request } from './client'
import type { InterviewStartResponse, InterviewAnswerResponse, InterviewEvaluateResponse } from './types'
import { getMockStartResponse, getMockAnswerResponse, getMockEvaluateResponse } from '@/mocks/interview'

interface InterviewConfig {
  skill?: string
  total_questions?: number
  follow_up_count?: number
}

export async function startInterview(config: InterviewConfig) {
  return request<InterviewStartResponse>(
    '/api/interview/start',
    {
      method: 'POST',
      body: config,
    },
    getMockStartResponse
  )
}

export async function submitAnswer(sessionId: string, answer: string) {
  return request<InterviewAnswerResponse>(
    '/api/interview/answer',
    {
      method: 'POST',
      body: { session_id: sessionId, answer },
      preserve503: true,
    },
    () => getMockAnswerResponse(sessionId)
  )
}

export async function evaluateInterview(sessionId: string) {
  return request<InterviewEvaluateResponse>(
    '/api/interview/evaluate',
    {
      method: 'POST',
      body: { session_id: sessionId },
    },
    () => getMockEvaluateResponse(sessionId)
  )
}
