import { useState } from 'react'
import type { InterviewEvaluateResponse } from '@/api/types'

interface EvaluationReportProps {
  data: InterviewEvaluateResponse
}

export function EvaluationReport({ data }: EvaluationReportProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null)
  const scoreCircleLength = 2 * Math.PI * 40

  function getScoreColor(score: number) {
    if (score >= 7) return 'text-[#3D8C5C] dark:text-[#5BA97A]'
    if (score >= 5) return 'text-[#C4841D] dark:text-[#E0A03C]'
    return 'text-[#C53030] dark:text-[#E05252]'
  }

  function getScoreBarColor(score: number) {
    if (score >= 7) return 'bg-[#3D8C5C] dark:bg-[#5BA97A]'
    if (score >= 5) return 'bg-[#C4841D] dark:bg-[#E0A03C]'
    return 'bg-[#C53030] dark:bg-[#E05252]'
  }

  return (
    <div className="space-y-6">
      {/* 总分 */}
      <div className="flex items-center gap-6 rounded-[14px] border border-input bg-card p-6">
        <div className="relative flex h-24 w-24 items-center justify-center">
          <svg className="h-24 w-24 -rotate-90" viewBox="0 0 96 96">
            <circle
              cx="48" cy="48" r="40"
              fill="none"
              stroke="currentColor"
              strokeWidth="8"
              className="text-input"
            />
            <circle
              cx="48" cy="48" r="40"
              fill="none"
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={`${(data.overall_score / 10) * scoreCircleLength} ${scoreCircleLength}`}
              className="text-[#C8553A] dark:text-[#DA7756]"
              stroke="currentColor"
            />
          </svg>
          <span className={`absolute text-[28px] font-bold ${getScoreColor(data.overall_score)}`}>
            {data.overall_score}
          </span>
        </div>
        <div className="flex-1">
          <p className="text-[15px] leading-[1.6] text-foreground">{data.summary}</p>
        </div>
      </div>

      {/* 强项 / 待改进 */}
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-[14px] border border-input bg-card p-5">
          <h3 className="mb-3 text-[18px] font-semibold text-foreground">强项</h3>
          <div className="flex flex-wrap gap-2">
            {data.strengths.map((s, i) => (
              <span
                key={i}
                className="rounded-[6px] bg-[rgba(61,140,92,0.1)] px-3 py-1 text-[13px] text-[#3D8C5C] dark:bg-[rgba(91,169,122,0.15)] dark:text-[#5BA97A]"
              >
                {s}
              </span>
            ))}
          </div>
        </div>
        <div className="rounded-[14px] border border-input bg-card p-5">
          <h3 className="mb-3 text-[18px] font-semibold text-foreground">待改进</h3>
          <div className="flex flex-wrap gap-2">
            {data.improvements.map((s, i) => (
              <span
                key={i}
                className="rounded-[6px] bg-[rgba(196,132,29,0.1)] px-3 py-1 text-[13px] text-[#C4841D] dark:bg-[rgba(224,160,60,0.15)] dark:text-[#E0A03C]"
              >
                {s}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* 逐题详情 */}
      <div className="space-y-3">
        <h3 className="text-[18px] font-semibold text-foreground">逐题详情</h3>
        {data.items.map((item, i) => (
          <div key={i} className="rounded-[14px] border border-input bg-card">
            <button
              onClick={() => setExpandedIndex(expandedIndex === i ? null : i)}
              className="flex w-full items-center justify-between p-4 text-left"
            >
              <div className="flex-1">
                <span className="text-[13px] text-muted-foreground">{item.category}</span>
                <p className="text-[15px] text-foreground">{item.question}</p>
              </div>
              <div className="ml-4 flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <div className="h-2 w-16 overflow-hidden rounded-full bg-input">
                    <div
                      className={`h-full rounded-full ${getScoreBarColor(item.score)}`}
                      style={{ width: `${(item.score / 10) * 100}%` }}
                    />
                  </div>
                  <span className={`text-[15px] font-semibold ${getScoreColor(item.score)}`}>
                    {item.score}
                  </span>
                </div>
                <svg
                  className={`h-4 w-4 text-muted-foreground transition-transform duration-200 ${expandedIndex === i ? 'rotate-180' : ''}`}
                  fill="none" viewBox="0 0 24 24" stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </div>
            </button>
            {expandedIndex === i && (
              <div className="border-t border-input px-4 py-4 space-y-3">
                <div>
                  <span className="text-[13px] font-medium text-muted-foreground">回答</span>
                  <p className="mt-1 text-[15px] leading-[1.6] text-foreground">{item.answer}</p>
                </div>
                <div>
                  <span className="text-[13px] font-medium text-muted-foreground">反馈</span>
                  <p className="mt-1 text-[15px] leading-[1.6] text-foreground">{item.feedback}</p>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
