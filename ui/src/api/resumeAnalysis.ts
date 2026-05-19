import { request } from './client'
import type { ResumeStatus, ResumeReport } from './types'
import { useMockModeStore } from '@/stores/mockMode'
import {
  mockUploadResponse,
  mockReportResponse,
  mockPollStatus,
} from '@/mocks/resumeAnalysis'

interface UploadResponse {
  resume_id: string
  status: 'analyzing'
}

export async function uploadResume(file: File, targetRole?: string) {
  const formData = new FormData()
  formData.append('file', file)
  if (targetRole) formData.append('target_role', targetRole)

  return request<UploadResponse>(
    '/api/resume/upload',
    { method: 'POST', body: formData },
    () => mockUploadResponse
  )
}

export async function getResumeStatus(resumeId: string) {
  return request<ResumeStatus>(
    `/api/resume/${resumeId}/status`,
    { method: 'GET' },
    () => ({ resume_id: resumeId, status: 'completed' as const })
  )
}

export async function getResumeReport(resumeId: string) {
  return request<ResumeReport>(
    `/api/resume/${resumeId}/report`,
    { method: 'GET' },
    () => mockReportResponse
  )
}

/**
 * 轮询简历分析状态，2 秒间隔，60 秒硬性超时
 * mock 模式下模拟 3 秒完成
 */
export function pollResumeStatus(
  resumeId: string,
  onStatusChange: (status: ResumeStatus) => void,
  onComplete: (status: ResumeStatus) => void,
  onTimeout: () => void
): { cancel: () => void } {
  // mock 短路
  if (useMockModeStore.getState().isMockMode) {
    return mockPollStatus(resumeId, onStatusChange, () => {
      onComplete({ resume_id: resumeId, status: 'completed' })
    })
  }

  let cancelled = false
  let intervalId: ReturnType<typeof setInterval>
  const timeoutId = setTimeout(() => {
    cancelled = true
    clearInterval(intervalId)
    onTimeout()
  }, 60_000)

  intervalId = setInterval(async () => {
    if (cancelled) return
    try {
      const status = await getResumeStatus(resumeId)
      onStatusChange(status)
      if (status.status === 'completed' || status.status === 'failed') {
        cancelled = true
        clearInterval(intervalId)
        clearTimeout(timeoutId)
        onComplete(status)
      }
    } catch {
      // 单次轮询失败不中断，继续下一次
    }
  }, 2000)

  return {
    cancel: () => {
      cancelled = true
      clearInterval(intervalId)
      clearTimeout(timeoutId)
    },
  }
}
