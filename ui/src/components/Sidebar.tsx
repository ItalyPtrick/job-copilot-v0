import { NavLink } from 'react-router-dom'
import { useThemeStore } from '@/stores/theme'
import { useMockModeStore } from '@/stores/mockMode'
import {
  FileSearch,
  FileText,
  MessageSquare,
  Mic,
  BookOpen,
  ClipboardCheck,
  Sun,
  Moon,
} from 'lucide-react'

const navItems = [
  { to: '/app/jd-analyze', label: 'JD 分析', icon: FileSearch },
  { to: '/app/resume-optimize', label: '简历优化', icon: FileText },
  { to: '/app/interview', label: '模拟面试', icon: MessageSquare },
  { to: '/app/self-intro', label: '自我介绍', icon: Mic },
  { to: '/app/knowledge-base', label: '知识库', icon: BookOpen },
  { to: '/app/resume-analysis', label: '简历分析', icon: ClipboardCheck },
]

export function Sidebar() {
  const { theme, toggle } = useThemeStore()
  const isMockMode = useMockModeStore((s) => s.isMockMode)

  return (
    <aside
      className="fixed left-0 z-10 flex w-[220px] flex-col border-r border-border bg-muted"
      style={{ top: isMockMode ? 32 : 0, height: isMockMode ? 'calc(100vh - 32px)' : '100vh' }}
    >
      <div className="flex h-14 items-center px-4">
        <span className="text-[15px] font-semibold text-foreground">Job Copilot</span>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-2">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex h-9 items-center gap-2 rounded-[8px] px-3 text-[15px] transition-colors duration-100 ${
                isActive
                  ? 'bg-[rgba(0,0,0,0.06)] font-medium text-foreground dark:bg-[rgba(255,255,255,0.08)]'
                  : 'text-muted-foreground hover:bg-[rgba(0,0,0,0.03)] dark:hover:bg-[rgba(255,255,255,0.04)]'
              }`
            }
          >
            <item.icon size={18} />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-border px-3 py-3">
        <button
          onClick={toggle}
          className="flex h-9 w-full items-center gap-2 rounded-[8px] px-3 text-[15px] text-muted-foreground transition-colors duration-100 hover:bg-[rgba(0,0,0,0.03)] dark:hover:bg-[rgba(255,255,255,0.04)]"
        >
          {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
          <span>{theme === 'light' ? '暗色模式' : '亮色模式'}</span>
        </button>
      </div>
    </aside>
  )
}
