import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Building2,
  Users,
  GraduationCap,
  MapPin,
  Target,
  Settings,
  Shield,
  LogOut,
  MailPlus,
  UserRound,
} from 'lucide-react'
import { useAuth } from '../hooks/useAuth'

const nav = [
  { to: '/admin', icon: LayoutDashboard, label: 'Dashboard', end: true },
  { to: '/admin/organizations', icon: Building2, label: 'Organizadoras' },
  { to: '/admin/academy', icon: GraduationCap, label: 'Academy' },
  { to: '/admin/locations', icon: MapPin, label: 'Locais de Aplicação' },
  { to: '/admin/missions', icon: Target, label: 'Missions' },
  { to: '/admin/network', icon: Users, label: 'Rede de Colaboradores' },
  { to: '/admin/invitations', icon: MailPlus, label: 'Convites' },
  { to: '/admin/participants', icon: UserRound, label: 'Participantes' },
  { to: '/admin/security', icon: Shield, label: 'Segurança' },
  { to: '/admin/settings', icon: Settings, label: 'Configurações' },
]

export function Sidebar() {
  const { logout } = useAuth()

  return (
    <aside className="w-64 bg-gray-950 border-r border-gray-800 flex flex-col h-screen fixed left-0 top-0">
      <div className="p-6 border-b border-gray-800">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-violet-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">O</span>
          </div>
          <div>
            <p className="text-white font-bold text-sm">OPERAN</p>
            <p className="text-gray-500 text-xs">Admin Platform</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
        {nav.map(({ to, icon: Icon, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-violet-600/20 text-violet-400 border border-violet-600/30'
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
        <button
          onClick={logout}
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-gray-400 hover:bg-gray-800 hover:text-red-400 transition-colors w-full"
        >
          <LogOut className="w-4 h-4" />
          Sair
        </button>
      </div>
    </aside>
  )
}
