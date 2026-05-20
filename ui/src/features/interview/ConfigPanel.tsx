import { useState } from 'react'

interface ConfigPanelProps {
  onStart: (config: { skill: string; total_questions: number; follow_up_count: number }) => void
  loading: boolean
  visible: boolean
}

export function ConfigPanel({ onStart, loading, visible }: ConfigPanelProps) {
  const [skill, setSkill] = useState('python_backend')
  const [totalQuestions, setTotalQuestions] = useState(10)
  const [followUpCount, setFollowUpCount] = useState(1)

  function clampNumber(value: string, min: number, max: number) {
    const n = Number(value)
    if (!Number.isFinite(n)) return min
    return Math.min(max, Math.max(min, Math.trunc(n)))
  }

  function handleStart(e: React.FormEvent) {
    e.preventDefault()
    onStart({
      skill,
      total_questions: clampNumber(String(totalQuestions), 1, 20),
      follow_up_count: clampNumber(String(followUpCount), 0, 3),
    })
  }

  return (
    <div
      className={`overflow-hidden transition-all duration-[350ms] ${
        visible ? 'max-h-[360px] opacity-100' : 'max-h-0 opacity-0'
      }`}
    >
      <form onSubmit={handleStart} className="space-y-4 rounded-[14px] border border-input bg-card p-5">
        <h3 className="text-[18px] font-semibold leading-[1.4] text-foreground">面试配置</h3>

        <div>
          <label className="mb-2 block text-[15px] text-foreground">技能方向</label>
          <select
            value={skill}
            onChange={(e) => setSkill(e.target.value)}
            className="h-10 w-full rounded-[8px] border border-input bg-background px-4 text-[15px] text-foreground transition-colors duration-150 focus:border-foreground focus:outline-none"
          >
            <option value="python_backend">Python 后端开发</option>
          </select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-2 block text-[15px] text-foreground">题目数量</label>
            <input
              type="number"
              min={1}
              max={20}
              value={totalQuestions}
              onChange={(e) => setTotalQuestions(clampNumber(e.target.value, 1, 20))}
              className="h-10 w-full rounded-[8px] border border-input bg-background px-4 text-[15px] text-foreground transition-colors duration-150 focus:border-foreground focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-2 block text-[15px] text-foreground">追问次数</label>
            <input
              type="number"
              min={0}
              max={3}
              value={followUpCount}
              onChange={(e) => setFollowUpCount(clampNumber(e.target.value, 0, 3))}
              className="h-10 w-full rounded-[8px] border border-input bg-background px-4 text-[15px] text-foreground transition-colors duration-150 focus:border-foreground focus:outline-none"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={loading || !visible}
          className="inline-flex h-10 items-center rounded-[10px] bg-primary px-4 text-[15px] font-medium text-primary-foreground transition-colors duration-150 hover:bg-[#333] disabled:cursor-not-allowed disabled:bg-[#E8E4DD] disabled:text-[#9C9690] dark:hover:bg-[rgba(255,255,255,0.9)] dark:disabled:bg-[#3D3A35]"
        >
          {loading ? '准备中...' : '开始面试'}
        </button>
      </form>
    </div>
  )
}
