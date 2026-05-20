import test from 'node:test'
import assert from 'node:assert/strict'
import { request, HttpError } from './client.ts'
import { useMockModeStore } from '../stores/mockMode.ts'

test('request falls back to mock on 503 by default', async () => {
  const originalFetch = globalThis.fetch
  useMockModeStore.getState().setMockMode(false)
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ detail: 'temporary unavailable' }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    })

  try {
    const result = await request('/api/other', {}, () => ({ ok: true }))

    assert.deepEqual(result, { ok: true })
    assert.equal(useMockModeStore.getState().isMockMode, true)
  } finally {
    globalThis.fetch = originalFetch
    useMockModeStore.getState().setMockMode(false)
  }
})

test('request throws HttpError on 503 when preserve503 is true', async () => {
  const originalFetch = globalThis.fetch
  useMockModeStore.getState().setMockMode(false)
  globalThis.fetch = async () =>
    new Response(JSON.stringify({ detail: '面试服务暂时不可用。' }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    })

  try {
    await assert.rejects(
      () => request('/api/interview/answer', { preserve503: true }, () => ({ ok: true })),
      (err: unknown) => {
        assert.ok(err instanceof HttpError)
        assert.equal(err.status, 503)
        assert.equal(err.message, '面试服务暂时不可用。')
        return true
      }
    )
    // 不应进入 mock 模式
    assert.equal(useMockModeStore.getState().isMockMode, false)
  } finally {
    globalThis.fetch = originalFetch
    useMockModeStore.getState().setMockMode(false)
  }
})
