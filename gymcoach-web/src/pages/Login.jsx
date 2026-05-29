import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, setToken } from '../lib/api'

export default function Login() {
  const nav           = useNavigate()
  const [params]      = useSearchParams()
  const [err,  setErr]  = useState('')
  const [busy, setBusy] = useState(false)
  const [uid,  setUid]  = useState('')
  const [pin,  setPin]  = useState('')

  // Auto-login si hay ?token= en la URL (magic link desde el bot)
  useEffect(() => {
    const token = params.get('token')
    if (!token) return
    setBusy(true)
    api.authToken(token)
      .then(res => {
        setToken(res.token)
        nav('/hoy', { replace: true })
      })
      .catch(e => {
        setErr(e.message)
        setBusy(false)
      })
  }, [])

  async function loginPin(e) {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      const res = await api.login(uid, pin)
      setToken(res.token)
      nav('/hoy', { replace: true })
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  // Si hay token en URL — mostrar pantalla de carga
  if (params.get('token')) {
    return (
      <div className="min-h-dvh flex flex-col items-center justify-center bg-slate-950 px-6">
        <div className="text-5xl mb-4">💪</div>
        {busy
          ? <p className="text-slate-300">Entrando...</p>
          : <div className="text-center">
              <p className="text-red-400 mb-4">{err}</p>
              <p className="text-slate-400 text-sm">
                Escribe <span className="font-mono text-white">/login</span> al bot para un nuevo link.
              </p>
            </div>
        }
      </div>
    )
  }

  return (
    <div className="min-h-dvh flex flex-col items-center justify-center px-6 bg-slate-950">
      <div className="w-full max-w-sm">

        <div className="text-center mb-8">
          <div className="text-5xl mb-3">💪</div>
          <h1 className="text-2xl font-semibold text-white">GymCoach</h1>
          <p className="text-slate-400 text-sm mt-1">Tu coach de gym personal</p>
        </div>

        {/* Instrucción principal */}
        <div className="bg-slate-800 rounded-2xl p-5 mb-6 text-center">
          <p className="text-white font-medium mb-1">¿Primera vez?</p>
          <p className="text-slate-400 text-sm mb-3">
            Escribe al bot de Telegram y toca el botón que aparece
          </p>
          <div className="bg-slate-900 rounded-xl px-4 py-3 font-mono text-blue-400 text-lg">
            /login
          </div>
          <p className="text-slate-500 text-xs mt-2">en el bot @CoachHealth_bot</p>
        </div>

        {/* Separador */}
        <div className="flex items-center gap-3 mb-5">
          <div className="flex-1 h-px bg-slate-800" />
          <span className="text-slate-600 text-xs">o entra con PIN</span>
          <div className="flex-1 h-px bg-slate-800" />
        </div>

        {/* Formulario PIN */}
        <form onSubmit={loginPin} className="space-y-3">
          <input
            type="number"
            value={uid}
            onChange={e => setUid(e.target.value)}
            placeholder="Tu ID de Telegram"
            required
            inputMode="numeric"
            className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-white text-base focus:outline-none focus:border-blue-500"
          />
          <input
            type="password"
            value={pin}
            onChange={e => setPin(e.target.value)}
            placeholder="PIN de 4 dígitos"
            required
            maxLength={4}
            inputMode="numeric"
            className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-white text-base focus:outline-none focus:border-blue-500 tracking-widest text-center text-xl"
          />
          {err && <p className="text-red-400 text-sm text-center">{err}</p>}
          <button
            type="submit"
            disabled={busy}
            className="w-full bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white font-medium py-3 rounded-xl transition-colors"
          >
            {busy ? 'Entrando...' : 'Entrar con PIN'}
          </button>
        </form>

      </div>
    </div>
  )
}
