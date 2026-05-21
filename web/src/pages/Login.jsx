import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, setToken } from '../lib/api'

export default function Login() {
  const [uid,  setUid]  = useState('')
  const [pin,  setPin]  = useState('')
  const [err,  setErr]  = useState('')
  const [busy, setBusy] = useState(false)
  const nav = useNavigate()

  async function submit(e) {
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

  return (
    <div className="min-h-dvh flex flex-col items-center justify-center px-6 bg-slate-950">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="text-4xl mb-3">💪</div>
          <h1 className="text-2xl font-semibold text-white">GymCoach</h1>
          <p className="text-slate-400 text-sm mt-1">Tu coach de gym personal</p>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">
              Tu ID de Telegram
            </label>
            <input
              type="number"
              value={uid}
              onChange={e => setUid(e.target.value)}
              placeholder="Ej: 1234567890"
              required
              inputMode="numeric"
              className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-white text-base focus:outline-none focus:border-blue-500"
            />
            <p className="text-xs text-slate-500 mt-1">
              Encuéntralo en el bot con /setpin
            </p>
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">PIN de 4 dígitos</label>
            <input
              type="password"
              value={pin}
              onChange={e => setPin(e.target.value)}
              placeholder="••••"
              required
              maxLength={4}
              inputMode="numeric"
              className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-white text-base focus:outline-none focus:border-blue-500 tracking-widest text-center text-xl"
            />
          </div>

          {err && (
            <p className="text-red-400 text-sm text-center">{err}</p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium py-3 rounded-xl text-base transition-colors"
          >
            {busy ? 'Entrando...' : 'Entrar'}
          </button>
        </form>

        <p className="text-center text-xs text-slate-500 mt-6">
          ¿Sin PIN? Abre el bot de Telegram y escribe{' '}
          <span className="font-mono text-slate-400">/setpin 1234</span>
        </p>
      </div>
    </div>
  )
}
