import { useState, useEffect, useCallback } from 'react'
import { api } from './api'

export function useFetch(fn, deps = []) {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const d = await fn()
      setData(d)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, deps)

  useEffect(() => { load() }, [load])
  return { data, loading, error, refetch: load }
}

export function useRutina()   { return useFetch(api.rutina) }
export function usePlan()     { return useFetch(api.plan) }
export function useProgreso() { return useFetch(api.progreso) }
export function useStats()    { return useFetch(api.stats) }
export function useResumen()  { return useFetch(api.resumen) }

export function useProgresoEj(eid) {
  return useFetch(() => api.progresoEj(eid), [eid])
}
