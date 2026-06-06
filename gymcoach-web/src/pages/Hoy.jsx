import { useState } from 'react'
import { RefreshCw, ChevronRight, Check, Zap } from 'lucide-react'
import { useRutina, useMacros } from '../lib/hooks'
import { api } from '../lib/api'

const GRUPO_COLOR = {
  gluteo: '#FF375F', pierna: '#BF5AF2', empuje: '#0A84FF',
  tiron:  '#32ADE6', core:   '#FFD60A', cardio: '#30D158',
}
const GRUPO_ICON = {
  gluteo: '🍑', pierna: '🦵', empuje: '💪',
  tiron: '🏋️', core: '🎯', cardio: '🏃',
}

export default function Hoy() {
  const { data, loading, error, refetch } = useRutina()
  const { data: macros } = useMacros()
  const [swapOpen,    setSwapOpen]    = useState(null)
  const [alts,        setAlts]        = useState([])
  const [sesionModal, setSesionModal] = useState(false)
  const [rir,         setRir]         = useState(2)
  const [fatiga,      setFatiga]      = useState(2)
  const [saving,      setSaving]      = useState(false)
  const [pesos,       setPesos]       = useState({})
  const [done,        setDone]        = useState(false)

  if (loading) return <Spinner />
  if (error)   return <ErrorScreen msg={error} onRetry={refetch} />
  if (!data)   return null
  if (data.tipo === 'recovery') return <RecoveryScreen data={data} />

  const { semana, dia, grupo, duracion_min, calentamiento, ejercicios, racha } = data
  const fuerza = ejercicios.filter(e => !e.es_cardio)
  const cardio = ejercicios.find(e => e.es_cardio)
  const color  = GRUPO_COLOR[grupo] || '#0A84FF'

  async function openSwap(eid) {
    setSwapOpen(eid)
    const res = await api.alternativas(eid)
    setAlts(res.alternativas || [])
  }

  async function doSwap(orig, nuevo) {
    await api.swap(orig, nuevo)
    setSwapOpen(null)
    refetch()
  }

  async function completar() {
    setSaving(true)
    for (const [eid, peso] of Object.entries(pesos)) {
      if (peso) {
        const ej = ejercicios.find(e => e.ejercicio_id === eid)
        await api.guardarPeso({
          ejercicio_id: eid, peso_lbs: parseFloat(peso),
          semana, dia, series: ej?.series, reps: ej?.reps,
        })
      }
    }
    await api.completarSesion({ semana, dia, rir, fatiga })
    setSaving(false)
    setDone(true)
  }

  if (done) return <DoneScreen racha={racha + 1} onNext={refetch} />

  return (
    <div className="bg-black min-h-dvh pb-24">
      {/* Hero header */}
      <div
        className="px-5 pt-12 pb-6"
        style={{ background: `linear-gradient(180deg, ${color}22 0%, transparent 100%)` }}
      >
        <p className="text-zinc-500 text-sm font-medium uppercase tracking-widest mb-1">
          Semana {semana}
        </p>
        <h1 className="text-3xl font-bold text-white capitalize mb-1">
          {GRUPO_ICON[grupo]} {dia}
        </h1>
        <div className="flex items-center gap-3 mt-2">
          <span className="text-sm font-medium px-3 py-1 rounded-full"
            style={{ background: `${color}25`, color }}>
            {grupo}
          </span>
          <span className="text-zinc-500 text-sm">~{duracion_min} min</span>
          {racha > 0 && (
            <span className="text-sm font-medium" style={{ color: '#FF6B00' }}>
              🔥 {racha} días
            </span>
          )}
        </div>
      </div>

      <div className="px-4 space-y-3">
        {/* Macros del día */}
        {macros?.tiene_datos && (
          <div className="card px-4 py-3 mb-3">
            <div className="flex items-center justify-between">
              <span className="text-zinc-500 text-xs uppercase tracking-wider">Macros de hoy</span>
              <span className="font-mono text-yellow-400 font-bold text-sm">{macros.calorias} kcal</span>
            </div>
            <div className="flex gap-3 mt-2">
              {[
                { label: 'Prot', val: macros.proteina, unit: 'g', color: '#FF375F' },
                { label: 'Carbs', val: macros.carbs,   unit: 'g', color: '#FFD60A' },
                { label: 'Grasas', val: macros.grasas, unit: 'g', color: '#30D158' },
              ].map(m => (
                <div key={m.label} className="flex-1 text-center">
                  <p className="text-white font-bold text-sm">{m.val}<span className="text-zinc-600 text-xs">{m.unit}</span></p>
                  <p className="text-zinc-600 text-xs">{m.label}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Warmup */}
        <div className="card px-4 py-3 flex items-center gap-3"
          style={{ background: '#1C1C1E', borderLeft: `3px solid ${color}` }}>
          <span className="text-lg">🔥</span>
          <div>
            <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Calentamiento</p>
            <p className="text-white text-sm mt-0.5">{calentamiento.nombre}</p>
          </div>
        </div>

        {/* Exercises */}
        {fuerza.map((ej, i) => {
          const peso = pesos[ej.ejercicio_id] || ''
          const sug  = ej.peso_sugerido
          const prev = ej.ultimo_peso
          return (
            <div key={ej.ejercicio_id} className="card">
              <div className="px-4 pt-4 pb-3">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold px-2 py-0.5 rounded-md text-black"
                        style={{ background: color }}>
                        {i + 1}
                      </span>
                      <p className="text-white font-semibold text-sm">{ej.nombre}</p>
                    </div>
                    <p className="text-zinc-500 text-xs mt-1 ml-7">
                      {ej.series} series × {ej.reps} reps
                    </p>
                  </div>
                  <button
                    onClick={() => openSwap(ej.ejercicio_id)}
                    className="text-zinc-600 hover:text-zinc-400 p-1.5 rounded-xl bg-zinc-800/50"
                  >
                    <RefreshCw size={13} />
                  </button>
                </div>

                {/* Peso anterior → sugerido */}
                {(prev || sug) && (
                  <div className="flex items-center gap-2 ml-7 mb-3">
                    {prev && <span className="text-zinc-600 text-xs line-through">{prev} lbs</span>}
                    {prev && sug && <ChevronRight size={10} className="text-zinc-700" />}
                    {sug && (
                      <span className="text-xs font-semibold px-2 py-0.5 rounded-md"
                        style={{ background: `${color}20`, color }}>
                        {sug} lbs hoy
                      </span>
                    )}
                  </div>
                )}

                {/* Weight input */}
                <div className="flex items-center gap-3 ml-7">
                  <div className="relative flex-1 max-w-[140px]">
                    <input
                      type="number"
                      value={peso}
                      onChange={e => setPesos(p => ({ ...p, [ej.ejercicio_id]: e.target.value }))}
                      placeholder={sug ? `${sug}` : '0'}
                      inputMode="decimal"
                      className="w-full bg-zinc-800 rounded-xl px-3 py-2.5 text-white text-base font-semibold focus:outline-none pr-12"
                      style={{ caretColor: color }}
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 text-sm">lbs</span>
                  </div>
                  {peso && (
                    <div className="w-7 h-7 rounded-full flex items-center justify-center"
                      style={{ background: color }}>
                      <Check size={13} className="text-black" strokeWidth={3} />
                    </div>
                  )}
                </div>

                {/* Nota técnica */}
                {ej.notas && (
                  <p className="text-zinc-600 text-xs mt-2 ml-7 leading-relaxed">{ej.notas}</p>
                )}
              </div>
            </div>
          )
        })}

        {/* Cardio */}
        {cardio && (
          <div className="card px-4 py-4" style={{ borderLeft: '3px solid #30D158' }}>
            <p className="text-xs text-zinc-500 font-medium uppercase tracking-wider mb-1">Cardio final</p>
            <p className="text-white font-semibold">🏃 {cardio.nombre}</p>
            <p className="text-zinc-500 text-sm mt-0.5">{cardio.reps} · Zona 2 · 120-135 bpm</p>
          </div>
        )}

        {/* Finish button */}
        <button
          onClick={() => setSesionModal(true)}
          className="w-full py-4 rounded-2xl text-base font-bold text-black flex items-center justify-center gap-2 active:scale-95 transition-transform"
          style={{ background: color }}
        >
          <Check size={20} strokeWidth={3} />
          Terminé la rutina
        </button>
      </div>

      {/* Swap modal */}
      {swapOpen && (
        <BottomSheet title="Cambiar ejercicio" onClose={() => setSwapOpen(null)}>
          {alts.length === 0
            ? <p className="text-zinc-500 text-sm text-center py-6">Sin alternativas disponibles</p>
            : alts.map(a => (
              <button
                key={a.ejercicio_id}
                onClick={() => doSwap(swapOpen, a.ejercicio_id)}
                className="w-full text-left px-4 py-3.5 rounded-2xl bg-zinc-800 hover:bg-zinc-700 mb-2 active:scale-[0.99] transition-all"
              >
                <div className="flex justify-between items-center">
                  <span className="text-white font-medium text-sm">{a.nombre}</span>
                  <div className="flex items-center gap-1">
                    <Zap size={11} className="text-yellow-400" />
                    <span className="text-zinc-400 text-xs">{a.emg_score}</span>
                  </div>
                </div>
                {a.cue && <p className="text-zinc-600 text-xs mt-0.5">{a.cue}</p>}
              </button>
            ))
          }
        </BottomSheet>
      )}

      {/* Session feedback modal */}
      {sesionModal && (
        <BottomSheet title="¿Cómo estuvo?" onClose={() => setSesionModal(false)}>
          <div className="space-y-2 mb-5">
            {[
              { rir: 0, fat: 5, emoji: '🔥', label: 'Sin reserva', sub: 'Lo diste todo' },
              { rir: 2, fat: 3, emoji: '💪', label: 'Bien',        sub: 'Quedaban 1-2 reps' },
              { rir: 3, fat: 2, emoji: '😌', label: 'Fácil',       sub: 'Podías más' },
              { rir: 2, fat: 4, emoji: '😓', label: 'Muy cansado', sub: 'Día duro' },
            ].map(opt => {
              const sel = rir === opt.rir && fatiga === opt.fat
              return (
                <button
                  key={opt.label}
                  onClick={() => { setRir(opt.rir); setFatiga(opt.fat) }}
                  className={`w-full text-left px-4 py-3.5 rounded-2xl flex items-center gap-3 transition-all active:scale-[0.99] ${
                    sel ? 'bg-blue-600' : 'bg-zinc-800 hover:bg-zinc-700'
                  }`}
                >
                  <span className="text-2xl">{opt.emoji}</span>
                  <div>
                    <p className="text-white font-semibold text-sm">{opt.label}</p>
                    <p className={`text-xs ${sel ? 'text-blue-200' : 'text-zinc-500'}`}>{opt.sub}</p>
                  </div>
                </button>
              )
            })}
          </div>
          <button
            onClick={completar}
            disabled={saving}
            className="w-full bg-white text-black font-bold py-4 rounded-2xl text-base disabled:opacity-50 active:scale-95 transition-all"
          >
            {saving ? 'Guardando...' : 'Guardar sesión'}
          </button>
        </BottomSheet>
      )}
    </div>
  )
}

function BottomSheet({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 bg-black/70 flex items-end z-50 backdrop-blur-sm"
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="w-full bg-zinc-900 rounded-t-3xl p-5 pb-10 safe-bottom max-h-[85dvh] overflow-y-auto">
        <div className="w-10 h-1 bg-zinc-700 rounded-full mx-auto mb-5" />
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-white font-bold text-base">{title}</h3>
          <button onClick={onClose} className="text-zinc-500 text-sm">Cancelar</button>
        </div>
        {children}
      </div>
    </div>
  )
}

function RecoveryScreen({ data }) {
  return (
    <div className="bg-black min-h-dvh px-5 pt-12">
      <div className="bg-gradient-to-br from-green-500/20 to-transparent rounded-3xl p-6 mb-5">
        <p className="text-zinc-400 text-sm uppercase tracking-widest mb-1">Hoy</p>
        <h1 className="text-3xl font-bold text-white mb-1 capitalize">{data.dia}</h1>
        <p className="text-green-400 font-semibold">Recovery activo</p>
      </div>
      <p className="text-zinc-400 text-sm mb-4">Elige tu actividad de hoy 👇</p>
      <div className="space-y-2">
        {data.opciones?.map((o, i) => (
          <div key={i} className="card px-4 py-4">
            <p className="text-white font-semibold">{o.emoji} {o.nombre}</p>
            <p className="text-zinc-500 text-sm mt-1">{o.desc}</p>
          </div>
        ))}
      </div>
      <p className="text-zinc-600 text-xs mt-5 text-center">
        El músculo crece hoy. Proteína alta, 7-9 hrs de sueño.
      </p>
    </div>
  )
}

function DoneScreen({ racha, onNext }) {
  return (
    <div className="bg-black min-h-dvh flex flex-col items-center justify-center px-6 text-center">
      <div className="w-24 h-24 rounded-full bg-gradient-to-br from-green-400 to-green-600 flex items-center justify-center mb-6 shadow-lg shadow-green-500/30">
        <Check size={44} className="text-black" strokeWidth={3} />
      </div>
      <h2 className="text-2xl font-bold text-white mb-2">¡Sesión completa!</h2>
      {racha >= 3 && (
        <p className="text-orange-400 font-semibold mb-1">🔥 {racha} días de racha</p>
      )}
      <p className="text-zinc-500 text-sm mb-10">Los pesos fueron registrados.</p>
      <button
        onClick={onNext}
        className="w-full max-w-xs bg-white text-black font-bold py-4 rounded-2xl active:scale-95 transition-transform"
      >
        Ver siguiente día
      </button>
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

function ErrorScreen({ msg, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-dvh bg-black px-6 text-center">
      <p className="text-zinc-400 mb-4 text-sm">{msg}</p>
      <button onClick={onRetry} className="text-blue-400 text-sm font-medium">Reintentar</button>
    </div>
  )
}
