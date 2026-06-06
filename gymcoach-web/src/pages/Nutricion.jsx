import { useState } from 'react'
import { ChevronDown, ChevronUp, Flame, Beef, Wheat, Droplets, RefreshCw } from 'lucide-react'
import { useNutricion, useMacros } from '../lib/hooks'
import { api } from '../lib/api'

const TIPO_CONFIG = {
  GYM:          { color: '#0A84FF', label: 'Día de Gym',       emoji: '🏋️' },
  CASA:         { color: '#30D158', label: 'Día Normal',        emoji: '🏠' },
  FIN_DE_SEMANA:{ color: '#BF5AF2', label: 'Fin de Semana',     emoji: '🌅' },
  RESETEO:      { color: '#FF9F0A', label: 'Reseteo',           emoji: '🔄' },
}
const COMIDA_ICON = {
  Desayuno: '🌅', Almuerzo: '☀️', Colacion: '🍎',
  Cena: '🌙', Rutina: '💪', Snack: '🫐',
}
const DIAS = ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom']

function MacroRing({ label, value, unit, color, max, icon: Icon }) {
  const pct  = Math.min(100, Math.round((value / max) * 100))
  const r    = 30
  const circ = 2 * Math.PI * r
  const dash = circ * (pct / 100)

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="relative w-[72px] h-[72px]">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 72 72">
          <circle cx="36" cy="36" r={r} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="6" />
          <circle
            cx="36" cy="36" r={r} fill="none"
            stroke={color} strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={`${dash} ${circ - dash}`}
            style={{ transition: 'stroke-dasharray 0.8s cubic-bezier(0.16,1,0.3,1)' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-sm font-bold text-white" style={{ fontFamily: 'var(--font-display)' }}>
            {value}
          </span>
          <span className="text-[9px] text-zinc-600">{unit}</span>
        </div>
      </div>
      <span className="text-[11px] text-zinc-500 font-medium">{label}</span>
    </div>
  )
}

function MealCard({ comida }) {
  const [open, setOpen] = useState(false)
  const icon = COMIDA_ICON[comida.nombre] || '🍽️'

  return (
    <div className="card overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3.5 btn-press"
      >
        <div className="flex items-center gap-3">
          <span className="text-xl">{icon}</span>
          <div className="text-left">
            <p className="text-white font-semibold text-sm">{comida.nombre}</p>
            <p className="text-zinc-500 text-xs mt-0.5">
              {comida.kcal} kcal · {comida.proteina}g prot
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-600 font-mono">{comida.kcal} kcal</span>
          {open
            ? <ChevronUp size={14} className="text-zinc-500" />
            : <ChevronDown size={14} className="text-zinc-500" />
          }
        </div>
      </button>

      {open && (
        <div className="border-t border-white/5 px-4 py-3 space-y-2 fade-in">
          {(comida.alimentos || []).map((a, i) => (
            <div key={i} className="flex items-start justify-between gap-2">
              <div className="flex-1">
                <p className="text-zinc-200 text-sm">{a.nombre}</p>
                {a.cantidad && (
                  <p className="text-zinc-600 text-xs">{a.cantidad}</p>
                )}
              </div>
              <div className="text-right flex-shrink-0">
                <p className="text-zinc-400 text-xs font-mono">{a.kcal} kcal</p>
                <p className="text-zinc-600 text-xs">{a.proteina}g P</p>
              </div>
            </div>
          ))}
          {comida.nota && (
            <p className="text-zinc-600 text-xs italic border-t border-white/5 pt-2 mt-2">
              {comida.nota}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export default function Nutricion() {
  const { data: plan,   loading: lp } = useNutricion()
  const { data: macros, loading: lm } = useMacros()
  const [diaIdx, setDiaIdx] = useState(new Date().getDay() === 0 ? 6 : new Date().getDay() - 1)
  const [regen, setRegen]   = useState(false)

  if (lp || lm) return <Spinner />

  const diaActual   = plan?.dias?.[diaIdx]
  const tipoConfig  = TIPO_CONFIG[diaActual?.tipo] || TIPO_CONFIG.CASA
  const color       = tipoConfig.color

  async function regenerar() {
    setRegen(true)
    try { await api.request?.('POST', '/nutricion/generar') }
    catch (e) { /* silent */ }
    setRegen(false)
    window.location.reload()
  }

  return (
    <div className="min-h-dvh bg-black pb-8">
      {/* Header */}
      <div
        className="px-5 pt-12 pb-6"
        style={{ background: `linear-gradient(180deg, ${color}18 0%, transparent 100%)` }}
      >
        <div className="flex items-center justify-between mb-1">
          <div>
            <p className="text-zinc-500 text-xs font-medium uppercase tracking-widest">Nutrición</p>
            <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'var(--font-display)' }}>
              Plan semanal
            </h1>
          </div>
          <button
            onClick={regenerar}
            disabled={regen}
            className="p-2.5 rounded-full bg-white/8 btn-press disabled:opacity-40"
          >
            <RefreshCw size={16} className={`text-zinc-400 ${regen ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Macros diarios */}
        {macros?.tiene_datos && (
          <div className="card-glass px-4 py-4 mt-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Hoy</p>
              <div className="flex items-center gap-1">
                <Flame size={12} className="text-orange-400" />
                <span className="text-orange-400 font-bold text-sm">{macros.calorias} kcal</span>
              </div>
            </div>
            <div className="flex justify-around">
              <MacroRing label="Proteína" value={macros.proteina} unit="g" color="#FF375F" max={250} />
              <MacroRing label="Carbs"    value={macros.carbs}    unit="g" color="#FFD60A" max={350} />
              <MacroRing label="Grasas"   value={macros.grasas}   unit="g" color="#30D158" max={100} />
            </div>
            {macros.fuente === 'estimado' && (
              <p className="text-center text-zinc-600 text-xs mt-3">
                ⚠️ Estimación — pésate para mayor precisión
              </p>
            )}
          </div>
        )}
      </div>

      {/* Day selector */}
      <div className="px-4 mb-4">
        <div className="flex gap-1.5 overflow-x-auto pb-1 scrollbar-none">
          {DIAS.map((d, i) => {
            const dia     = plan?.dias?.[i]
            const tc      = TIPO_CONFIG[dia?.tipo] || TIPO_CONFIG.CASA
            const isToday = i === (new Date().getDay() === 0 ? 6 : new Date().getDay() - 1)
            const sel     = i === diaIdx
            return (
              <button
                key={d}
                onClick={() => setDiaIdx(i)}
                className={`flex-shrink-0 flex flex-col items-center px-3 py-2 rounded-2xl transition-all duration-200 btn-press ${
                  sel ? 'bg-white/10' : 'bg-zinc-900/50'
                }`}
              >
                <span className={`text-[10px] font-medium uppercase tracking-wider ${sel ? 'text-white' : 'text-zinc-600'}`}>
                  {d}
                </span>
                <div
                  className="w-1.5 h-1.5 rounded-full mt-1.5"
                  style={{ background: sel ? tc.color : 'transparent', border: `1.5px solid ${sel ? tc.color : '#3F3F46'}` }}
                />
                {isToday && <span className="text-[8px] text-zinc-600 mt-0.5">HOY</span>}
              </button>
            )
          })}
        </div>
      </div>

      {/* Day content */}
      {diaActual ? (
        <div className="px-4 space-y-3 fade-up stagger">
          {/* Day type badge */}
          <div
            className="flex items-center gap-2 px-4 py-3 rounded-2xl"
            style={{ background: `${color}15`, border: `1px solid ${color}30` }}
          >
            <span className="text-lg">{tipoConfig.emoji}</span>
            <div>
              <p className="text-white font-semibold text-sm">{tipoConfig.label}</p>
              <p className="text-xs" style={{ color }}>{diaActual.kcal_total} kcal · {diaActual.proteina_total}g proteína</p>
            </div>
          </div>

          {/* Meals */}
          {(diaActual.comidas || []).map((comida, i) => (
            <MealCard key={i} comida={comida} />
          ))}

          {/* Tips */}
          {diaActual.tip && (
            <div className="card px-4 py-3">
              <p className="text-zinc-500 text-xs font-medium uppercase tracking-wider mb-1">Tip del día</p>
              <p className="text-zinc-300 text-sm leading-relaxed">{diaActual.tip}</p>
            </div>
          )}
        </div>
      ) : (
        <div className="px-4">
          <div className="card px-5 py-8 text-center">
            <p className="text-4xl mb-3">🥗</p>
            <p className="text-white font-semibold mb-1">Sin plan de nutrición</p>
            <p className="text-zinc-500 text-sm mb-4">El plan se genera cada domingo con tus datos de la báscula.</p>
            <button
              onClick={regenerar}
              disabled={regen}
              className="px-5 py-2.5 rounded-full bg-white/10 text-white text-sm font-medium btn-press disabled:opacity-40"
            >
              {regen ? 'Generando...' : 'Generar ahora'}
            </button>
          </div>
        </div>
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
