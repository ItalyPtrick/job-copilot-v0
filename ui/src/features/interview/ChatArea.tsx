import { useState, useRef, useEffect } from 'react'
import { ChatBubble } from '@/components/ChatBubble'
import { useInterviewStore } from '@/stores/interview'

interface ChatAreaProps {
  onSendAnswer: (answer: string) => void
  onEvaluate: () => void
  sendingAnswer: boolean
  evaluating: boolean
}

export function ChatArea({ onSendAnswer, onEvaluate, sendingAnswer, evaluating }: ChatAreaProps) {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const { messages, status } = useInterviewStore()

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function handleSend(e: React.FormEvent) {
    e.preventDefault()
    if (!input.trim() || sendingAnswer) return
    onSendAnswer(input.trim())
    setInput('')
  }

  const inputDisabled = status === 'completed' || status === 'evaluated' || sendingAnswer

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {messages.map((msg) => {
          const questionType = msg.metadata?.questionType as string | undefined
          let label: string | undefined
          if (questionType === 'main' || questionType === 'follow_up') {
            // 计算该消息的题号/追问号：扫描到它为止的同类消息计数
            let mainIdx = 0
            let followIdx = 0
            for (const m of messages) {
              if (m.id === msg.id) break
              const qt = m.metadata?.questionType as string | undefined
              if (qt === 'main') { mainIdx++; followIdx = 0 }
              else if (qt === 'follow_up') { followIdx++ }
            }
            if (questionType === 'main') {
              label = `Q${mainIdx + 1}`
            } else {
              label = `追问 ${followIdx + 1}`
            }
          }
          return <ChatBubble key={msg.id} role={msg.role} content={msg.content} status={msg.status} label={label} />
        })}
        {sendingAnswer && (
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-[16px] bg-[#F3F2EE] px-4 py-3 dark:bg-[#242320]">
              <span className="text-[15px] text-muted-foreground animate-pulse">思考中...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-input p-4">
        {status === 'completed' ? (
          <button
            onClick={onEvaluate}
            disabled={evaluating}
            className="inline-flex h-10 w-full items-center justify-center rounded-[10px] bg-primary px-4 text-[15px] font-medium text-primary-foreground transition-colors duration-150 hover:bg-[#333] disabled:cursor-not-allowed disabled:bg-[#E8E4DD] disabled:text-[#9C9690] dark:hover:bg-[rgba(255,255,255,0.9)] dark:disabled:bg-[#3D3A35]"
          >
            {evaluating ? '评估中...' : '获取评估'}
          </button>
        ) : (
          <form onSubmit={handleSend} className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={inputDisabled}
              placeholder={inputDisabled ? '面试已结束' : '输入你的回答...'}
              className="h-10 flex-1 rounded-[8px] border border-input bg-background px-4 text-[15px] text-foreground placeholder:text-[#9C9690] transition-colors duration-150 focus:border-foreground focus:outline-none disabled:bg-[#F3F2EE] disabled:text-[#9C9690] dark:disabled:bg-[#242320]"
            />
            <button
              type="submit"
              disabled={inputDisabled || !input.trim()}
              className="inline-flex h-10 items-center rounded-[10px] bg-primary px-4 text-[15px] font-medium text-primary-foreground transition-colors duration-150 hover:bg-[#333] disabled:cursor-not-allowed disabled:bg-[#E8E4DD] disabled:text-[#9C9690] dark:hover:bg-[rgba(255,255,255,0.9)] dark:disabled:bg-[#3D3A35]"
            >
              发送
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
