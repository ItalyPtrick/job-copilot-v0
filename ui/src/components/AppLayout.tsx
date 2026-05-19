import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { MockBanner } from './MockBanner'
import { useMockModeStore } from '@/stores/mockMode'

export function AppLayout() {
  const isMockMode = useMockModeStore((s) => s.isMockMode)

  return (
    <div className="min-h-screen">
      <MockBanner />
      <Sidebar />
      <main
        className="ml-[220px] min-h-screen"
        style={{ paddingTop: isMockMode ? '32px' : undefined }}
      >
        <div className="mx-auto max-w-[720px] px-8 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
