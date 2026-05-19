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
        className="ml-[220px] h-screen overflow-hidden"
        style={{
          height: isMockMode ? 'calc(100vh - 32px)' : undefined,
          marginTop: isMockMode ? '32px' : undefined,
        }}
      >
        <div className="mx-auto flex h-full w-full max-w-[720px] flex-col overflow-y-auto px-8 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
