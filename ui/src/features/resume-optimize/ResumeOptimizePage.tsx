import { useState } from 'react'
import type { ReactNode } from 'react'
import { optimizeResume } from '@/api/resume'
import type { ResumeOptimizeResult } from '@/api/resume'
import { mockResumeOriginal } from '@/mocks/resume'
import { SkeletonBlock } from '@/components/SkeletonBlock'
import { useToast } from '@/components/Toast'

export function ResumeOptimizePage() {
  const [resumeItem, setResumeItem] = useState('')
  const [keywords, setKeywords] = useState('')
  const [roleSummary, setRoleSummary] = useState('')
  const [loading, setLoading] = useState(false)
  const [original, setOriginal] = useState<string | null>(null)
  const [optimized, setOptimized] = useState<string | null>(null)
  const toast = useToast()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!resumeItem.trim()) return

    setLoading(true)
    setOriginal(null)
    setOptimized(null)

    const keywordList = keywords
      .split(/[,，]/)
      .map((k) => k.trim())
      .filter(Boolean)

    try {
      const res = await optimizeResume(resumeItem, keywordList, roleSummary)
      const optimizedText = getOptimizedText(res.result)
      if (res.status === 'success' && optimizedText) {
        setOriginal(resumeItem)
        setOptimized(optimizedText)
      } else {
        toast.error(res.error?.error_message || '优化失败')
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '请求失败')
    } finally {
      setLoading(false)
    }
  }

  function fillExample() {
    setResumeItem(mockResumeOriginal)
    setKeywords('FastAPI, Python, RESTful API')
    setRoleSummary('Python后端开发工程师')
  }

  function clearForm() {
    setResumeItem('')
    setKeywords('')
    setRoleSummary('')
    setOriginal(null)
    setOptimized(null)
  }

  function getOptimizedText(result: ResumeOptimizeResult | null) {
    if (typeof result === 'string') return result
    return result?.optimized || ''
  }

  function renderDiffText(before: string, after: string): ReactNode {
    let prefixLength = 0
    while (
      prefixLength < before.length &&
      prefixLength < after.length &&
      before[prefixLength] === after[prefixLength]
    ) {
      prefixLength += 1
    }

    let suffixLength = 0
    while (
      suffixLength < before.length - prefixLength &&
      suffixLength < after.length - prefixLength &&
      before[before.length - 1 - suffixLength] === after[after.length - 1 - suffixLength]
    ) {
      suffixLength += 1
    }

    const prefix = after.slice(0, prefixLength)
    const changed = after.slice(prefixLength, after.length - suffixLength)
    const suffix = suffixLength ? after.slice(after.length - suffixLength) : ''

    return (
      <>
        {prefix}
        {changed && <mark className="rounded bg-[rgba(200,85,58,0.12)] px-1 text-foreground">{changed}</mark>}
        {suffix}
      </>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-[28px] font-semibold leading-[1.2] tracking-[-0.015em] text-foreground">
        简历优化
      </h1>

      {!original && !loading && (
        <>
          {!resumeItem && (
            <p className="text-[15px] text-muted-foreground">
              粘贴简历片段，对比优化前后效果
            </p>
          )}
          <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-2 block text-[15px] text-foreground">
              简历片段
            </label>
            <textarea
              value={resumeItem}
              onChange={(e) => setResumeItem(e.target.value)}
              placeholder="粘贴一段简历经历描述..."
              className="min-h-[120px] w-full rounded-[8px] border border-input bg-background px-4 py-3 text-[15px] text-foreground placeholder:text-[#9C9690] transition-colors duration-150 focus:border-foreground focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-2 block text-[15px] text-foreground">
              目标关键词（逗号分隔）
            </label>
            <input
              type="text"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="如：FastAPI, Python, RESTful API"
              className="h-10 w-full rounded-[8px] border border-input bg-background px-4 text-[15px] text-foreground placeholder:text-[#9C9690] transition-colors duration-150 focus:border-foreground focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-2 block text-[15px] text-foreground">
              目标岗位
            </label>
            <input
              type="text"
              value={roleSummary}
              onChange={(e) => setRoleSummary(e.target.value)}
              placeholder="如：Python后端开发工程师"
              className="h-10 w-full rounded-[8px] border border-input bg-background px-4 text-[15px] text-foreground placeholder:text-[#9C9690] transition-colors duration-150 focus:border-foreground focus:outline-none"
            />
          </div>

          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={loading || !resumeItem.trim()}
              className="inline-flex h-10 items-center rounded-[10px] bg-primary px-4 text-[15px] font-medium text-primary-foreground transition-colors duration-150 hover:bg-[#333] disabled:cursor-not-allowed disabled:bg-[#E8E4DD] disabled:text-[#9C9690] dark:hover:bg-[rgba(255,255,255,0.9)] dark:disabled:bg-[#3D3A35]"
            >
              {loading ? '优化中...' : '开始优化'}
            </button>
            <button
              type="button"
              onClick={fillExample}
              className="inline-flex h-10 items-center rounded-[10px] px-4 text-[15px] text-muted-foreground transition-colors duration-150 hover:bg-[rgba(0,0,0,0.04)] dark:hover:bg-[rgba(255,255,255,0.04)]"
            >
              试试示例
            </button>
            <button
              type="button"
              onClick={clearForm}
              className="inline-flex h-10 items-center rounded-[10px] px-4 text-[15px] text-muted-foreground transition-colors duration-150 hover:bg-[rgba(0,0,0,0.04)] dark:hover:bg-[rgba(255,255,255,0.04)]"
            >
              清空
            </button>
          </div>
        </form>
        </>
      )}

      {loading && (
        <div className="space-y-4">
          <SkeletonBlock lines={5} />
        </div>
      )}

      {original && optimized && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-[14px] border border-input bg-card p-5">
              <h3 className="mb-3 text-[18px] font-semibold leading-[1.4] text-foreground">
                原文
              </h3>
              <p className="text-[15px] leading-[1.6] text-foreground">
                {original}
              </p>
            </div>
            <div className="rounded-[14px] border border-input bg-card p-5">
              <h3 className="mb-3 text-[18px] font-semibold leading-[1.4] text-foreground">
                优化后
              </h3>
              <p className="text-[15px] leading-[1.6] text-foreground">
                {renderDiffText(original, optimized)}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              setOriginal(null)
              setOptimized(null)
            }}
            className="inline-flex h-10 items-center rounded-[10px] border border-[#C8553A] px-4 text-[15px] text-[#C8553A] transition-colors duration-150 hover:bg-[rgba(200,85,58,0.06)] dark:border-[#DA7756] dark:text-[#DA7756]"
          >
            重新优化
          </button>
        </div>
      )}
    </div>
  )
}
