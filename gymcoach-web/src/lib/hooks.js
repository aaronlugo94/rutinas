import { useState, useEffect, useCallback } from 'react'
import { api } from './api'

export function useFetch(fn, deps = []) {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try   { setData(await fn()) }
    catch (e) { setError(e.message) }
    finally   { setLoading(false) }
  }, deps)

  useEffect(() => { load() }, [load])
  return { data, loading, error, refetch: load }
}

export const useRutina    = () => useFetch(api.rutina)
export const usePlan      = () => useFetch(api.plan)
export const useProgreso  = () => useFetch(api.progreso)
export const useStats     = () => useFetch(api.stats)
export const useResumen   = () => useFetch(api.resumen)
export const useCuerpo    = () => useFetch(api.cuerpo)
export const useNutricion = () => useFetch(api.nutricionPlan)
export const useMacros    = () => useFetch(api.nutricionMacros)

export function useProgresoEj(eid) {
  return useFetch(() => api.progresoEj(eid), [eid])
}
