import { useState, useEffect } from 'react'
import { TrendingDown, TrendingUp, Minus, Target } from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, ReferenceLine, CartesianGrid,
} from 'recharts'
import { useCuerpo } from '../lib/hooks'
import { api } from '../lib/api'

const MIMO_CONFIG = {
  RECOMPOSICION:  { color: '#BF5AF2', emoji: '🔥', label: 'Recomposición activa' },
  CUTTING_LIMPIO: { color: '#30D158', emoji: '✅', label: 'Cutting limpio'        },
  CATABOLISMO:    { color: '#FF453A', emoji: '⚠️', label: 'Catabolismo detectado'  },
  ESTANCAMIENTO:  { color: '#FFD60A', emoji: '⏸', label: 'Estancamiento'          },
  ZONA_GRIS:      { color: '#8E8E93', emoji: '〰️', label: 'Señales mixtas'         },
}

function ScoreRing({ score, desc }) {
  const r   = 54
  const circ = 2 * Math.PI * r
  const pct  = score / 100
  const color = score >= 65 ? '#30D158' : score >= 45 ? '#0A84FF' : score >= 30 ? '#FFD60A' : '#FF453A'

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-36 h-36">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 128 128">
          <circle cx="64" cy="64" r={r} fill="none" stroke="#27272A" strokeWidth="10" />
          <circle
            cx="64" cy="64" r={r} fill="none"
            stroke={color} strokeWidth="10"
            strokeDasharray={`${circ * pct} ${circ * (1 - pct)}`}
            strokeLinecap="round"
            style={{ filter: `drop-shadow(0 0 8px ${color})`, transition: 'stroke-dasharray 1s ease' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-black text-white">{score}</span>
          <span className="text-xs text-zinc-500">/ 100</span>
        </div>
      </div>
      <p className="text-sm font-semibold mt-2" style={{ color }}>{desc}</p>
    </div>
  )
}

function StatBar({ label, value, unit, color, min, max, optimal }) {
  const pct = Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100))
  const optPct = optimal ? Math.min(100, Math.max(0, ((optimal - min) / (max - min)) * 100)) : null
  return (
    <div className="mb-4">
      <div className="flex justify-between items-baseline mb-1.5">
        <span className="text-zinc-400 text-sm">{label}</span>
        <span className="text-white font-bold text-sm">{value}{unit}</span>
      </div>
      <div className="h-2 bg-zinc-800 rounded-full overflow-visible relative">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, background: color, boxShadow: `0 0 8px ${color}60` }}
        />
        {optPct !== null && (
          <div
            className="absolute top-1/2 -translate-y-1/2 w-0.5 h-4 rounded-full bg-white/40"
            style={{ left: `${optPct}%` }}
          />
        )}
      </div>
    </div>
  )
}

export default function Cuerpo() {
  const { data, loading } = useCuerpo()
  const [historial, setHistorial] = useState([])
  const [loadingHist, setLoadingHist] = useState(true)
  const [metric, setMetric] = useState('Peso_kg')

  useEffect(() => {
    api.cuerpoHistorial()
      .then(d => setHistorial(d.historial || []))
      .catch(() => setHistorial([]))
      .finally(() => setLoadingHist(false))
  }, [])

  if (loading) return <Spinner />

  if (!data?.tiene_datos) {
    return (
      <div className="bg-black min-h-dvh flex flex-col items-center justify-center px-6 text-center">
        <div className="text-5xl mb-4">⚖️</div>
        <h2 className="text-white font-bold text-lg mb-2">Sin pesajes aún</h2>
        <p className="text-zinc-500 text-sm leading-relaxed">
          Pésate mañana en ayunas entre 6-9am.<br />
          El sistema lo detecta automáticamente.
        </p>
      </div>
    )
  }

  const {
    score, score_desc, peso_kg, grasa_pct, musculo_pct,
    agua_pct, visceral, bmr, bmi, ffm_kg,
    estado_mimo, kg_a_perder, semanas_eta,
    peso_meta_kg, fecha, anterior,
  } = data

  const mimo = MIMO_CONFIG[estado_mimo] || MIMO_CONFIG.ZONA_GRIS

  // Chart data
  const METRICS = {
    Peso_kg:           { label: 'Peso', unit: 'kg', color: '#0A84FF' },
    Grasa_Porcentaje:  { label: 'Grasa', unit: '%', color: '#FF375F' },
    Musculo_Pct:       { label: 'Músculo', unit: '%', color: '#30D158' },
  }
  const chartData = historial.map(r => ({
    fecha: r.Fecha?.slice(5),
    valor: r[metric],
  })).filter(d => d.valor)

  const metaGrasa = 22.0
  const ant = anterior

  function delta(actual, prev, invertir = false) {
    if (!prev) return null
    const d = actual - prev
    if (Math.abs(d) < 0.05) return { val: d, ok: null }
    const ok = invertir ? d < 0 : d > 0
    return { val: d, ok }
  }

  return (
    <div className="bg-black min-h-dvh px-4 pt-10 pb-6 fade-up">

      {/* Header */}
      <p className="text-zinc-500 text-sm uppercase tracking-widest mb-1">Composición</p>
      <div className="flex items-baseline justify-between mb-6">
        <h1 className="text-3xl font-bold text-white">Cuerpo</h1>
        <p className="text-zinc-600 text-xs">{fecha}</p>
      </div>

      {/* Score ring + MIMO */}
      <div className="card mb-4 p-5">
        <div className="flex items-center justify-between">
          <ScoreRing score={score} desc={score_desc} />
          <div className="flex-1 ml-5">
            <div className="mb-3 px-3 py-2 rounded-xl" style={{ background: `${mimo.color}18` }}>
              <p className="text-xs font-semibold" style={{ color: mimo.color }}>
                {mimo.emoji} {mimo.label}
              </p>
            </div>
            <div className="space-y-1.5">
              <div className="flex justify-between">
                <span className="text-zinc-500 text-xs">Peso</span>
                <div className="flex items-center gap-1">
                  <span className="text-white text-sm font-bold">{peso_kg} kg</span>
                  {delta(peso_kg, ant?.peso_kg, true) && (
                    <span className={`text-xs ${delta(peso_kg, ant?.peso_kg, true).ok ? 'text-green-400' : 'text-red-400'}`}>
                      {delta(peso_kg, ant?.peso_kg, true).val > 0 ? '+' : ''}{delta(peso_kg, ant?.peso_kg, true).val?.toFixed(1)}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500 text-xs">BMR</span>
                <span className="text-white text-sm font-semibold">{bmr} kcal</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500 text-xs">FFM</span>
                <span className="text-white text-sm font-semibold">{ffm_kg?.toFixed(1)} kg</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Métricas */}
      <div className="card p-4 mb-4">
        <StatBar label="Grasa corporal"   value={grasa_pct}  unit="%" color="#FF375F" min={10} max={40} optimal={metaGrasa} />
        <StatBar label="Músculo esquelético" value={musculo_pct} unit="%" color="#30D158" min={30} max={55} optimal={47} />
        <StatBar label="Agua corporal"    value={agua_pct}   unit="%" color="#32ADE6" min={40} max={70} optimal={58} />
        <StatBar label="Grasa visceral"   value={visceral}   unit=""  color="#BF5AF2" min={1}  max={20} optimal={7}  />
        <p className="text-zinc-700 text-xs mt-2">La línea blanca marca el objetivo óptimo</p>
      </div>

      {/* Proyección a meta */}
      {kg_a_perder > 0 && (
        <div className="card p-4 mb-4 flex items-center gap-4"
          style={{ background: '#30D15815', border: '1px solid #30D15830' }}>
          <Target size={28} className="text-green-400 shrink-0" />
          <div>
            <p className="text-white font-bold">Meta: {metaGrasa}% grasa</p>
            <p className="text-zinc-400 text-sm">
              Faltan <span className="text-green-400 font-bold">{kg_a_perder} kg</span> · ~{semanas_eta} semanas
            </p>
            <p className="text-zinc-600 text-xs mt-0.5">
              Objetivo: {peso_meta_kg} kg · ritmo 0.5 kg/semana
            </p>
          </div>
        </div>
      )}

      {/* Gráfica de tendencia */}
      <div className="card p-4 mb-4">
        <p className="text-zinc-500 text-xs uppercase tracking-wider mb-3">Tendencia 90 días</p>

        {/* Metric selector */}
        <div className="flex gap-2 mb-4">
          {Object.entries(METRICS).map(([key, { label, color }]) => (
            <button
              key={key}
              onClick={() => setMetric(key)}
              className={`px-3 py-1 rounded-full text-xs font-semibold transition-all ${
                metric === key ? 'text-black' : 'text-zinc-500 bg-zinc-800'
              }`}
              style={metric === key ? { background: color } : {}}
            >
              {label}
            </button>
          ))}
        </div>

        {loadingHist ? (
          <div className="h-32 shimmer rounded-xl" />
        ) : chartData.length > 1 ? (
          <ResponsiveContainer width="100%" height={140}>
            <LineChart data={chartData} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272A" vertical={false} />
              <XAxis dataKey="fecha" tick={{ fill: '#52525B', fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#52525B', fontSize: 10 }} axisLine={false} tickLine={false}
                     domain={['auto', 'auto']} />
              <Tooltip
                contentStyle={{ background: '#18181B', border: 'none', borderRadius: 10, fontSize: 12, color: '#fff' }}
                formatter={v => [`${v} ${METRICS[metric].unit}`, METRICS[metric].label]}
              />
              <Line
                type="monotone" dataKey="valor"
                stroke={METRICS[metric].color} strokeWidth={2.5}
                dot={false} activeDot={{ r: 4, fill: METRICS[metric].color }}
              />
              {metric === 'Grasa_Porcentaje' && (
                <ReferenceLine y={metaGrasa} stroke="#30D158" strokeDasharray="4 4"
                  label={{ value: 'Meta', fill: '#30D158', fontSize: 10 }} />
              )}
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-zinc-600 text-sm text-center py-8">Necesitas más pesajes para ver la tendencia</p>
        )}
      </div>

      {/* BMI */}
      <div className="grid grid-cols-2 gap-2">
        <div className="card-sm p-3 text-center">
          <p className="text-zinc-600 text-xs">BMI</p>
          <p className="text-white text-xl font-bold mt-0.5">{bmi?.toFixed(1)}</p>
        </div>
        <div className="card-sm p-3 text-center">
          <p className="text-zinc-600 text-xs">FFM</p>
          <p className="text-white text-xl font-bold mt-0.5">{ffm_kg?.toFixed(1)} kg</p>
        </div>
      </div>
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
