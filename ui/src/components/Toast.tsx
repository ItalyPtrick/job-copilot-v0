import { createContext, useCallback, useContext, useState } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

type ToastType = 'error' | 'success' | 'warning' | 'info'

interface ToastItem {
  id: number
  type: ToastType
  message: string
}

interface ToastContextValue {
  error: (message: string) => void
  success: (message: string) => void
  warning: (message: string) => void
  info: (message: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const TYPE_COLORS: Record<ToastType, string> = {
  error: 'bg-[#C53030] dark:bg-[#E05252]',
  success: 'bg-[#3D8C5C] dark:bg-[#5BA97A]',
  warning: 'bg-[#C4841D] dark:bg-[#E0A03C]',
  info: 'bg-[#2B6CB0] dark:bg-[#5B9BD5]',
}

let nextId = 0

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const addToast = useCallback((type: ToastType, message: string) => {
    const id = nextId++
    setToasts((prev) => [...prev, { id, type, message }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 4000)
  }, [])

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const ctx: ToastContextValue = {
    error: (msg) => addToast('error', msg),
    success: (msg) => addToast('success', msg),
    warning: (msg) => addToast('warning', msg),
    info: (msg) => addToast('info', msg),
  }

  return (
    <ToastContext.Provider value={ctx}>
      {children}
      {createPortal(
        <div className="fixed right-4 top-4 z-[60] flex flex-col gap-3">
          {toasts.map((t) => (
            <div
              key={t.id}
              className="flex max-w-[360px] animate-toast-in items-start gap-3 rounded-[10px] border border-input bg-card p-4"
            >
              <div className={`w-[3px] shrink-0 self-stretch rounded-full ${TYPE_COLORS[t.type]}`} />
              <p className="flex-1 text-[15px] leading-[1.6] text-foreground">{t.message}</p>
              <button
                onClick={() => remove(t.id)}
                className="shrink-0 text-muted-foreground transition-colors duration-150 hover:text-foreground"
              >
                <X size={16} />
              </button>
            </div>
          ))}
        </div>,
        document.body
      )}
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}