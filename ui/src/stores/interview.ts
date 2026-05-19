import { create } from 'zustand'
import type { InterviewEvaluateResponse } from '@/api/types'

interface Message {
  id: string
  role: 'system' | 'user'
  content: string
  metadata?: Record<string, unknown>
  status?: 'sent' | 'failed'
}

type InterviewStatus = 'idle' | 'in_progress' | 'completed' | 'evaluated'

interface InterviewState {
  sessionId: string | null
  status: InterviewStatus
  messages: Message[]
  evaluationResult: InterviewEvaluateResponse | null
  startSession: (sessionId: string, firstQuestion: string) => void
  addMessage: (role: 'system' | 'user', content: string, metadata?: Record<string, unknown>) => string
  markMessageFailed: (id: string) => void
  setStatus: (status: InterviewStatus) => void
  setEvaluation: (result: InterviewEvaluateResponse) => void
  reset: () => void
}

let messageSeq = 0

function createMessage(role: 'system' | 'user', content: string, metadata?: Record<string, unknown>): Message {
  messageSeq += 1
  return { id: `message-${messageSeq}`, role, content, metadata, status: 'sent' }
}

export const useInterviewStore = create<InterviewState>((set) => ({
  sessionId: null,
  status: 'idle',
  messages: [],
  evaluationResult: null,

  startSession: (sessionId, firstQuestion) =>
    set({
      sessionId,
      status: 'in_progress',
      messages: [createMessage('system', firstQuestion)],
      evaluationResult: null,
    }),

  addMessage: (role, content, metadata) => {
    const message = createMessage(role, content, metadata)
    set((state) => ({
      messages: [...state.messages, message],
    }))
    return message.id
  },

  markMessageFailed: (id) =>
    set((state) => ({
      messages: state.messages.map((message) =>
        message.id === id ? { ...message, status: 'failed' } : message
      ),
    })),

  setStatus: (status) => set({ status }),

  setEvaluation: (result) =>
    set({ evaluationResult: result, status: 'evaluated' }),

  reset: () =>
    set({
      sessionId: null,
      status: 'idle',
      messages: [],
      evaluationResult: null,
    }),
}))
