import { useState } from 'react'
import { TrendingUp, TrendingDown, Minus, ArrowLeft } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { useProgreso, useProgresoEj } from '../lib/hooks'

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

  // Group by grupo
  const grupos = {}
  for (const e of data.ejercicios) {
    if (!grupos[e.grupo]) grupos[e.grupo] = []
    grupos[e.grupo].push(e)
  }

  // Top 3 gains for summary cards
  const top = [...data.ejercicios]
    .filter(e => e.ganancia_total > 0)
    .sort((a, b) => b.ganancia_total - a.ganancia_total)
    .slice(0, 4)

  return (
    <div className="px-4 pt-6 pb-4">
      <h1 className="text-xl font-semibold text-white mb-4">Progreso de pesos</h1>

      {/* Summary cards */}
      {top.length > 0 && (
        <div className="grid grid-cols-2 gap-2 mb-5">
          {top.map(e => (
            <button
              key={e.ejercicio_id}
              onClick={() => setSelected(e.ejercicio_id)}
              className="bg-slate-800 rounded-xl p-3 text-left"
            >
              <p className="text-xs text-slate-400 leading-tight mb-1">{e.nombre.split(' ').slice(0,3).join(' ')}</p>
              <p className="text-lg font-semibold text-green-400">+{e.ganancia_total} lbs</p>
              <p className="text-xs text-slate-500">{e.semanas_registradas} sem</p>
            </button>
          ))}
        </div>
      )}

      {/* List by grupo */}
      {Object.entries(grupos).map(([grupo, ejs]) => (
        <div key={grupo} className="mb-5">
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">
            {GRUPO_ICON[grupo]} {grupo}
          </p>
          <div className="space-y-2">
            {ejs.map(e => (
              <button
                key={e.ejercicio_id}
                onClick={() => setSelected(e.ejercicio_id)}
                className="w-full bg-slate-800/60 border border-slate-700 rounded-xl px-4 py-3 text-left flex items-center justify-between"
              >
                <div>
                  <p className="text-white text-sm">{e.nombre}</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {e.peso_maximo} lbs · {e.semanas_registradas} sem
                  </p>
                </div>
                <div className="flex items-center gap-1">
                  {e.ganancia_total > 0
                    ? <><TrendingUp size={14} className="text-green-400" /><span className="text-green-400 text-sm font-medium">+{e.ganancia_total}</span></>
                    : e.ganancia_total < 0
                    ? <><TrendingDown size={14} className="text-red-400" /><span className="text-red-400 text-sm">{e.ganancia_total}</span></>
                    : <Minus size={14} className="text-slate-500" />
                  }
                </div>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function DetalleEjercicio({ eid, onBack }) {
  const { data, loading } = useProgresoEj(eid)

  if (loading) return <Spinner />
  if (!data)   return null

  const { nombre, historial, ganancia_total, peso_sugerido, tendencia } = data
  const chartData = historial.map(h => ({ semana: `S${h.semana}`, peso: h.peso }))
  const maxPeso   = Math.max(...chartData.map(d => d.peso || 0))
  const minPeso   = Math.min(...chartData.map(d => d.peso || 0)) * 0.95

  return (
    <div className="px-4 pt-6 pb-4">
      <button
        onClick={onBack}
        className="flex items-center gap-1 text-slate-400 text-sm mb-4 hover:text-white transition-colors"
      >
        <ArrowLeft size={16} /> Todos los ejercicios
      </button>

      <h1 className="text-lg font-semibold text-white mb-1">{nombre}</h1>

      <div className="flex items-center gap-3 mb-5">
        {tendencia === 'up' && (
          <span className="flex items-center gap-1 text-green-400 font-semibold">
            <TrendingUp size={16} /> +{ganancia_total} lbs totales
          </span>
        )}
        {tendencia === 'flat' && (
          <span className="text-slate-400 text-sm">Sin cambio</span>
        )}
        {peso_sugerido && (
          <span className="text-blue-400 text-sm">
            Próxima: {peso_sugerido} lbs
          </span>
        )}
      </div>

      {/* Bar chart */}
      {chartData.length > 0 && (
        <div className="bg-slate-800/50 rounded-xl p-4 mb-4">
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <XAxis
                dataKey="semana"
                tick={{ fill: '#94a3b8', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={[minPeso, maxPeso * 1.05]}
                tick={{ fill: '#94a3b8', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: 'none', borderRadius: 8, color: '#f1f5f9' }}
                formatter={v => [`${v} lbs`, 'Peso']}
              />
              <Bar dataKey="peso" radius={[4,4,0,0]}>
                {chartData.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={i === chartData.length - 1 ? '#3b82f6' : '#334155'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* History table */}
      <div className="space-y-2">
        {[...historial].reverse().map(h => (
          <div
            key={h.semana}
            className="flex items-center justify-between bg-slate-800/60 rounded-xl px-4 py-3"
          >
            <span className="text-slate-400 text-sm">Semana {h.semana}</span>
            <div className="text-right">
              <p className="text-white font-medium">{h.peso} lbs</p>
              {h.series && (
                <p className="text-slate-500 text-xs">{h.series} × {h.reps}</p>
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
      <div className="text-slate-400 text-sm">Cargando...</div>
    </div>
  )
}

function Empty() {
  return (
    <div className="flex flex-col items-center justify-center min-h-dvh px-6 text-center">
      <div className="text-4xl mb-4">📊</div>
      <h2 className="text-white font-medium mb-2">Sin registros aún</h2>
      <p className="text-slate-400 text-sm">
        Completa tu primera sesión y registra los pesos para ver tu progresión aquí.
      </p>
    </div>
  )
}
