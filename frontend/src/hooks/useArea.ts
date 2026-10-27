import { useLocation } from 'react-router-dom'

export type Area = 'admin' | 'cliente' | 'participante'

export function useArea(): Area {
  const { pathname } = useLocation()
  if (pathname.startsWith('/admin')) return 'admin'
  if (pathname.startsWith('/cliente')) return 'cliente'
  return 'participante'
}
