import { useState, useRef, useCallback, useEffect } from 'react'
import { queryKBStream } from '@/api/kb'
import { MarkdownRenderer } from '@/components/MarkdownRenderer'

const EXAMPLE_QUESTION = 'Python 装饰器的原理是什么？如何实现带参数的装饰器？'

export function KnowledgeBasePage() {
  const [question, setQuestion] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [answer, setAnswer] = useState('')
  const [error, setError] = useState<string | null>(null)
  const controllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    return () => {
      controllerRef.current?.abort()
    }
  }, [])

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault()
      if (!question.trim() || streaming) return

      setStreaming(true)
      setAnswer('')
      setError(null)

      const controller = queryKBStream(
        question,
        {},
        (chunk) => {
          setAnswer((prev) => prev + chunk)
        },
        () => {
          setStreaming(false)
        },
        (err) => {
          setStreaming(false)
          setError(err.message || '生成中断，请重试')
        }
      )
      controllerRef.current = controller
    },
    [question, streaming]
  )

  function handleCancel() {
    controllerRef.current?.abort()
    setStreaming(false)
  }

  function fillExample() {
    setQuestion(EXAMPLE_QUESTION)
  }

  return (
    <div className="space-y-6">
      <h1 className="text-[28px] font-semibold leading-[1.2] tracking-[-0.015em] text-foreground">
        知识库查询
      </h1>

      {/* 空状态引导 */}
      {!answer && !streaming && !error && !question && (
        <div className="flex items-center gap-3">
          <span className="text-[15px] text-muted-foreground">
            向知识库提问，获取 RAG 增强的回答
          </span>
          <button
            type="button"
            onClick={fillExample}
            className="rounded-[10px] px-3 py-1.5 text-[15px] text-muted-foreground transition-colors duration-150 hover:bg-[rgba(0,0,0,0.04)] dark:hover:bg-[rgba(255,255,255,0.04)]"
          >
            试试示例
          </button>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="mb-2 block text-[15px] text-foreground">问题</label>
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="输入你想了解的技术问题..."
            className="min-h-[120px] w-full rounded-[8px] border border-input bg-background px-4 py-3 text-[15px] text-foreground placeholder:text-[#9C9690] transition-colors duration-150 focus:border-foreground focus:outline-none"
          />
        </div>

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={streaming || !question.trim()}
            className="inline-flex h-10 items-center rounded-[10px] bg-primary px-6 text-[15px] font-medium text-primary-foreground transition-colors duration-150 hover:bg-[#333] disabled:cursor-not-allowed disabled:bg-[#E8E4DD] disabled:text-[#9C9690] dark:hover:bg-[rgba(255,255,255,0.9)] dark:disabled:bg-[#3D3A35]"
          >
            {streaming ? '生成中...' : '提问'}
          </button>
          {streaming && (
            <button
              type="button"
              onClick={handleCancel}
              className="inline-flex h-10 items-center rounded-[10px] border border-input px-4 text-[15px] text-foreground transition-colors duration-150 hover:bg-[rgba(0,0,0,0.04)] dark:hover:bg-[rgba(255,255,255,0.04)]"
            >
              停止
            </button>
          )}
        </div>
      </form>

      {error && (
        <div className="rounded-lg bg-[rgba(197,48,48,0.1)] px-4 py-3 text-[15px] text-[#C53030] dark:text-[#E05252]">
          {error}
        </div>
      )}

      {(answer || streaming) && (
        <div className="rounded-[14px] border border-input bg-card p-5">
          <MarkdownRenderer content={answer} />
          {streaming && (
            <span className="inline-block w-[2px] h-[1em] bg-foreground align-middle ml-0.5 animate-[cursor-blink_800ms_step-end_infinite]" />
          )}
        </div>
      )}
    </div>
  )
}
