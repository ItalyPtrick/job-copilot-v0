import { useMockModeStore } from '@/stores/mockMode'

export class HttpError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'HttpError'
    this.status = status
  }
}

interface RequestOptions {
  method?: string
  body?: unknown
  headers?: Record<string, string>
  preserve503?: boolean
}

export async function request<T>(
  url: string,
  options: RequestOptions = {},
  mockFn?: () => T | Promise<T>
): Promise<T> {
  // 全局 mock 短路
  if (useMockModeStore.getState().isMockMode) {
    if (mockFn) return mockFn()
    throw new Error(`Mock mode active but no mockFn provided for ${url}`)
  }

  const { method = 'GET', body, headers = {}, preserve503 = false } = options

  const fetchOptions: RequestInit = { method, headers: { ...headers } }

  if (body !== undefined) {
    if (body instanceof FormData) {
      fetchOptions.body = body
    } else {
      ;(fetchOptions.headers as Record<string, string>)['Content-Type'] = 'application/json'
      fetchOptions.body = JSON.stringify(body)
    }
  }

  try {
    const response = await fetch(url, fetchOptions)

    // 特定业务流需要保留 503，避免进入全局 mock。
    if (response.status === 503 && preserve503) {
      const errorData = await response.json().catch(() => ({}))
      throw new HttpError(503, (errorData as { detail?: string }).detail || '服务暂时不可用')
    }

    // 其他 5xx 触发 mock
    if (response.status >= 500) {
      return fallbackToMock(mockFn, url)
    }

    // 检测非 JSON 响应（proxy 未生效时可能返回 HTML）
    const contentType = response.headers.get('content-type') || ''
    if (!contentType.includes('application/json')) {
      return fallbackToMock(mockFn, url)
    }

    // 4xx 业务错误正常抛出，不触发 mock
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error((errorData as { detail?: string }).detail || `HTTP ${response.status}`)
    }

    return (await response.json()) as T
  } catch (err) {
    // 网络错误（TypeError: Failed to fetch）
    if (err instanceof TypeError) {
      return fallbackToMock(mockFn, url)
    }
    throw err
  }
}

function fallbackToMock<T>(mockFn: (() => T | Promise<T>) | undefined, url: string): T | Promise<T> {
  useMockModeStore.getState().setMockMode(true)
  if (mockFn) return mockFn()
  throw new Error(`Backend unavailable and no mockFn for ${url}`)
}
