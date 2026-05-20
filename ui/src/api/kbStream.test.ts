import test from 'node:test'
import assert from 'node:assert/strict'
import {
  parseSSEEvents,
  shouldFallbackToMockStream,
} from './kbStream.ts'

test('parseSSEEvents splits CRLF separated SSE events and keeps incomplete tail', () => {
  const parsed = parseSSEEvents(
    'event: message\r\ndata: hello\r\n\r\nevent: done\r\ndata: [DONE]\r\n\r\nevent: message\r\n'
  )

  assert.deepEqual(parsed.events, [
    { event: 'message', data: 'hello' },
    { event: 'done', data: '[DONE]' },
  ])
  assert.equal(parsed.buffer, 'event: message\r\n')
})

test('parseSSEEvents joins multiple data lines with newlines', () => {
  const parsed = parseSSEEvents('event: message\r\ndata: line 1\r\ndata: line 2\r\n\r\n')

  assert.deepEqual(parsed.events, [
    { event: 'message', data: 'line 1\nline 2' },
  ])
  assert.equal(parsed.buffer, '')
})

test('shouldFallbackToMockStream only falls back for network-like errors', () => {
  assert.equal(shouldFallbackToMockStream(new TypeError('Failed to fetch')), true)
  assert.equal(shouldFallbackToMockStream(new TypeError('NetworkError when attempting to fetch resource')), true)
  assert.equal(shouldFallbackToMockStream(new TypeError('undefined is not a function')), false)
  assert.equal(shouldFallbackToMockStream(new Error('HTTP 500')), false)
})
