import { Outlet, NavLink } from 'react-router-dom'
import { Dumbbell, TrendingUp, Calendar, Trophy } from 'lucide-react'

const tabs = [
  { to: '/hoy',      icon: Dumbbell,    label: 'Hoy'      },
  { to: '/progreso', icon: TrendingUp,  label: 'Progreso' },
  { to: '/plan',     icon: Calendar,    label: 'Plan'     },
  { to: '/stats',    icon: Trophy,      label: 'Stats'    },
]

export default function Layout() {
  return (
    <div className="flex flex-col min-h-dvh">
      <main className="flex-1 overflow-y-auto pb-20">
        <Outlet />
      </main>

      <nav className="fixed bottom-0 left-0 right-0 bg-slate-900 border-t border-slate-800 safe-bottom">
        <div className="flex">
          {tabs.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex-1 flex flex-col items-center py-2 gap-0.5 text-xs transition-colors ${
                  isActive ? 'text-blue-400' : 'text-slate-500'
                }`
              }
            >
              <Icon size={22} strokeWidth={1.8} />
              {label}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  )
}
