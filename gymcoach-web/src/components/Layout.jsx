import { Outlet, NavLink } from 'react-router-dom'
import { Dumbbell, TrendingUp, Calendar, Trophy } from 'lucide-react'

const tabs = [
  { to: '/hoy',      icon: Dumbbell,   label: 'Hoy'      },
  { to: '/progreso', icon: TrendingUp, label: 'Progreso' },
  { to: '/plan',     icon: Calendar,   label: 'Plan'     },
  { to: '/stats',    icon: Trophy,     label: 'Stats'    },
]

export default function Layout() {
  return (
    <div className="flex flex-col min-h-dvh">
      <main className="flex-1 overflow-y-auto pb-20">
        <Outlet />
      </main>
      <nav className="fixed bottom-0 left-0 right-0 nav-bg safe-bottom">
        <div className="flex">
          {tabs.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex-1 flex flex-col items-center py-3 gap-0.5 text-xs transition-all ${
                  isActive
                    ? 'text-blue-400'
                    : 'text-slate-600 hover:text-slate-400'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <div className={`p-1.5 rounded-xl transition-all ${isActive ? 'bg-blue-500/15' : ''}`}>
                    <Icon size={20} strokeWidth={isActive ? 2.2 : 1.6} />
                  </div>
                  <span className={isActive ? 'font-medium' : ''}>{label}</span>
                </>
              )}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  )
}
