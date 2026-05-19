import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface MarkdownRendererProps {
  content: string
}

export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: ({ children }) => (
          <h1 className="mb-4 mt-6 text-[22px] font-semibold leading-[1.3] text-foreground first:mt-0">
            {children}
          </h1>
        ),
        h2: ({ children }) => (
          <h2 className="mb-3 mt-6 text-[18px] font-semibold leading-[1.4] text-foreground first:mt-0">
            {children}
          </h2>
        ),
        h3: ({ children }) => (
          <h3 className="mb-2 mt-4 text-[15px] font-semibold leading-[1.5] text-foreground first:mt-0">
            {children}
          </h3>
        ),
        p: ({ children }) => (
          <p className="mb-4 text-[15px] leading-[1.6] text-foreground last:mb-0">
            {children}
          </p>
        ),
        ul: ({ children }) => (
          <ul className="mb-4 list-disc pl-5 text-[15px] leading-[1.6] text-foreground last:mb-0">
            {children}
          </ul>
        ),
        ol: ({ children }) => (
          <ol className="mb-4 list-decimal pl-5 text-[15px] leading-[1.6] text-foreground last:mb-0">
            {children}
          </ol>
        ),
        li: ({ children }) => <li className="mb-2">{children}</li>,
        code: ({ className, children }) => {
          const isBlock = className?.includes('language-')
          if (isBlock) {
            return (
              <code className={`block text-[14px] leading-[1.5] font-mono ${className || ''}`}>
                {children}
              </code>
            )
          }
          return (
            <code className="rounded-[4px] bg-[rgba(0,0,0,0.04)] px-1.5 py-0.5 font-mono text-[14px] dark:bg-[rgba(255,255,255,0.06)]">
              {children}
            </code>
          )
        },
        pre: ({ children }) => (
          <pre className="mb-4 overflow-x-auto rounded-[8px] bg-[#F3F2EE] p-4 dark:bg-[#1A1917] last:mb-0">
            {children}
          </pre>
        ),
        blockquote: ({ children }) => (
          <blockquote className="mb-4 border-l-[3px] border-input pl-4 text-muted-foreground last:mb-0">
            {children}
          </blockquote>
        ),
        table: ({ children }) => (
          <div className="mb-4 overflow-x-auto last:mb-0">
            <table className="w-full border-collapse text-[15px]">{children}</table>
          </div>
        ),
        th: ({ children }) => (
          <th className="border-b border-input px-3 py-2 text-left text-[13px] font-semibold">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="border-b border-input px-3 py-2 text-[15px]">{children}</td>
        ),
        strong: ({ children }) => (
          <strong className="font-semibold">{children}</strong>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  )
}
