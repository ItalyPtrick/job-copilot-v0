import { Button } from '@/components/ui/button'
import { useThemeStore } from '@/stores/theme'

function App() {
  const { theme, toggle } = useThemeStore()

  return (
    <div className="min-h-screen flex items-center justify-center gap-4">
      <h1 className="text-2xl font-semibold text-foreground">Job Copilot</h1>
      <Button onClick={toggle}>
        {theme === 'light' ? '切换暗色' : '切换亮色'}
      </Button>
    </div>
  )
}

export default App
