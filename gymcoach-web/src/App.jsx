import { Routes, Route, Navigate } from 'react-router-dom'
import { isLoggedIn } from './lib/api'
import Login     from './pages/Login'
import Layout    from './components/Layout'
import Hoy       from './pages/Hoy'
import Progreso  from './pages/Progreso'
import Plan      from './pages/Plan'
import Stats     from './pages/Stats'

function Guard({ children }) {
  return isLoggedIn() ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Guard><Layout /></Guard>}>
        <Route index           element={<Navigate to="/hoy" replace />} />
        <Route path="hoy"      element={<Hoy />} />
        <Route path="progreso" element={<Progreso />} />
        <Route path="plan"     element={<Plan />} />
        <Route path="stats"    element={<Stats />} />
      </Route>
    </Routes>
  )
}
