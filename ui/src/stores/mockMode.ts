import { create } from 'zustand'

interface MockModeState {
  isMockMode: boolean
  setMockMode: (v: boolean) => void
}

export const useMockModeStore = create<MockModeState>((set) => ({
  isMockMode: false,
  setMockMode: (v) => set({ isMockMode: v }),
}))
