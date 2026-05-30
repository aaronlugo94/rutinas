import { useState, useEffect } from 'react'
import { Brain, Zap, ChevronDown, ChevronUp } from 'lucide-react'
import { useStats, useResumen } from '../lib/hooks'
import { api } from '../lib/api'

const NIVEL_COLOR = {
  'En Forma': '#30D158', 'Consistente': '#0A84FF',
  'Dedicado': '#BF5AF2', 'Élite': '#FF6B00',
}

export default function Stats() {
  const { data: stats,   loading: ls } = useStats()
  const { data: resumen, loading: lr } = useResumen()
  const [analisis,     setAnalisis]     = useState(null)
  const [historial,    setHistorial]    = useState([])
  const [loadingAI,    setLoadingAI]    = useState(true)
  const [showHistorial, setShowHistorial] = useState(false)

  useEffect(() => {
    Promise.all([
      api.analisisIA?.().catch(() => null),
      api.analisisHistorial?.().catch(() => ({ historial: [] })),
    ]).then(([ai, hist]) => {
      setAnalisis(ai)
      setHistorial(hist?.historial || [])
      setLoadingAI(false)
    })
  }, [])

  if (ls || lr) return <Spinner />
  if (!stats) return null

  const {
    rutinas_totales, racha_actual, racha_maxima,
    progresiones, xp_total, xp_en_nivel, xp_para_nivel, nivel, badges,
  } = stats

  const xp_pct     = xp_para_nivel > 0 ? Math.round(xp_en_nivel / xp_para_nivel * 100) : 100
  const nivelColor = NIVEL_COLOR[nivel] || '#0A84FF'

  return (
    <div className="bg-black min-h-dvh px-4 pt-12 pb-6 fade-up">

      {/* Header */}
      <p className="text-zinc-500 text-sm uppercase tracking-widest mb-1">Tu rendimiento</p>
      <h1 className="text-3xl font-bold text-white mb-6">Estadísticas</h1>

      {/* Activity rings style — racha + sesiones + progresiones */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        {[
          { val: racha_actual, label: 'Racha', unit: 'días', color: '#FA114F', emoji: '🔥' },
          { val: rutinas_totales, label: 'Sesiones', unit: '', color: '#92E82A', emoji: '🏋️' },
          { val: progresiones, label: 'Subidas', unit: '', color: '#00D4FF', emoji: '📈' },
        ].map(({ val, label, unit, color, emoji }) => (
          <div
            key={label}
            className="card-sm p-4 text-center"
            style={{ background: `${color}18`, border: `1px solid ${color}30` }}
          >
            <p className="text-xl mb-1">{emoji}</p>
            <p className="text-2xl font-black" style={{ color }}>{val}</p>
            <p className="text-zinc-500 text-xs mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {/* XP + Nivel */}
      <div className="card p-4 mb-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Zap size={16} style={{ color: nivelColor }} />
            <span className="text-white font-bold text-sm">{nivel}</span>
          </div>
          <span className="font-mono text-sm font-bold" style={{ color: nivelColor }}>
            {xp_total} XP
          </span>
        </div>
        <div className="h-3 bg-zinc-800 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-1000"
            style={{
              width: `${xp_pct}%`,
              background: `linear-gradient(90deg, ${nivelColor}, ${nivelColor}99)`,
              boxShadow: `0 0 12px ${nivelColor}60`,
            }}
          />
        </div>
        <p className="text-zinc-600 text-xs mt-2 text-right">
          {xp_para_nivel - xp_en_nivel} XP para el siguiente nivel
        </p>
      </div>

      {/* Récord racha */}
      {racha_maxima > 0 && (
        <div className="card p-4 mb-4 flex items-center justify-between"
          style={{ background: '#FF6B0015', border: '1px solid #FF6B0030' }}>
          <div>
            <p className="text-zinc-500 text-xs uppercase tracking-wider">Racha récord</p>
            <p className="text-2xl font-black text-white mt-0.5">{racha_maxima} días</p>
          </div>
          <span className="text-4xl">🏆</span>
        </div>
      )}

      {/* Análisis IA */}
      <div className="card p-4 mb-4">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-6 h-6 rounded-lg bg-purple-500/20 flex items-center justify-center">
            <Brain size={13} className="text-purple-400" />
          </div>
          <span className="text-white font-bold text-sm">Coach IA</span>
          <span className="ml-auto text-xs text-zinc-600">Gemini</span>
        </div>

        {loadingAI ? (
          <div className="space-y-2">
            {[100, 80, 60].map(w => (
              <div key={w} className="shimmer h-3" style={{ width: `${w}%` }} />
            ))}
          </div>
        ) : analisis?.texto ? (
          <p className="text-zinc-300 text-sm leading-relaxed">{analisis.texto}</p>
        ) : resumen?.progresiones?.length > 0 ? (
          <>
            <p className="text-zinc-500 text-xs uppercase tracking-wider mb-2">Esta semana</p>
            {resumen.progresiones.slice(0,3).map(p => (
              <div key={p.ejercicio_id} className="flex justify-between items-center py-1.5 border-b border-zinc-800 last:border-0">
                <span className="text-zinc-400 text-sm truncate mr-2">{p.nombre}</span>
                <span className="text-green-400 text-sm font-mono font-bold shrink-0">
                  {p.peso_anterior ? `+${(p.peso_actual - p.peso_anterior).toFixed(1)}` : `${p.peso_actual}`} lbs
                </span>
              </div>
            ))}
            <p className="text-zinc-700 text-xs mt-3">
              Análisis completo a las 9pm por Telegram 🌙
            </p>
          </>
        ) : (
          <div className="py-2 text-center">
            <p className="text-zinc-500 text-sm">Entrena y registra pesos</p>
            <p className="text-zinc-700 text-xs mt-1">El análisis aparece después de tu primera semana completa</p>
          </div>
        )}

        {/* Historial de análisis */}
        {historial.length > 0 && (
          <div className="mt-3 pt-3 border-t border-zinc-800">
            <button
              onClick={() => setShowHistorial(!showHistorial)}
              className="flex items-center gap-1 text-zinc-500 text-xs hover:text-zinc-300"
            >
              {showHistorial ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              {showHistorial ? 'Ocultar' : `Ver historial (${historial.length})`}
            </button>
            {showHistorial && (
              <div className="mt-3 space-y-3">
                {historial.map((h, i) => (
                  <div key={i} className="bg-zinc-800/50 rounded-xl p-3">
                    <p className="text-zinc-600 text-xs mb-1">{h.fecha}</p>
                    <p className="text-zinc-300 text-xs leading-relaxed">{h.texto}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Semana actual */}
      {resumen && (
        <div className="card p-4 mb-4">
          <div className="flex items-center justify-between mb-3">
            <p className="text-white font-bold text-sm">Semana {resumen.semana}</p>
            <span className={`text-sm font-bold ${resumen.pct === 100 ? 'text-green-400' : 'text-blue-400'}`}>
              {resumen.completadas}/{resumen.programadas}
            </span>
          </div>
          <div className="flex gap-1.5">
            {Array.from({ length: resumen.programadas }).map((_, i) => (
              <div
                key={i}
                className="flex-1 h-2.5 rounded-full transition-all"
                style={{
                  background: i < resumen.completadas
                    ? `linear-gradient(90deg, #0A84FF, #30D158)`
                    : '#27272A',
                  boxShadow: i < resumen.completadas ? '0 0 8px #0A84FF60' : 'none',
                }}
              />
            ))}
          </div>
        </div>
      )}

      {/* Badges */}
      {badges?.length > 0 && (
        <>
          <p className="text-zinc-600 text-xs uppercase tracking-widest mb-3 mt-2">Logros</p>
          <div className="grid grid-cols-2 gap-2">
            {badges.map(b => (
              <div key={b.key} className="card-sm p-3.5 flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-zinc-800 flex items-center justify-center text-xl">
                  {b.emoji || '🏅'}
                </div>
                <div>
                  <p className="text-white text-xs font-semibold">{b.nombre}</p>
                  <p className="text-zinc-600 text-xs">{b.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function Spinner() {
  return (
    <div className="flex items-center justify-center min-h-dvh bg-black">
      <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )
}
