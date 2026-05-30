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
    <div className="flex flex-col min-h-dvh bg-black">
      <main className="flex-1 overflow-y-auto pb-20">
        <Outlet />
      </main>
      <nav className="fixed bottom-0 left-0 right-0 nav-bg safe-bottom z-50">
        <div className="flex max-w-lg mx-auto">
          {tabs.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex-1 flex flex-col items-center pt-2 pb-1 gap-0.5 text-xs transition-all ${
                  isActive ? 'text-white' : 'text-zinc-600'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={22} strokeWidth={isActive ? 2.5 : 1.8}
                    className={isActive ? 'drop-shadow-[0_0_8px_rgba(10,132,255,0.8)]' : ''} />
                  <span className={`text-[10px] ${isActive ? 'font-semibold text-white' : 'text-zinc-600'}`}>
                    {label}
                  </span>
                </>
              )}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  )
}
