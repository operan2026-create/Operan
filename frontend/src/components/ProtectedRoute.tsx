import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

interface ProtectedRouteProps {
  allowedRoles?: Array<'ADMIN' | 'CLIENT' | 'PARTICIPANT'>
}

export function ProtectedRoute({ allowedRoles }: ProtectedRouteProps) {
  const { user, loading, primaryRole } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin w-8 h-8 border-2 border-violet-600 border-t-transparent rounded-full" />
          <p className="text-gray-400 text-xs font-medium">Verificando autorização...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  if (allowedRoles && !allowedRoles.includes(primaryRole)) {
    // Redirect user to their own area based on role
    if (primaryRole === 'ADMIN') {
      return <Navigate to="/admin" replace />
    }
    if (primaryRole === 'CLIENT') {
      return <Navigate to="/cliente" replace />
    }
    return <Navigate to="/participante" replace />
  }

  return <Outlet />
}
