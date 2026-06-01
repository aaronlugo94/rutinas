import { useState } from 'react'
import { TrendingUp, TrendingDown, ArrowLeft, Zap } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from 'recharts'
import { useProgreso, useProgresoEj } from '../lib/hooks'

const GRUPO_COLOR = {
  gluteo: '#ec4899', pierna: '#8b5cf6', empuje: '#3b82f6',
  tiron:  '#06b6d4', core:   '#f59e0b', cardio: '#10b981',
}
const GRUPO_ICON = {
  gluteo: '🍑', pierna: '🦵', empuje: '💪',
  tiron: '🏋️', core: '🎯', cardio: '🏃',
}

export default function Progreso() {
  const { data, loading } = useProgreso()
  const [selected, setSelected] = useState(null)

  if (loading) return <Spinner />
  if (!data?.ejercicios?.length) return <Empty />
  if (selected)
    return <DetalleEjercicio eid={selected} onBack={() => setSelected(null)} />

  const grupos = {}
  for (const e of data.ejercicios) {
    if (!grupos[e.grupo]) grupos[e.grupo] = []
    grupos[e.grupo].push(e)
  }

  const top = [...data.ejercicios]
    .filter(e => e.ganancia_total > 0)
    .sort((a, b) => b.ganancia_total - a.ganancia_total)
    .slice(0, 4)

  const totalLbs = data.ejercicios.reduce((s, e) => s + (e.peso_maximo || 0), 0)

  return (
    <div className="px-4 pt-8 pb-4 fade-up">
      <div className="mb-6">
        <p className="text-slate-500 text-sm">Tu fuerza</p>
        <h1 className="text-2xl font-bold text-white">Progreso</h1>
      </div>

      {/* Big number */}
      {top.length > 0 && (
        <div className="card-glow-green p-5 mb-4 text-center">
          <p className="text-slate-400 text-xs uppercase tracking-widest mb-1">Mayor ganancia</p>
          <p className="text-5xl font-black text-gradient-green">
            +{top[0].ganancia_total}
          </p>
          <p className="text-slate-400 text-sm mt-1">
            lbs en {top[0].nombre.split(' ').slice(0,3).join(' ')}
          </p>
        </div>
      )}

      {/* Top gains grid */}
      {top.length > 1 && (
        <div className="grid grid-cols-2 gap-2 mb-5">
          {top.slice(1).map(e => {
            const color = GRUPO_COLOR[e.grupo] || '#3b82f6'
            return (
              <button
                key={e.ejercicio_id}
                onClick={() => setSelected(e.ejercicio_id)}
                className="card p-3 text-left active:scale-95 transition-transform"
              >
                <p className="text-slate-500 text-xs mb-1 truncate">
                  {e.nombre.split(' ').slice(0,3).join(' ')}
                </p>
                <p className="text-xl font-bold" style={{ color }}>
                  +{e.ganancia_total} lbs
                </p>
                <p className="text-slate-600 text-xs">{e.semanas_registradas} sem</p>
              </button>
            )
          })}
        </div>
      )}

      {/* Grupos */}
      {Object.entries(grupos).map(([grupo, ejs]) => {
        const color = GRUPO_COLOR[grupo] || '#3b82f6'
        return (
          <div key={grupo} className="mb-5">
            <div className="flex items-center gap-2 mb-2">
              <div
                className="w-2 h-2 rounded-full"
                style={{ background: color }}
              />
              <p className="text-xs font-medium uppercase tracking-widest"
                 style={{ color }}>
                {GRUPO_ICON[grupo]} {grupo}
              </p>
            </div>
            <div className="space-y-2">
              {ejs.map(e => (
                <button
                  key={e.ejercicio_id}
                  onClick={() => setSelected(e.ejercicio_id)}
                  className="card w-full px-4 py-3 text-left flex items-center justify-between active:scale-[0.99] transition-transform"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-white text-sm font-medium truncate">{e.nombre}</p>
                    <p className="text-slate-600 text-xs mt-0.5">
                      {e.peso_maximo} lbs · {e.semanas_registradas} {e.semanas_registradas === 1 ? 'sesión' : 'semanas'}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 ml-3 shrink-0">
                    {e.ganancia_total > 0 ? (
                      <span className="text-green-400 text-sm font-bold">+{e.ganancia_total}</span>
                    ) : (
                      <span className="text-slate-600 text-sm">—</span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function DetalleEjercicio({ eid, onBack }) {
  const { data, loading } = useProgresoEj(eid)

  if (loading) return <Spinner />
  if (!data) return null

  const { nombre, historial, ganancia_total, peso_sugerido, tendencia, grupo } = data
  const color    = GRUPO_COLOR[grupo] || '#3b82f6'
  const chartData = historial.map(h => ({ semana: `S${h.semana}`, peso: h.peso }))
  const maxPeso  = Math.max(...chartData.map(d => d.peso || 0))
  const minPeso  = Math.min(...chartData.map(d => d.peso || 0))
  const domain   = [Math.floor(minPeso * 0.96), Math.ceil(maxPeso * 1.04)]

  return (
    <div className="px-4 pt-6 pb-4 fade-up">
      <button
        onClick={onBack}
        className="flex items-center gap-1.5 text-slate-500 text-sm mb-5 hover:text-white transition-colors"
      >
        <ArrowLeft size={15} /> Progreso
      </button>

      <p className="text-slate-500 text-xs uppercase tracking-widest mb-1"
         style={{ color }}>
        {GRUPO_ICON[grupo]} {grupo}
      </p>
      <h1 className="text-xl font-bold text-white mb-4">{nombre}</h1>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-2 mb-5">
        <div className="card p-3 text-center">
          <p className="text-slate-600 text-xs mb-1">Máximo</p>
          <p className="text-white font-bold">{maxPeso}</p>
          <p className="text-slate-600 text-xs">lbs</p>
        </div>
        <div className="card p-3 text-center">
          <p className="text-slate-600 text-xs mb-1">Ganancia</p>
          <p className="font-bold" style={{ color: ganancia_total > 0 ? '#4ade80' : '#94a3b8' }}>
            {ganancia_total > 0 ? `+${ganancia_total}` : ganancia_total || '—'}
          </p>
          <p className="text-slate-600 text-xs">lbs</p>
        </div>
        <div className="card p-3 text-center">
          <p className="text-slate-600 text-xs mb-1">Próxima</p>
          <p className="text-blue-400 font-bold">{peso_sugerido || '—'}</p>
          <p className="text-slate-600 text-xs">lbs</p>
        </div>
      </div>

      {/* Chart */}
      {chartData.length > 0 && (
        <div className="card p-4 mb-4">
          <p className="text-slate-500 text-xs mb-3 uppercase tracking-wider">Progresión</p>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={chartData} margin={{ top: 4, right: 0, left: -28, bottom: 0 }}>
              <XAxis
                dataKey="semana"
                tick={{ fill: '#475569', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={domain}
                tick={{ fill: '#475569', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{
                  background: '#0F1623',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 10,
                  color: '#f1f5f9',
                  fontSize: 12,
                }}
                formatter={v => [`${v} lbs`]}
              />
              <Bar dataKey="peso" radius={[6,6,0,0]}>
                {chartData.map((_, i) => (
                  <Cell
                    key={i}
                    fill={i === chartData.length - 1 ? color : 'rgba(255,255,255,0.08)'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* History */}
      <div className="space-y-2">
        {[...historial].reverse().map((h, i) => (
          <div
            key={h.semana}
            className={`card px-4 py-3 flex items-center justify-between ${
              i === 0 ? 'border-opacity-40' : ''
            }`}
            style={i === 0 ? { borderColor: color } : {}}
          >
            <div className="flex items-center gap-2">
              {i === 0 && (
                <div className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
              )}
              <span className="text-slate-500 text-sm">Semana {h.semana}</span>
            </div>
            <div className="text-right">
              <p className={`font-semibold ${i === 0 ? 'text-white' : 'text-slate-400'}`}>
                {h.peso} lbs
              </p>
              {h.series && (
                <p className="text-slate-600 text-xs">{h.series}×{h.reps}</p>
              )}
            </div>
          </div>
        ))}
      </div>
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

function Empty() {
  return (
    <div className="flex flex-col items-center justify-center min-h-dvh px-6 text-center fade-up">
      <div className="text-5xl mb-4">📊</div>
      <h2 className="text-white font-bold text-lg mb-2">Sin registros aún</h2>
      <p className="text-slate-500 text-sm leading-relaxed">
        Completa tu primera sesión desde el bot y registra los pesos.<br />
        Aquí verás tu progresión semana a semana.
      </p>
    </div>
  )
}
