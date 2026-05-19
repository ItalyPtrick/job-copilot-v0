import type { ResumeStatus, ResumeReport } from '@/api/types'

export const mockUploadResponse = {
  resume_id: 'mock-resume-123',
  status: 'analyzing' as const,
}

export function getMockStatus(resumeId: string): ResumeStatus {
  return {
    resume_id: resumeId,
    status: 'completed',
  }
}

export const mockReportResponse: ResumeReport = {
  resume_id: 'mock-resume-123',
  overall_score: 7.2,
  summary:
    '简历整体结构清晰，技术栈描述具体。建议在项目经历中增加量化成果（如性能提升百分比、用户量级），并突出与目标岗位的技能匹配度。',
  sections: [
    {
      name: '基本信息',
      score: 8,
      feedback: '联系方式完整，求职意向明确。',
      suggestions: ['可补充 GitHub/博客链接展示技术深度'],
    },
    {
      name: '教育背景',
      score: 7,
      feedback: '学历信息完整。',
      suggestions: ['如有相关课程或 GPA 优势可补充'],
    },
    {
      name: '项目经历',
      score: 6.5,
      feedback: '项目描述偏叙述性，缺少量化指标。',
      suggestions: [
        '每个项目补充 1-2 个量化成果',
        '使用 STAR 法则重构描述',
        '突出技术选型的决策过程',
      ],
    },
    {
      name: '技能清单',
      score: 8,
      feedback: '技术栈覆盖面广，与目标岗位匹配度高。',
      suggestions: ['按熟练度分级展示', '移除与目标岗位无关的技能'],
    },
  ],
}

/**
 * 模拟上传后 3 秒完成分析
 */
export function mockPollStatus(
  resumeId: string,
  onStatusChange: (status: ResumeStatus) => void,
  onComplete: () => void
): { cancel: () => void } {
  let cancelled = false

  // 模拟 analyzing 状态
  setTimeout(() => {
    if (cancelled) return
    onStatusChange({ resume_id: resumeId, status: 'analyzing' })
  }, 1000)

  // 模拟 completed 状态
  setTimeout(() => {
    if (cancelled) return
    onStatusChange({ resume_id: resumeId, status: 'completed' })
    onComplete()
  }, 3000)

  return {
    cancel: () => {
      cancelled = true
    },
  }
}
