import { Routes, Route, Navigate } from 'react-router-dom'
import { isLoggedIn } from './lib/api'
import Login    from './pages/Login'
import Layout   from './components/Layout'
import Hoy      from './pages/Hoy'
import Fuerza   from './pages/Progreso'
import Cuerpo   from './pages/Cuerpo'
import Nutricion from './pages/Nutricion'
import Stats    from './pages/Stats'

function Guard({ children }) {
  return isLoggedIn() ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/auth"  element={<Login />} />
      <Route path="/" element={<Guard><Layout /></Guard>}>
        <Route index           element={<Navigate to="/hoy" replace />} />
        <Route path="hoy"      element={<Hoy />} />
        <Route path="fuerza"   element={<Fuerza />} />
        <Route path="cuerpo"   element={<Cuerpo />} />
        <Route path="nutricion" element={<Nutricion />} />
        <Route path="stats"    element={<Stats />} />
      </Route>
    </Routes>
  )
}
