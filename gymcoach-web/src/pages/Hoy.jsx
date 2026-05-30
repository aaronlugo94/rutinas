import { useState } from 'react'
import { RefreshCw, ChevronRight, Check, Flame, Bike } from 'lucide-react'
import { useRutina } from '../lib/hooks'
import { api } from '../lib/api'

const GRUPO_ICON = {
  gluteo: '🍑', pierna: '🦵', empuje: '💪',
  tiron: '🏋️', core: '🎯', cardio: '🏃',
}

export default function Hoy() {
  const { data, loading, error, refetch } = useRutina()
  const [swapOpen,  setSwapOpen]  = useState(null)
  const [alts,      setAlts]      = useState([])
  const [sesionModal, setSesionModal] = useState(false)
  const [rir,       setRir]       = useState(2)
  const [fatiga,    setFatiga]    = useState(2)
  const [saving,    setSaving]    = useState(false)
  const [pesos,     setPesos]     = useState({})
  const [done,      setDone]      = useState(false)

  if (loading) return <LoadingScreen />
  if (error)   return <ErrorScreen msg={error} onRetry={refetch} />
  if (!data)   return null

  if (data.tipo === 'recovery') return <RecoveryScreen data={data} />

  const { semana, dia, grupo, duracion_min, calentamiento, ejercicios, racha, nivel } = data
  const fuerza  = ejercicios.filter(e => !e.es_cardio)
  const cardio  = ejercicios.find(e => e.es_cardio)

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
    // Save all entered weights
    for (const [eid, peso] of Object.entries(pesos)) {
      if (peso) {
        const ej = ejercicios.find(e => e.ejercicio_id === eid)
        await api.guardarPeso({
          ejercicio_id: eid,
          peso_lbs: parseFloat(peso),
          semana, dia,
          series: ej?.series,
          reps:   ej?.reps,
        })
      }
    }
    await api.completarSesion({ semana, dia, rir, fatiga })
    setSaving(false)
    setDone(true)
  }

  if (done) return <DoneScreen racha={racha + 1} onNext={refetch} />

  return (
    <div className="px-4 pt-6 pb-4">
      {/* Header */}
      <div className="mb-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-white capitalize">
              {GRUPO_ICON[grupo]} {dia} — {grupo}
            </h1>
            <p className="text-sm text-slate-400 mt-0.5">
              S{semana} · 🏋️ Gym · ~{duracion_min} min
            </p>
          </div>
          {racha > 0 && (
            <div className="flex items-center gap-1 bg-orange-500/10 px-3 py-1.5 rounded-full">
              <Flame size={14} className="text-orange-400" />
              <span className="text-orange-400 text-sm font-medium">{racha}d</span>
            </div>
          )}
        </div>
      </div>

      {/* Calentamiento */}
      <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl px-4 py-3 mb-4">
        <p className="text-blue-300 text-sm font-medium">🔥 Calentamiento</p>
        <p className="text-blue-200 text-sm mt-0.5">{calentamiento.nombre}</p>
      </div>

      {/* Ejercicios */}
      <div className="space-y-3 mb-4">
        {fuerza.map((ej, i) => (
          <EjercicioCard
            key={ej.ejercicio_id}
            ej={ej}
            num={i + 1}
            peso={pesos[ej.ejercicio_id] || ''}
            onPeso={v => setPesos(p => ({ ...p, [ej.ejercicio_id]: v }))}
            onSwap={() => openSwap(ej.ejercicio_id)}
          />
        ))}

        {cardio && (
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl px-4 py-3">
            <p className="text-slate-300 text-sm">
              🏃 {cardio.nombre} — {cardio.reps}
            </p>
            <p className="text-slate-500 text-xs mt-0.5">Zona 2 · 120-135 bpm</p>
          </div>
        )}
      </div>

      {/* Terminar */}
      <button
        onClick={() => setSesionModal(true)}
        className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-4 rounded-xl text-base transition-colors flex items-center justify-center gap-2"
      >
        <Check size={18} />
        Terminé la rutina
      </button>

      {/* Swap modal */}
      {swapOpen && (
        <Modal title="Cambiar ejercicio" onClose={() => setSwapOpen(null)}>
          {alts.length === 0
            ? <p className="text-slate-400 text-sm text-center py-4">Sin alternativas</p>
            : alts.map(a => (
              <button
                key={a.ejercicio_id}
                onClick={() => doSwap(swapOpen, a.ejercicio_id)}
                className="w-full text-left px-4 py-3 bg-slate-800 hover:bg-slate-700 rounded-xl mb-2 transition-colors"
              >
                <div className="flex justify-between items-center">
                  <span className="text-white text-sm">{a.nombre}</span>
                  <span className="text-slate-400 text-xs">EMG {a.emg_score}⚡</span>
                </div>
                {a.cue && <p className="text-slate-500 text-xs mt-0.5">{a.cue}</p>}
              </button>
            ))
          }
        </Modal>
      )}

      {/* Sesion modal */}
      {sesionModal && (
        <Modal title="¿Cómo estuvo?" onClose={() => setSesionModal(false)}>
          <div className="space-y-3 mb-5">
            {[
              { rir: 0, fat: 5, label: '🔥 Sin reserva — lo di todo' },
              { rir: 2, fat: 3, label: '💪 Bien — quedaban 1-2 reps' },
              { rir: 3, fat: 2, label: '😌 Fácil — podía más' },
              { rir: 2, fat: 4, label: '😓 Muy cansado hoy' },
            ].map(opt => (
              <button
                key={opt.label}
                onClick={() => { setRir(opt.rir); setFatiga(opt.fat) }}
                className={`w-full text-left px-4 py-3 rounded-xl border transition-colors text-sm ${
                  rir === opt.rir && fatiga === opt.fat
                    ? 'bg-blue-600/20 border-blue-500 text-white'
                    : 'bg-slate-800 border-slate-700 text-slate-300 hover:border-slate-600'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <button
            onClick={completar}
            disabled={saving}
            className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium py-3 rounded-xl transition-colors"
          >
            {saving ? 'Guardando...' : 'Guardar sesión'}
          </button>
        </Modal>
      )}
    </div>
  )
}

function EjercicioCard({ ej, num, peso, onPeso, onSwap }) {
  return (
    <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1">
          <p className="text-white font-medium text-sm leading-snug">{ej.nombre}</p>
          <p className="text-slate-400 text-xs mt-0.5">
            {ej.series} × {ej.reps} reps
          </p>
        </div>
        <button
          onClick={onSwap}
          className="text-slate-500 hover:text-slate-300 text-xs flex items-center gap-0.5 shrink-0 mt-0.5"
        >
          <RefreshCw size={12} /> cambiar
        </button>
      </div>

      {/* Peso anterior → sugerido */}
      {ej.ultimo_peso && (
        <p className="text-xs text-slate-500 mb-2 flex items-center gap-1">
          <span className="line-through">{ej.ultimo_peso} lbs</span>
          <ChevronRight size={10} />
          <span className="text-green-400 font-medium">
            {ej.peso_sugerido ? `${ej.peso_sugerido} lbs hoy` : ''}
          </span>
        </p>
      )}

      {/* Input peso */}
      <div className="flex items-center gap-2">
        <input
          type="number"
          value={peso}
          onChange={e => onPeso(e.target.value)}
          placeholder={ej.peso_sugerido ? `${ej.peso_sugerido}` : '0'}
          inputMode="decimal"
          className="w-28 bg-slate-900 border border-slate-600 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-blue-500"
        />
        <span className="text-slate-400 text-sm">lbs</span>
        {ej.notas && (
          <p className="text-xs text-slate-500 flex-1 leading-tight">{ej.notas}</p>
        )}
      </div>
    </div>
  )
}

function RecoveryScreen({ data }) {
  return (
    <div className="px-4 pt-8">
      <h1 className="text-xl font-semibold text-white mb-1">
        🌿 {data.dia?.charAt(0).toUpperCase() + data.dia?.slice(1)} — Recovery
      </h1>
      <p className="text-slate-400 text-sm mb-6">El músculo crece hoy. Elige una actividad:</p>
      <div className="space-y-3">
        {data.opciones?.map((o, i) => (
          <div key={i} className="bg-slate-800 border border-slate-700 rounded-xl px-4 py-4">
            <p className="text-white font-medium">{o.emoji} {o.nombre}</p>
            <p className="text-slate-400 text-sm mt-1">{o.desc}</p>
          </div>
        ))}
      </div>
      <div className="mt-6 bg-slate-800/50 rounded-xl px-4 py-3 text-sm text-slate-400">
        Proteína alta aunque no entrenes. Duerme 7-9 hrs.
      </div>
    </div>
  )
}

function DoneScreen({ racha, onNext }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-dvh px-6 text-center">
      <div className="text-5xl mb-4">✅</div>
      <h2 className="text-2xl font-semibold text-white mb-2">Sesión guardada</h2>
      {racha >= 7 && (
        <div className="flex items-center gap-2 text-orange-400 text-lg mb-2">
          <Flame size={20} />
          <span>{racha} días de racha</span>
        </div>
      )}
      <p className="text-slate-400 text-sm mb-8">Los pesos fueron registrados.</p>
      <button
        onClick={onNext}
        className="w-full max-w-xs bg-blue-600 hover:bg-blue-500 text-white font-medium py-3 rounded-xl transition-colors"
      >
        Ver rutina de mañana
      </button>
    </div>
  )
}

function Modal({ title, onClose, children }) {
  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-end z-50"
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div className="w-full bg-slate-900 rounded-t-2xl p-5 pb-8 safe-bottom">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-white font-medium">{title}</h3>
          <button onClick={onClose} className="text-slate-400 text-sm">Cancelar</button>
        </div>
        {children}
      </div>
    </div>
  )
}

function LoadingScreen() {
  return (
    <div className="flex items-center justify-center min-h-dvh">
      <div className="text-slate-400">Cargando...</div>
    </div>
  )
}

function ErrorScreen({ msg, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-dvh px-6 text-center">
      <p className="text-red-400 mb-4">{msg}</p>
      <button onClick={onRetry} className="text-blue-400 text-sm">Reintentar</button>
    </div>
  )
}
