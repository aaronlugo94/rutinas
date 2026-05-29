import { useState } from 'react'
import { CheckCircle, Circle } from 'lucide-react'
import { usePlan } from '../lib/hooks'

const GRUPO_ICON = {
  gluteo: '🍑', pierna: '🦵', empuje: '💪',
  tiron: '🏋️', core: '🎯', cardio: '🏃', general: '⚡',
}

export default function Plan() {
  const { data, loading } = usePlan()
  const [semSel, setSemSel] = useState(null)

  if (loading) return <Spinner />
  if (!data?.semanas?.length) return <Empty />

  const semActual = data.semana_actual
  const semanas   = data.semanas
  const sem       = semanas.find(s => s.semana === (semSel ?? semActual)) || semanas[0]

  return (
    <div className="px-4 pt-6 pb-4">
      <h1 className="text-xl font-semibold text-white mb-4">Plan de entrenamiento</h1>

      {/* Week selector */}
      <div className="flex gap-2 mb-5 overflow-x-auto pb-1">
        {semanas.map(s => (
          <button
            key={s.semana}
            onClick={() => setSemSel(s.semana)}
            className={`shrink-0 px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
              (semSel ?? semActual) === s.semana
                ? 'bg-blue-600 text-white'
                : s.semana === semActual
                ? 'bg-blue-600/20 text-blue-400 border border-blue-500/40'
                : 'bg-slate-800 text-slate-400'
            }`}
          >
            S{s.semana}{s.semana === semActual ? ' ←' : ''}
          </button>
        ))}
      </div>

      {/* Days */}
      <div className="space-y-3">
        {sem.dias.map(dia => {
          const pct = dia.total > 0 ? Math.round(dia.completado / dia.total * 100) : 0
          const hecho = pct === 100
          const esHoy = dia.es_hoy

          return (
            <div
              key={dia.dia}
              className={`border rounded-xl overflow-hidden ${
                esHoy  ? 'border-blue-500/50 bg-blue-500/5' :
                hecho  ? 'border-green-500/30 bg-green-500/5' :
                         'border-slate-700 bg-slate-800/40'
              }`}
            >
              {/* Day header */}
              <div className="px-4 py-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {hecho
                    ? <CheckCircle size={16} className="text-green-400" />
                    : <Circle size={16} className="text-slate-600" />
                  }
                  <div>
                    <span className="text-white font-medium text-sm capitalize">{dia.dia}</span>
                    {esHoy && <span className="ml-2 text-xs text-blue-400">hoy</span>}
                    <p className="text-xs text-slate-400">
                      {GRUPO_ICON[dia.grupo]} {dia.grupo}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-xs text-slate-500">{dia.completado}/{dia.total}</p>
                  {pct > 0 && pct < 100 && (
                    <div className="w-12 h-1 bg-slate-700 rounded-full mt-1 overflow-hidden">
                      <div className="h-full bg-blue-500 rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                  )}
                </div>
              </div>

              {/* Exercises */}
              <div className="border-t border-slate-700/50 divide-y divide-slate-700/30">
                {dia.ejercicios.map(ej => (
                  <div key={ej.ejercicio_id} className="px-4 py-2 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {ej.completado
                        ? <CheckCircle size={12} className="text-green-400 shrink-0" />
                        : <div className="w-3 h-3 rounded-full border border-slate-600 shrink-0" />
                      }
                      <span className={`text-sm ${ej.completado ? 'text-slate-400 line-through' : 'text-slate-300'}`}>
                        {ej.es_cardio ? '🏃 ' : ''}{ej.nombre}
                      </span>
                    </div>
                    <span className="text-xs text-slate-500 shrink-0 ml-2">
                      {ej.es_cardio ? ej.reps : `${ej.series}×${ej.reps}`}
                    </span>
                  </div>
                ))}
              </div>
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
      <div className="text-slate-400 text-sm">Cargando...</div>
    </div>
  )
}

function Empty() {
  return (
    <div className="flex flex-col items-center justify-center min-h-dvh px-6 text-center">
      <div className="text-4xl mb-4">📅</div>
      <h2 className="text-white font-medium mb-2">Sin plan activo</h2>
      <p className="text-slate-400 text-sm">Crea tu plan desde el bot de Telegram.</p>
    </div>
  )
}
