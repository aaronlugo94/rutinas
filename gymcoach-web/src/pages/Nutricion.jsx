import { useState } from 'react'
import { ChevronDown, ChevronUp, Zap } from 'lucide-react'
import { useNutricion, useMacros } from '../lib/hooks'

const TIPO_COLOR = {
  GYM:          '#0A84FF',
  CASA:         '#30D158',
  FIN_DE_SEMANA:'#BF5AF2',
  RESETEO:      '#FF9F0A',
}
const TIPO_LABEL = {
  GYM:          '🏋️ Gym',
  CASA:         '🏠 Casa',
  FIN_DE_SEMANA:'🌅 Fin de semana',
  RESETEO:      '🔄 Reseteo',
}
const COMIDA_ICON = {
  Desayuno: '🌅', Almuerzo: '☀️', Colacion: '🍎',
  Cena: '🌙', Rutina: '💪',
}

function MacroRing({ label, value, unit, color, max }) {
  const pct = Math.min(100, Math.round((value / max) * 100))
  const r   = 28
  const circ = 2 * Math.PI * r
  return (
    <div className="flex flex-col items-center">
      <div className="relative w-16 h-16">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 64 64">
          <circle cx="32" cy="32" r={r} fill="none" stroke="#27272A" strokeWidth="6" />
          <circle cx="32" cy="32" r={r} fill="none"
            stroke={color} strokeWidth="6"
            strokeDasharray={`${circ * pct / 100} ${circ * (1 - pct / 100)}`}
            strokeLinecap="round"
            style={{ filter: `drop-shadow(0 0 6px ${color}80)` }}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-white text-xs font-bold">{value}</span>
        </div>
      </div>
      <p className="text-zinc-500 text-xs mt-1">{label}</p>
      <p className="text-zinc-600 text-[10px]">{unit}</p>
    </div>
  )
}

export default function Nutricion() {
  const { data: plan,   loading: lp } = useNutricion()
  const { data: macros, loading: lm } = useMacros()
  const [diaOpen, setDiaOpen] = useState(0)

  if (lp || lm) return <Spinner />

  return (
    <div className="bg-black min-h-dvh px-4 pt-10 pb-6 fade-up">
      <p className="text-zinc-500 text-sm uppercase tracking-widest mb-1">Plan adaptativo</p>
      <h1 className="text-3xl font-bold text-white mb-6">Nutrición</h1>

      {/* Macros del día */}
      <div className="card p-4 mb-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-white font-bold text-sm">Macros de hoy</p>
          {macros?.tiene_datos && (
            <div className="flex items-center gap-1">
              <Zap size={12} className="text-yellow-400" />
              <span className="text-yellow-400 font-mono text-sm font-bold">
                {macros.calorias} kcal
              </span>
            </div>
          )}
        </div>
        {macros?.tiene_datos ? (
          <div className="flex justify-around">
            <MacroRing label="Proteína" value={macros.proteina} unit="g"    color="#FF375F" max={250} />
            <MacroRing label="Carbs"    value={macros.carbs}    unit="g"    color="#FFD60A" max={400} />
            <MacroRing label="Grasas"   value={macros.grasas}   unit="g"    color="#30D158" max={120} />
            <MacroRing label="Kcal"     value={macros.calorias} unit="kcal" color="#0A84FF" max={3500} />
          </div>
        ) : (
          <p className="text-zinc-600 text-sm text-center py-2">
            Sin datos — pésate en ayunas para calcular tus macros
          </p>
        )}
      </div>

      {/* Plan semanal */}
      {!plan?.tiene_plan ? (
        <div className="card p-6 text-center">
          <div className="text-4xl mb-3">📅</div>
          <p className="text-white font-semibold mb-1">Sin plan esta semana</p>
          <p className="text-zinc-500 text-sm">
            El plan se genera automáticamente cada domingo con tus datos de la báscula.
          </p>
        </div>
      ) : (
        <>
          {/* Diagnóstico */}
          {plan.diagnostico && (
            <div className="card p-4 mb-4" style={{ background: '#BF5AF215', border: '1px solid #BF5AF230' }}>
              <p className="text-xs text-purple-400 font-semibold uppercase tracking-wider mb-2">
                🧠 Diagnóstico semanal
              </p>
              <p className="text-zinc-300 text-sm leading-relaxed">{plan.diagnostico}</p>
            </div>
          )}

          {/* Estado MIMO + multiplicador */}
          <div className="flex gap-2 mb-4">
            {plan.estado_mimo && (
              <div className="flex-1 card-sm p-3 text-center">
                <p className="text-zinc-600 text-xs">Estado metabólico</p>
                <p className="text-white text-xs font-bold mt-0.5">{plan.estado_mimo.replace('_',' ')}</p>
              </div>
            )}
            {plan.kcal_mult && (
              <div className="flex-1 card-sm p-3 text-center">
                <p className="text-zinc-600 text-xs">Multiplicador</p>
                <p className="text-white text-sm font-bold mt-0.5">{plan.kcal_mult} kcal/kg</p>
              </div>
            )}
          </div>

          {/* Días */}
          <div className="space-y-2">
            {plan.dias?.map((dia, idx) => {
              const color = TIPO_COLOR[dia.tipo] || '#8E8E93'
              const isOpen = diaOpen === idx
              return (
                <div
                  key={idx}
                  className="card overflow-hidden"
                  style={isOpen ? { borderColor: `${color}40` } : {}}
                >
                  <button
                    className="w-full px-4 py-3.5 flex items-center justify-between"
                    onClick={() => setDiaOpen(isOpen ? null : idx)}
                  >
                    <div className="text-left">
                      <p className="text-white font-semibold text-sm">{dia.nombre}</p>
                      <p className="text-xs mt-0.5 font-medium" style={{ color }}>
                        {TIPO_LABEL[dia.tipo] || dia.tipo}
                        {dia.subtitulo ? ` · ${dia.subtitulo}` : ''}
                      </p>
                    </div>
                    {isOpen
                      ? <ChevronUp size={16} className="text-zinc-600 shrink-0" />
                      : <ChevronDown size={16} className="text-zinc-600 shrink-0" />
                    }
                  </button>

                  {isOpen && (
                    <div className="border-t border-zinc-800 divide-y divide-zinc-800/50">
                      {dia.comidas?.map((comida, ci) => (
                        <div key={ci} className="px-4 py-3">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-base">{COMIDA_ICON[comida.label] || '🍽'}</span>
                            <span className="text-xs font-bold uppercase tracking-wider"
                              style={{ color }}>{comida.label}</span>
                          </div>
                          <p className="text-zinc-300 text-sm leading-relaxed ml-6">{comida.texto}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          <p className="text-zinc-700 text-xs text-center mt-4">
            Plan generado el {plan.fecha} · Se actualiza cada domingo
          </p>
        </>
      )}
    </div>
  )
}

function Spinner() {
  return (
    <div className="flex items-center justify-center min-h-dvh bg-black">
      <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )
}
