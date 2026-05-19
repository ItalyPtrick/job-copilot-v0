import { useState, useEffect, useRef } from 'react'
import { Upload } from 'lucide-react'
import { uploadResume, getResumeReport, pollResumeStatus } from '@/api/resumeAnalysis'
import type { ResumeReport } from '@/api/types'
import { SkeletonBlock } from '@/components/SkeletonBlock'

type PageState = 'idle' | 'uploading' | 'analyzing' | 'done' | 'error'

const MAX_FILE_SIZE = 10 * 1024 * 1024

function scoreColor(score: number): string {
  if (score >= 7) return 'text-[#3D8C5C] dark:text-[#5BA97A]'
  if (score >= 5) return 'text-[#C4841D] dark:text-[#E0A03C]'
  return 'text-[#C53030] dark:text-[#E05252]'
}

export function ResumeAnalysisPage() {
  const [state, setState] = useState<PageState>('idle')
  const [targetRole, setTargetRole] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [report, setReport] = useState<ResumeReport | null>(null)
  const cancelRef = useRef<{ cancel: () => void } | null>(null)

  useEffect(() => {
    return () => {
      cancelRef.current?.cancel()
    }
  }, [])

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0]
    if (!selected) return
    if (selected.size > MAX_FILE_SIZE) {
      setError('文件大小不能超过 10MB')
      setFile(null)
      return
    }
    setError(null)
    setFile(selected)
  }

  async function handleUpload() {
    if (!file) return

    setState('uploading')
    setError(null)
    setReport(null)

    try {
      const res = await uploadResume(file, targetRole || undefined)
      setState('analyzing')

      const poll = pollResumeStatus(
        res.resume_id,
        () => {},
        async (status) => {
          if (status.status === 'completed') {
            try {
              const r = await getResumeReport(res.resume_id)
              setReport(r)
              setState('done')
            } catch {
              setError('获取报告失败')
              setState('error')
            }
          } else {
            setError(status.error || '分析失败')
            setState('error')
          }
        },
        () => {
          setError('分析超时，请重试')
          setState('error')
        }
      )
      cancelRef.current = poll
    } catch (err) {
      setError(err instanceof Error ? err.message : '上传失败')
      setState('error')
    }
  }

  function handleRetry() {
    setState('idle')
    setError(null)
    setFile(null)
    setReport(null)
  }

  return (
    <div className="space-y-6">
      <h1 className="text-[28px] font-semibold leading-[1.2] tracking-[-0.015em] text-foreground">
        简历分析
      </h1>

      {state === 'idle' && !report && (
        <p className="text-[15px] text-muted-foreground">
          上传简历文件，获取结构化分析报告和改进建议
        </p>
      )}

      {/* 上传表单 */}
      {(state === 'idle' || state === 'error') && (
        <div className="space-y-4">
          <div>
            <label className="mb-2 block text-[15px] text-foreground">简历文件</label>
            <label className="flex h-[120px] cursor-pointer items-center justify-center rounded-[8px] border-2 border-dashed border-input bg-background transition-colors duration-150 hover:border-foreground">
              <input
                type="file"
                accept=".pdf,.docx,.txt"
                onChange={handleFileChange}
                className="hidden"
              />
              <div className="flex flex-col items-center gap-2 text-muted-foreground">
                <Upload size={20} />
                <span className="text-[15px]">
                  {file ? file.name : '点击选择文件（PDF / DOCX / TXT）'}
                </span>
              </div>
            </label>
          </div>

          <div>
            <label className="mb-2 block text-[15px] text-foreground">
              目标岗位<span className="text-muted-foreground">（可选）</span>
            </label>
            <input
              type="text"
              value={targetRole}
              onChange={(e) => setTargetRole(e.target.value)}
              placeholder="如：Python 后端开发工程师"
              className="h-10 w-full rounded-[8px] border border-input bg-background px-4 text-[15px] text-foreground placeholder:text-[#9C9690] transition-colors duration-150 focus:border-foreground focus:outline-none"
            />
          </div>

          <button
            type="button"
            onClick={handleUpload}
            disabled={!file}
            className="inline-flex h-10 items-center rounded-[10px] bg-primary px-6 text-[15px] font-medium text-primary-foreground transition-colors duration-150 hover:bg-[#333] disabled:cursor-not-allowed disabled:bg-[#E8E4DD] disabled:text-[#9C9690] dark:hover:bg-[rgba(255,255,255,0.9)] dark:disabled:bg-[#3D3A35]"
          >
            开始分析
          </button>
        </div>
      )}

      {/* 分析中 */}
      {(state === 'uploading' || state === 'analyzing') && (
        <div className="space-y-4">
          <p className="text-[15px] text-muted-foreground">
            {state === 'uploading' ? '上传中...' : '分析中，请稍候...'}
          </p>
          <SkeletonBlock lines={6} />
        </div>
      )}

      {/* 错误 */}
      {error && (
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-[rgba(197,48,48,0.1)] px-4 py-3 text-[15px] text-[#C53030] dark:text-[#E05252]">
            {error}
          </div>
          <button
            type="button"
            onClick={handleRetry}
            className="rounded-[10px] border border-input px-4 py-2 text-[15px] text-foreground transition-colors duration-150 hover:bg-[rgba(0,0,0,0.04)] dark:hover:bg-[rgba(255,255,255,0.04)]"
          >
            重试
          </button>
        </div>
      )}

      {/* 报告 */}
      {report && state === 'done' && (
        <div className="space-y-5">
          {/* 总分 + 总结 */}
          <div className="rounded-[14px] border border-input bg-card p-5">
            <div className="mb-3 flex items-baseline gap-3">
              <span className={`text-[36px] font-bold leading-none ${scoreColor(report.overall_score)}`}>
                {report.overall_score.toFixed(1)}
              </span>
              <span className="text-[15px] text-muted-foreground">/ 10</span>
            </div>
            <p className="text-[15px] leading-[1.6] text-foreground">{report.summary}</p>
          </div>

          {/* 各 section */}
          {report.sections.map((section) => (
            <div
              key={section.name}
              className="rounded-[14px] border border-input bg-card p-5"
            >
              <div className="mb-2 flex items-baseline justify-between">
                <h3 className="text-[18px] font-semibold text-foreground">{section.name}</h3>
                <span className={`text-[18px] font-semibold ${scoreColor(section.score)}`}>
                  {section.score}
                </span>
              </div>
              <p className="mb-3 text-[15px] leading-[1.6] text-foreground">
                {section.feedback}
              </p>
              {section.suggestions.length > 0 && (
                <ul className="space-y-1.5 pl-5">
                  {section.suggestions.map((s, i) => (
                    <li
                      key={i}
                      className="list-disc text-[15px] leading-[1.6] text-muted-foreground"
                    >
                      {s}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}

          <button
            type="button"
            onClick={handleRetry}
            className="rounded-[10px] border border-input px-4 py-2 text-[15px] text-foreground transition-colors duration-150 hover:bg-[rgba(0,0,0,0.04)] dark:hover:bg-[rgba(255,255,255,0.04)]"
          >
            分析另一份简历
          </button>
        </div>
      )}
    </div>
  )
}
