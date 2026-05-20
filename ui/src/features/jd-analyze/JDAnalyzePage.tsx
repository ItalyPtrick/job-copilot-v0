import { useState } from 'react'
import { analyzeJD } from '@/api/jd'
import { ResultCard } from '@/components/ResultCard'
import { SkeletonBlock } from '@/components/SkeletonBlock'
import { useToast } from '@/components/Toast'

interface JDResult {
  hard_requirements: string[]
  core_skills: string[]
  bonus_skills: string[]
}

const EXAMPLE_JD = `职位：Python 后端工程师
要求：3年以上 Python 开发经验，熟悉 FastAPI/Django，了解 PostgreSQL、Redis，有微服务架构经验优先。`

export function JDAnalyzePage() {
  const [jdText, setJdText] = useState('')
  const [targetRole, setTargetRole] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<JDResult | null>(null)
  const toast = useToast()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!jdText.trim()) return

    setLoading(true)
    setResult(null)

    try {
      const res = await analyzeJD(jdText, targetRole)
      if (res.status === 'success' && res.result) {
        setResult(res.result)
      } else {
        toast.error(res.error?.error_message || '分析失败')
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '请求失败')
    } finally {
      setLoading(false)
    }
  }

  function fillExample() {
    setJdText(EXAMPLE_JD)
  }

  return (
    <div className="space-y-6">
      <h1 className="text-[28px] font-semibold leading-[1.2] tracking-[-0.015em] text-foreground">
        JD 分析
      </h1>

      {!result && !loading && !jdText && (
        <div className="flex items-center gap-3">
          <span className="text-[15px] text-muted-foreground">
            粘贴职位描述，快速提取核心要求
          </span>
          <button
            type="button"
            onClick={fillExample}
            className="rounded-[10px] px-3 py-1 text-[15px] text-muted-foreground transition-colors duration-150 hover:bg-[rgba(0,0,0,0.04)] dark:hover:bg-[rgba(255,255,255,0.04)]"
          >
            试试示例
          </button>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="mb-2 block text-[15px] text-foreground">
            职位描述
          </label>
          <textarea
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            placeholder="粘贴 JD 全文..."
            className="min-h-[120px] w-full rounded-[8px] border border-input bg-background px-4 py-3 text-[15px] text-foreground placeholder:text-[#9C9690] transition-colors duration-150 focus:border-foreground focus:outline-none"
          />
        </div>

        <div>
          <label className="mb-2 block text-[15px] text-foreground">
            目标岗位
          </label>
          <input
            type="text"
            value={targetRole}
            onChange={(e) => setTargetRole(e.target.value)}
            placeholder="如：Python 后端工程师"
            className="h-10 w-full rounded-[8px] border border-input bg-background px-4 text-[15px] text-foreground placeholder:text-[#9C9690] transition-colors duration-150 focus:border-foreground focus:outline-none"
          />
        </div>

        <button
          type="submit"
          disabled={loading || !jdText.trim()}
          className="inline-flex h-10 items-center rounded-[10px] bg-primary px-4 text-[15px] font-medium text-primary-foreground transition-colors duration-150 hover:bg-[#333] disabled:cursor-not-allowed disabled:bg-[#E8E4DD] disabled:text-[#9C9690] dark:hover:bg-[rgba(255,255,255,0.9)] dark:disabled:bg-[#3D3A35]"
        >
          {loading ? '分析中...' : '开始分析'}
        </button>
      </form>

      {loading && (
        <div className="space-y-4">
          <SkeletonBlock lines={4} />
          <SkeletonBlock lines={3} />
          <SkeletonBlock lines={3} />
        </div>
      )}

      {result && (
        <div className="space-y-4">
          <ResultCard title="硬性要求" items={result.hard_requirements} />
          <ResultCard title="核心技能" items={result.core_skills} />
          <ResultCard title="加分项" items={result.bonus_skills} />
        </div>
      )}
    </div>
  )
}
