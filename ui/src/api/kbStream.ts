export interface SSEEvent {
  event: string
  data: string
}

export function parseSSEEvents(buffer: string): { events: SSEEvent[]; buffer: string } {
  const parts = buffer.split(/\r?\n\r?\n/)
  const tail = parts.pop() || ''

  return {
    events: parts
      .map(parseSSEEvent)
      .filter((event): event is SSEEvent => event !== null),
    buffer: tail,
  }
}

export function shouldFallbackToMockStream(err: unknown): boolean {
  return err instanceof TypeError && /fetch|network/i.test(err.message)
}

function parseSSEEvent(raw: string): SSEEvent | null {
  let event = 'message'
  const dataLines: string[] = []

  for (const line of raw.split(/\r?\n/)) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart())
    }
  }

  if (!event) return null
  return { event, data: dataLines.join('\n') }
}
