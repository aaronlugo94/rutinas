import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, setToken } from '../lib/api'

const BOT_NAME = import.meta.env.VITE_BOT_NAME || 'Gym_Coach_bot'

export default function Login() {
  const nav       = useNavigate()
  const widgetRef = useRef(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    // Telegram Login Widget — inyecta el botón oficial de Telegram
    // Cuando el usuario confirma, Telegram llama window.onTelegramAuth
    window.onTelegramAuth = async (user) => {
      setErr('')
      setBusy(true)
      try {
        // user contiene: id, first_name, last_name, username, photo_url, auth_date, hash
        const res = await api.loginTelegram(user)
        setToken(res.token)
        nav('/hoy', { replace: true })
      } catch (e) {
        setErr(e.message)
        setBusy(false)
      }
    }

    // Insertar script del widget de Telegram
    const script = document.createElement('script')
    script.src    = 'https://telegram.org/js/telegram-widget.js?22'
    script.setAttribute('data-telegram-login', BOT_NAME)
    script.setAttribute('data-size',           'large')
    script.setAttribute('data-onauth',         'onTelegramAuth(user)')
    script.setAttribute('data-request-access', 'write')
    script.async = true
    widgetRef.current?.appendChild(script)

    return () => {
      delete window.onTelegramAuth
    }
  }, [])

  return (
    <div className="min-h-dvh flex flex-col items-center justify-center px-6 bg-slate-950">
      <div className="w-full max-w-sm text-center">

        {/* Logo */}
        <div className="text-5xl mb-4">💪</div>
        <h1 className="text-2xl font-semibold text-white mb-1">GymCoach</h1>
        <p className="text-slate-400 text-sm mb-10">Tu coach de gym personal</p>

        {/* Telegram Login Widget */}
        <div className="flex justify-center mb-4">
          {busy
            ? <p className="text-slate-400 text-sm">Verificando...</p>
            : <div ref={widgetRef} />
          }
        </div>

        {err && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3 mb-4">
            <p className="text-red-400 text-sm">{err}</p>
            {err.includes('bot') && (
              <p className="text-slate-400 text-xs mt-1">
                Escribe <span className="font-mono text-slate-300">/start</span> al bot primero.
              </p>
            )}
          </div>
        )}

        <p className="text-xs text-slate-600 mt-8">
          Al entrar, Telegram comparte tu ID con GymCoach.
          No compartimos tus datos con nadie.
        </p>
      </div>
    </div>
  )
}
