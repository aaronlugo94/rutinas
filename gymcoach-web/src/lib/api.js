const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function getToken() { return localStorage.getItem('gc_token') }

async function request(method, path, body) {
  const headers = { 'Content-Type': 'application/json' }
  const token   = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (res.status === 401) {
    localStorage.removeItem('gc_token')
    window.location.href = '/login'
    return
  }
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'Error del servidor')
  return data
}

export const api = {
  // Auth
  login:              (user_id, pin)  => request('POST', '/auth/login', { user_id: Number(user_id), pin }),
  loginTelegram:      (tgUser)        => request('POST', '/auth/telegram', tgUser),
  authToken:          (token)         => request('GET',  `/auth/token?token=${token}`),

  // Gym
  rutina:             ()              => request('GET',  '/rutina/hoy'),
  plan:               ()              => request('GET',  '/plan'),
  guardarPeso:        (body)          => request('POST', '/pesos', body),
  completarSesion:    (body)          => request('POST', '/sesion/completar', body),
  alternativas:       (eid)           => request('GET',  `/ejercicio/${eid}/alternativas`),
  swap:               (orig, nuevo)   => request('POST', '/ejercicio/swap', {
                                          ejercicio_id_original: orig,
                                          ejercicio_id_nuevo: nuevo,
                                        }),

  // Fuerza (progreso)
  progreso:           ()              => request('GET',  '/progreso'),
  progresoEj:         (eid)           => request('GET',  `/progreso/${eid}`),

  // Stats
  stats:              ()              => request('GET',  '/stats'),
  resumen:            ()              => request('GET',  '/resumen'),
  analisisIA:         ()              => request('GET',  '/analisis'),
  analisisHistorial:  ()              => request('GET',  '/analisis/historial'),

  // Cuerpo
  cuerpo:             ()              => request('GET',  '/cuerpo'),
  cuerpoHistorial:    ()              => request('GET',  '/cuerpo/historial'),

  // Nutrición
  nutricionPlan:      ()              => request('GET',  '/nutricion/plan'),
  nutricionMacros:    ()              => request('GET',  '/nutricion/macros'),
}

export function setToken(t)  { localStorage.setItem('gc_token', t) }
export function clearToken() { localStorage.removeItem('gc_token') }
export function isLoggedIn() { return !!getToken() }
