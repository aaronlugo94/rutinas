import { useState, useEffect } from 'react'
import { Flame, Zap, Trophy, TrendingUp, Brain } from 'lucide-react'
import { useStats, useResumen } from '../lib/hooks'
import { api } from '../lib/api'

export default function Stats() {
  const { data: stats,   loading: ls } = useStats()
  const { data: resumen, loading: lr } = useResumen()
  const [analisis, setAnalisis] = useState(null)
  const [loadingAI, setLoadingAI] = useState(false)

  useEffect(() => {
    // Fetch AI analysis
    setLoadingAI(true)
    api.analisisIA?.()
      .then(d => setAnalisis(d))
      .catch(() => setAnalisis(null))
      .finally(() => setLoadingAI(false))
  }, [])

  if (ls || lr) return <Spinner />
  if (!stats) return null

  const {
    rutinas_totales, racha_actual, racha_maxima,
    progresiones, xp_total, xp_en_nivel, xp_para_nivel,
    nivel, badges,
  } = stats

  const xp_pct = xp_para_nivel > 0
    ? Math.round(xp_en_nivel / xp_para_nivel * 100)
    : 100

  return (
    <div className="px-4 pt-8 pb-4 fade-up">

      {/* Header */}
      <div className="mb-6">
        <p className="text-slate-500 text-sm">Tu rendimiento</p>
        <h1 className="text-2xl font-bold text-white">Estadísticas</h1>
      </div>

      {/* Racha — hero card */}
      <div className={`card-glow-orange p-5 mb-3 text-center ${racha_actual >= 7 ? '' : 'card'}`}>
        <div className="flex items-center justify-center gap-3 mb-1">
          {racha_actual >= 3 && (
            <Flame size={28} className="text-orange-400" fill="rgba(249,115,22,0.3)" />
          )}
          <span className="text-6xl font-black text-white">{racha_actual}</span>
          {racha_actual >= 3 && (
            <Flame size={28} className="text-orange-400" fill="rgba(249,115,22,0.3)" />
          )}
        </div>
        <p className="text-orange-300/70 text-sm font-medium">
          {racha_actual === 0 ? 'Empieza tu racha hoy' :
           racha_actual === 1 ? 'Día 1 — sigue así' :
           racha_actual < 7  ? `${racha_actual} días seguidos` :
           `🔥 ${racha_actual} días — récord personal`}
        </p>
        {racha_maxima > racha_actual && (
          <p className="text-slate-600 text-xs mt-1">Récord: {racha_maxima} días</p>
        )}
      </div>

      {/* XP nivel */}
      <div className="card-glow-blue p-4 mb-3">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Zap size={16} className="text-blue-400" />
            <span className="text-white font-semibold text-sm">{nivel}</span>
          </div>
          <span className="text-blue-400 font-mono text-sm">{xp_total} XP</span>
        </div>
        <div className="h-2 bg-white/5 rounded-full overflow-hidden mb-1">
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{
              width: `${xp_pct}%`,
              background: 'linear-gradient(90deg, #3b82f6, #8b5cf6)',
            }}
          />
        </div>
        <p className="text-slate-600 text-xs text-right">
          {xp_para_nivel - xp_en_nivel} XP para siguiente nivel
        </p>
      </div>

      {/* Grid stats */}
      <div className="grid grid-cols-2 gap-2 mb-3">
        {[
          { icon: '🏋️', label: 'Sesiones',     val: rutinas_totales, color: 'text-white' },
          { icon: '📈', label: 'Progresiones', val: progresiones,    color: 'text-green-400' },
          { icon: '🔥', label: 'Racha actual', val: `${racha_actual}d`, color: 'text-orange-400' },
          { icon: '🏆', label: 'Récord',       val: `${racha_maxima}d`, color: 'text-yellow-400' },
        ].map(({ icon, label, val, color }) => (
          <div key={label} className="card p-4">
            <p className="text-xl mb-1">{icon}</p>
            <p className={`text-2xl font-bold ${color}`}>{val}</p>
            <p className="text-slate-600 text-xs mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {/* Análisis IA */}
      <div className="card p-4 mb-3">
        <div className="flex items-center gap-2 mb-3">
          <Brain size={16} className="text-purple-400" />
          <span className="text-white font-semibold text-sm">Análisis de tu semana</span>
        </div>
        {loadingAI ? (
          <div className="space-y-2">
            <div className="h-3 bg-white/5 rounded-full w-full pulse-slow" />
            <div className="h-3 bg-white/5 rounded-full w-4/5 pulse-slow" />
            <div className="h-3 bg-white/5 rounded-full w-3/5 pulse-slow" />
          </div>
        ) : analisis?.texto ? (
          <p className="text-slate-300 text-sm leading-relaxed">{analisis.texto}</p>
        ) : resumen?.progresiones?.length > 0 ? (
          <div className="space-y-2">
            <p className="text-slate-400 text-sm">Esta semana:</p>
            {resumen.progresiones.slice(0,3).map(p => (
              <div key={p.ejercicio_id} className="flex justify-between items-center">
                <span className="text-slate-400 text-xs truncate mr-2">{p.nombre}</span>
                <span className="text-green-400 text-xs font-mono shrink-0">
                  {p.peso_anterior ? `${p.peso_anterior}→${p.peso_actual}` : `${p.peso_actual}`} lbs
                </span>
              </div>
            ))}
            <p className="text-slate-600 text-xs mt-2">
              El análisis completo llega a las 9pm por Telegram 🌙
            </p>
          </div>
        ) : (
          <div className="text-center py-2">
            <p className="text-slate-500 text-sm">Entrena y registra pesos</p>
            <p className="text-slate-600 text-xs mt-1">
              El análisis con IA aparece después de tu primera semana
            </p>
          </div>
        )}
      </div>

      {/* Resumen semanal */}
      {resumen && (
        <div className="card p-4 mb-3">
          <div className="flex items-center justify-between mb-3">
            <span className="text-white font-semibold text-sm">Semana {resumen.semana}</span>
            <span className={`text-sm font-bold ${resumen.pct === 100 ? 'text-green-400' : 'text-blue-400'}`}>
              {resumen.pct}%
            </span>
          </div>
          <div className="flex gap-1 mb-3">
            {Array.from({ length: resumen.programadas }).map((_, i) => (
              <div
                key={i}
                className={`flex-1 h-2 rounded-full ${
                  i < resumen.completadas ? 'bg-blue-500' : 'bg-white/5'
                }`}
              />
            ))}
          </div>
          <p className="text-slate-500 text-xs">
            {resumen.completadas} de {resumen.programadas} sesiones completadas
          </p>
        </div>
      )}

      {/* Badges */}
      {badges?.length > 0 && (
        <div>
          <p className="text-slate-600 text-xs uppercase tracking-widest mb-3 mt-4">Logros</p>
          <div className="grid grid-cols-2 gap-2">
            {badges.map(b => (
              <div key={b.key} className="card p-3 flex items-center gap-3">
                <div className="text-2xl">{b.emoji || '🏅'}</div>
                <div>
                  <p className="text-white text-xs font-semibold">{b.nombre}</p>
                  <p className="text-slate-600 text-xs">{b.desc}</p>
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
      <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )
}
