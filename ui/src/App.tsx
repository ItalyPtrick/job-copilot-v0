import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AppLayout } from '@/components/AppLayout'
import { LandingPage } from '@/features/landing/LandingPage'
import { JDAnalyzePage } from '@/features/jd-analyze/JDAnalyzePage'
import { ResumeOptimizePage } from '@/features/resume-optimize/ResumeOptimizePage'
import { InterviewPage } from '@/features/interview/InterviewPage'

function Placeholder({ name }: { name: string }) {
  return <p className="text-muted-foreground">Coming Soon — {name}</p>
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/app" element={<AppLayout />}>
          <Route index element={<Navigate to="/app/jd-analyze" replace />} />
          <Route path="jd-analyze" element={<JDAnalyzePage />} />
          <Route path="resume-optimize" element={<ResumeOptimizePage />} />
          <Route path="interview" element={<InterviewPage />} />
          <Route path="self-intro" element={<Placeholder name="自我介绍" />} />
          <Route path="knowledge-base" element={<Placeholder name="知识库" />} />
          <Route path="resume-analysis" element={<Placeholder name="简历分析" />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
