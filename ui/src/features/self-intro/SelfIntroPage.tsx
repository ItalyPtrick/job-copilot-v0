import { useState } from 'react'
import { Copy, Check } from 'lucide-react'
import { generateSelfIntro } from '@/api/selfIntro'
import { SkeletonBlock } from '@/components/SkeletonBlock'
import { useToast } from '@/components/Toast'

type Tone = 'formal' | 'conversational'

const EXAMPLE = {
  tone: 'formal' as Tone,
  resumeItem: '使用 FastAPI + LangChain 搭建 RAG 问答系统，支持文档解析、向量检索和流式输出；Docker 部署，CI/CD 自动化。',
  keywords: 'Python, FastAPI, LangChain, Docker',
  role: 'Python 后端开发工程师',
}

export function SelfIntroPage() {
  const [tone, setTone] = useState<Tone>('formal')
  const [resumeItem, setResumeItem] = useState('')
  const [keywords, setKeywords] = useState('')
  const [role, setRole] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const toast = useToast()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!resumeItem.trim()) return

    setLoading(true)
    setResult(null)

    try {
      const keywordList = keywords
        .split(/[,，]/)
        .map((k) => k.trim())
        .filter(Boolean)
      const res = await generateSelfIntro(tone, resumeItem, keywordList, role)
      if (res.status === 'success' && res.result) {
        setResult(res.result)
      } else {
        toast.error(res.error?.error_message || '生成失败')
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '请求失败')
    } finally {
      setLoading(false)
    }
  }

  function fillExample() {
    setTone(EXAMPLE.tone)
    setResumeItem(EXAMPLE.resumeItem)
    setKeywords(EXAMPLE.keywords)
    setRole(EXAMPLE.role)
  }

  async function handleCopy() {
    if (!result) return
    await navigator.clipboard.writeText(result)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="space-y-6">
      <h1 className="text-[28px] font-semibold leading-[1.2] tracking-[-0.015em] text-foreground">
        自我介绍生成
      </h1>

      {/* 空状态引导 */}
      {!result && !loading && !resumeItem && (
        <div className="flex items-center gap-3">
          <span className="text-[15px] text-muted-foreground">
            输入核心经历，生成面试自我介绍
          </span>
          <button
            type="button"
            onClick={fillExample}
            className="text-[15px] text-muted-foreground transition-colors duration-150 hover:bg-[rgba(0,0,0,0.04)] dark:hover:bg-[rgba(255,255,255,0.04)] rounded-[10px] px-3 py-1"
          >
            试试示例
          </button>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* 语气选择 */}
        <div>
          <label className="mb-2 block text-[15px] text-foreground">语气风格</label>
          <div className="flex gap-2">
            {(['formal', 'conversational'] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTone(t)}
                className={`rounded-[10px] px-4 py-2 text-[15px] transition-colors duration-150 ${
                  tone === t
                    ? 'bg-primary text-primary-foreground'
                    : 'border border-input text-foreground hover:bg-[rgba(0,0,0,0.04)] dark:hover:bg-[rgba(255,255,255,0.04)]'
                }`}
              >
                {t === 'formal' ? '正式' : '轻松'}
              </button>
            ))}
          </div>
        </div>

        {/* 核心经历 */}
        <div>
          <label className="mb-2 block text-[15px] text-foreground">核心经历</label>
          <textarea
            value={resumeItem}
            onChange={(e) => setResumeItem(e.target.value)}
            placeholder="简述你最核心的项目经历或技术亮点..."
            className="min-h-[120px] w-full rounded-[8px] border border-input bg-background px-4 py-3 text-[15px] text-foreground placeholder:text-[#9C9690] transition-colors duration-150 focus:border-foreground focus:outline-none"
          />
        </div>

        {/* 目标关键词 */}
        <div>
          <label className="mb-2 block text-[15px] text-foreground">目标关键词</label>
          <input
            type="text"
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            placeholder="逗号分隔，如：Python, FastAPI, Docker"
            className="h-10 w-full rounded-[8px] border border-input bg-background px-4 text-[15px] text-foreground placeholder:text-[#9C9690] transition-colors duration-150 focus:border-foreground focus:outline-none"
          />
        </div>

        {/* 目标岗位 */}
        <div>
          <label className="mb-2 block text-[15px] text-foreground">目标岗位</label>
          <input
            type="text"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            placeholder="如：Python 后端开发工程师"
            className="h-10 w-full rounded-[8px] border border-input bg-background px-4 text-[15px] text-foreground placeholder:text-[#9C9690] transition-colors duration-150 focus:border-foreground focus:outline-none"
          />
        </div>

        <button
          type="submit"
          disabled={loading || !resumeItem.trim()}
          className="inline-flex h-10 items-center rounded-[10px] bg-primary px-4 text-[15px] font-medium text-primary-foreground transition-colors duration-150 hover:bg-[#333] disabled:cursor-not-allowed disabled:bg-[#E8E4DD] disabled:text-[#9C9690] dark:hover:bg-[rgba(255,255,255,0.9)] dark:disabled:bg-[#3D3A35]"
        >
          {loading ? '生成中...' : '生成自我介绍'}
        </button>
      </form>

      {loading && <SkeletonBlock lines={5} />}

      {result && (
        <div className="relative rounded-[14px] border border-input bg-card p-5">
          <button
            type="button"
            onClick={handleCopy}
            className="absolute right-4 top-4 rounded-[8px] p-2 text-muted-foreground transition-colors duration-150 hover:bg-[rgba(0,0,0,0.04)] dark:hover:bg-[rgba(255,255,255,0.04)]"
            title="复制到剪贴板"
          >
            {copied ? <Check size={16} /> : <Copy size={16} />}
          </button>
          <p className="whitespace-pre-wrap pr-10 text-[15px] leading-[1.6] text-foreground">
            {result}
          </p>
          {copied && (
            <span className="absolute right-4 top-12 text-[12px] text-muted-foreground">
              已复制
            </span>
          )}
        </div>
      )}
    </div>
  )
}
