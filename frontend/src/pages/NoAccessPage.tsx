import { ShieldAlert, LogOut } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { useAuth } from '../hooks/useAuth'

export function NoAccessPage() {
  const { user, logout } = useAuth()

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-gray-900 border border-gray-800 rounded-2xl p-8 text-center">
        <div className="w-14 h-14 bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 rounded-2xl flex items-center justify-center mx-auto mb-5">
          <ShieldAlert className="w-7 h-7" />
        </div>
        <h1 className="text-xl font-bold text-white">Conta sem perfil de acesso</h1>
        <p className="text-gray-400 text-sm mt-2">
          O usuário <strong className="text-gray-200">{user?.email}</strong> está autenticado, mas não possui um papel
          ativo (Administração, Cliente ou Participante). Solicite a um administrador a atribuição do perfil correto.
        </p>
        <Button className="w-full mt-6" variant="secondary" onClick={logout}>
          <LogOut className="w-4 h-4 mr-2" />
          Sair e entrar com outra conta
        </Button>
      </div>
    </div>
  )
}
