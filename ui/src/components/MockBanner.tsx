import { useMockModeStore } from '@/stores/mockMode'

export function MockBanner() {
  const isMockMode = useMockModeStore((s) => s.isMockMode)

  if (!isMockMode) return null

  return (
    <div className="fixed top-0 left-0 right-0 z-[70] flex h-8 items-center justify-center bg-[#FEF3CD] text-xs text-[#856404] dark:bg-[#3D3520] dark:text-[#E0C060]">
      当前为演示模式（后端未连接）
    </div>
  )
}
