import { Outlet, NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  MapPin,
  Target,
  Users,
  Building2,
  LogOut,
  ShieldCheck,
  MailPlus,
  UserRound,
} from 'lucide-react'
import { useAuth } from '../hooks/useAuth'

const clientNav = [
  { to: '/cliente', icon: LayoutDashboard, label: 'Visão Geral', end: true },
  { to: '/cliente/locations', icon: MapPin, label: 'Locais de Aplicação' },
  { to: '/cliente/missions', icon: Target, label: 'Missões & Operações' },
  { to: '/cliente/network', icon: Users, label: 'Rede de Colaboradores' },
  { to: '/cliente/invitations', icon: MailPlus, label: 'Convites' },
  { to: '/cliente/participants', icon: UserRound, label: 'Participantes' },
]

export function ClientLayout() {
  const { user, logout } = useAuth()
  const primaryOrg = user?.memberships?.[0]?.organization_name || 'Banca / Organizadora'

  return (
    <div className="min-h-screen bg-gray-950 flex">
      {/* Sidebar do Cliente */}
      <aside className="w-64 bg-gray-950 border-r border-gray-800 flex flex-col h-screen fixed left-0 top-0 z-30">
        <div className="p-6 border-b border-gray-800">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-blue-600/20 font-bold">
              <Building2 className="w-5 h-5 text-white" />
            </div>
            <div className="overflow-hidden">
              <p className="text-white font-bold text-sm truncate">{primaryOrg}</p>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="w-1.5 h-1.5 bg-blue-400 rounded-full" />
                <p className="text-blue-400 text-xs font-semibold uppercase tracking-wider">Área do Cliente</p>
              </div>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {clientNav.map(({ to, icon: Icon, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600/20 text-blue-400 border border-blue-600/30'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                }`
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-gray-800">
          <div className="px-3 py-2.5 mb-2 rounded-xl bg-gray-900 border border-gray-800">
            <p className="text-xs text-gray-500 font-medium">Usuário Autenticado</p>
            <p className="text-xs font-bold text-white truncate mt-0.5">{user?.email}</p>
            <span className="inline-block text-[10px] uppercase font-mono font-bold bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded mt-1.5">
              Gestor Cliente
            </span>
          </div>

          <button
            onClick={logout}
            className="flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium text-gray-400 hover:bg-gray-800 hover:text-red-400 transition-colors w-full"
          >
            <LogOut className="w-4 h-4" />
            Sair
          </button>
        </div>
      </aside>

      {/* Conteúdo Principal */}
      <main className="flex-1 ml-64 p-8 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
