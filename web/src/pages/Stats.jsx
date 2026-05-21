import { Flame } from 'lucide-react'
import { useStats, useResumen } from '../lib/hooks'

export default function Stats() {
  const { data: stats,   loading: ls } = useStats()
  const { data: resumen, loading: lr } = useResumen()

  if (ls || lr) return <Spinner />
  if (!stats)   return null

  const {
    rutinas_totales, racha_actual, racha_maxima, progresiones,
    xp_total, xp_en_nivel, xp_para_nivel, nivel, badges,
  } = stats

  const xp_pct = xp_para_nivel > 0 ? Math.round(xp_en_nivel / xp_para_nivel * 100) : 100

  return (
    <div className="px-4 pt-6 pb-4">
      <h1 className="text-xl font-semibold text-white mb-5">Estadísticas</h1>

      {/* Streak hero */}
      <div className="bg-slate-800/60 border border-slate-700 rounded-2xl p-5 mb-4 text-center">
        <div className="flex items-center justify-center gap-2 mb-1">
          {racha_actual >= 7 && <Flame size={24} className="text-orange-400" />}
          <span className="text-5xl font-bold text-white">{racha_actual}</span>
        </div>
        <p className="text-slate-400 text-sm">
          días de racha · récord {racha_maxima} días
        </p>
      </div>

      {/* XP bar */}
      <div className="bg-slate-800/60 border border-slate-700 rounded-xl px-4 py-3 mb-4">
        <div className="flex justify-between text-sm mb-2">
          <span className="text-white font-medium">{nivel}</span>
          <span className="text-slate-400">{xp_total} XP</span>
        </div>
        <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 rounded-full transition-all"
            style={{ width: `${xp_pct}%` }}
          />
        </div>
        <p className="text-xs text-slate-500 mt-1 text-right">
          {xp_para_nivel - xp_en_nivel} XP para el siguiente nivel
        </p>
      </div>

      {/* Summary grid */}
      <div className="grid grid-cols-2 gap-2 mb-5">
        {[
          { label: 'Sesiones',      val: rutinas_totales },
          { label: 'Progresiones',  val: progresiones   },
          { label: 'Racha actual',  val: `${racha_actual}d` },
          { label: 'Racha récord',  val: `${racha_maxima}d` },
        ].map(({ label, val }) => (
          <div key={label} className="bg-slate-800 rounded-xl p-3">
            <p className="text-xs text-slate-400">{label}</p>
            <p className="text-xl font-semibold text-white mt-0.5">{val}</p>
          </div>
        ))}
      </div>

      {/* Weekly summary */}
      {resumen && (
        <div className="bg-slate-800/60 border border-slate-700 rounded-xl px-4 py-3 mb-5">
          <p className="text-white font-medium text-sm mb-2">Semana {resumen.semana}</p>
          <div className="flex items-center gap-3 mb-2">
            <div className="h-2 flex-1 bg-slate-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${resumen.pct === 100 ? 'bg-green-500' : 'bg-blue-500'}`}
                style={{ width: `${resumen.pct}%` }}
              />
            </div>
            <span className="text-slate-400 text-sm shrink-0">
              {resumen.completadas}/{resumen.programadas}
            </span>
          </div>
          {resumen.progresiones.length > 0 && (
            <div className="space-y-1 mt-2">
              {resumen.progresiones.slice(0,4).map(p => (
                <div key={p.ejercicio_id} className="flex justify-between text-xs">
                  <span className="text-slate-400 truncate mr-2">{p.nombre}</span>
                  <span className="text-green-400 font-medium shrink-0">
                    {p.peso_anterior ? `${p.peso_anterior} → ${p.peso_actual} lbs` : `${p.peso_actual} lbs`}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Badges */}
      {badges?.length > 0 && (
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-3">Logros</p>
          <div className="grid grid-cols-2 gap-2">
            {badges.map(b => (
              <div key={b.key} className="bg-slate-800 rounded-xl p-3 flex items-center gap-3">
                <span className="text-2xl">{b.emoji || '🏅'}</span>
                <div>
                  <p className="text-white text-xs font-medium">{b.nombre}</p>
                  <p className="text-slate-500 text-xs">{b.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function Spinner() {
  return (
    <div className="flex items-center justify-center min-h-dvh">
      <div className="text-slate-400 text-sm">Cargando...</div>
    </div>
  )
}
