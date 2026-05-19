export interface TaskResult<T = unknown> {
  status: 'success' | 'error'
  task_type: string
  result: T | null
  error: { error_type: string; error_message: string } | null
  retriever_context: unknown | null
  trace: { node_name: string; status: string; remark: string }[] | null
}

interface InterviewQuestion {
  question: string
  category: string
  difficulty: string
  difficulty_reason: string
  follow_up_hint: string
  assessment_focus: string
}

export interface InterviewStartResponse {
  session_id: string
  question: InterviewQuestion
}

export interface InterviewAnswerResponse {
  action: 'follow_up' | 'next_question' | 'complete'
  reason: string
  performance_signal: string
  follow_up?: string
  question?: InterviewQuestion
}

export interface InterviewEvaluateResponse {
  overall_score: number
  summary: string
  strengths: string[]
  improvements: string[]
  items: Array<{
    question: string
    answer: string
    score: number
    feedback: string
    category: string
  }>
}

export interface ResumeStatus {
  resume_id: string
  status: 'pending' | 'analyzing' | 'completed' | 'failed'
  error?: string
}

export interface ResumeReport {
  resume_id: string
  overall_score: number
  sections: Array<{
    name: string
    score: number
    feedback: string
    suggestions: string[]
  }>
  summary: string
}
