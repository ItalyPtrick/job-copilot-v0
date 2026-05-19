import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AppLayout } from '@/components/AppLayout'
import { LandingPage } from '@/features/landing/LandingPage'
import { JDAnalyzePage } from '@/features/jd-analyze/JDAnalyzePage'
import { ResumeOptimizePage } from '@/features/resume-optimize/ResumeOptimizePage'
import { InterviewPage } from '@/features/interview/InterviewPage'
import { SelfIntroPage } from '@/features/self-intro/SelfIntroPage'
import { KnowledgeBasePage } from '@/features/knowledge-base/KnowledgeBasePage'
import { ResumeAnalysisPage } from '@/features/resume-analysis/ResumeAnalysisPage'

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
          <Route path="self-intro" element={<SelfIntroPage />} />
          <Route path="knowledge-base" element={<KnowledgeBasePage />} />
          <Route path="resume-analysis" element={<ResumeAnalysisPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
