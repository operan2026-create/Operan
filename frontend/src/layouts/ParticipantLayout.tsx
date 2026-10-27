import { Outlet, NavLink } from 'react-router-dom'
import {
  ShieldCheck,
  GraduationCap,
  Target,
  UserRound,
  LogOut,
  Star,
  School,
} from 'lucide-react'
import { useAuth } from '../hooks/useAuth'

export function ParticipantLayout() {
  const { user, logout, isProfessional, isRepresentative } = useAuth()
  const participantNav = [
    { to: '/participante', icon: ShieldCheck, label: 'Passaporte Global', end: true },
    ...(isProfessional
      ? [
          { to: '/participante/academy', icon: GraduationCap, label: 'Academy & Cursos', end: false },
          { to: '/participante/missions', icon: Target, label: 'Missoes & Candidaturas', end: false },
        ]
      : []),
    ...(isRepresentative
      ? [{ to: '/participante/escolas', icon: School, label: 'Minhas Escolas', end: false }]
      : []),
    { to: '/participante/conta', icon: UserRound, label: 'Conta & Documentos', end: false },
  ]
  const profName = user?.professional?.full_name || user?.email?.split('@')[0] || 'Colaborador'
  const repScore = user?.professional?.reputation_score

  return (
    <div className="min-h-screen bg-gray-950 flex">
      {/* Sidebar do Participante */}
      <aside className="w-64 bg-gray-950 border-r border-gray-800 flex flex-col h-screen fixed left-0 top-0 z-30">
        <div className="p-6 border-b border-gray-800">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-violet-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-violet-600/20 font-bold">
              <ShieldCheck className="w-5 h-5 text-white" />
            </div>
            <div className="overflow-hidden">
              <p className="text-white font-bold text-sm truncate">{profName}</p>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
                <p className="text-green-400 text-xs font-semibold uppercase tracking-wider">Rede OPERAN</p>
              </div>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {participantNav.map(({ to, icon: Icon, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-colors ${
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
          {/* Card de Reputação Rápida */}
          <div className="px-3.5 py-3 mb-2 rounded-2xl bg-gray-900 border border-gray-800 flex items-center justify-between">
            <div>
              <p className="text-[10px] text-gray-500 font-medium uppercase tracking-wider">Confiabilidade</p>
              <p className="text-sm font-black text-violet-400">{repScore !== undefined ? repScore.toFixed(1) : '-'} <span className="text-[10px] text-gray-400 font-normal">/100</span></p>
            </div>
            <div className="w-7 h-7 bg-violet-500/10 rounded-lg flex items-center justify-center">
              <Star className="w-3.5 h-3.5 text-violet-400 fill-violet-400/40" />
            </div>
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
