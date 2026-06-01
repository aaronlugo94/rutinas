import { Outlet, NavLink } from 'react-router-dom'
import { Dumbbell, TrendingUp, Activity, Salad, Trophy } from 'lucide-react'

const tabs = [
  { to: '/hoy',       icon: Dumbbell,    label: 'Hoy'      },
  { to: '/fuerza',    icon: TrendingUp,  label: 'Fuerza'   },
  { to: '/cuerpo',    icon: Activity,    label: 'Cuerpo'   },
  { to: '/nutricion', icon: Salad,       label: 'Nutrición'},
  { to: '/stats',     icon: Trophy,      label: 'Stats'    },
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
                `flex-1 flex flex-col items-center pt-2 pb-1 gap-0.5 transition-all ${
                  isActive ? 'text-white' : 'text-zinc-600'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <div className={`p-1.5 rounded-xl transition-all ${isActive ? 'bg-white/10' : ''}`}>
                    <Icon size={19} strokeWidth={isActive ? 2.4 : 1.6} />
                  </div>
                  <span className={`text-[9px] font-medium ${isActive ? 'text-white' : 'text-zinc-600'}`}>
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
