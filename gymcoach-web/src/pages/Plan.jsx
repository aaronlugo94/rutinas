import { useState } from 'react'
import { CheckCircle2, Circle, ChevronRight } from 'lucide-react'
import { usePlan } from '../lib/hooks'

const GRUPO_COLOR = {
  gluteo: '#ec4899', pierna: '#8b5cf6', empuje: '#3b82f6',
  tiron: '#06b6d4', core: '#f59e0b', general: '#10b981',
}
const GRUPO_ICON = {
  gluteo: '🍑', pierna: '🦵', empuje: '💪',
  tiron: '🏋️', core: '🎯', general: '⚡',
}

export default function Plan() {
  const { data, loading } = usePlan()
  const [semSel, setSemSel] = useState(null)
  const [diaOpen, setDiaOpen] = useState(null)

  if (loading) return <Spinner />
  if (!data?.semanas?.length) return <Empty />

  const semActual = data.semana_actual
  const semanas   = data.semanas
  const sem       = semanas.find(s => s.semana === (semSel ?? semActual)) || semanas[0]

  return (
    <div className="px-4 pt-8 pb-4 fade-up">
      <div className="mb-6">
        <p className="text-slate-500 text-sm">Tu programa</p>
        <h1 className="text-2xl font-bold text-white">Plan</h1>
      </div>

      {/* Week selector */}
      <div className="flex gap-2 mb-5 overflow-x-auto pb-1 -mx-1 px-1">
        {semanas.map(s => {
          const activa = (semSel ?? semActual) === s.semana
          const total  = s.dias.reduce((acc, d) => acc + d.total, 0)
          const hechos = s.dias.reduce((acc, d) => acc + d.completado, 0)
          const pct    = total > 0 ? Math.round(hechos / total * 100) : 0
          return (
            <button
              key={s.semana}
              onClick={() => setSemSel(s.semana)}
              className={`shrink-0 flex flex-col items-center px-4 py-2.5 rounded-2xl text-sm transition-all ${
                activa
                  ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20'
                  : 'card text-slate-400 hover:text-white'
              }`}
            >
              <span className="font-semibold">S{s.semana}</span>
              {s.semana === semActual && (
                <span className={`text-xs mt-0.5 ${activa ? 'text-blue-200' : 'text-blue-400'}`}>
                  actual
                </span>
              )}
              {pct > 0 && (
                <div className={`w-8 h-0.5 rounded-full mt-1.5 ${activa ? 'bg-white/40' : 'bg-white/10'}`}>
                  <div
                    className={`h-full rounded-full ${activa ? 'bg-white' : 'bg-blue-500'}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              )}
            </button>
          )
        })}
      </div>

      {/* Days */}
      <div className="space-y-2">
        {sem.dias.map(dia => {
          const color   = GRUPO_COLOR[dia.grupo] || '#3b82f6'
          const pct     = dia.total > 0 ? Math.round(dia.completado / dia.total * 100) : 0
          const hecho   = pct === 100
          const esHoy   = dia.es_hoy
          const isOpen  = diaOpen === dia.dia

          return (
            <div
              key={dia.dia}
              className="card overflow-hidden transition-all"
              style={esHoy ? { borderColor: `${color}40` } : {}}
            >
              <button
                className="w-full px-4 py-3.5 flex items-center gap-3"
                onClick={() => setDiaOpen(isOpen ? null : dia.dia)}
              >
                {/* Status icon */}
                {hecho
                  ? <CheckCircle2 size={18} className="shrink-0" style={{ color }} />
                  : <Circle size={18} className="shrink-0 text-slate-700" />
                }

                <div className="flex-1 text-left">
                  <div className="flex items-center gap-2">
                    <span className="text-white font-medium text-sm capitalize">{dia.dia}</span>
                    {esHoy && (
                      <span
                        className="text-xs px-2 py-0.5 rounded-full font-medium"
                        style={{ background: `${color}20`, color }}
                      >
                        hoy
                      </span>
                    )}
                  </div>
                  <p className="text-xs mt-0.5" style={{ color: `${color}99` }}>
                    {GRUPO_ICON[dia.grupo]} {dia.grupo} · {dia.total} ejercicios
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  {pct > 0 && pct < 100 && (
                    <span className="text-xs text-slate-500">{pct}%</span>
                  )}
                  <ChevronRight
                    size={16}
                    className={`text-slate-700 transition-transform ${isOpen ? 'rotate-90' : ''}`}
                  />
                </div>
              </button>

              {/* Exercises list */}
              {isOpen && (
                <div className="border-t border-white/5 divide-y divide-white/5">
                  {dia.ejercicios.map(ej => (
                    <div key={ej.ejercicio_id} className="px-4 py-2.5 flex items-center justify-between">
                      <div className="flex items-center gap-2.5 flex-1 min-w-0">
                        {ej.completado
                          ? <div className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: color }} />
                          : <div className="w-1.5 h-1.5 rounded-full shrink-0 bg-slate-700" />
                        }
                        <span className={`text-sm truncate ${ej.completado ? 'text-slate-500 line-through' : 'text-slate-300'}`}>
                          {ej.es_cardio ? '🏃 ' : ''}{ej.nombre}
                        </span>
                      </div>
                      <span className="text-slate-600 text-xs shrink-0 ml-2">
                        {ej.es_cardio ? ej.reps : `${ej.series}×${ej.reps}`}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
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
      <div className="text-5xl mb-4">📅</div>
      <h2 className="text-white font-bold text-lg mb-2">Sin plan activo</h2>
      <p className="text-slate-500 text-sm">Crea tu plan desde el bot de Telegram.</p>
    </div>
  )
}
