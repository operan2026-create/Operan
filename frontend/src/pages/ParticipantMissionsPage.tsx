import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Target, MapPin, Calendar, DollarSign, CheckCircle2, Clock, ShieldCheck, AlertCircle } from 'lucide-react'
import api from '../api/client'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { useAuth } from '../hooks/useAuth'
import type { Mission } from '../types'

export function ParticipantMissionsPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<'assigned' | 'open'>('assigned')

  const { data: myMissions, isLoading: loadingMy } = useQuery({
    queryKey: ['participant-my-missions'],
    queryFn: () => api.get<Mission[]>('/missions?only_my=true').then(r => r.data),
  })

  const { data: openMissions, isLoading: loadingOpen } = useQuery({
    queryKey: ['participant-open-missions'],
    queryFn: () => api.get<Mission[]>('/missions?status=OPEN').then(r => r.data),
  })

  const acceptMutation = useMutation({
    mutationFn: (missionId: string) => api.patch(`/missions/${missionId}/status`, { status: 'IN_PROGRESS' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['participant-my-missions'] })
      queryClient.invalidateQueries({ queryKey: ['participant-open-missions'] })
    },
  })

  const displayed = tab === 'assigned' ? myMissions : openMissions
  const isLoading = tab === 'assigned' ? loadingMy : loadingOpen

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black text-white flex items-center gap-3">
          <div className="w-9 h-9 bg-violet-600 rounded-xl flex items-center justify-center text-white">
            <Target className="w-5 h-5" />
          </div>
          Missões Territoriais & Convocatórias
        </h1>
        <p className="text-gray-400 text-sm mt-0.5">
          Atividades de vistoria presencial, captação de prédios e reconfirmação de infraestrutura
        </p>
      </div>

      {/* Seletor de Abas */}
      <div className="flex items-center gap-2 border-b border-gray-800 pb-2">
        <button
          onClick={() => setTab('assigned')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-sm transition-all ${
            tab === 'assigned'
              ? 'bg-violet-600 text-white shadow-lg shadow-violet-600/20'
              : 'text-gray-400 hover:text-white hover:bg-gray-900'
          }`}
        >
          <Clock className="w-4 h-4" />
          Minhas Missões Atribuídas ({myMissions?.length || 0})
        </button>

        <button
          onClick={() => setTab('open')}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-sm transition-all ${
            tab === 'open'
              ? 'bg-violet-600 text-white shadow-lg shadow-violet-600/20'
              : 'text-gray-400 hover:text-white hover:bg-gray-900'
          }`}
        >
          <Target className="w-4 h-4" />
          Oportunidades Disponíveis ({openMissions?.length || 0})
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin w-8 h-8 border-2 border-violet-600 border-t-transparent rounded-full" />
        </div>
      ) : !displayed || displayed.length === 0 ? (
        <Card className="text-center py-16">
          <Target className="w-12 h-12 text-gray-700 mx-auto mb-3" />
          <p className="text-white font-semibold">
            {tab === 'assigned' ? 'Nenhuma missão atribuída no momento' : 'Nenhuma oportunidade em aberto no seu estado'}
          </p>
          <p className="text-gray-500 text-sm mt-1 max-w-sm mx-auto">
            {tab === 'assigned'
              ? 'Mantenha suas certificações atualizadas na Academy para receber convocações prioritárias.'
              : 'Novas missões são abertas conforme as bancas contratantes confirmam cronogramas de aplicação.'}
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {displayed.map(mission => (
            <Card key={mission.id} className="border border-gray-800 hover:border-violet-600/40 transition-colors flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-mono font-bold bg-violet-600/20 text-violet-400 border border-violet-600/30 px-2.5 py-0.5 rounded-full">
                    {mission.mission_type}
                  </span>
                  <span className="text-xs font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-0.5 rounded-full flex items-center gap-1">
                    <DollarSign className="w-3.5 h-3.5" />
                    R$ {mission.reward_amount.toFixed(2)}
                  </span>
                </div>

                <h3 className="text-lg font-bold text-white mb-2">{mission.title}</h3>

                <div className="space-y-1.5 text-xs text-gray-400 mb-4">
                  <p className="flex items-center gap-1.5">
                    <MapPin className="w-3.5 h-3.5 text-gray-500" />
                    {mission.city} / {mission.state} {mission.location_name ? `• ${mission.location_name}` : ''}
                  </p>
                  {mission.deadline && (
                    <p className="flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5 text-gray-500" />
                      Prazo: {new Date(mission.deadline).toLocaleDateString('pt-BR')}
                    </p>
                  )}
                </div>

                {mission.checklist && mission.checklist.length > 0 && (
                  <div className="pt-3 border-t border-gray-800 space-y-2">
                    <p className="text-xs font-bold text-gray-300">Checklist Operacional:</p>
                    <ul className="space-y-1">
                      {mission.checklist.map((item, i) => (
                        <li key={i} className="text-xs text-gray-400 flex items-center gap-2">
                          <CheckCircle2 className={`w-3.5 h-3.5 ${item.done ? 'text-green-400' : 'text-gray-600'}`} />
                          <span className={item.done ? 'line-through text-gray-500' : ''}>{item.item}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              <div className="pt-4 border-t border-gray-800 mt-4 flex items-center justify-between">
                <span className="text-xs text-gray-500">
                  Status: <strong className="text-white">{mission.status}</strong>
                </span>

                {mission.status === 'OPEN' && (
                  <Button
                    size="sm"
                    loading={acceptMutation.isPending}
                    onClick={() => acceptMutation.mutate(mission.id)}
                  >
                    Aceitar Missão
                  </Button>
                )}
                {mission.status === 'IN_PROGRESS' && (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => alert('Envio de evidências e relatório em homologação.')}
                  >
                    Enviar Evidências
                  </Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
