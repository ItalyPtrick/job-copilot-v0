interface ChatBubbleProps {
  role: 'system' | 'user'
  content: string
  status?: 'sent' | 'failed'
  label?: string
}

export function ChatBubble({ role, content, status = 'sent', label }: ChatBubbleProps) {
  const isUser = role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[80%] ${isUser ? 'text-right' : 'text-left'}`}>
        <div className="mb-1 text-[12px] text-muted-foreground">
          {isUser ? '你' : '系统'}
          {!isUser && label && <span className="ml-1.5 text-[11px] text-[#9C9690]">· {label}</span>}
          {status === 'failed' && <span className="ml-2 text-[#C53030] dark:text-[#E05252]">发送失败</span>}
        </div>
        <div
          className={`rounded-[16px] px-4 py-3 text-[15px] leading-[1.6] ${
            isUser
              ? 'bg-[#E8E1D8] text-foreground dark:bg-[#3D3A35]'
              : 'bg-[#F3F2EE] text-foreground dark:bg-[#242320]'
          }`}
        >
          <p className="whitespace-pre-wrap">{content}</p>
        </div>
      </div>
    </div>
  )
}
