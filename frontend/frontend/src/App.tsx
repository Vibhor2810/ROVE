import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { FlowProvider } from './flow/FlowContext'
import Onboard from './pages/Onboard'
import SetReview from './pages/SetReview'
import Live from './pages/Live'
import Complete from './pages/Complete'
import MySets from './pages/MySets'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <FlowProvider>
          <Routes>
            <Route path="/" element={<Navigate to="/start" replace />} />
            <Route path="/login" element={<Navigate to="/start" replace />} />
            <Route path="/start" element={<Onboard />} />
            <Route path="/review" element={<SetReview />} />
            <Route path="/set" element={<Navigate to="/review" replace />} />
            <Route path="/live" element={<Live />} />
            <Route path="/done" element={<Complete />} />
            <Route path="/sets" element={<MySets />} />
            <Route path="*" element={<Navigate to="/start" replace />} />
          </Routes>
        </FlowProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
