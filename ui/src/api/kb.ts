import { request } from './client'
import { parseSSEEvents, shouldFallbackToMockStream } from './kbStream'
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
        if (readerDone || sig.aborted) break

        resetTimeout()
        buffer += decoder.decode(value, { stream: true })

        const parsed = parseSSEEvents(buffer)
        buffer = parsed.buffer

        for (const event of parsed.events) {
          if (event.event === 'message') {
            chunk(event.data)
          } else if (event.event === 'done') {
            receivedDone = true
            done()
          }
        }
      }

      clearTimeout(timeoutId)

      // 流结束但未收到 done 事件 → 异常终止（abort 除外）
      if (!receivedDone && !sig.aborted) {
        error(new Error('生成中断，请重试'))
      }
    } catch (err) {
      clearTimeout(timeoutId)

      // abort 后静默退出，不调用任何回调
      if (sig.aborted) return

      if (shouldFallbackToMockStream(err)) {
        useMockModeStore.getState().setMockMode(true)
        mockKBStream(chunk, done, error, sig)
        return
      }

      error(err instanceof Error ? err : new Error('生成中断，请重试'))
    }
  }
}
