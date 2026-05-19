import { Link } from 'react-router-dom'
import { useThemeStore } from '@/stores/theme'
import { Sun, Moon } from 'lucide-react'

const techGroups = [
  {
    title: '后端框架',
    items: ['FastAPI', 'Pydantic', 'Uvicorn', 'Celery'],
  },
  {
    title: '数据层',
    items: ['PostgreSQL', 'Redis', 'SQLAlchemy', 'Alembic'],
  },
  {
    title: 'AI 能力',
    items: ['LangChain', 'ChromaDB', 'OpenAI API', 'RAG'],
  },
  {
    title: '部署',
    items: ['Docker', 'Nginx', 'Multi-stage Build'],
  },
]

export function LandingPage() {
  const { theme, toggle } = useThemeStore()

  return (
    <div className="min-h-screen bg-background">
      {/* 右上角暗色切换 */}
      <header className="fixed right-6 top-5 z-10">
        <button
          onClick={toggle}
          className="flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-colors duration-150 hover:bg-[rgba(0,0,0,0.04)] dark:hover:bg-[rgba(255,255,255,0.06)]"
        >
          {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
        </button>
      </header>

      <div className="mx-auto max-w-[1080px] px-8">
        {/* Hero */}
        <section className="flex min-h-[70vh] flex-col items-center justify-center text-center">
          <h1 className="text-[36px] font-bold leading-[1.1] tracking-[-0.02em] text-foreground">
            Job Copilot
          </h1>
          <p className="mt-4 max-w-[480px] text-[15px] leading-relaxed text-muted-foreground">
            基于 LLM 的求职 AI 助手 — JD 分析、简历优化、模拟面试、知识库问答，一站式提升求职效率。
          </p>
          <Link
            to="/app/jd-analyze"
            className="mt-8 inline-flex h-10 items-center rounded-[10px] bg-primary px-6 text-[15px] font-medium text-primary-foreground transition-colors duration-150 hover:bg-[#333] dark:hover:bg-[rgba(255,255,255,0.9)]"
          >
            试一试
          </Link>
        </section>

        {/* 技术栈 */}
        <section className="pb-20">
          <h2 className="mb-8 text-center text-[22px] font-semibold leading-[1.3] text-foreground">
            技术栈
          </h2>
          <div className="grid grid-cols-2 gap-5 lg:grid-cols-4">
            {techGroups.map((group) => (
              <div
                key={group.title}
                className="rounded-[14px] border border-border bg-card p-5"
              >
                <h3 className="mb-3 text-[13px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {group.title}
                </h3>
                <div className="flex flex-wrap gap-2">
                  {group.items.map((item) => (
                    <span
                      key={item}
                      className="rounded-[6px] bg-muted px-2 py-1 text-[13px] text-foreground"
                    >
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
