import { useQuery } from '@tanstack/react-query'
import { Building2, MapPin, Target, Users, ShieldCheck, ArrowRight, Activity, Calendar } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import api from '../api/client'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { useAuth } from '../hooks/useAuth'
import type { Location, Mission, Professional, Organization } from '../types'

export function ClientDashboardPage() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const { data: myOrg } = useQuery({
    queryKey: ['my-organization'],
    queryFn: () => api.get<Organization>('/organizations/my').then(r => r.data).catch(() => null),
  })

  const { data: locations } = useQuery({
    queryKey: ['client-locations'],
    queryFn: () => api.get<Location[]>('/locations').then(r => r.data),
  })

  const { data: missions } = useQuery({
    queryKey: ['client-missions'],
    queryFn: () => api.get<Mission[]>('/missions').then(r => r.data),
  })

  const { data: professionals } = useQuery({
    queryKey: ['client-professionals'],
    queryFn: () => api.get<Professional[]>('/professionals').then(r => r.data).catch(() => []),
  })

  const confirmedLocations = locations?.filter(l => l.status === 'CONFIRMADO').length || 0
  const totalCapacity = locations?.reduce((acc, l) => acc + l.total_capacity, 0) || 0
  const activeMissions = missions?.filter(m => m.status === 'IN_PROGRESS' || m.status === 'OPEN').length || 0

  return (
    <div className="space-y-8">
      {/* Header com Identificação da Organizadora */}
      <div className="bg-gradient-to-r from-blue-950/60 via-gray-900 to-gray-950 border border-blue-900/40 rounded-3xl p-8 relative overflow-hidden">
        <div className="absolute right-0 top-0 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="flex items-center gap-5">
            <div className="w-16 h-16 bg-gradient-to-br from-blue-600 to-indigo-800 rounded-2xl flex items-center justify-center text-white shadow-xl shadow-blue-950/50 border border-white/10">
              <Building2 className="w-8 h-8 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-xs font-mono font-bold bg-blue-600/20 text-blue-400 border border-blue-600/30 px-2.5 py-0.5 rounded-full">
                  {myOrg?.public_id || 'ORG-CLIENTE'}
                </span>
                <span className="text-xs font-bold uppercase tracking-wider bg-green-500/20 text-green-400 border border-green-500/30 px-2.5 py-0.5 rounded-full flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
                  Conta Institucional Ativa
                </span>
              </div>
              <h1 className="text-2xl font-black text-white">{myOrg?.name || 'Portal da Organizadora Cliente'}</h1>
              <p className="text-gray-400 text-sm mt-0.5">
                Painel exclusivo de infraestrutura de aplicação e gestão de operações em campo
              </p>
            </div>
          </div>

          <Button onClick={() => navigate('/cliente/locations')}>
            <MapPin className="w-4 h-4 mr-2" /> Declarar Novo Local
          </Button>
        </div>

        {/* Métricas do Cliente */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8 pt-6 border-t border-gray-800/80">
          <div>
            <p className="text-xs text-gray-500">Locais Mapeados</p>
            <p className="text-2xl font-bold text-white mt-0.5">{locations?.length || 0}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Locais Confirmados</p>
            <p className="text-2xl font-bold text-blue-400 mt-0.5">{confirmedLocations}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Capacidade de Carteiras</p>
            <p className="text-2xl font-bold text-emerald-400 mt-0.5">{totalCapacity.toLocaleString('pt-BR')}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Operações & Missões Ativas</p>
            <p className="text-2xl font-bold text-amber-400 mt-0.5">{activeMissions}</p>
          </div>
        </div>
      </div>

      {/* Seções Rápidas */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="hover:border-blue-500/40 transition-colors flex flex-col justify-between">
          <div>
            <div className="w-10 h-10 rounded-xl bg-blue-500/10 text-blue-400 flex items-center justify-center mb-4">
              <MapPin className="w-5 h-5" />
            </div>
            <h3 className="text-lg font-bold text-white mb-1">Locais de Aplicação</h3>
            <p className="text-gray-400 text-sm">
              Consulte a malha de escolas, colégios e faculdades mapeados para seus concursos e processos seletivos.
            </p>
          </div>
          <Button variant="secondary" className="mt-4 justify-between" onClick={() => navigate('/cliente/locations')}>
            <span>Acessar Locais</span>
            <ArrowRight className="w-4 h-4" />
          </Button>
        </Card>

        <Card className="hover:border-blue-500/40 transition-colors flex flex-col justify-between">
          <div>
            <div className="w-10 h-10 rounded-xl bg-orange-500/10 text-orange-400 flex items-center justify-center mb-4">
              <Target className="w-5 h-5" />
            </div>
            <h3 className="text-lg font-bold text-white mb-1">Missões de Campo</h3>
            <p className="text-gray-400 text-sm">
              Acompanhe em tempo real o checklist de vistoria e reconfirmação presencial dos locais de prova.
            </p>
          </div>
          <Button variant="secondary" className="mt-4 justify-between" onClick={() => navigate('/cliente/missions')}>
            <span>Ver Operações</span>
            <ArrowRight className="w-4 h-4" />
          </Button>
        </Card>

        <Card className="hover:border-blue-500/40 transition-colors flex flex-col justify-between">
          <div>
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center mb-4">
              <Users className="w-5 h-5" />
            </div>
            <h3 className="text-lg font-bold text-white mb-1">Rede Territorial Habilitada</h3>
            <p className="text-gray-400 text-sm">
              Consulte o contingente de colaboradores com capacitação comprovada na OPERAN Academy prontos para atuação.
            </p>
          </div>
          <Button variant="secondary" className="mt-4 justify-between" onClick={() => navigate('/cliente/network')}>
            <span>Consultar Rede</span>
            <ArrowRight className="w-4 h-4" />
          </Button>
        </Card>
      </div>

      {/* Garantia de Isolamento de Dados */}
      <Card className="bg-gray-900/60 border border-gray-800">
        <div className="flex items-center gap-3">
          <ShieldCheck className="w-5 h-5 text-blue-400 shrink-0" />
          <div className="text-xs text-gray-400">
            <span className="font-bold text-white block">Isolamento Multi-Tenant Garantido</span>
            Suas operações, locais declarados e missões são estritamente isolados e protegidos por criptografia em nível de registro. Nenhuma outra organizadora tem acesso às suas instalações ou rotas operacionais.
          </div>
        </div>
      </Card>
    </div>
  )
}
