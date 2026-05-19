import { useState } from 'react'
import { useInterviewStore } from '@/stores/interview'
import { startInterview, submitAnswer, evaluateInterview } from '@/api/interview'
import { ConfigPanel } from './ConfigPanel'
import { ChatArea } from './ChatArea'
import { EvaluationReport } from './EvaluationReport'

export function InterviewPage() {
  const [startLoading, setStartLoading] = useState(false)
  const [sendingAnswer, setSendingAnswer] = useState(false)
  const [evaluating, setEvaluating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const {
    status,
    sessionId,
    evaluationResult,
    startSession,
    addMessage,
    markMessageFailed,
    setStatus,
    setEvaluation,
    reset,
  } = useInterviewStore()

  async function handleStart(config: { skill: string; total_questions: number; follow_up_count: number }) {
    setStartLoading(true)
    setError(null)
    try {
      const res = await startInterview(config)
      startSession(res.session_id, res.question.question)
    } catch (err) {
      setError(err instanceof Error ? err.message : '启动面试失败')
    } finally {
      setStartLoading(false)
    }
  }

  async function handleSendAnswer(answer: string) {
    if (!sessionId) return
    const userMessageId = addMessage('user', answer)
    setSendingAnswer(true)
    setError(null)

    try {
      const res = await submitAnswer(sessionId, answer)
      switch (res.action) {
        case 'follow_up':
          if (res.follow_up) addMessage('system', res.follow_up)
          break
        case 'next_question':
          if (res.question) addMessage('system', res.question.question)
          break
        case 'complete':
          addMessage('system', '面试已结束，可以点击“获取评估”查看报告。')
          setStatus('completed')
          break
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : '提交回答失败'
      markMessageFailed(userMessageId)
      setError(message)
    } finally {
      setSendingAnswer(false)
    }
  }

  async function handleEvaluate() {
    if (!sessionId) return
    setEvaluating(true)
    setError(null)
    try {
      const res = await evaluateInterview(sessionId)
      setEvaluation(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取评估失败')
    } finally {
      setEvaluating(false)
    }
  }

  if (status === 'evaluated' && evaluationResult) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-[28px] font-semibold leading-[1.2] tracking-[-0.015em] text-foreground">
            面试评估报告
          </h1>
          <button
            onClick={reset}
            className="inline-flex h-10 items-center rounded-[10px] border border-[#C8553A] px-4 text-[15px] text-[#C8553A] transition-colors duration-150 hover:bg-[rgba(200,85,58,0.06)] dark:border-[#DA7756] dark:text-[#DA7756]"
          >
            重新开始
          </button>
        </div>
        <EvaluationReport data={evaluationResult} />
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col space-y-4">
      <h1 className="text-[28px] font-semibold leading-[1.2] tracking-[-0.015em] text-foreground">
        模拟面试
      </h1>

      {error && (
        <div className="rounded-lg bg-[rgba(197,48,48,0.1)] px-4 py-3 text-[15px] text-[#C53030] dark:text-[#E05252]">
          {error}
        </div>
      )}

      <ConfigPanel onStart={handleStart} loading={startLoading} visible={status === 'idle'} />

      {status !== 'idle' && (
        <div className="flex min-h-0 flex-1 flex-col rounded-[14px] border border-input">
          <ChatArea
            onSendAnswer={handleSendAnswer}
            onEvaluate={handleEvaluate}
            sendingAnswer={sendingAnswer}
            evaluating={evaluating}
          />
        </div>
      )}
    </div>
  )
}
