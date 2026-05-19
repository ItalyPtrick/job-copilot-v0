import { request } from './client'
import { useMockModeStore } from '@/stores/mockMode'
import { mockKBQuery, mockKBStream } from '@/mocks/kb'

interface KBQueryResponse {
  answer: string
  sources: { content: string; metadata: Record<string, unknown> }[]
}

interface KBStreamOptions {
  collectionName?: string
  topK?: number
}

/**
 * 同步知识库查询（返回完整答案 + sources）
 */
export async function queryKB(question: string, collectionName?: string, topK?: number) {
  return request<KBQueryResponse>(
    '/api/kb/query',
    {
      method: 'POST',
      body: { question, collection_name: collectionName, top_k: topK },
    },
    () => mockKBQuery()
  )
}

/**
 * SSE 流式知识库查询
 * 不经过 client.ts 的 request()，自行处理 fetch + ReadableStream
 * 返回 AbortController 供调用方取消
 */
export function queryKBStream(
  question: string,
  options: KBStreamOptions,
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (err: Error) => void
): AbortController {
  const controller = new AbortController()
  const { signal } = controller

  // mock 短路
  if (useMockModeStore.getState().isMockMode) {
    mockKBStream(onChunk, onDone, onError, signal)
    return controller
  }

  startStream(question, options, onChunk, onDone, onError, signal)
  return controller

  async function startStream(
    q: string,
    opts: KBStreamOptions,
    chunk: (t: string) => void,
    done: () => void,
    error: (e: Error) => void,
    sig: AbortSignal
  ) {
    // 30 秒无数据超时
    let timeoutId = setTimeout(() => controller.abort(), 30_000)
    const resetTimeout = () => {
      clearTimeout(timeoutId)
      timeoutId = setTimeout(() => controller.abort(), 30_000)
    }

    try {
      const response = await fetch('/api/kb/query/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: q,
          collection_name: opts.collectionName,
          top_k: opts.topK,
        }),
        signal: sig,
      })

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let receivedDone = false

      while (true) {
        const { value, done: readerDone } = await reader.read()
        if (readerDone) break

        resetTimeout()
        buffer += decoder.decode(value, { stream: true })

        // 按 \n\n 分割事件
        const events = buffer.split('\n\n')
        // 最后一段可能不完整，留在 buffer
        buffer = events.pop() || ''

        for (const event of events) {
          const parsed = parseSSEEvent(event)
          if (!parsed) continue

          if (parsed.event === 'message') {
            chunk(parsed.data)
          } else if (parsed.event === 'done') {
            receivedDone = true
            done()
          }
        }
      }

      clearTimeout(timeoutId)

      // 流结束但未收到 done 事件 → 异常终止
      if (!receivedDone) {
        error(new Error('生成中断，请重试'))
      }
    } catch (err) {
      clearTimeout(timeoutId)

      if (sig.aborted) {
        error(new Error('生成中断，请重试'))
        return
      }

      // 网络错误 → 降级到 mock
      useMockModeStore.getState().setMockMode(true)
      mockKBStream(chunk, done, error, sig)
    }
  }
}

function parseSSEEvent(raw: string): { event: string; data: string } | null {
  let event = 'message'
  let data = ''

  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      data = line.slice(5).trimStart()
    }
  }

  if (!event) return null
  return { event, data }
}
